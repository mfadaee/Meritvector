"""AI Coordinator and Meeting Intelligence endpoints (assistance data only)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from meritvector_api import audit
from meritvector_api.db import get_db
from meritvector_api.models import (
    CoordinatorTask,
    Dependency,
    Employee,
    Meeting,
    MeetingInsight,
    Milestone,
    OutboxMessage,
    Project,
    Risk,
    Tenant,
)
from meritvector_api.routers.workspace import _me, _meeting_dict, my_meetings, my_projects
from meritvector_api.security import Principal, current_principal
from meritvector_api.services import health_map, process_meeting, tenant_today, to_dict
from meritvector_connectors import (
    Authorisation,
    DeliveryNotAuthorised,
    DeliveryPolicy,
    MockDataSource,
    OutboundMessage,
    build_connectors,
)
from meritvector_coordinator import management_summary, project_documentation, unresolved_dependencies, weekly_status_report

router = APIRouter(tags=["coordinator"])


# ------------------------------------------------------------------ meetings
@router.get("/meetings")
def meetings(
    scope: Literal["past", "upcoming", "all"] = "all", p: Principal = Depends(current_principal), db: Session = Depends(get_db)
) -> list[dict]:
    _me(p)
    now_ = datetime.combine(tenant_today(db, p.tenant_id), time.min)
    ms = my_meetings(db, p)
    if scope == "past":
        ms = [m for m in ms if m.scheduled_at < now_]
    elif scope == "upcoming":
        ms = [m for m in ms if m.scheduled_at >= now_]
    ins = {i.meeting_id: i for i in db.scalars(select(MeetingInsight).where(MeetingInsight.meeting_id.in_([m.id for m in ms])))}
    return [_meeting_dict(m, ins.get(m.id)) for m in ms]


def _attended(db: Session, p: Principal, meeting_id: str) -> Meeting:
    m = db.get(Meeting, meeting_id)
    if m is None or m.tenant_id != p.tenant_id or p.employee_id not in (m.attendees or []):
        # Transcripts are visible only to attendees — not to managers, HR or administrators.
        raise HTTPException(404, "Meeting not found")
    return m


@router.get("/meetings/{meeting_id}")
def meeting(meeting_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    m = _attended(db, p, meeting_id)
    names = {e.id: e.display_name for e in db.scalars(select(Employee).where(Employee.id.in_(m.attendees)))}
    tasks = db.scalars(select(CoordinatorTask).where(CoordinatorTask.source_meeting_id == m.id)).all()
    d = _meeting_dict(m, db.get(MeetingInsight, m.id), with_transcript=True)
    d["attendee_names"] = names
    d["tasks_created"] = [to_dict(t) | {"owner_name": names.get(t.owner_employee_id)} for t in tasks]
    return d


@router.post("/meetings/{meeting_id}/process")
def process(meeting_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    m = _attended(db, p, meeting_id)
    if not m.transcript:
        raise HTTPException(409, "No transcript available for this meeting")
    t = db.get(Tenant, p.tenant_id)
    if not t.settings.get("transcript_processing_enabled", True):
        raise HTTPException(403, "Transcript processing is disabled for this organisation")
    ins = process_meeting(db, m, actor_user_id=p.user_id)
    audit.record_principal(db, p, "meeting_processed", "meeting", m.id, detail={"actions": len(ins.actions)})
    return meeting(meeting_id, p, db)


class TranscriptIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    transcript: str = Field(min_length=10, max_length=50000)
    meeting_date: date | None = None
    project_id: str | None = None


@router.post("/coordinator/process-transcript")
def process_transcript(body: TranscriptIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    """Process a pasted transcript. The caller is the only attendee recorded, so tasks are created only for them."""
    me = _me(p)
    if body.project_id:
        pr = db.get(Project, body.project_id)
        if pr is None or pr.tenant_id != p.tenant_id:
            raise HTTPException(404, "Project not found")
    when = body.meeting_date or tenant_today(db, p.tenant_id)
    mid = f"ADHOC-{me}-{audit.now():%Y%m%d%H%M%S%f}"
    m = Meeting(
        id=mid,
        tenant_id=p.tenant_id,
        project_id=body.project_id,
        title=body.title,
        scheduled_at=datetime.combine(when, time(9, 0)),
        attendees=[me],
        organiser_id=me,
        transcript=body.transcript,
        source="user_upload",
        data_category="assistance",
    )
    db.add(m)
    db.commit()
    process_meeting(db, m, actor_user_id=p.user_id)
    audit.record_principal(db, p, "transcript_uploaded", "meeting", mid)
    return meeting(mid, p, db)


# ------------------------------------------------------------------ tasks
class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    due_date: date | None = None
    project_id: str | None = None


class TaskPatch(BaseModel):
    status: Literal["open", "in_progress", "done"] | None = None
    due_date: date | None = None


@router.get("/coordinator/tasks")
def tasks(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> list[dict]:
    me = _me(p)
    today_ = tenant_today(db, p.tenant_id)
    rows = db.scalars(
        select(CoordinatorTask)
        .where(CoordinatorTask.tenant_id == p.tenant_id, CoordinatorTask.owner_employee_id == me)
        .order_by(CoordinatorTask.status, CoordinatorTask.due_date)
    ).all()
    return [to_dict(t) | {"overdue": bool(t.status != "done" and t.due_date and t.due_date < today_)} for t in rows]


@router.post("/coordinator/tasks")
def add_task(body: TaskIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    me = _me(p)
    t = CoordinatorTask(
        tenant_id=p.tenant_id,
        owner_employee_id=me,
        project_id=body.project_id,
        title=body.title,
        due_date=body.due_date,
        status="open",
        created_by=p.user_id,
        created_at=audit.now(),
    )
    db.add(t)
    db.commit()
    return to_dict(t)


@router.patch("/coordinator/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    t = db.get(CoordinatorTask, task_id)
    if t is None or t.tenant_id != p.tenant_id or t.owner_employee_id != p.employee_id:
        raise HTTPException(404, "Task not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(t, k, v)
    db.commit()
    # Completing an assistance task never creates assessment evidence.
    return to_dict(t)


# ------------------------------------------------------------------ reports
def _own_project(db: Session, p: Principal, project_id: str) -> Project:
    pr = db.get(Project, project_id)
    if pr is None or pr.tenant_id != p.tenant_id:
        raise HTTPException(404, "Project not found")
    if pr.lead_employee_id != p.employee_id and p.role not in ("manager", "hr_reviewer"):
        raise HTTPException(403, "Reports can be prepared by the project lead or a manager")
    return pr


@router.get("/coordinator/reports/weekly/{project_id}")
def weekly(project_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    pr = _own_project(db, p, project_id)
    today_ = tenant_today(db, p.tenant_id)
    ms = [to_dict(m) for m in db.scalars(select(Milestone).where(Milestone.project_id == pr.id).order_by(Milestone.planned_date))]
    rs = [to_dict(r) for r in db.scalars(select(Risk).where(Risk.project_id == pr.id))]
    ds = [to_dict(d) for d in db.scalars(select(Dependency).where(Dependency.project_id == pr.id))]
    acts = [
        to_dict(t) for t in db.scalars(select(CoordinatorTask).where(CoordinatorTask.project_id == pr.id, CoordinatorTask.status != "done"))
    ]
    names = {e.id: e.display_name for e in db.scalars(select(Employee).where(Employee.id.in_([a["owner_employee_id"] for a in acts])))}
    for a in acts:
        a["owner_name"] = names.get(a["owner_employee_id"])
    meetings_ = db.scalars(select(Meeting).where(Meeting.project_id == pr.id)).all()
    decisions = [
        d for i in db.scalars(select(MeetingInsight).where(MeetingInsight.meeting_id.in_([m.id for m in meetings_]))) for d in i.decisions
    ]
    health = health_map(db, p.tenant_id, [pr.id]).get(pr.id, {}).get("health")
    return weekly_status_report(
        project=to_dict(pr),
        milestones=ms,
        risks=rs,
        dependencies=ds,
        actions=acts,
        decisions=decisions,
        health=health,
        today=today_,
    )


@router.get("/coordinator/reports/documentation/{project_id}")
def documentation(project_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    pr = _own_project(db, p, project_id)
    lead = db.get(Employee, pr.lead_employee_id)
    md = project_documentation(
        project=to_dict(pr) | {"lead_name": lead.display_name if lead else pr.lead_employee_id},
        milestones=[
            to_dict(m) for m in db.scalars(select(Milestone).where(Milestone.project_id == pr.id).order_by(Milestone.planned_date))
        ],
        risks=[to_dict(r) for r in db.scalars(select(Risk).where(Risk.project_id == pr.id))],
        dependencies=[to_dict(d) for d in db.scalars(select(Dependency).where(Dependency.project_id == pr.id))],
    )
    return {
        "markdown": md,
        "generator": "deterministic",
        "disclosure": "Generated by deterministic rules (no language model was used).",
    }


@router.get("/coordinator/management-summary")
def mgmt_summary(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    _me(p)
    if p.role == "manager":
        team = [e.id for e in db.scalars(select(Employee).where(Employee.manager_id == p.employee_id))] + [p.employee_id]
        ps = db.scalars(
            select(Project).where(Project.tenant_id == p.tenant_id, Project.lead_employee_id.in_(team), Project.status == "active")
        ).all()
    else:
        ps = my_projects(db, p)
    health = {k: v["health"] for k, v in health_map(db, p.tenant_id, [x.id for x in ps]).items()}
    return {
        "summary": management_summary(projects=[to_dict(x) | {"project_id": x.id} for x in ps], health=health),
        "generator": "deterministic",
        "projects": len(ps),
    }


@router.get("/coordinator/dependencies")
def dependencies(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> list[dict]:
    _me(p)
    pids = [x.id for x in my_projects(db, p)]
    deps = [to_dict(d) for d in db.scalars(select(Dependency).where(Dependency.project_id.in_(pids)))]
    return unresolved_dependencies(deps, tenant_today(db, p.tenant_id))


# ------------------------------------------------------------------ outbox (delivery disabled by default)
class OutboxIn(BaseModel):
    channel: Literal["ms_teams", "outlook", "slack"]
    recipient: str = Field(min_length=2, max_length=200)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20000)


class SendIn(BaseModel):
    confirm: bool


@router.get("/coordinator/outbox")
def outbox(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    rows = db.scalars(
        select(OutboxMessage)
        .where(OutboxMessage.tenant_id == p.tenant_id, OutboxMessage.author_user_id == p.user_id)
        .order_by(OutboxMessage.created_at.desc())
    ).all()
    return {
        "external_delivery_enabled": t.settings.get("external_delivery_enabled", False),
        "messages": [to_dict(r) for r in rows],
    }


@router.post("/coordinator/outbox")
def draft(body: OutboxIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    m = OutboxMessage(
        tenant_id=p.tenant_id,
        author_user_id=p.user_id,
        channel=body.channel,
        recipient=body.recipient,
        subject=body.subject,
        body=body.body,
        status="draft",
        created_at=audit.now(),
    )
    db.add(m)
    db.commit()
    return to_dict(m)


@router.post("/coordinator/outbox/{message_id}/send")
def send(message_id: int, body: SendIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    m = db.get(OutboxMessage, message_id)
    if m is None or m.tenant_id != p.tenant_id or m.author_user_id != p.user_id:
        raise HTTPException(404, "Message not found")
    t = db.get(Tenant, p.tenant_id)
    policy = DeliveryPolicy(external_delivery_enabled=bool(t.settings.get("external_delivery_enabled", False)))
    auth = Authorisation(message_id=str(m.id), authorised_by=p.user_id, confirmed=body.confirm) if body.confirm else None
    conn = build_connectors(MockDataSource())[m.channel]
    try:
        receipt = conn.deliver(OutboundMessage(str(m.id), m.channel, m.recipient, m.subject, m.body), policy=policy, authorisation=auth)
    except DeliveryNotAuthorised as exc:
        m.status, m.status_detail = "blocked", str(exc)
        audit.record_principal(db, p, "delivery_blocked", "outbox_message", str(m.id), detail={"reason": str(exc)})
        raise HTTPException(403, str(exc)) from exc
    m.status, m.status_detail, m.authorised_at = receipt.status, receipt.detail, audit.now()
    audit.record_principal(db, p, "delivery_authorised", "outbox_message", str(m.id), detail={"channel": m.channel})
    return to_dict(m)
