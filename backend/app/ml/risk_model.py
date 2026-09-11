"""Random-forest asset risk pipeline with cached inference loading."""

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
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from backend.app.config import ASSETS_PATH, RISK_MODEL_PATH


FEATURE_COLUMNS = [
    "age_years",
    "condition_score",
    "previous_failures",
    "days_since_maintenance",
    "criticality",
    "weather_condition",
]
NUMERIC_FEATURES = [
    "age_years",
    "condition_score",
    "previous_failures",
    "days_since_maintenance",
]
CATEGORICAL_FEATURES = ["criticality", "weather_condition"]
TARGET_COLUMN = "risk_level"


def _build_pipeline() -> Pipeline:
    numeric_pipeline = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median"))]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )
    preprocessing = ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        sparse_threshold=0.0,
    )
    classifier = RandomForestClassifier(
        n_estimators=400,
        max_depth=10,
        min_samples_leaf=1,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    return Pipeline(steps=[("preprocessing", preprocessing), ("model", classifier)])


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


def _atomic_json_dump(payload: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        json.dump(payload, temporary_file, indent=2, sort_keys=True)
        temporary_path = Path(temporary_file.name)
    os.replace(temporary_path, destination)


def train_risk_model(
    data_path: str | Path = ASSETS_PATH,
    model_path: str | Path = RISK_MODEL_PATH,
) -> dict[str, Any]:
    """Evaluate on a holdout split, refit on all rows, and save the full pipeline."""
    frame = pd.read_csv(data_path)
    missing = set(FEATURE_COLUMNS + [TARGET_COLUMN]).difference(frame.columns)
    if missing:
        raise ValueError(f"Risk training data is missing columns: {sorted(missing)}")
    if frame[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Risk training requires at least two target classes")

    features = frame[FEATURE_COLUMNS]
    target = frame[TARGET_COLUMN].astype(str)
    class_counts = target.value_counts()
    stratify = target if int(class_counts.min()) >= 2 else None
    test_size = max(target.nunique(), round(len(frame) * 0.33))
    train_features, test_features, train_target, test_target = train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=42,
        stratify=stratify,
    )

    evaluation_pipeline = _build_pipeline()
    evaluation_pipeline.fit(train_features, train_target)
    predictions = evaluation_pipeline.predict(test_features)
    metrics: dict[str, Any] = {
        "algorithm": "RandomForestClassifier",
        "records": int(len(frame)),
        "test_records": int(len(test_target)),
        "accuracy": round(float(accuracy_score(test_target, predictions)), 6),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(test_target, predictions)), 6
        ),
        "macro_f1": round(float(f1_score(test_target, predictions, average="macro")), 6),
        "class_counts": {str(key): int(value) for key, value in class_counts.items()},
        "seed": 42,
        "evaluation": "deterministic holdout; final artifact refit on all synthetic rows",
    }

    final_pipeline = _build_pipeline()
    final_pipeline.fit(features, target)
    destination = Path(model_path)
    _atomic_joblib_dump(final_pipeline, destination)
    _atomic_json_dump(metrics, destination.with_suffix(".metrics.json"))
    _load_risk_model.cache_clear()
    return metrics


@lru_cache(maxsize=4)
def _load_risk_model(resolved_path: str, modified_ns: int) -> Pipeline:
    del modified_ns
    model = joblib.load(resolved_path)
    if not isinstance(model, Pipeline):
        raise TypeError("Risk artifact is not a Scikit-Learn Pipeline")
    return model


def load_risk_model(model_path: str | Path = RISK_MODEL_PATH) -> Pipeline:
    path = Path(model_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Risk model is missing: {path}")
    return _load_risk_model(str(path), path.stat().st_mtime_ns)


def predict_asset_risk(
    features_dict: dict[str, Any],
    model_path: str | Path = RISK_MODEL_PATH,
    *,
    model: Pipeline | None = None,
) -> tuple[str, dict[str, float]]:
    """Predict one risk class and a complete normalized probability mapping."""
    missing = set(FEATURE_COLUMNS).difference(features_dict)
    if missing:
        raise ValueError(f"Risk features are missing: {sorted(missing)}")
    inference_model = model or load_risk_model(model_path)
    frame = pd.DataFrame([{key: features_dict[key] for key in FEATURE_COLUMNS}])
    predicted_class = str(inference_model.predict(frame)[0])
    probabilities = inference_model.predict_proba(frame)[0]
    classifier = inference_model.named_steps["model"]
    probability_map = {
        str(label): round(float(probability), 8)
        for label, probability in zip(classifier.classes_, probabilities, strict=True)
    }
    return predicted_class, probability_map

