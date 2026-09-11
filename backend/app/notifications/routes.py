"""Authenticated notification REST and WebSocket endpoints."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.service import current_crew, decode_token, get_crew
from backend.app.db.base import SessionLocal, get_db
from backend.app.db.models import Crew, Notification
from backend.app.notifications.service import NOTIFICATION_TYPES, manager, serialize

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _bearer(websocket: WebSocket) -> str | None:
    header = websocket.headers.get("authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = _bearer(websocket)
    payload = decode_token(token or "")
    db = SessionLocal()
    crew = get_crew(db, str(payload["sub"])) if payload else None
    if not crew or not crew.is_active:
        db.close()
        await websocket.close(code=4001, reason="Authentication required")
        return
    await manager.connect(websocket, crew.id, crew.role)
    db.close()
    try:
        while True:
            message = await websocket.receive_text()
            if message:
                try:
                    if json.loads(message).get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    continue
    except WebSocketDisconnect:
        manager.disconnect(crew.id)


@router.get("")
def list_notifications(unread: bool = False, crew: Crew = Depends(current_crew), db: Session = Depends(get_db)) -> list[dict]:
    query = select(Notification).where(Notification.user_id == crew.id)
    if unread:
        query = query.where(Notification.read_at.is_(None))
    return [serialize(item) for item in db.scalars(query.order_by(Notification.created_at.desc()).limit(100)).all()]


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, crew: Crew = Depends(current_crew), db: Session = Depends(get_db)) -> dict:
    notification = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == crew.id))
    if not notification:
        raise HTTPException(404, "Notification not found")
    notification.read_at = notification.read_at or datetime.utcnow()
    db.commit()
    return serialize(notification)


@router.get("/types")
def get_notification_types(_: Crew = Depends(current_crew)) -> dict:
    return {"types": list(NOTIFICATION_TYPES)}
