"""Small, provider-neutral email delivery layer for crew account events.

Local development uses a durable JSONL outbox so the workflow is observable
without sending real email. Production can set EMAIL_MODE=smtp and provide the
SMTP_* settings. SMTP failures are retained in the outbox for later retry.
"""
from __future__ import annotations

import json
import os
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _outbox_path() -> Path:
    configured = os.getenv("EMAIL_OUTBOX_PATH")
    return Path(configured) if configured else ROOT / "backend" / "app" / "data" / "email_outbox.jsonl"


def _queue(*, to: str, subject: str, body: str, error: str | None = None) -> dict[str, str]:
    path = _outbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "message_id": f"MAIL-{secrets.token_hex(8).upper()}",
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "subject": subject,
        "body": body,
        "status": "QUEUED",
    }
    if error:
        record["last_error"] = error[:500]
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "QUEUED", "message_id": record["message_id"]}


def deliver_email(*, to: str, subject: str, body: str) -> dict[str, str]:
    """Deliver through SMTP when configured, otherwise queue a local preview."""
    mode = os.getenv("EMAIL_MODE", "outbox").strip().lower()
    host = os.getenv("SMTP_HOST", "").strip()
    if mode != "smtp" or not host:
        try:
            return _queue(to=to, subject=subject, body=body)
        except OSError as exc:
            return {"status": "FAILED", "message_id": "", "error": str(exc)[:500]}

    sender = os.getenv("EMAIL_FROM", "no-reply@railway.local").strip()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        use_tls = os.getenv("SMTP_TLS", "true").lower() not in {"0", "false", "no"}
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            username = os.getenv("SMTP_USERNAME", "").strip()
            password = os.getenv("SMTP_PASSWORD", "")
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
        return {"status": "SENT", "message_id": f"SMTP-{secrets.token_hex(8).upper()}"}
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        try:
            return _queue(to=to, subject=subject, body=body, error=str(exc))
        except OSError as queue_error:
            return {"status": "FAILED", "message_id": "", "error": str(queue_error)[:500]}


def registration_received_email(*, full_name: str, employee_id: str, to: str) -> dict[str, str]:
    return deliver_email(
        to=to,
        subject="Crew account received — administrator review pending",
        body=(
            f"Hello {full_name},\n\n"
            f"Your crew account request ({employee_id}) has been received. "
            "An administrator must approve it before you can sign in. "
            "You will receive another email after approval.\n\n"
            "Railway Operations"
        ),
    )


def admin_registration_email(*, full_name: str, employee_id: str, crew_email: str, to: str) -> dict[str, str]:
    return deliver_email(
        to=to,
        subject="New crew registration requires approval",
        body=(
            f"A new crew registration is waiting for review.\n\n"
            f"Name: {full_name}\nEmployee ID: {employee_id}\nCrew email: {crew_email}\n\n"
            "Open the administrator dashboard to approve or reject the request.\n\n"
            "Railway Operations"
        ),
    )


def approval_email(*, full_name: str, employee_id: str, to: str, approver: str) -> dict[str, str]:
    return deliver_email(
        to=to,
        subject="Crew account approved — you can sign in",
        body=(
            f"Hello {full_name},\n\n"
            f"Your crew account ({employee_id}) has been approved by {approver}. "
            "You can now sign in to the Railway Operations crew dashboard.\n\n"
            "Railway Operations"
        ),
    )
