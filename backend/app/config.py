"""Filesystem configuration resolved independently of the working directory."""

import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent


def _load_local_env() -> None:
    """Load simple KEY=VALUE settings for local runs without overriding the shell."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()
DATA_DIR = APP_DIR / "data"
MODEL_DIR = APP_DIR / "ml" / "artifacts"
GRAPH_PATH = APP_DIR / "graph" / "railway_graph.json"

TIMETABLE_PATH = DATA_DIR / "timetable_base.csv"
TRAINS_PATH = DATA_DIR / "trains.csv"
ASSETS_PATH = DATA_DIR / "assets.csv"
CREWS_PATH = DATA_DIR / "crews.csv"
JOBS_PATH = DATA_DIR / "maintenance_jobs.csv"
WEATHER_PATH = DATA_DIR / "weather.csv"
TRAFFIC_PROFILE_PATH = DATA_DIR / "traffic_profile.csv"
MAINTENANCE_REQUESTS_PATH = DATA_DIR / "maintenance_requests.csv"
PLAN_STORE_PATH = DATA_DIR / "optimization_plans.json"
FEEDBACK_PATH = DATA_DIR / "simulation_feedback.csv"
RISK_MODEL_PATH = MODEL_DIR / "risk_model.joblib"
DURATION_MODEL_PATH = MODEL_DIR / "duration_model.joblib"
METRICS_PATH = MODEL_DIR / "model_metrics.json"

# --- Criticality scoring weights (normalized to 0-100) ---
# Each factor contributes a weighted portion to the final operational criticality score.
# Weights must sum to 1.0 across all factors.
CRITICALITY_WEIGHTS = {
    "asset_risk": 0.25,
    "condition_score": 0.15,
    "age_years": 0.10,
    "previous_failures": 0.10,
    "days_since_maintenance": 0.15,
    "weather_condition": 0.10,
    "train_traffic": 0.10,
    "section_impact": 0.05,
}

# Weather condition penalty multipliers for criticality calculation
WEATHER_CRITICALITY_PENALTY = {
    "CLEAR": 0.0,
    "CLOUDY": 1.0,
    "LIGHT_RAIN": 4.0,
    "HEAVY_RAIN": 8.0,
    "FOG": 5.0,
}

# Risk level mapping for criticality calculation
RISK_SEVERITY_SCORE = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
RISK_CRITICALITY_BUMP = {"LOW": 10.0, "MEDIUM": 20.0, "HIGH": 35.0, "CRITICAL": 55.0}

# Criticality class boundaries (0-100 scale)
CRITICALITY_THRESHOLDS = {"HIGH": 70.0, "MEDIUM": 40.0}

# --- Confidence threshold ---
MIN_CONFIDENCE = float(os.getenv("BLOCKWISE_MIN_CONFIDENCE", "0.60"))

# --- Data quality: minimum required fields for risk prediction ---
REQUIRED_RISK_FEATURES = [
    "age_years",
    "condition_score",
    "previous_failures",
    "days_since_maintenance",
    "criticality",
    "weather_condition",
]
