"""Coordinator and organisational-reporting services shared by routers, seeding and jobs.

Nothing in this module reads performance-assessment outputs: the coordinator works on
assistance and organisational-reporting data only.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from meritvector_analytics.descriptive import project_health
from meritvector_api.audit import now
from meritvector_api.models import (
    CoordinatorTask,
    Dependency,
    Employee,
    Meeting,
    MeetingInsight,
    Milestone,
    Project,
    Risk,
    Tenant,
)
from meritvector_coordinator import extract


def tenant_today(db: Session, tenant_id: str) -> date:
    """The demo runs on the synthetic organisation's clock (its ``as_of`` date)."""
    t = db.get(Tenant, tenant_id)
    return t.as_of if t else date.today()


def to_dict(obj) -> dict[str, Any]:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def process_meeting(db: Session, meeting: Meeting, *, actor_user_id: str, create_tasks: bool = True) -> MeetingInsight:
    if not meeting.transcript:
        raise ValueError("Meeting has no transcript")
    attendees = db.scalars(select(Employee).where(Employee.id.in_(meeting.attendees))).all()
    first_names: dict[str, str] = {}
    for e in attendees:
        first = e.display_name.split()[0]
        # Only map unambiguous first names within the meeting.
        first_names[first] = "" if first in first_names else e.id
    known = {k: v for k, v in first_names.items() if v}
    ins = extract(meeting.transcript, meeting.scheduled_at.date(), known_people=known)
    existing = db.get(MeetingInsight, meeting.id)
    if existing is not None:
        db.delete(existing)
        db.flush()
    row = MeetingInsight(
        meeting_id=meeting.id, tenant_id=meeting.tenant_id, summary=ins.summary,
        actions=[a.__dict__ for a in ins.actions], decisions=ins.decisions, risks=ins.risks,
        dependencies=ins.dependencies, generator=ins.generator, disclosure=ins.disclosure, created_at=now(),
    )
    db.add(row)
    if create_tasks:
        already = {(t.owner_employee_id, t.title) for t in db.scalars(
            select(CoordinatorTask).where(CoordinatorTask.source_meeting_id == meeting.id))}
        for a in ins.actions:
            if a.owner not in known.values():
                continue  # owner not resolvable to an attendee — left in the insight for manual triage
            if (a.owner, a.description) in already:
                continue
            db.add(CoordinatorTask(
                tenant_id=meeting.tenant_id, owner_employee_id=a.owner, project_id=meeting.project_id, title=a.description,
                due_date=date.fromisoformat(a.due_date) if a.due_date else None, status="open",
                source_meeting_id=meeting.id, source_line=a.source_line, created_by=actor_user_id, created_at=now(),
            ))
    db.commit()
    return row


def frames_for_health(db: Session, tenant_id: str, project_ids: list[str] | None = None) -> pd.DataFrame:
    def q(model):
        stmt = select(model).where(model.tenant_id == tenant_id)
        if project_ids is not None:
            col = model.id if model is Project else model.project_id
            stmt = stmt.where(col.in_(project_ids))
        rows = [to_dict(o) for o in db.scalars(stmt)]
        return pd.DataFrame(rows, columns=[c.name for c in model.__table__.columns])

    projects = q(Project).rename(columns={"id": "project_id"})
    if projects.empty:
        return pd.DataFrame(columns=["project_id", "health"])
    milestones = q(Milestone)
    risks = q(Risk)
    deps = q(Dependency)
    return project_health(projects, milestones, risks, deps, tenant_today(db, tenant_id))


def health_map(db: Session, tenant_id: str, project_ids: list[str] | None = None) -> dict[str, dict[str, Any]]:
    h = frames_for_health(db, tenant_id, project_ids)
    out = {}
    for r in h.to_dict("records"):
        r = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in r.items()}
        out[r["project_id"]] = r
    return out
