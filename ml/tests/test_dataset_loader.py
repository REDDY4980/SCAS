"""Dataset loader tests — validated against the real Requirement 1 dataset."""

from pathlib import Path

import pandas as pd
import pytest

from ml.datasets.dataset_loader import DatasetLoader

REAL_DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "datasets" / "crop_recommendation" / "Crop_recommendation.csv"
)
KNOWN_SHA256 = "808e1d84a544647f1ab2fdae04f434b1842692d6be09eee18a5c2d43eb78d77c"


def test_real_dataset_matches_known_facts():
    loader = DatasetLoader()
    df, report = loader.load_and_validate(REAL_DATASET_PATH)
    assert report.rows == 2200
    assert report.classes == 22
    assert report.duplicate_rows_removed == 0
    assert report.out_of_range_rows_removed == 0
    assert report.sha256 == KNOWN_SHA256
    assert report.warnings == []


def test_missing_file_raises():
    loader = DatasetLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_and_validate("/nonexistent/path.csv")


def test_missing_required_column_raises(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    pd.DataFrame({"N": [1, 2], "P": [1, 2], "label": ["rice", "maize"]}).to_csv(bad_csv, index=False)
    loader = DatasetLoader()
    with pytest.raises(ValueError, match="missing required columns"):
        loader.load_and_validate(bad_csv)


def test_duplicates_are_removed(tmp_path):
    csv_path = tmp_path / "dupes.csv"
    row = {"N": 90, "P": 42, "K": 43, "temperature": 20.0, "humidity": 80.0, "ph": 6.5, "rainfall": 200.0, "label": "rice"}
    pd.DataFrame([row, row, row]).to_csv(csv_path, index=False)
    loader = DatasetLoader()
    df, report = loader.load_and_validate(csv_path)
    assert len(df) == 1
    assert report.duplicate_rows_removed == 2


def test_out_of_range_ph_is_removed(tmp_path):
    csv_path = tmp_path / "bad_ph.csv"
    good = {"N": 90, "P": 42, "K": 43, "temperature": 20.0, "humidity": 80.0, "ph": 6.5, "rainfall": 200.0, "label": "rice"}
    bad = {**good, "ph": 17.0}  # impossible pH
    pd.DataFrame([good, bad]).to_csv(csv_path, index=False)
    loader = DatasetLoader()
    df, report = loader.load_and_validate(csv_path)
    assert len(df) == 1
    assert report.out_of_range_rows_removed == 1


def test_missing_values_dropped_not_imputed(tmp_path):
    csv_path = tmp_path / "missing.csv"
    good = {"N": 90, "P": 42, "K": 43, "temperature": 20.0, "humidity": 80.0, "ph": 6.5, "rainfall": 200.0, "label": "rice"}
    incomplete = {**good, "ph": None}
    pd.DataFrame([good, incomplete]).to_csv(csv_path, index=False)
    loader = DatasetLoader()
    df, report = loader.load_and_validate(csv_path)
    assert len(df) == 1  # the incomplete row is dropped, not filled in
    assert report.missing_values_before["ph"] == 1


def test_small_class_triggers_warning(tmp_path):
    csv_path = tmp_path / "small_class.csv"
    rows = [
        {"N": 90, "P": 42, "K": 43, "temperature": 20.0, "humidity": 80.0, "ph": 6.5, "rainfall": 200.0, "label": "rice"}
        for _ in range(25)
    ]
    rows.append(
        {"N": 10, "P": 10, "K": 10, "temperature": 25.0, "humidity": 60.0, "ph": 6.0, "rainfall": 100.0, "label": "rare_crop"}
    )
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    loader = DatasetLoader()
    df, report = loader.load_and_validate(csv_path)
    assert any("smallest class" in w.lower() for w in report.warnings)
