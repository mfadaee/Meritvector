"""Administration, governance, privacy disclosure, audit log, jobs and connectors."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meritvector_api import audit
from meritvector_api.db import get_db, session
from meritvector_api.models import (
    AuditLog,
    EvidenceEventRow,
    GovernanceApproval,
    JobRun,
    ScheduledJob,
    Tenant,
    User,
)
from meritvector_api.security import Principal, current_principal, require_roles
from meritvector_api.services import to_dict
from meritvector_api.workflows import REGISTRY, run_job
from meritvector_connectors import MockDataSource, build_connectors

router = APIRouter(tags=["administration"])


# ------------------------------------------------------------------ privacy (all users)
DATA_INVENTORY = [
    {
        "category": "assistance",
        "label": "Productivity assistance",
        "what": "Meeting transcripts you attend, summaries, follow-up tasks, drafts, reminders.",
        "why": "To help you coordinate work.",
        "used_for_assessment": False,
        "sources": ["Microsoft Teams (mock)", "Outlook calendar (mock)", "Items you create"],
    },
    {
        "category": "org_reporting",
        "label": "Organisational reporting",
        "what": "Project registers: milestones, risks, issues, dependencies, project status and health.",
        "why": "Portfolio management and status reporting.",
        "used_for_assessment": False,
        "sources": ["PMO register (mock)", "Jira / Asana / monday.com (mock)"],
    },
    {
        "category": "assessment_evidence",
        "label": "Performance-assessment evidence",
        "what": "Validated work records: milestones achieved, risks mitigated, blockers and dependencies resolved, "
        "deliverable reviews, stakeholder survey results, project outcomes and operating context.",
        "why": "Evidence-based, context-adjusted development conversations — only after governance approval.",
        "used_for_assessment": True,
        "sources": [
            "Jira / Asana / monday.com (mock)",
            "Microsoft Graph document approvals (mock)",
            "PMO register (mock)",
            "Stakeholder survey (mock)",
        ],
    },
    {
        "category": "diagnostic_activity",
        "label": "Activity metadata (synthetic diagnostics only)",
        "what": "Monthly counts of meetings, e-mails and hours in the synthetic dataset. No content.",
        "why": "To demonstrate that activity volume is not a measure of merit.",
        "used_for_assessment": False,
        "sources": ["Microsoft Graph (mock, metadata only)"],
    },
]
NEVER_COLLECTED = [
    "E-mail or chat message content",
    "Keystrokes",
    "Screenshots or screen recording",
    "Browsing history",
    "Location",
    "Webcam or microphone outside meetings you choose to transcribe",
    "Protected characteristics in any individual estimate",
]


@router.get("/privacy/notice")
def notice(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    return {
        "notice_text": t.settings.get("notice_text"),
        "assessment_purpose": t.settings.get("assessment_purpose"),
        "assessment_enabled": t.assessment_enabled,
        "external_delivery_enabled": t.settings.get("external_delivery_enabled", False),
        "never_collected": NEVER_COLLECTED,
        "covert_monitoring": False,
    }


@router.get("/privacy/inventory")
def inventory(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    ret = t.settings.get("retention_days", {})
    return {
        "categories": [dict(c, retention_days=ret.get(c["category"])) for c in DATA_INVENTORY],
        "never_collected": NEVER_COLLECTED,
    }


@router.post("/privacy/acknowledge")
def acknowledge(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    audit.record_principal(db, p, "notice_acknowledged", "privacy_notice")
    return {"acknowledged": True}


# ------------------------------------------------------------------ settings
class SettingsUpdate(BaseModel):
    notice_text: str | None = Field(default=None, max_length=5000)
    assessment_purpose: str | None = Field(default=None, max_length=5000)
    external_delivery_enabled: bool | None = None
    transcript_processing_enabled: bool | None = None
    retention_days: dict[str, int] | None = None


@router.get("/admin/settings")
def get_settings_(p: Principal = Depends(require_roles("admin", "hr_reviewer")), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    return {
        "tenant": {
            "id": t.id,
            "name": t.name,
            "is_synthetic": t.is_synthetic,
            "assessment_enabled": t.assessment_enabled,
            "as_of": str(t.as_of),
        },
        "settings": t.settings,
    }


@router.put("/admin/settings")
def put_settings(body: SettingsUpdate, p: Principal = Depends(require_roles("admin")), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    new = dict(t.settings)
    changes = body.model_dump(exclude_none=True)
    if "retention_days" in changes:
        if any(v < 1 for v in changes["retention_days"].values()):
            raise HTTPException(422, "Retention periods must be at least 1 day")
        new["retention_days"] = {**new.get("retention_days", {}), **changes.pop("retention_days")}
    new.update(changes)
    t.settings = new
    audit.record_principal(db, p, "settings_updated", "tenant", t.id, detail=body.model_dump(exclude_none=True))
    return {"settings": t.settings}


# ------------------------------------------------------------------ governance
class GovernanceRequest(BaseModel):
    purpose: str = Field(min_length=20, max_length=5000)
    features: list[str] = ["contribution_evidence", "contextual_analysis", "development_insights", "model_validation"]


@router.get("/admin/governance")
def governance(p: Principal = Depends(require_roles("admin", "hr_reviewer")), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    rows = db.scalars(
        select(GovernanceApproval).where(GovernanceApproval.tenant_id == p.tenant_id).order_by(GovernanceApproval.created_at.desc())
    ).all()
    return {
        "assessment_enabled": t.assessment_enabled,
        "approvals": [to_dict(r) for r in rows],
        "rule": "Assessment features require approval by both an administrator and an HR reviewer.",
    }


@router.post("/admin/governance/request")
def governance_request(body: GovernanceRequest, p: Principal = Depends(require_roles("admin")), db: Session = Depends(get_db)) -> dict:
    g = GovernanceApproval(
        tenant_id=p.tenant_id,
        purpose=body.purpose,
        scope={"features": body.features},
        requested_by=p.user_id,
        admin_approved_by=p.user_id,
        status="pending",
        created_at=audit.now(),
    )
    db.add(g)
    db.flush()
    audit.record_principal(db, p, "governance_requested", "governance_approval", str(g.id), detail={"features": body.features})
    return to_dict(g)


@router.post("/admin/governance/{approval_id}/approve")
def governance_approve(
    approval_id: int, p: Principal = Depends(require_roles("admin", "hr_reviewer")), db: Session = Depends(get_db)
) -> dict:
    g = db.get(GovernanceApproval, approval_id)
    if g is None or g.tenant_id != p.tenant_id:
        raise HTTPException(404, "Approval request not found")
    if g.status != "pending":
        raise HTTPException(409, f"Request is {g.status}")
    if p.role == "hr_reviewer":
        g.hr_approved_by = p.user_id
    else:
        g.admin_approved_by = p.user_id
    if g.hr_approved_by and g.admin_approved_by:
        g.status, g.decided_at = "approved", audit.now()
        db.get(Tenant, p.tenant_id).assessment_enabled = True
    audit.record_principal(db, p, "governance_approved", "governance_approval", str(g.id), detail={"status": g.status})
    return to_dict(g)


@router.post("/admin/governance/revoke")
def governance_revoke(p: Principal = Depends(require_roles("admin", "hr_reviewer")), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    t.assessment_enabled = False
    for g in db.scalars(
        select(GovernanceApproval).where(GovernanceApproval.tenant_id == p.tenant_id, GovernanceApproval.status == "approved")
    ):
        g.status, g.decided_at = "revoked", audit.now()
    audit.record_principal(db, p, "governance_revoked", "tenant", t.id)
    return {"assessment_enabled": False}


# ------------------------------------------------------------------ audit log
@router.get("/admin/audit")
def audit_log(
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
    p: Principal = Depends(require_roles("admin", "hr_reviewer")),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AuditLog).where(AuditLog.tenant_id == p.tenant_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.at.desc(), AuditLog.id.desc()).offset(offset).limit(min(limit, 500))).all()
    actions = db.scalars(select(AuditLog.action).where(AuditLog.tenant_id == p.tenant_id).distinct()).all()
    return {"total": total, "entries": [to_dict(r) for r in rows], "actions": sorted(actions)}


# ------------------------------------------------------------------ jobs
@router.get("/admin/jobs")
def jobs(p: Principal = Depends(require_roles("admin")), db: Session = Depends(get_db)) -> dict:
    js = db.scalars(select(ScheduledJob).order_by(ScheduledJob.name)).all()
    runs = db.scalars(select(JobRun).order_by(JobRun.started_at.desc()).limit(30)).all()
    return {
        "jobs": [to_dict(j) for j in js],
        "runs": [
            {k: v for k, v in to_dict(r).items() if k != "detail"} | {"detail": {k: v for k, v in (r.detail or {}).items() if k != "trace"}}
            for r in runs
        ],
    }


def _run_in_background(name: str) -> None:
    with session() as db:
        run_job(db, name, trigger="manual")


@router.post("/admin/jobs/{name}/run")
def run_job_now(
    name: str, bg: BackgroundTasks, p: Principal = Depends(require_roles("admin", "hr_reviewer")), db: Session = Depends(get_db)
) -> dict:
    if name not in REGISTRY:
        raise HTTPException(404, "Unknown job")
    if name == "retrain_models" and not db.get(Tenant, p.tenant_id).assessment_enabled:
        raise HTTPException(403, "Assessment is not enabled for this organisation")
    if p.role == "hr_reviewer" and name != "retrain_models":
        raise HTTPException(403, "HR reviewers may only trigger model retraining")
    audit.record_principal(db, p, "job_triggered", "job", name)
    bg.add_task(_run_in_background, name)
    return {"queued": name}


# ------------------------------------------------------------------ connectors & users
@router.get("/admin/connectors")
def connectors(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    counts = dict(
        db.execute(
            select(EvidenceEventRow.source_system, func.count())
            .where(EvidenceEventRow.tenant_id == p.tenant_id)
            .group_by(EvidenceEventRow.source_system)
        ).all()
    )
    out = []
    for name, c in build_connectors(MockDataSource()).items():
        d = c.describe()
        d["records_ingested"] = int(counts.get(name, 0))
        out.append(d)
    return out


class RoleUpdate(BaseModel):
    role: Literal["employee", "manager", "hr_reviewer", "admin", "researcher"]


@router.get("/admin/users")
def users(q: str = "", p: Principal = Depends(require_roles("admin")), db: Session = Depends(get_db)) -> dict:
    counts = dict(db.execute(select(User.role, func.count()).where(User.tenant_id == p.tenant_id).group_by(User.role)).all())
    stmt = select(User).where(User.tenant_id == p.tenant_id)
    if q:
        stmt = stmt.where(User.display_name.ilike(f"%{q}%"))
    rows = db.scalars(stmt.order_by(User.role.desc(), User.display_name).limit(50)).all()
    return {
        "role_counts": counts,
        "users": [{"user_id": u.id, "display_name": u.display_name, "role": u.role, "employee_id": u.employee_id} for u in rows],
    }


@router.put("/admin/users/{user_id}/role")
def set_role(user_id: str, body: RoleUpdate, p: Principal = Depends(require_roles("admin")), db: Session = Depends(get_db)) -> dict:
    u = db.get(User, user_id)
    if u is None or u.tenant_id != p.tenant_id:
        raise HTTPException(404, "User not found")
    if u.id == p.user_id:
        raise HTTPException(409, "Administrators cannot change their own role")
    old, u.role = u.role, body.role
    audit.record_principal(db, p, "role_changed", "user", u.id, detail={"from": old, "to": body.role})
    return {"user_id": u.id, "role": u.role}
