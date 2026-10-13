"""Append-only audit logging."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from meritvector_api.models import AuditLog


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def record(
    db: Session,
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
            at=now(),
        )
    )
    if commit:
        db.commit()


def record_principal(
    db: Session,
    p,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    record(
        db,
        tenant_id=p.tenant_id,
        actor_user_id=p.user_id,
        actor_role=p.role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        commit=commit,
    )
