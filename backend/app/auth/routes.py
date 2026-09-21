"""Authentication and crew-account endpoints."""
from __future__ import annotations

from datetime import datetime, time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth.service import (
    ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, create_refresh_token,
    current_crew, decode_token, get_crew, hash_password,
    verify_password,
    require_roles,
)
from backend.app.auth.email_service import admin_registration_email, approval_email, registration_received_email
from backend.app.db.base import get_db
from backend.app.db.models import AuditLog, Crew
from backend.app.notifications.service import create_notification

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    employee_id: str = Field(pattern=r"^EMP-\d{3,}$")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["GANG", "MATE", "GANGMAN", "SUPERVISOR"] = "GANG"
    primary_skill: Literal["TRACK", "SIGNAL", "OHE", "POINT_MACHINE", "BRIDGE", "TELECOM"] = "TRACK"
    shift_start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$")
    shift_end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$")
    department_id: str | None = Field(default=None, max_length=64)
    provider_type: Literal["WORKS_CONTRACT", "AMC_CAMC", "OEM_AUTHORIZED"] | None = None
    provider_id: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ApprovalRequest(BaseModel):
    employee_id: str


def _parse_shift(value: str) -> time:
    return time.fromisoformat(value if len(value.split(":")) == 3 else f"{value}:00")


def _token_response(crew: Crew) -> dict:
    return {"access_token": create_access_token(crew), "refresh_token": create_refresh_token(crew), "token_type": "bearer", "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60, "crew": {"employee_id": crew.employee_id, "full_name": crew.full_name, "role": crew.role}}


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if payload.provider_type and not payload.provider_id:
        raise HTTPException(status_code=422, detail="provider_id is required for provider-affiliated crew")
    if payload.provider_id and not payload.provider_type:
        raise HTTPException(status_code=422, detail="provider_type is required when provider_id is supplied")
    crew = Crew(employee_id=payload.employee_id, email=str(payload.email).lower(), password_hash=hash_password(payload.password), full_name=payload.full_name.strip(), role=payload.role, primary_skill=payload.primary_skill, shift_start=_parse_shift(payload.shift_start), shift_end=_parse_shift(payload.shift_end), department_id=payload.department_id, provider_type=payload.provider_type, provider_id=payload.provider_id, is_active=False)
    db.add(crew)
    try:
        db.flush()
        db.add(AuditLog(action="CREW_REGISTERED", entity_type="CREW", entity_id=crew.id, after={"employee_id": crew.employee_id, "role": crew.role, "email": crew.email}))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Employee ID or email already exists") from exc
    db.refresh(crew)
    admins = db.scalars(select(Crew).where(Crew.role == "ADMIN", Crew.is_active.is_(True))).all()
    admin_email_deliveries = []
    for admin in admins:
        create_notification(
            db,
            user_id=admin.id,
            notif_type="APPROVAL_REQUIRED",
            title="New crew registration",
            message=f"{crew.full_name} ({crew.employee_id}) is waiting for approval.",
            payload={"employee_id": crew.employee_id, "email": crew.email},
            priority="HIGH",
        )
        admin_email_deliveries.append(admin_registration_email(full_name=crew.full_name, employee_id=crew.employee_id, crew_email=crew.email, to=admin.email))
    email_delivery = registration_received_email(full_name=crew.full_name, employee_id=crew.employee_id, to=crew.email)
    return {"employee_id": crew.employee_id, "full_name": crew.full_name, "role": crew.role, "email": crew.email, "is_active": False, "email_delivery": email_delivery, "admin_email_deliveries": admin_email_deliveries, "message": "Account created. Check your email; an administrator must approve it before sign-in."}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    crew = get_crew(db, payload.employee_id)
    if not crew or not verify_password(payload.password, crew.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials or account not approved", headers={"WWW-Authenticate": "Bearer"})
    if not crew.is_active:
        raise HTTPException(status_code=403, detail="Account pending administrator approval. Check your email for confirmation.")
    return _token_response(crew)


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    token = decode_token(payload.refresh_token, expected_type="refresh")
    crew = get_crew(db, str(token["sub"])) if token else None
    if not crew or not crew.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return _token_response(crew)


@router.post("/approve")
def approve(payload: ApprovalRequest, approver: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> dict:
    crew = get_crew(db, payload.employee_id)
    if not crew:
        raise HTTPException(status_code=404, detail="Crew member not found")
    if crew.is_active:
        raise HTTPException(status_code=409, detail="Crew member is already active")
    if crew.role == "ADMIN":
        raise HTTPException(status_code=422, detail="Administrator accounts cannot be approved through crew registration")
    crew.is_active = True
    crew.approved_at = datetime.utcnow()
    crew.approved_by = approver.id
    db.add(AuditLog(user_id=approver.id, action="CREW_APPROVED", entity_type="CREW", entity_id=crew.id, after={"employee_id": crew.employee_id, "approved_by": approver.employee_id}))
    db.commit()
    notification = create_notification(db, user_id=crew.id, notif_type="SYSTEM", title="Crew account approved", message="Your crew account is approved. You can now sign in.", payload={"employee_id": crew.employee_id}, priority="HIGH")
    email_delivery = approval_email(full_name=crew.full_name, employee_id=crew.employee_id, to=crew.email, approver=approver.full_name)
    return {"employee_id": crew.employee_id, "is_active": True, "approved_by": approver.employee_id, "email": crew.email, "email_delivery": email_delivery, "notification_id": notification.id}


@router.get("/me")
def me(crew: Crew = Depends(current_crew)) -> dict:
    return {"employee_id": crew.employee_id, "full_name": crew.full_name, "role": crew.role, "primary_skill": crew.primary_skill, "availability": crew.availability, "department_id": crew.department_id, "provider_type": crew.provider_type, "provider_id": crew.provider_id, "is_active": crew.is_active}


@router.get("/pending")
def pending(_: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> list[dict]:
    return [{"employee_id": c.employee_id, "full_name": c.full_name, "email": c.email, "role": c.role, "primary_skill": c.primary_skill, "department_id": c.department_id, "provider_type": c.provider_type, "provider_id": c.provider_id, "created_at": c.created_at.isoformat()} for c in db.scalars(select(Crew).where(Crew.is_active.is_(False), Crew.role != "ADMIN").order_by(Crew.created_at)).all()]


@router.get("/active")
def active(_: Crew = Depends(require_roles("ADMIN")), db: Session = Depends(get_db)) -> list[dict]:
    return [{"employee_id": c.employee_id, "full_name": c.full_name, "role": c.role, "primary_skill": c.primary_skill, "secondary_skills": c.secondary_skills or [], "availability": c.availability, "department_id": c.department_id, "provider_type": c.provider_type, "provider_id": c.provider_id} for c in db.scalars(select(Crew).where(Crew.is_active.is_(True), Crew.role != "ADMIN").order_by(Crew.full_name)).all()]
