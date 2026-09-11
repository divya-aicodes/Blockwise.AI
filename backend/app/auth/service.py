"""Password authentication, signed tokens, and role checks."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import SessionLocal, get_db
from backend.app.db.models import Crew

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
_configured_secret = os.getenv("RAILWAY_JWT_SECRET")
if os.getenv("APP_ENV", "development").lower() == "production" and not _configured_secret:
    raise RuntimeError("RAILWAY_JWT_SECRET is required in production")
SECRET_KEY = _configured_secret or secrets.token_urlsafe(48)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
ROLE_LEVEL = {"GANG": 1, "MATE": 2, "GANGMAN": 3, "SUPERVISOR": 4, "ADMIN": 5}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(crew: Crew) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": crew.employee_id, "role": crew.role, "type": "access", "iat": now, "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(crew: Crew) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": crew.employee_id, "type": "refresh", "iat": now, "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, *, expected_type: str = "access") -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type or not payload.get("sub"):
            return None
        return payload
    except JWTError:
        return None


def get_crew(db: Session, employee_id: str) -> Crew | None:
    return db.scalar(select(Crew).where(Crew.employee_id == employee_id))


def authenticate_crew(db: Session, employee_id: str, password: str) -> Crew | None:
    crew = get_crew(db, employee_id)
    if not crew or not crew.is_active or not verify_password(password, crew.password_hash):
        return None
    return crew


def current_crew(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Crew:
    payload = decode_token(token)
    crew = get_crew(db, str(payload["sub"])) if payload else None
    if not crew or not crew.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return crew


def require_roles(*roles: str) -> Callable:
    allowed = {role.upper() for role in roles}

    def dependency(crew: Crew = Depends(current_crew)) -> Crew:
        if crew.role.upper() not in allowed and not ("SUPERVISOR" in allowed and ROLE_LEVEL.get(crew.role, 0) >= ROLE_LEVEL["SUPERVISOR"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return crew

    return dependency


def admin_or_anonymous(
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)),
    db: Session = Depends(get_db),
) -> Crew | None:
    """Allow the public synthetic demo, but never allow a signed-in worker into it.

    The dashboard can still be previewed without an account. Once a worker is
    authenticated, all operational APIs protected with this dependency require
    the ADMIN role. This prevents a worker from bypassing the UI by replaying an
    API request with their bearer token.
    """
    if not token:
        return None
    payload = decode_token(token)
    crew = get_crew(db, str(payload["sub"])) if payload else None
    if not crew or not crew.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if crew.role.upper() != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return crew


def can_manage(crew: Crew) -> bool:
    return ROLE_LEVEL.get(crew.role, 0) >= ROLE_LEVEL["SUPERVISOR"]


def ensure_bootstrap_admin() -> None:
    """Create the first admin only when all explicit bootstrap env values exist."""
    employee_id = os.getenv("RAILWAY_BOOTSTRAP_ADMIN_ID")
    email = os.getenv("RAILWAY_BOOTSTRAP_ADMIN_EMAIL")
    password = os.getenv("RAILWAY_BOOTSTRAP_ADMIN_PASSWORD")
    if not employee_id or not email or not password:
        return
    if len(password) < 16:
        raise RuntimeError("RAILWAY_BOOTSTRAP_ADMIN_PASSWORD must contain at least 16 characters")
    db = SessionLocal()
    try:
        if db.scalar(select(Crew).where(Crew.role == "ADMIN")):
            return
        db.add(Crew(employee_id=employee_id, email=email.lower(), password_hash=hash_password(password), full_name="System Administrator", role="ADMIN", primary_skill="TRACK", is_active=True, approved_at=datetime.utcnow()))
        db.commit()
    finally:
        db.close()
