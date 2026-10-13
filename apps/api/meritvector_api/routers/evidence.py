"""Evidence visibility and the correction (challenge) workflow."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meritvector_api import audit
from meritvector_api.db import get_db
from meritvector_api.models import Employee, EvidenceChallenge, EvidenceEventRow
from meritvector_api.security import Principal, can_review, current_principal
from meritvector_api.services import to_dict

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/me")
def my_evidence(
    category: str | None = None,
    data_category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    p: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Every record held about the caller — available regardless of whether assessment is enabled."""
    if not p.employee_id:
        raise HTTPException(403, "This account has no employee record")
    stmt = select(EvidenceEventRow).where(
        EvidenceEventRow.tenant_id == p.tenant_id, EvidenceEventRow.employee_id == p.employee_id
    )
    if category:
        stmt = stmt.where(EvidenceEventRow.category == category)
    if data_category:
        stmt = stmt.where(EvidenceEventRow.data_category == data_category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(EvidenceEventRow.occurred_at.desc()).offset(offset).limit(min(limit, 200))).all()
    cats = dict(
        db.execute(
            select(EvidenceEventRow.category, func.count())
            .where(EvidenceEventRow.tenant_id == p.tenant_id, EvidenceEventRow.employee_id == p.employee_id)
            .group_by(EvidenceEventRow.category)
        ).all()
    )
    return {"total": total, "items": [to_dict(r) for r in rows], "category_counts": cats}


class ChallengeIn(BaseModel):
    reason: str = Field(min_length=10, max_length=4000)
    proposed_correction: str | None = Field(default=None, max_length=4000)


@router.post("/{event_id}/challenge")
def challenge(event_id: str, body: ChallengeIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    ev = db.get(EvidenceEventRow, event_id)
    if ev is None or ev.tenant_id != p.tenant_id or ev.employee_id != p.employee_id:
        raise HTTPException(404, "Record not found")
    pending = db.scalar(select(func.count()).where(EvidenceChallenge.event_id == event_id, EvidenceChallenge.status == "pending"))
    if pending:
        raise HTTPException(409, "This record already has a pending challenge")
    c = EvidenceChallenge(
        tenant_id=p.tenant_id,
        event_id=event_id,
        employee_id=p.employee_id,
        reason=body.reason,
        proposed_correction=body.proposed_correction,
        previous_status=ev.validation_status,
        status="pending",
        created_at=audit.now(),
    )
    # Challenged records are excluded from analysis until a reviewer resolves the challenge.
    ev.validation_status = "disputed"
    db.add(c)
    db.flush()
    audit.record_principal(db, p, "evidence_challenged", "evidence_event", event_id, detail={"challenge_id": c.id})
    return to_dict(c)


@router.get("/challenges")
def challenges(status: str | None = None, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> list[dict]:
    if p.role == "admin":
        raise HTTPException(403, "Administrators do not review evidence challenges")
    stmt = select(EvidenceChallenge).where(EvidenceChallenge.tenant_id == p.tenant_id)
    if p.role == "hr_reviewer":
        pass
    elif p.role == "manager":
        team = [e.id for e in db.scalars(select(Employee).where(Employee.manager_id == p.employee_id))]
        stmt = stmt.where(EvidenceChallenge.employee_id.in_(team + [p.employee_id]))
    else:
        stmt = stmt.where(EvidenceChallenge.employee_id == p.employee_id)
    if status:
        stmt = stmt.where(EvidenceChallenge.status == status)
    rows = db.scalars(stmt.order_by(EvidenceChallenge.created_at.desc())).all()
    names = {e.id: e.display_name for e in db.scalars(select(Employee).where(Employee.id.in_({r.employee_id for r in rows})))}
    evs = {
        e.event_id: e
        for e in db.scalars(select(EvidenceEventRow).where(EvidenceEventRow.event_id.in_([r.event_id for r in rows])))
    }
    return [
        to_dict(r)
        | {
            "employee_name": names.get(r.employee_id),
            "event": {
                k: v
                for k, v in to_dict(evs[r.event_id]).items()
                if k in ("category", "occurred_at", "evidence_ref", "payload", "source_system")
            }
            if r.event_id in evs
            else None,
        }
        for r in rows
    ]


class ResolveIn(BaseModel):
    decision: Literal["upheld_retract", "upheld_corrected", "rejected"]
    note: str = Field(min_length=5, max_length=4000)


@router.post("/challenges/{challenge_id}/resolve")
def resolve(challenge_id: int, body: ResolveIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    c = db.get(EvidenceChallenge, challenge_id)
    if c is None or c.tenant_id != p.tenant_id:
        raise HTTPException(404, "Challenge not found")
    emp = db.get(Employee, c.employee_id)
    if not can_review(p, emp):
        raise HTTPException(403, "Only the employee's manager or an HR reviewer can resolve a challenge")
    if c.status != "pending":
        raise HTTPException(409, f"Challenge already {c.status}")
    ev = db.get(EvidenceEventRow, c.event_id)
    ev.validation_status = {"upheld_retract": "retracted", "upheld_corrected": "corrected", "rejected": c.previous_status}[
        body.decision
    ]
    c.status, c.resolution_note, c.resolved_by, c.resolved_at = body.decision, body.note, p.user_id, audit.now()
    audit.record_principal(
        db, p, "challenge_resolved", "evidence_challenge", str(c.id), detail={"decision": body.decision, "event_id": c.event_id}
    )
    return to_dict(c)
