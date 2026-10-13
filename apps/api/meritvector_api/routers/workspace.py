"""Employee workspace: Today, My Projects, My Coordinator, My Development, My Data."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meritvector_api import audit
from meritvector_api.db import get_db
from meritvector_api.models import (
    CoordinatorTask,
    Dependency,
    DevelopmentGoal,
    Employee,
    EmployeeRunOutput,
    EvidenceChallenge,
    EvidenceEventRow,
    Meeting,
    MeetingInsight,
    Milestone,
    Project,
    Reminder,
    ReviewNote,
    Risk,
    Tenant,
    User,
)
from meritvector_api.security import Principal, current_principal, require_assessment_enabled
from meritvector_api.services import health_map, tenant_today, to_dict
from meritvector_api.training import latest_run
from meritvector_coordinator import daily_briefing, unresolved_dependencies, weekly_status_report

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _me(p: Principal) -> str:
    if not p.employee_id:
        raise HTTPException(403, "This account has no employee workspace")
    return p.employee_id


def my_meetings(db: Session, p: Principal, start: datetime | None = None, end: datetime | None = None) -> list[Meeting]:
    rows = db.scalars(select(Meeting).where(Meeting.tenant_id == p.tenant_id)).all()
    out = [m for m in rows if p.employee_id in (m.attendees or [])]
    if start:
        out = [m for m in out if m.scheduled_at >= start]
    if end:
        out = [m for m in out if m.scheduled_at <= end]
    return sorted(out, key=lambda m: m.scheduled_at)


def my_projects(db: Session, p: Principal, active_only: bool = True) -> list[Project]:
    stmt = select(Project).where(Project.tenant_id == p.tenant_id, Project.lead_employee_id == p.employee_id)
    if active_only:
        stmt = stmt.where(Project.status == "active")
    return list(db.scalars(stmt.order_by(Project.start_date.desc())))


def _meeting_dict(m: Meeting, insight: MeetingInsight | None = None, with_transcript: bool = False) -> dict[str, Any]:
    d = {k: v for k, v in to_dict(m).items() if k != "transcript" or with_transcript}
    d["has_transcript"] = bool(m.transcript)
    if insight is not None:
        d["insight"] = {k: v for k, v in to_dict(insight).items() if k not in ("meeting_id", "tenant_id")}
    return d


@router.get("/today")
def today(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    me = _me(p)
    today_ = tenant_today(db, p.tenant_id)
    start = datetime.combine(today_, time.min)
    meetings = my_meetings(db, p, start, start + timedelta(days=7))
    tasks = db.scalars(select(CoordinatorTask).where(CoordinatorTask.tenant_id == p.tenant_id,
                                                     CoordinatorTask.owner_employee_id == me,
                                                     CoordinatorTask.status != "done").order_by(CoordinatorTask.due_date)).all()
    projects = my_projects(db, p)
    pids = [x.id for x in projects]
    deadlines = db.scalars(select(Milestone).where(Milestone.project_id.in_(pids), Milestone.status != "achieved",
                                                   Milestone.planned_date <= today_ + timedelta(days=30))
                           .order_by(Milestone.planned_date)).all()
    risks = db.scalars(select(Risk).where(Risk.project_id.in_(pids), Risk.status.in_(["open", "issue"]))
                       .order_by(Risk.severity, Risk.identified_on.desc())).all()
    past = my_meetings(db, p, start - timedelta(days=14), start)
    ins = {i.meeting_id: i for i in db.scalars(select(MeetingInsight).where(MeetingInsight.meeting_id.in_([m.id for m in past])))}
    decisions = [{"text": d["text"], "meeting": m.title, "date": str(m.scheduled_at.date())}
                 for m in reversed(past) if m.id in ins for d in ins[m.id].decisions][:8]
    reminders = db.scalars(select(Reminder).where(Reminder.tenant_id == p.tenant_id, Reminder.employee_id == me)).all()
    pname = {x.id: x.name for x in projects}
    return {
        "today": str(today_),
        "upcoming_meetings": [_meeting_dict(m) for m in meetings],
        "open_actions": [to_dict(t) | {"overdue": bool(t.due_date and t.due_date < today_)} for t in tasks],
        "deadlines": [to_dict(m) | {"project_name": pname.get(m.project_id), "overdue": m.planned_date < today_} for m in deadlines],
        "risks": [to_dict(r) | {"project_name": pname.get(r.project_id)} for r in risks],
        "recent_decisions": decisions,
        "reminders": [to_dict(r) for r in reminders],
    }


@router.get("/projects")
def projects(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> list[dict]:
    _me(p)
    today_ = tenant_today(db, p.tenant_id)
    ps = my_projects(db, p)
    health = health_map(db, p.tenant_id, [x.id for x in ps])
    out = []
    for pr in ps:
        ms = db.scalars(select(Milestone).where(Milestone.project_id == pr.id).order_by(Milestone.planned_date)).all()
        deps = db.scalars(select(Dependency).where(Dependency.project_id == pr.id)).all()
        rs = db.scalars(select(Risk).where(Risk.project_id == pr.id)).all()
        out.append({
            **to_dict(pr),
            "health": health.get(pr.id, {}),
            "milestones": [to_dict(m) for m in ms],
            "blockers": [to_dict(r) for r in rs if r.status == "issue"]
            + [{"title": f"Waiting on {d['depends_on']}", **d} for d in unresolved_dependencies([to_dict(x) for x in deps], today_) if d["stale"]],
            "risks": [to_dict(r) for r in rs if r.status in ("open", "issue")],
            "dependencies": [to_dict(d) for d in deps],
            "documents": [{"title": f"{m.name} deliverable", "status": "approved" if m.status == "achieved" else "in preparation",
                           "milestone_id": m.id, "due": str(m.planned_date)} for m in ms],
        })
    return out


@router.get("/coordinator")
def coordinator(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    me = _me(p)
    today_ = tenant_today(db, p.tenant_id)
    start = datetime.combine(today_, time.min)
    meetings = my_meetings(db, p, start - timedelta(days=14), start + timedelta(days=7))
    ins = {i.meeting_id: i for i in db.scalars(select(MeetingInsight).where(MeetingInsight.meeting_id.in_([m.id for m in meetings])))}
    tasks = db.scalars(select(CoordinatorTask).where(CoordinatorTask.tenant_id == p.tenant_id,
                                                     CoordinatorTask.owner_employee_id == me)).all()
    projects_ = my_projects(db, p)
    pids = [x.id for x in projects_]
    ms = db.scalars(select(Milestone).where(Milestone.project_id.in_(pids))).all()
    rs = db.scalars(select(Risk).where(Risk.project_id.in_(pids))).all()
    decisions = [d for m in meetings if m.id in ins for d in ins[m.id].decisions]
    brief = daily_briefing(person=p.display_name, today=today_,
                           meetings=[{"scheduled_at": m.scheduled_at, "title": m.title} for m in meetings],
                           tasks=[to_dict(t) for t in tasks], milestones=[to_dict(m) for m in ms], risks=[to_dict(r) for r in rs],
                           decisions=decisions)
    health = health_map(db, p.tenant_id, pids)
    drafts = []
    for pr in projects_:
        drafts.append({"project_id": pr.id, "project_name": pr.name, **weekly_status_report(
            project=to_dict(pr), milestones=[to_dict(m) for m in ms if m.project_id == pr.id],
            risks=[to_dict(r) for r in rs if r.project_id == pr.id],
            dependencies=[to_dict(d) for d in db.scalars(select(Dependency).where(Dependency.project_id == pr.id))],
            actions=[to_dict(t) for t in tasks if t.project_id == pr.id and t.status != "done"],
            decisions=[d for m in meetings if m.id in ins and m.project_id == pr.id for d in ins[m.id].decisions],
            health=health.get(pr.id, {}).get("health"), today=today_)})
    follow_ups = [{"task_id": t.id, "suggestion": f"Follow up on “{t.title}” — it was due {t.due_date}.",
                   "draft_message": f"Hi team, a quick check on “{t.title}” (due {t.due_date}). Could you share the status or a "
                                    "revised date? Thanks."}
                  for t in tasks if t.status != "done" and t.due_date and t.due_date < today_]
    return {
        "briefing": brief,
        "meeting_summaries": [_meeting_dict(m, ins.get(m.id)) for m in reversed(meetings) if m.id in ins],
        "suggested_follow_ups": follow_ups,
        "draft_reports": drafts,
        "outstanding_actions": [to_dict(t) for t in tasks if t.status != "done"],
    }


@router.get("/development")
def development(p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    me = _me(p)
    run = latest_run(db, p.tenant_id)
    out = db.get(EmployeeRunOutput, (run.id, me)) if run else None
    counts = dict(db.execute(select(EvidenceEventRow.category, func.count()).where(
        EvidenceEventRow.tenant_id == p.tenant_id, EvidenceEventRow.employee_id == me,
        EvidenceEventRow.data_category == "assessment_evidence").group_by(EvidenceEventRow.category)).all())
    recent = db.scalars(select(EvidenceEventRow).where(
        EvidenceEventRow.tenant_id == p.tenant_id, EvidenceEventRow.employee_id == me,
        EvidenceEventRow.data_category == "assessment_evidence").order_by(EvidenceEventRow.occurred_at.desc()).limit(12)).all()
    feedback = db.scalars(select(EvidenceEventRow).where(
        EvidenceEventRow.tenant_id == p.tenant_id, EvidenceEventRow.employee_id == me,
        EvidenceEventRow.category == "stakeholder_feedback").order_by(EvidenceEventRow.occurred_at.desc())).all()
    reviews = db.scalars(select(ReviewNote).where(ReviewNote.tenant_id == p.tenant_id, ReviewNote.employee_id == me)
                         .order_by(ReviewNote.created_at.desc())).all()
    goals = db.scalars(select(DevelopmentGoal).where(DevelopmentGoal.tenant_id == p.tenant_id, DevelopmentGoal.employee_id == me)).all()
    comps = (out.payload.get("competencies") if out else []) or []
    audit.record_principal(db, p, "viewed_own_development", "employee", me)
    return {
        "run_id": run.id if run else None,
        "competencies": comps,
        "evidence_counts": counts,
        "recent_evidence": [to_dict(e) for e in recent],
        "feedback_history": [{"date": str(e.occurred_at.date()), "score": e.payload.get("score"),
                              "respondent_role": e.payload.get("respondent_role"), "project_id": e.project_id} for e in feedback],
        "review_notes": [to_dict(r) for r in reviews],
        "goals": [to_dict(g) for g in goals],
        "missing_evidence": [c for c in comps if c["status"] in ("evidence_gap", "emerging")],
        "estimates": (out.payload.get("estimates") if out else None),
        "trend": (out.payload.get("trend") if out else None),
        "disclaimer": "This is a summary of recorded evidence, not a rating. Gaps may reflect the work you were given "
                      "rather than your capability. Discuss it with your manager and challenge anything inaccurate.",
    }


class GoalIn(BaseModel):
    competency: str = Field(max_length=64)
    goal: str = Field(min_length=5, max_length=2000)


@router.post("/goals")
def add_goal(body: GoalIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    me = _me(p)
    g = DevelopmentGoal(tenant_id=p.tenant_id, employee_id=me, competency=body.competency, goal=body.goal, created_at=audit.now())
    db.add(g)
    db.commit()
    return to_dict(g)


@router.get("/data")
def my_data(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    me = _me(p)
    by_cat = db.execute(select(EvidenceEventRow.data_category, EvidenceEventRow.source_system, func.count()).where(
        EvidenceEventRow.tenant_id == p.tenant_id, EvidenceEventRow.employee_id == me)
        .group_by(EvidenceEventRow.data_category, EvidenceEventRow.source_system)).all()
    t = db.get(Tenant, p.tenant_id)
    n_meetings = len(my_meetings(db, p))
    n_tasks = db.scalar(select(func.count()).where(CoordinatorTask.owner_employee_id == me, CoordinatorTask.tenant_id == p.tenant_id))
    challenges = db.scalars(select(EvidenceChallenge).where(EvidenceChallenge.employee_id == me,
                                                            EvidenceChallenge.tenant_id == p.tenant_id)
                            .order_by(EvidenceChallenge.created_at.desc())).all()
    user = db.get(User, p.user_id)
    emp = db.get(Employee, me)
    return {
        "profile": {"employee_id": me, "display_name": emp.display_name, "job_family": emp.job_family, "level": emp.level,
                    "business_unit": emp.business_unit, "is_synthetic": emp.is_synthetic},
        "records": [{"data_category": c, "source_system": s, "count": n} for c, s, n in by_cat]
        + [{"data_category": "assistance", "source_system": "meetings", "count": n_meetings},
           {"data_category": "assistance", "source_system": "coordinator_tasks", "count": n_tasks}],
        "assessment_enabled": t.assessment_enabled,
        "retention_days": t.settings.get("retention_days", {}),
        "challenges": [to_dict(c) for c in challenges],
        "privacy_preferences": {"transcript_processing": user.preferences.get("transcript_processing", True),
                                "daily_briefing": user.preferences.get("daily_briefing", True)},
    }


class Prefs(BaseModel):
    transcript_processing: bool | None = None
    daily_briefing: bool | None = None


@router.put("/preferences")
def prefs(body: Prefs, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    u = db.get(User, p.user_id)
    u.preferences = {**u.preferences, **body.model_dump(exclude_none=True)}
    audit.record_principal(db, p, "privacy_preferences_updated", "user", p.user_id, detail=body.model_dump(exclude_none=True))
    return u.preferences
