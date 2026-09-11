"""Random-forest maintenance duration pipeline with cached inference loading."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from backend.app.config import DURATION_MODEL_PATH, JOBS_PATH


FEATURE_COLUMNS = [
    "job_type",
    "asset_condition",
    "crew_size",
    "weather_condition",
    "historical_duration",
]
NUMERIC_FEATURES = ["asset_condition", "crew_size", "historical_duration"]
CATEGORICAL_FEATURES = ["job_type", "weather_condition"]
TARGET_COLUMN = "duration_min"


def _build_pipeline() -> Pipeline:
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))]),
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        sparse_threshold=0.0,
    )
    regressor = RandomForestRegressor(
        n_estimators=500,
        max_depth=12,
        min_samples_leaf=1,
        max_features=0.9,
        random_state=42,
        n_jobs=-1,
    )
    return Pipeline(steps=[("preprocessing", preprocessing), ("model", regressor)])


def _atomic_joblib_dump(model: Pipeline, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
    try:
        joblib.dump(model, temporary_path, compress=3)
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def train_duration_model(
    data_path: str | Path = JOBS_PATH,
    model_path: str | Path = DURATION_MODEL_PATH,
) -> dict[str, Any]:
    """Evaluate on unseen rows, refit on all rows, and save the full pipeline."""
    frame = pd.read_csv(data_path)
    missing = set(FEATURE_COLUMNS + [TARGET_COLUMN]).difference(frame.columns)
    if missing:
        raise ValueError(f"Duration training data is missing columns: {sorted(missing)}")
    if len(frame) < 12:
        raise ValueError("Duration training requires at least 12 records")

    features = frame[FEATURE_COLUMNS]
    target = frame[TARGET_COLUMN].astype(float)
    train_features, test_features, train_target, test_target = train_test_split(
        features, target, test_size=0.25, random_state=42
    )
    evaluation_pipeline = _build_pipeline()
    evaluation_pipeline.fit(train_features, train_target)
    predictions = evaluation_pipeline.predict(test_features)
    metrics: dict[str, Any] = {
        "algorithm": "RandomForestRegressor",
        "records": int(len(frame)),
        "test_records": int(len(test_target)),
        "mae_minutes": round(float(mean_absolute_error(test_target, predictions)), 6),
        "rmse_minutes": round(
            float(mean_squared_error(test_target, predictions) ** 0.5), 6
        ),
        "r2": round(float(r2_score(test_target, predictions)), 6),
        "seed": 42,
        "evaluation": "deterministic holdout; final artifact refit on all synthetic rows",
    }

    final_pipeline = _build_pipeline()
    final_pipeline.fit(features, target)
    destination = Path(model_path)
    _atomic_joblib_dump(final_pipeline, destination)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".metrics.tmp",
        delete=False,
    ) as temporary_file:
        json.dump(metrics, temporary_file, indent=2, sort_keys=True)
        metrics_temporary_path = Path(temporary_file.name)
    os.replace(metrics_temporary_path, destination.with_suffix(".metrics.json"))
    _load_duration_model.cache_clear()
    return metrics


@lru_cache(maxsize=4)
def _load_duration_model(resolved_path: str, modified_ns: int) -> Pipeline:
    del modified_ns
    model = joblib.load(resolved_path)
    if not isinstance(model, Pipeline):
        raise TypeError("Duration artifact is not a Scikit-Learn Pipeline")
    return model


def load_duration_model(model_path: str | Path = DURATION_MODEL_PATH) -> Pipeline:
    path = Path(model_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Duration model is missing: {path}")
    return _load_duration_model(str(path), path.stat().st_mtime_ns)


def predict_maintenance_duration(
    features_dict: dict[str, Any],
    model_path: str | Path = DURATION_MODEL_PATH,
    *,
    model: Pipeline | None = None,
) -> float:
    """Predict one bounded, positive duration in minutes."""
    missing = set(FEATURE_COLUMNS).difference(features_dict)
    if missing:
        raise ValueError(f"Duration features are missing: {sorted(missing)}")
    inference_model = model or load_duration_model(model_path)
    frame = pd.DataFrame([{key: features_dict[key] for key in FEATURE_COLUMNS}])
    prediction = float(inference_model.predict(frame)[0])
    return round(max(1.0, prediction), 2)

