"""Central database configuration used by every crew-management module."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_URL = f"sqlite:///{ROOT / 'backend' / 'app' / 'data' / 'crew_management.db'}"


class Base(DeclarativeBase):
    pass


def _engine(url: str):
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        pool_pre_ping=True,
        future=True,
    )


DATABASE_URL = os.getenv("RAILWAY_DATABASE_URL", DEFAULT_DATABASE_URL)
engine = _engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure_database(url: str) -> None:
    global DATABASE_URL, engine, SessionLocal
    engine.dispose()
    DATABASE_URL = url
    engine = _engine(url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _additive_schema_upgrade()
    from backend.app.auth.service import ensure_bootstrap_admin
    ensure_bootstrap_admin()


def _additive_schema_upgrade() -> None:
    """Add newly introduced nullable columns for an existing local SQLite DB."""
    additions = {
        "crews": {
            "parent_crew_id": "VARCHAR(36)", "certifications": "JSON",
            "phone": "VARCHAR(20)", "emergency_contact": "JSON",
            "department_id": "VARCHAR(64)", "provider_type": "VARCHAR(24)",
            "provider_id": "VARCHAR(64)",
        },
        "work_orders": {
            "asset_type": "VARCHAR(50)", "variance_minutes": "INTEGER",
            "gps_start": "JSON", "gps_end": "JSON",
            "overtime_minutes": "INTEGER DEFAULT 0",
            "material_cost": "NUMERIC(10, 2) DEFAULT 0",
            "equipment_cost": "NUMERIC(10, 2) DEFAULT 0",
            "rejection_reason": "TEXT",
            "execution_mode": "VARCHAR(24) NOT NULL DEFAULT 'DEPARTMENTAL'",
            "department_id": "VARCHAR(64)", "contract_id": "VARCHAR(64)",
            "amc_id": "VARCHAR(64)", "oem_service_id": "VARCHAR(64)",
        },
        "checklists": {"created_at": "DATETIME"},
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)} if table in inspector.get_table_names() else set()
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}'))
