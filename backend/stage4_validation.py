"""Isolated storage for Stage 4 browser verification; uses existing Stage 1 artifacts."""
from backend.app.config import PROJECT_ROOT
from backend.app.main import create_application

app = create_application(maintenance_requests_path=PROJECT_ROOT / '.stage4-validation' / 'maintenance_requests.csv')
