"""Persisted notifications and authenticated WebSocket fan-out."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import WebSocket
from sqlalchemy.orm import Session

from backend.app.db.models import Notification

NOTIFICATION_TYPES = ("WORK_ORDER_ASSIGNED", "WORK_ORDER_UPDATED", "APPROVAL_REQUIRED", "CHECKLIST_DUE", "SHIFT_REMINDER", "EMERGENCY", "SYSTEM")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.role_connections: dict[str, set[str]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user_id: str, role: str) -> None:
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.role_connections[role].add(user_id)

    def disconnect(self, user_id: str) -> None:
        self.active_connections.pop(user_id, None)
        for users in self.role_connections.values():
            users.discard(user_id)

    async def send_personal(self, user_id: str, message: dict[str, Any]) -> None:
        socket = self.active_connections.get(user_id)
        if socket:
            try:
                await socket.send_text(json.dumps(message, default=str))
            except Exception:
                self.disconnect(user_id)

    async def broadcast_to_role(self, role: str, message: dict[str, Any]) -> None:
        for user_id in list(self.role_connections.get(role, set())):
            await self.send_personal(user_id, message)


manager = ConnectionManager()


def create_notification(db: Session, *, user_id: str, notif_type: str, title: str, message: str, payload: dict | None = None, priority: str = "NORMAL") -> Notification:
    if notif_type not in NOTIFICATION_TYPES:
        raise ValueError("Invalid notification type")
    notification = Notification(user_id=user_id, type=notif_type, title=title, message=message, payload=payload or {}, priority=priority)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def serialize(notification: Notification) -> dict:
    return {"id": notification.id, "user_id": notification.user_id, "type": notification.type, "title": notification.title, "message": notification.message, "payload": notification.payload or {}, "priority": notification.priority, "read_at": notification.read_at.isoformat() if notification.read_at else None, "created_at": notification.created_at.isoformat() if notification.created_at else None}
