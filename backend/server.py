"""Vercel ASGI entrypoint for the Blockwise.AI backend service.

Vercel Functions expose an immutable application bundle. The prototype's
mutable SQLite and file-backed workflow stores are therefore copied to /tmp for
the lifetime of each warm function instance. Production deployments should set
RAILWAY_DATABASE_URL to a durable PostgreSQL database and replace the file
stores with durable storage.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import types
from typing import Awaitable, Callable


BACKEND_ROOT = Path(__file__).resolve().parent

# The service root is backend/. Register that folder as the ``backend`` package
# so existing absolute imports keep working in Vercel's isolated service.
if "backend" not in sys.modules:
    package = types.ModuleType("backend")
    package.__path__ = [str(BACKEND_ROOT)]  # type: ignore[attr-defined]
    sys.modules["backend"] = package

SOURCE_DATA = BACKEND_ROOT / "app" / "data"
RUNTIME_ROOT = Path(os.getenv("BLOCKWISE_RUNTIME_DIR", "/tmp/blockwise"))
RUNTIME_DATA = RUNTIME_ROOT / "data"
RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)

if not RUNTIME_DATA.exists():
    shutil.copytree(SOURCE_DATA, RUNTIME_DATA)

os.environ.setdefault(
    "RAILWAY_DATABASE_URL",
    f"sqlite:///{(RUNTIME_ROOT / 'crew_management.db').as_posix()}",
)
os.environ.setdefault(
    "EMAIL_OUTBOX_PATH",
    str(RUNTIME_ROOT / "email_outbox.jsonl"),
)

from backend.app.config import (  # noqa: E402
    DURATION_MODEL_PATH,
    GRAPH_PATH,
    RISK_MODEL_PATH,
)
from backend.app.main import create_application  # noqa: E402


backend_app = create_application(
    data_dir=RUNTIME_DATA,
    risk_model_path=RISK_MODEL_PATH,
    duration_model_path=DURATION_MODEL_PATH,
    graph_path=GRAPH_PATH,
    traffic_profile_path=RUNTIME_DATA / "traffic_profile.csv",
    maintenance_requests_path=RUNTIME_DATA / "maintenance_requests.csv",
    plan_store_path=RUNTIME_DATA / "optimization_plans.json",
    feedback_path=RUNTIME_DATA / "simulation_feedback.csv",
)


class ApiPrefixAdapter:
    """Strip the public /api prefix before FastAPI route matching."""

    def __init__(self, application: Callable[..., Awaitable[None]]) -> None:
        self.application = application

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") in {"http", "websocket"}:
            path = str(scope.get("path", ""))
            if path == "/api" or path.startswith("/api/"):
                adjusted = dict(scope)
                adjusted_path = path[4:] or "/"
                adjusted["path"] = adjusted_path
                adjusted["raw_path"] = adjusted_path.encode("utf-8")
                scope = adjusted
        await self.application(scope, receive, send)


app = ApiPrefixAdapter(backend_app)
