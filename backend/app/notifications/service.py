"""Persisted notifications and authenticated WebSocket fan-out."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Crew, Notification, WorkOrder

NOTIFICATION_TYPES = (
    "WORK_ORDER_ASSIGNED", "WORK_ORDER_UPDATED", "APPROVAL_REQUIRED",
    "WORK_ORDER_COMPLETED", "WORK_ORDER_VERIFIED", "WORK_ORDER_REJECTED",
    "CHECKLIST_DUE", "SHIFT_REMINDER", "EMERGENCY", "SYSTEM",
)


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


def resolve_notification_recipients(
    db: Session, work_order: WorkOrder, event: str
) -> tuple[list[Crew], list[str]]:
    """Resolve only users related to this order; never falls back to a broadcast."""
    recipient_ids: set[str] = set()
    unresolved: list[str] = []
    if event in {"WORK_ORDER_ASSIGNED", "WORK_ORDER_UPDATED", "WORK_ORDER_VERIFIED", "WORK_ORDER_REJECTED", "EMERGENCY"}:
        if work_order.assigned_crew_id:
            recipient_ids.add(work_order.assigned_crew_id)
        else:
            unresolved.append("assigned_crew")
    if event in {"WORK_ORDER_ASSIGNED", "WORK_ORDER_UPDATED", "APPROVAL_REQUIRED", "WORK_ORDER_COMPLETED", "EMERGENCY"}:
        if work_order.supervisor_id:
            recipient_ids.add(work_order.supervisor_id)
        else:
            unresolved.append("supervisor")

    managers: list[Crew] = []
    if work_order.execution_mode == "DEPARTMENTAL" and work_order.department_id:
        managers = list(db.scalars(select(Crew).where(
            Crew.is_active.is_(True), Crew.role == "SUPERVISOR",
            Crew.department_id == work_order.department_id,
        )).all())
    elif work_order.execution_mode in {"WORKS_CONTRACT", "AMC_CAMC", "OEM_AUTHORIZED"}:
        reference = {
            "WORKS_CONTRACT": work_order.contract_id,
            "AMC_CAMC": work_order.amc_id,
            "OEM_AUTHORIZED": work_order.oem_service_id,
        }[work_order.execution_mode]
        if reference:
            managers = list(db.scalars(select(Crew).where(
                Crew.is_active.is_(True), Crew.role == "SUPERVISOR",
                Crew.provider_type == work_order.execution_mode,
                Crew.provider_id == reference,
            )).all())
        else:
            unresolved.append("provider_reference")
    for manager in managers:
        recipient_ids.add(manager.id)

    recipients = list(db.scalars(select(Crew).where(
        Crew.id.in_(recipient_ids), Crew.is_active.is_(True)
    )).all()) if recipient_ids else []
    if managers == [] and (
        (work_order.execution_mode == "DEPARTMENTAL" and work_order.department_id)
        or work_order.execution_mode in {"WORKS_CONTRACT", "AMC_CAMC", "OEM_AUTHORIZED"}
    ):
        unresolved.append("responsible_manager")
    return recipients, sorted(set(unresolved))


def create_targeted_notifications(
    db: Session,
    *,
    work_order: WorkOrder,
    event: str,
    title: str,
    message: str,
    next_action: str,
    priority: str = "NORMAL",
) -> dict[str, Any]:
    recipients, unresolved = resolve_notification_recipients(db, work_order, event)
    payload = {
        "work_order_id": work_order.id,
        "work_order_number": work_order.work_order_number,
        "plan_id": work_order.plan_id,
        "maintenance_id": work_order.maintenance_id,
        "execution_mode": work_order.execution_mode,
        "asset_id": work_order.asset_id,
        "section_id": work_order.section_id,
        "planned_start": work_order.planned_start.isoformat() if work_order.planned_start else None,
        "planned_end": work_order.planned_end.isoformat() if work_order.planned_end else None,
        "priority": work_order.priority,
        "next_action": next_action,
    }
    if event not in NOTIFICATION_TYPES:
        raise ValueError("Invalid notification type")
    created = [
        Notification(
            user_id=recipient.id,
            type=event,
            title=title,
            message=message,
            payload=payload,
            priority=priority,
        )
        for recipient in recipients
    ]
    evidence = dict(work_order.evidence or {})
    routing = dict(evidence.get("notification_routing") or {})
    routing[event] = {
        "recipient_user_ids": [recipient.id for recipient in recipients],
        "unresolved_recipients": unresolved,
    }
    evidence["notification_routing"] = routing
    work_order.evidence = evidence
    db.add_all(created)
    db.commit()
    for notification in created:
        db.refresh(notification)
    return {
        "notification_ids": [item.id for item in created],
        "recipient_user_ids": [item.user_id for item in created],
        "unresolved_recipients": unresolved,
    }


def serialize(notification: Notification) -> dict:
    return {"id": notification.id, "user_id": notification.user_id, "type": notification.type, "title": notification.title, "message": notification.message, "payload": notification.payload or {}, "priority": notification.priority, "read_at": notification.read_at.isoformat() if notification.read_at else None, "created_at": notification.created_at.isoformat() if notification.created_at else None}
