"""Employee contribution detail, team insights and human review notes.

No endpoint returns a ranking, a single score, or a promotion/dismissal recommendation.
Lists are alphabetical.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meritvector_analytics.narrative import contribution_narrative
from meritvector_api import audit
from meritvector_api.db import get_db
from meritvector_api.models import Employee, EmployeeRunOutput, EvidenceEventRow, Project, ReviewNote
from meritvector_api.security import Principal, can_review, get_visible_employee, require_assessment_enabled
from meritvector_api.services import to_dict
from meritvector_api.training import latest_run

router = APIRouter(tags=["contribution"])


def visible_employees(db: Session, p: Principal) -> list[Employee]:
    stmt = select(Employee).where(Employee.tenant_id == p.tenant_id)
    if p.role == "hr_reviewer":
        pass
    elif p.role == "manager":
        stmt = stmt.where(Employee.manager_id == p.employee_id)
    elif p.employee_id:
        stmt = stmt.where(Employee.id == p.employee_id)
    else:
        return []
    return list(db.scalars(stmt.order_by(Employee.display_name)))


@router.get("/employees")
def employees(q: str = "", p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    if p.role == "admin":
        raise HTTPException(403, "Administrators do not have access to individual performance evidence")
    emps = [e for e in visible_employees(db, p) if q.lower() in e.display_name.lower() or q.lower() in e.id.lower()]
    run = latest_run(db, p.tenant_id)
    outs = {
        o.employee_id: o.payload
        for o in db.scalars(
            select(EmployeeRunOutput).where(
                EmployeeRunOutput.run_id == (run.id if run else ""), EmployeeRunOutput.employee_id.in_([e.id for e in emps])
            )
        )
    }
    items = []
    for e in emps:
        est = outs.get(e.id, {}).get("estimates", {}).get("schedule_variance_pct", {})
        items.append(
            {
                **to_dict(e),
                "milestones_evidenced": est.get("n", 0),
                "evidence_sufficient": est.get("conclusion") not in (None, "insufficient_evidence"),
            }
        )
    return {
        "items": items,
        "ordering": "alphabetical — MeritVector does not rank employees",
        "scope": {"hr_reviewer": "all employees", "manager": "direct reports"}.get(p.role, "self"),
    }


@router.get("/employees/{employee_id}/contribution")
def contribution(employee_id: str, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    emp = get_visible_employee(db, p, employee_id)
    run = latest_run(db, p.tenant_id)
    out = db.get(EmployeeRunOutput, (run.id, emp.id)) if run else None
    payload = out.payload if out else {}
    counts = dict(
        db.execute(
            select(EvidenceEventRow.category, func.count())
            .where(
                EvidenceEventRow.tenant_id == p.tenant_id,
                EvidenceEventRow.employee_id == emp.id,
                EvidenceEventRow.data_category == "assessment_evidence",
            )
            .group_by(EvidenceEventRow.category)
        ).all()
    )
    status_counts = dict(
        db.execute(
            select(EvidenceEventRow.validation_status, func.count())
            .where(
                EvidenceEventRow.tenant_id == p.tenant_id,
                EvidenceEventRow.employee_id == emp.id,
                EvidenceEventRow.data_category == "assessment_evidence",
            )
            .group_by(EvidenceEventRow.validation_status)
        ).all()
    )
    recent = db.scalars(
        select(EvidenceEventRow)
        .where(
            EvidenceEventRow.tenant_id == p.tenant_id,
            EvidenceEventRow.employee_id == emp.id,
            EvidenceEventRow.data_category == "assessment_evidence",
            EvidenceEventRow.category.in_(
                [
                    "milestone_achieved",
                    "risk_mitigated",
                    "blocker_resolved",
                    "dependency_resolved",
                    "document_reviewed",
                    "stakeholder_feedback",
                    "project_outcome",
                ]
            ),
        )
        .order_by(EvidenceEventRow.occurred_at.desc())
        .limit(25)
    ).all()
    projects = db.scalars(select(Project).where(Project.lead_employee_id == emp.id).order_by(Project.start_date)).all()
    notes = db.scalars(
        select(ReviewNote)
        .where(ReviewNote.employee_id == emp.id, ReviewNote.tenant_id == p.tenant_id)
        .order_by(ReviewNote.created_at.desc())
    ).all()
    manager = db.get(Employee, emp.manager_id)

    est = payload.get("estimates", {})
    missing = []
    sched = est.get("schedule_variance_pct", {})
    if not sched or sched.get("conclusion") == "insufficient_evidence":
        missing.append("Too few achieved milestones (or too wide an interval) for a context-adjusted delivery estimate.")
    if est.get("quality_score", {}).get("conclusion") == "insufficient_evidence":
        missing.append("Deliverable quality scores are missing for many reviews; quality estimate withheld.")
    if not counts.get("stakeholder_feedback"):
        missing.append("No stakeholder survey responses on record.")
    if payload.get("trend", {}).get("trend_status") == "insufficient_history":
        missing.append("Fewer than three half-years with enough evidence — change over time cannot be assessed.")
    missing += [f"{c['label']}: {c['opportunity_note']}" for c in payload.get("competencies", []) if c.get("opportunity_note")]

    audit.record_principal(db, p, "viewed_contribution", "employee", emp.id, detail={"run_id": run.id if run else None})
    return {
        "employee": to_dict(emp) | {"manager_name": manager.display_name if manager else emp.manager_id},
        "run_id": run.id if run else None,
        "observed_evidence": {
            "counts_by_category": counts,
            "validation_status": status_counts,
            "recent": [to_dict(r) for r in recent],
        },
        "raw_metrics": payload.get("raw_metrics", {}),
        "adjusted": est,
        "competencies": payload.get("competencies", []),
        "trend": payload.get("trend", {}),
        "trend_series": payload.get("trend_series", []),
        "bootstrap_ci": payload.get("bootstrap_ci"),
        "projects": [to_dict(x) for x in projects],
        "missing_information": missing,
        "narrative": contribution_narrative(sched, payload.get("raw_metrics", {})),
        "review_notes": [to_dict(n) for n in notes],
        "can_add_review": can_review(p, emp),
        "interpretation": {
            "adjusted_estimate": "Difference between this person's milestone schedule outcomes and what operating conditions "
            "predict, in percentage points (positive = less slippage than expected), shrunk towards zero "
            "when evidence is limited.",
            "not_causal": "An adjusted association, not proof of individual causal impact. Unmeasured context remains.",
            "human_review": "Qualified human review is required before any employment-related use.",
        },
    }


class ReviewIn(BaseModel):
    agreement: Literal["agrees_with_evidence", "partially_agrees", "disagrees_with_evidence", "not_assessed"]
    judgement: str = Field(min_length=10, max_length=8000)
    disagreement_reasons: str | None = Field(default=None, max_length=8000)
    context_notes: str | None = Field(default=None, max_length=8000)


@router.get("/employees/{employee_id}/reviews")
def reviews(employee_id: str, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> list[dict]:
    emp = get_visible_employee(db, p, employee_id)
    return [
        to_dict(n) for n in db.scalars(select(ReviewNote).where(ReviewNote.employee_id == emp.id).order_by(ReviewNote.created_at.desc()))
    ]


@router.post("/employees/{employee_id}/reviews")
def add_review(employee_id: str, body: ReviewIn, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    emp = get_visible_employee(db, p, employee_id)
    if not can_review(p, emp):
        raise HTTPException(403, "Only the employee's manager or an HR reviewer can record a review")
    if body.agreement in ("disagrees_with_evidence", "partially_agrees") and not body.disagreement_reasons:
        raise HTTPException(422, "Please record your reasons for disagreeing with the evidence")
    run = latest_run(db, p.tenant_id)
    n = ReviewNote(
        tenant_id=p.tenant_id,
        employee_id=emp.id,
        author_user_id=p.user_id,
        author_role=p.role,
        run_id=run.id if run else None,
        agreement=body.agreement,
        judgement=body.judgement,
        disagreement_reasons=body.disagreement_reasons,
        context_notes=body.context_notes,
        created_at=audit.now(),
    )
    db.add(n)
    db.flush()
    audit.record_principal(db, p, "review_recorded", "employee", emp.id, detail={"review_id": n.id, "agreement": body.agreement})
    return to_dict(n)


@router.get("/team/insights")
def team_insights(p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    """Aggregated development insights for a manager's team (or the organisation for HR)."""
    if p.role not in ("manager", "hr_reviewer"):
        raise HTTPException(403, "Requires role: manager, hr_reviewer")
    emps = visible_employees(db, p)
    run = latest_run(db, p.tenant_id)
    outs = db.scalars(
        select(EmployeeRunOutput).where(
            EmployeeRunOutput.run_id == (run.id if run else ""), EmployeeRunOutput.employee_id.in_([e.id for e in emps])
        )
    ).all()
    comp: dict[str, Counter] = {}
    concl: Counter = Counter()
    trend: Counter = Counter()
    for o in outs:
        for c in o.payload.get("competencies", []):
            comp.setdefault(c["label"], Counter())[c["status"]] += 1
        concl[o.payload.get("estimates", {}).get("schedule_variance_pct", {}).get("conclusion", "no_estimate")] += 1
        trend[o.payload.get("trend", {}).get("trend_status", "insufficient_history")] += 1
    return {
        "team_size": len(emps),
        "run_id": run.id if run else None,
        "competency_status": {k: dict(v) for k, v in comp.items()},
        "evidence_conclusions": dict(concl),
        "trend_status": dict(trend),
        "note": "Counts only — use the contribution pages for individual context, not for comparison.",
    }
