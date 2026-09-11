"""Durable crew-management models with consistent string UUID foreign keys."""
from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


def uid() -> str:
    return str(uuid.uuid4())


class Crew(Base):
    __tablename__ = "crews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="GANG")
    parent_crew_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("crews.id"), nullable=True, index=True)
    primary_skill: Mapped[str] = mapped_column(String(20), default="TRACK")
    shift_start: Mapped[object] = mapped_column(Time, default=lambda: time(6, 0))
    shift_end: Mapped[object] = mapped_column(Time, default=lambda: time(14, 0))
    availability: Mapped[str] = mapped_column(String(20), default="AVAILABLE")
    secondary_skills: Mapped[list] = mapped_column(JSON, default=list)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emergency_contact: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("crews.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    work_order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    plan_id: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    maintenance_id: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_id: Mapped[str] = mapped_column(String(32))
    asset_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    required_skill: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    assigned_crew_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("crews.id"), nullable=True)
    supervisor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("crews.id"), nullable=True)
    planned_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estimated_duration_min: Mapped[int] = mapped_column(Integer, default=1)
    actual_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variance_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gps_start: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gps_end: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    material_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    equipment_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("crews.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Checklist(Base):
    __tablename__ = "checklists"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    work_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("work_orders.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    template_version: Mapped[str] = mapped_column(String(20))
    items: Mapped[list] = mapped_column(JSON, default=list)
    completed_items: Mapped[dict] = mapped_column(JSON, default=dict)
    signed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("crews.id"), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("crews.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
