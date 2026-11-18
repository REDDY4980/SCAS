"""
PP-OCR text detection/classification/recognition pipeline on ONNX Runtime.

WHY THIS MODULE EXISTS
----------------------
SCAS runs on Render's free tier (512 MB RAM). Measured against this exact
codebase (see docs/OCR_MEMORY_REPORT.md):

* The PaddlePaddle runtime alone maps ~220 MB of `libpaddle.so` plus
  ~100 MB of anonymous memory on import, before any model is loaded.
* PaddlePaddle 2.6 enables oneDNN for CPU inference by default — PaddleOCR
  2.8.1's `enable_mkldnn=False` never actually calls `disable_mkldnn()` —
  and oneDNN caches kernels/buffers per distinct input shape. Text-line
  recognition produces a new input width for almost every batch, so one
  4-page soil report drove the process to ~2.8 GB RSS.

The model weights themselves are small (~16 MB). This module runs the SAME
bundled PP-OCR weights (en_PP-OCRv3_det, en_PP-OCRv4_rec,
ch_ppocr_mobile_v2.0_cls), converted 1:1 to ONNX with paddle2onnx, on ONNX
Runtime, which never imports PaddlePaddle.

FIDELITY
--------
Everything below is a faithful port of the code paths PaddleOCR 2.8.1
actually executes for SCAS's configuration (`PaddleOCR(lang="en",
use_angle_cls=True)` + `ocr(img, cls=True)`): DetResizeForTest(limit 960,
"max"), NormalizeImage, DBPostProcess(quad, fast score), filter_tag_det_res,
sorted_boxes, get_rotate_crop_image, TextClassifier, TextRecognizer
(SVTR_LCNet) and CTCLabelDecode — same constants, same arithmetic, same
ordering. Only the tensor-execution backend differs. On the two bundled
calibration PDFs (8 pages, 599 text lines) the output text is identical to
PaddleOCR 2.8.1 + PaddlePaddle 2.6.2 (verified in
tests/integration/test_ocr_engine_real.py).

Ported from PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR, release
2.8.1), Copyright (c) 2020 PaddlePaddle Authors, licensed under the Apache
License, Version 2.0. Modifications: PaddlePaddle-specific code paths and
unused algorithms removed; inference executed via onnxruntime.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pyclipper
from shapely.geometry import Polygon

logger = logging.getLogger("scas.ocr.ppocr_onnx")

DET_MODEL_FILE = "det.onnx"
REC_MODEL_FILE = "rec.onnx"
CLS_MODEL_FILE = "cls.onnx"
REC_DICT_FILE = "en_dict.txt"
REQUIRED_MODEL_FILES = (DET_MODEL_FILE, REC_MODEL_FILE, CLS_MODEL_FILE, REC_DICT_FILE)


@dataclass(frozen=True)
class PPOCRConfig:
    """PaddleOCR 2.8.1 defaults for lang='en', ocr_version='PP-OCRv4'."""

    det_limit_side_len: int = 960
    det_limit_type: str = "max"
    det_db_thresh: float = 0.3
    det_db_box_thresh: float = 0.6
    det_db_unclip_ratio: float = 1.5
    det_max_candidates: int = 1000
    rec_image_shape: tuple[int, int, int] = (3, 48, 320)
    rec_batch_num: int = 6
    cls_image_shape: tuple[int, int, int] = (3, 48, 192)
    cls_batch_num: int = 6
    cls_thresh: float = 0.9
    cls_label_list: tuple[str, str] = ("0", "180")
    drop_score: float = 0.5
    use_angle_cls: bool = True
    num_threads: int = 1
    # SCAS addition (not in PaddleOCR): whole-page 90/270-degree rotation
    # correction. Off by default here so PPOCRSystem stays a faithful
    # PaddleOCR port; the production engine turns it on (OCR_AUTO_ROTATE).
    auto_rotate: bool = False
    rotate_min_boxes: int = 5
    rotate_tall_fraction: float = 0.5


def create_session(model_path: Path, num_threads: int):
    """ONNX Runtime CPU session tuned for a small, memory-capped container.

    * The CPU memory arena is disabled: with an arena, ORT keeps the peak
      working set of the largest input it has ever seen reserved forever.
    * Memory-pattern planning is disabled: it caches a plan per input shape,
      and recognition input widths vary per batch.
    """
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = num_threads
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    return ort.InferenceSession(
        str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
    )


class _OnnxModel:
    def __init__(self, model_path: Path, num_threads: int):
        self.session = create_session(model_path, num_threads)
        self.input_name = self.session.get_inputs()[0].name

    def run(self, batch: np.ndarray) -> np.ndarray:
        return self.session.run(None, {self.input_name: batch})[0]


# --------------------------------------------------------------------------
# Detection (ppocr/data/imaug/operators.py, ppocr/postprocess/db_postprocess.py,
# tools/infer/predict_det.py)
# --------------------------------------------------------------------------

_DET_MEAN = np.array([0.485, 0.456, 0.406]).reshape((1, 1, 3)).astype("float32")
_DET_STD = np.array([0.229, 0.224, 0.225]).reshape((1, 1, 3)).astype("float32")
_DET_SCALE = np.float32(1.0 / 255.0)


def _det_resize(img: np.ndarray, limit_side_len: int, limit_type: str):
    """DetResizeForTest.resize_image_type0 (+ its small-image padding)."""
    src_h, src_w, _ = img.shape
    if sum([src_h, src_w]) < 64:
        h, w, c = img.shape
        padded = np.zeros((max(32, h), max(32, w), c), np.uint8)
        padded[:h, :w, :] = img
        img = padded

    h, w, _ = img.shape
    if limit_type == "max":
        if max(h, w) > limit_side_len:
            ratio = float(limit_side_len) / h if h > w else float(limit_side_len) / w
        else:
            ratio = 1.0
    elif limit_type == "min":
        if min(h, w) < limit_side_len:
            ratio = float(limit_side_len) / h if h < w else float(limit_side_len) / w
        else:
            ratio = 1.0
    elif limit_type == "resize_long":
        ratio = float(limit_side_len) / max(h, w)
    else:
        raise ValueError(f"Unsupported det limit type: {limit_type}")

    resize_h = int(h * ratio)
    resize_w = int(w * ratio)
    resize_h = max(int(round(resize_h / 32) * 32), 32)
    resize_w = max(int(round(resize_w / 32) * 32), 32)
    if resize_w <= 0 or resize_h <= 0:
        return None, None
    resized = cv2.resize(img, (int(resize_w), int(resize_h)))
    shape = np.array([src_h, src_w, resize_h / float(h), resize_w / float(w)])
    return resized, shape


class DBPostProcess:
    def __init__(self, thresh: float, box_thresh: float, max_candidates: int, unclip_ratio: float):
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.unclip_ratio = unclip_ratio
        self.min_size = 3

    def boxes_from_bitmap(self, pred, bitmap, dest_width, dest_height):
        height, width = bitmap.shape
        outs = cv2.findContours(
            (bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = outs[1] if len(outs) == 3 else outs[0]
        num_contours = min(len(contours), self.max_candidates)

        boxes = []
        scores = []
        for index in range(num_contours):
            contour = contours[index]
            points, sside = self.get_mini_boxes(contour)
            if sside < self.min_size:
                continue
            points = np.array(points)
            score = self.box_score_fast(pred, points.reshape(-1, 2))
            if self.box_thresh > score:
                continue

            box = self.unclip(points, self.unclip_ratio)
            if len(box) > 1:
                continue
            box = np.array(box).reshape(-1, 1, 2)
            box, sside = self.get_mini_boxes(box)
            if sside < self.min_size + 2:
                continue

            box = np.array(box)
            box[:, 0] = np.clip(np.round(box[:, 0] / width * dest_width), 0, dest_width)
            box[:, 1] = np.clip(np.round(box[:, 1] / height * dest_height), 0, dest_height)
            boxes.append(box.astype("int32"))
            scores.append(score)
        return np.array(boxes, dtype="int32"), scores

    @staticmethod
    def unclip(box, unclip_ratio):
        poly = Polygon(box)
        distance = poly.area * unclip_ratio / poly.length
        offset = pyclipper.PyclipperOffset()
        offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        return offset.Execute(distance)

    @staticmethod
    def get_mini_boxes(contour):
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

        if points[1][1] > points[0][1]:
            index_1, index_4 = 0, 1
        else:
            index_1, index_4 = 1, 0
        if points[3][1] > points[2][1]:
            index_2, index_3 = 2, 3
        else:
            index_2, index_3 = 3, 2

        box = [points[index_1], points[index_2], points[index_3], points[index_4]]
        return box, min(bounding_box[1])

    @staticmethod
    def box_score_fast(bitmap, _box):
        h, w = bitmap.shape[:2]
        box = _box.copy()
        xmin = np.clip(np.floor(box[:, 0].min()).astype("int32"), 0, w - 1)
        xmax = np.clip(np.ceil(box[:, 0].max()).astype("int32"), 0, w - 1)
        ymin = np.clip(np.floor(box[:, 1].min()).astype("int32"), 0, h - 1)
        ymax = np.clip(np.ceil(box[:, 1].max()).astype("int32"), 0, h - 1)

        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        box[:, 0] = box[:, 0] - xmin
        box[:, 1] = box[:, 1] - ymin
        cv2.fillPoly(mask, box.reshape(1, -1, 2).astype("int32"), 1)
        return cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0]

    def __call__(self, pred: np.ndarray, shape: np.ndarray):
        pred = pred[:, 0, :, :]
        segmentation = pred > self.thresh
        src_h, src_w, _ratio_h, _ratio_w = shape
        boxes, _scores = self.boxes_from_bitmap(pred[0], segmentation[0], src_w, src_h)
        return boxes


def _order_points_clockwise(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    tmp = np.delete(pts, (np.argmin(s), np.argmax(s)), axis=0)
    diff = np.diff(np.array(tmp), axis=1)
    rect[1] = tmp[np.argmin(diff)]
    rect[3] = tmp[np.argmax(diff)]
    return rect


def _clip_det_res(points, img_height, img_width):
    for pno in range(points.shape[0]):
        points[pno, 0] = int(min(max(points[pno, 0], 0), img_width - 1))
        points[pno, 1] = int(min(max(points[pno, 1], 0), img_height - 1))
    return points


def _filter_tag_det_res(dt_boxes, image_shape):
    img_height, img_width = image_shape[0:2]
    dt_boxes_new = []
    for box in dt_boxes:
        if type(box) is list:
            box = np.array(box)
        box = _order_points_clockwise(box)
        box = _clip_det_res(box, img_height, img_width)
        rect_width = int(np.linalg.norm(box[0] - box[1]))
        rect_height = int(np.linalg.norm(box[0] - box[3]))
        if rect_width <= 3 or rect_height <= 3:
            continue
        dt_boxes_new.append(box)
    return np.array(dt_boxes_new)


class TextDetector:
    def __init__(self, model_path: Path, config: PPOCRConfig):
        self.model = _OnnxModel(model_path, config.num_threads)
        self.config = config
        self.postprocess = DBPostProcess(
            thresh=config.det_db_thresh,
            box_thresh=config.det_db_box_thresh,
            max_candidates=config.det_max_candidates,
            unclip_ratio=config.det_db_unclip_ratio,
        )

    def __call__(self, img: np.ndarray) -> np.ndarray:
        image_shape = img.shape
        resized, shape = _det_resize(img, self.config.det_limit_side_len, self.config.det_limit_type)
        if resized is None:
            return np.zeros((0, 4, 2), dtype=np.float32)
        normalized = (resized.astype("float32") * _DET_SCALE - _DET_MEAN) / _DET_STD
        del resized
        batch = np.expand_dims(normalized.transpose((2, 0, 1)), axis=0).copy()
        del normalized
        pred = self.model.run(batch)
        del batch
        boxes = self.postprocess(pred, shape)
        return _filter_tag_det_res(boxes, image_shape)


# --------------------------------------------------------------------------
# Text system helpers (tools/infer/predict_system.py, tools/infer/utility.py)
# --------------------------------------------------------------------------


def sorted_boxes(dt_boxes):
    """Sort text boxes top-to-bottom, left-to-right (PaddleOCR's exact rule)."""
    num_boxes = dt_boxes.shape[0]
    _boxes = list(sorted(dt_boxes, key=lambda x: (x[0][1], x[0][0])))
    for i in range(num_boxes - 1):
        for j in range(i, -1, -1):
            if abs(_boxes[j + 1][0][1] - _boxes[j][0][1]) < 10 and (
                _boxes[j + 1][0][0] < _boxes[j][0][0]
            ):
                _boxes[j], _boxes[j + 1] = _boxes[j + 1], _boxes[j]
            else:
                break
    return _boxes


def get_rotate_crop_image(img, points):
    assert len(points) == 4, "shape of points must be 4*2"
    img_crop_width = int(
        max(np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3]))
    )
    img_crop_height = int(
        max(np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2]))
    )
    pts_std = np.float32(
        [[0, 0], [img_crop_width, 0], [img_crop_width, img_crop_height], [0, img_crop_height]]
    )
    matrix = cv2.getPerspectiveTransform(points, pts_std)
    dst_img = cv2.warpPerspective(
        img,
        matrix,
        (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE,
        flags=cv2.INTER_CUBIC,
    )
    dst_img_height, dst_img_width = dst_img.shape[0:2]
    if dst_img_height * 1.0 / dst_img_width >= 1.5:
        dst_img = np.rot90(dst_img)
    return dst_img


# --------------------------------------------------------------------------
# Angle classification (tools/infer/predict_cls.py, ppocr/postprocess/cls_postprocess.py)
# --------------------------------------------------------------------------


class TextClassifier:
    def __init__(self, model_path: Path, config: PPOCRConfig):
        self.model = _OnnxModel(model_path, config.num_threads)
        self.cls_image_shape = config.cls_image_shape
        self.cls_batch_num = config.cls_batch_num
        self.cls_thresh = config.cls_thresh
        self.label_list = config.cls_label_list

    def resize_norm_img(self, img):
        img_c, img_h, img_w = self.cls_image_shape
        h, w = img.shape[0], img.shape[1]
        ratio = w / float(h)
        if math.ceil(img_h * ratio) > img_w:
            resized_w = img_w
        else:
            resized_w = int(math.ceil(img_h * ratio))
        resized_image = cv2.resize(img, (resized_w, img_h)).astype("float32")
        resized_image = resized_image.transpose((2, 0, 1)) / 255
        resized_image -= 0.5
        resized_image /= 0.5
        padding_im = np.zeros((img_c, img_h, img_w), dtype=np.float32)
        padding_im[:, :, 0:resized_w] = resized_image
        return padding_im

    def classify(self, img_list) -> list[tuple[str, float]]:
        """(label, score) per image, in input order."""
        img_num = len(img_list)
        width_list = [img.shape[1] / float(img.shape[0]) for img in img_list]
        indices = np.argsort(np.array(width_list))
        cls_res: list[tuple[str, float]] = [("", 0.0)] * img_num
        for beg in range(0, img_num, self.cls_batch_num):
            end = min(img_num, beg + self.cls_batch_num)
            batch = np.concatenate(
                [self.resize_norm_img(img_list[indices[i]])[np.newaxis, :] for i in range(beg, end)]
            ).copy()
            prob_out = self.model.run(batch)
            pred_idxs = prob_out.argmax(axis=1)
            for rno, idx in enumerate(pred_idxs):
                cls_res[indices[beg + rno]] = (self.label_list[idx], float(prob_out[rno, idx]))
        return cls_res

    def __call__(self, img_list):
        img_list = list(img_list)  # rotated entries are replaced, never mutated in place
        for i, (label, score) in enumerate(self.classify(img_list)):
            if "180" in label and score > self.cls_thresh:
                img_list[i] = cv2.rotate(img_list[i], 1)
        return img_list


# --------------------------------------------------------------------------
# Recognition (tools/infer/predict_rec.py, ppocr/postprocess/rec_postprocess.py)
# --------------------------------------------------------------------------


class CTCLabelDecode:
    def __init__(self, character_dict_path: Path, use_space_char: bool = True):
        characters: list[str] = []
        with open(character_dict_path, "rb") as fin:
            for line in fin.readlines():
                characters.append(line.decode("utf-8").strip("\n").strip("\r\n"))
        if use_space_char:
            characters.append(" ")
        self.character = ["blank"] + characters

    def __call__(self, preds: np.ndarray):
        preds_idx = preds.argmax(axis=2)
        preds_prob = preds.max(axis=2)
        results = []
        for batch_idx in range(len(preds_idx)):
            selection = np.ones(len(preds_idx[batch_idx]), dtype=bool)
            selection[1:] = preds_idx[batch_idx][1:] != preds_idx[batch_idx][:-1]
            selection &= preds_idx[batch_idx] != 0  # CTC blank
            char_list = [self.character[text_id] for text_id in preds_idx[batch_idx][selection]]
            conf_list = preds_prob[batch_idx][selection]
            if len(conf_list) == 0:
                conf_list = [0]
            results.append(("".join(char_list), np.mean(conf_list).tolist()))
        return results


class TextRecognizer:
    def __init__(self, model_path: Path, dict_path: Path, config: PPOCRConfig):
        self.model = _OnnxModel(model_path, config.num_threads)
        self.rec_image_shape = config.rec_image_shape
        self.rec_batch_num = config.rec_batch_num
        self.decode = CTCLabelDecode(dict_path, use_space_char=True)

    def resize_norm_img(self, img, max_wh_ratio):
        img_c, img_h, img_w = self.rec_image_shape
        assert img_c == img.shape[2]
        img_w = int(img_h * max_wh_ratio)
        h, w = img.shape[:2]
        ratio = w / float(h)
        if math.ceil(img_h * ratio) > img_w:
            resized_w = img_w
        else:
            resized_w = int(math.ceil(img_h * ratio))
        resized_image = cv2.resize(img, (resized_w, img_h)).astype("float32")
        resized_image = resized_image.transpose((2, 0, 1)) / 255
        resized_image -= 0.5
        resized_image /= 0.5
        padding_im = np.zeros((img_c, img_h, img_w), dtype=np.float32)
        padding_im[:, :, 0:resized_w] = resized_image
        return padding_im

    def __call__(self, img_list):
        img_num = len(img_list)
        width_list = [img.shape[1] / float(img.shape[0]) for img in img_list]
        indices = np.argsort(np.array(width_list))
        rec_res: list = [["", 0.0]] * img_num
        _img_c, img_h, img_w = self.rec_image_shape
        for beg in range(0, img_num, self.rec_batch_num):
            end = min(img_num, beg + self.rec_batch_num)
            max_wh_ratio = img_w / img_h
            for ino in range(beg, end):
                h, w = img_list[indices[ino]].shape[0:2]
                max_wh_ratio = max(max_wh_ratio, w * 1.0 / h)
            batch = np.concatenate(
                [
                    self.resize_norm_img(img_list[indices[ino]], max_wh_ratio)[np.newaxis, :]
                    for ino in range(beg, end)
                ]
            ).copy()
            preds = self.model.run(batch)
            del batch
            for rno, result in enumerate(self.decode(preds)):
                rec_res[indices[beg + rno]] = result
        return rec_res


# --------------------------------------------------------------------------
# Full system (tools/infer/predict_system.py TextSystem + paddleocr.py ocr())
# --------------------------------------------------------------------------


class PPOCRSystem:
    """Equivalent of `PaddleOCR(lang="en", use_angle_cls=...).ocr(img, cls=True)[0]`."""

    def __init__(self, model_dir: Path, config: PPOCRConfig | None = None):
        self.config = config or PPOCRConfig()
        model_dir = Path(model_dir)
        self.detector = TextDetector(model_dir / DET_MODEL_FILE, self.config)
        self.recognizer = TextRecognizer(
            model_dir / REC_MODEL_FILE, model_dir / REC_DICT_FILE, self.config
        )
        self.classifier = (
            TextClassifier(model_dir / CLS_MODEL_FILE, self.config)
            if self.config.use_angle_cls
            else None
        )

    @staticmethod
    def _to_bgr(img: np.ndarray) -> np.ndarray:
        """paddleocr.check_img / alpha_to_color for in-memory arrays."""
        if img.ndim == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.ndim == 3 and img.shape[2] == 4:
            b, g, r, a = cv2.split(img)
            alpha = a / 255
            bg = (255, 255, 255)
            r = (bg[0] * (1 - alpha) + r * alpha).astype(np.uint8)
            g = (bg[1] * (1 - alpha) + g * alpha).astype(np.uint8)
            b = (bg[2] * (1 - alpha) + b * alpha).astype(np.uint8)
            return cv2.merge((b, g, r))
        return img

    def _is_rotated_page(self, dt_boxes) -> bool:
        """True when most text boxes are tall — i.e. the page itself is
        turned 90/270 degrees (PaddleOCR's own crop rule treats h/w >= 1.5
        as vertical text)."""
        if dt_boxes is None or len(dt_boxes) < self.config.rotate_min_boxes:
            return False
        widths = np.linalg.norm(dt_boxes[:, 0] - dt_boxes[:, 1], axis=1)
        heights = np.linalg.norm(dt_boxes[:, 0] - dt_boxes[:, 3], axis=1)
        return float(np.mean(heights >= 1.5 * widths)) >= self.config.rotate_tall_fraction

    def _correct_page_rotation(self, img: np.ndarray, dt_boxes):
        """Turns a 90/270-degree page upright. The direction is chosen by
        the angle classifier: after a clockwise turn, if most text lines
        read as upside-down, the page needed the counter-clockwise turn."""
        turned = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        turned_boxes = self.detector(turned)
        if self.classifier is not None and len(turned_boxes) > 0:
            sample = sorted_boxes(turned_boxes)
            crops = [get_rotate_crop_image(turned, b.copy()) for b in sample]
            labels = self.classifier.classify(crops)
            del crops
            upside_down = sum(
                1 for label, score in labels if "180" in label and score > self.config.cls_thresh
            )
            if upside_down * 2 > len(labels):
                turned = cv2.rotate(turned, cv2.ROTATE_180)
                turned_boxes = self.detector(turned)
        if self._is_rotated_page(turned_boxes):
            return img, dt_boxes  # turning did not help; keep the original reading
        logger.info("Page rotated 90 degrees; corrected before recognition.")
        return turned, turned_boxes

    def __call__(self, img: np.ndarray) -> list[tuple[list[list[float]], str, float]]:
        """Returns [(box, text, confidence), ...] in PaddleOCR's reading order
        (with `auto_rotate`, in the reading order of the upright page)."""
        img = self._to_bgr(img)
        dt_boxes = self.detector(img)
        if self.config.auto_rotate and self._is_rotated_page(dt_boxes):
            img, dt_boxes = self._correct_page_rotation(img, dt_boxes)
        if dt_boxes is None or len(dt_boxes) == 0:
            return []

        dt_boxes = sorted_boxes(dt_boxes)
        crops = [get_rotate_crop_image(img, dt_boxes[bno].copy()) for bno in range(len(dt_boxes))]
        if self.classifier is not None:
            crops = self.classifier(crops)
        rec_res = self.recognizer(crops)
        del crops

        results = []
        for box, (text, score) in zip(dt_boxes, rec_res):
            if score >= self.config.drop_score:
                results.append((box.tolist(), text, float(score)))
        return results
