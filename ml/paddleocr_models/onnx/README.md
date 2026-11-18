# PP-OCR models (ONNX) used by the SCAS backend

These are the **same** PP-OCR weights that PaddleOCR 2.8.1 used for SCAS
(`../whl/`), converted 1:1 to ONNX so they run on ONNX Runtime without
PaddlePaddle (which cannot fit Render's 512 MB free tier — see
`docs/OCR_MEMORY_REPORT.md`). Nothing is downloaded at runtime.

| File | Source (in `../whl/`) | SHA-256 |
|---|---|---|
| `det.onnx` | `det/en/en_PP-OCRv3_det_infer` | `ea07c15d38ac40cd69da3c493444ec75b44ff23840553ff8ba102c1219ed39c2` |
| `rec.onnx` | `rec/en/en_PP-OCRv4_rec_infer` | `02672d591fee561a95a2491bd5504d66c812b145d1043026c5658ecc165c7e85` |
| `cls.onnx` | `cls/ch_ppocr_mobile_v2.0_cls_infer` | `e263cad54b85e6dd6ce5aed66154785682a221be2216300ce321e58a9d022296` |
| `en_dict.txt` | `paddleocr==2.8.1` `ppocr/utils/en_dict.txt` | `5662df9d2d03f0e8ca0d3b0649d6acbab904b6a14b3d3521463c71c37c668ce3` |

## How they were produced

In a separate environment with `paddlepaddle==2.6.2` and `paddle2onnx==1.2.11`:

```bash
paddle2onnx --model_dir ml/paddleocr_models/whl/det/en/en_PP-OCRv3_det_infer \
  --model_filename inference.pdmodel --params_filename inference.pdiparams \
  --save_file ml/paddleocr_models/onnx/det.onnx --opset_version 14 --enable_onnx_checker True
# same for rec (en_PP-OCRv4_rec_infer -> rec.onnx) and cls (ch_ppocr_mobile_v2.0_cls_infer -> cls.onnx)
```

## Verification

`backend/tests/integration/test_ocr_engine_real.py` checks that
`app/ocr/ppocr_onnx.py` running these files reproduces PaddleOCR 2.8.1 +
PaddlePaddle 2.6.2 text exactly on both calibration PDFs (8 pages, 599 text
lines; reference in `backend/tests/fixtures/paddleocr_2_8_1_reference.json`).

PP-OCR models and dictionary: © PaddlePaddle Authors, Apache License 2.0.
