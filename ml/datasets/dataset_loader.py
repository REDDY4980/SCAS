"""
DatasetLoader — AIB v1.0 Vol 9.5 Dataset Engineering Pipeline (first four
stages): Schema Validation -> Duplicate Removal -> Missing Value Handling
-> Range Validation.

Requirement 1 (MASTER_RESOURCE_INDEX.md) note: this loader validates
against the actual Kaggle "Crop Recommendation Dataset" schema — 7 input
columns (N, P, K, temperature, humidity, ph, rainfall) + label. Vol 9.4
also lists soil micronutrients and a categorical "Season" among the
*aspirational* full feature set, but Requirement 1's actual public
starter dataset does not include them. This loader is honest about that:
it validates the dataset that actually exists rather than pretending
columns are present that aren't. See ml/feature_engineering/README for
how this reconciles with Vol 9.4/9.6.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall", "label"]

# Vol 9.6 feature validation rules, restricted to columns that actually
# exist in Requirement 1's dataset.
_RANGE_RULES: dict[str, tuple[float, float]] = {
    "N": (0, float("inf")),
    "P": (0, float("inf")),
    "K": (0, float("inf")),
    "ph": (0, 14),
    "temperature": (-10, 60),  # generous physical bounds, not a crop-specific range
    "humidity": (0, 100),
    "rainfall": (0, float("inf")),
}


@dataclass
class DatasetValidationReport:
    rows: int
    columns: int
    duplicate_rows_removed: int
    missing_values_before: dict[str, int]
    out_of_range_rows_removed: int
    classes: int
    class_counts: dict[str, int]
    sha256: str
    warnings: list[str] = field(default_factory=list)


class DatasetLoader:
    """Vol 9.16 core component: DatasetLoader."""

    def load_and_validate(self, csv_path: str | Path) -> tuple[pd.DataFrame, DatasetValidationReport]:
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Dataset not found: {csv_path}")

        sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        df = pd.read_csv(csv_path)

        missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Dataset is missing required columns: {sorted(missing_cols)}")

        missing_values_before = {col: int(df[col].isna().sum()) for col in REQUIRED_COLUMNS}

        rows_before_dedup = len(df)
        df = df.drop_duplicates()
        duplicate_rows_removed = rows_before_dedup - len(df)

        # Vol 9.5 "Missing Value Handling": for this starter dataset the
        # verified fact sheet (Requirement 1 README) states 0 missing
        # values; rows with any NaN in a required column are dropped
        # defensively rather than silently imputed, since imputing a
        # *target label* would fabricate training data.
        df = df.dropna(subset=REQUIRED_COLUMNS)

        rows_before_range_check = len(df)
        mask = pd.Series(True, index=df.index)
        for column, (low, high) in _RANGE_RULES.items():
            mask &= df[column].between(low, high)
        out_of_range_rows_removed = rows_before_range_check - int(mask.sum())
        df = df[mask].reset_index(drop=True)

        class_counts = df["label"].value_counts().to_dict()

        warnings: list[str] = []
        if duplicate_rows_removed > 0:
            warnings.append(f"Removed {duplicate_rows_removed} duplicate row(s).")
        if out_of_range_rows_removed > 0:
            warnings.append(f"Removed {out_of_range_rows_removed} row(s) outside physical ranges.")
        min_class_count = min(class_counts.values()) if class_counts else 0
        if min_class_count < 20:
            warnings.append(
                f"Smallest class has only {min_class_count} samples — stratified splits may be unstable."
            )

        report = DatasetValidationReport(
            rows=len(df),
            columns=len(REQUIRED_COLUMNS),
            duplicate_rows_removed=duplicate_rows_removed,
            missing_values_before=missing_values_before,
            out_of_range_rows_removed=out_of_range_rows_removed,
            classes=df["label"].nunique(),
            class_counts=class_counts,
            sha256=sha256,
            warnings=warnings,
        )
        return df, report
