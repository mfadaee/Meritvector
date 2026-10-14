"""Deep Work Intelligence: evidence chains, manual attribution, responsibility scope and knowledge retrieval.

* Evidence chains are readable by anyone who can see the project. Inferred links carry the rule that produced them;
  manual links carry the person who recorded them.
* Attributions are a person's own account of their contribution. They are visible to the author, the author's
  manager and HR reviewers, can be confirmed or disputed by those reviewers, and are never used by the models.
* Knowledge retrieval searches only records the caller can already open and returns links, not generated answers.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from meritvector_analytics.evidence_chains import build_chains
from meritvector_analytics.responsibility import labelled_dimensions, responsibility_scope
from meritvector_api import audit
from meritvector_api.db import get_db
from meritvector_api.models import (
    Attribution,
    Dependency,
    Employee,
    EvidenceLink,
    MeetingInsight,
    Milestone,
    Project,
    Risk,
    User,
)
from meritvector_api.routers.workspace import my_meetings
from meritvector_api.security import (
    Principal,
    can_review,
    current_principal,
    get_visible_employee,
    require_assessment_enabled,
)
from meritvector_api.services import to_dict
from meritvector_coordinator import Document, search

router = APIRouter(tags=["deep-work"])

NodeType = Literal["risk", "mitigation", "milestone", "dependency"]
TargetType = Literal["risk", "mitigation", "milestone", "dependency", "project"]


def _project(db: Session, p: Principal, project_id: str) -> Project:
    pr = db.get(Project, project_id)
    if pr is None or pr.tenant_id != p.tenant_id:
        raise HTTPException(404, "Project not found")
    return pr


def _node(db: Session, p: Principal, kind: str, node_id: str) -> tuple[str, str | None]:
    """Resolve a node to (project_id, owner_employee_id); 404 if it does not exist in the caller's tenant."""
    if kind == "project":
        pr = _project(db, p, node_id)
        return pr.id, pr.lead_employee_id
    model = {"risk": Risk, "mitigation": Risk, "milestone": Milestone, "dependency": Dependency}[kind]
    obj = db.get(model, node_id)
    if obj is None or obj.tenant_id != p.tenant_id:
        raise HTTPException(404, f"Unknown {kind}")
    if kind == "mitigation" and obj.mitigated_on is None:
        raise HTTPException(422, "This risk has no recorded mitigation")
    return obj.project_id, obj.owner_employee_id


def _visible_attribution(db: Session, p: Principal, a: Attribution, cache: dict[str, Employee | None]) -> bool:
    if a.employee_id == p.employee_id:
        return True
    if a.employee_id not in cache:
        cache[a.employee_id] = db.get(Employee, a.employee_id)
    emp = cache[a.employee_id]
    return emp is not None and can_review(p, emp)


def _names(db: Session, tenant_id: str) -> dict[str, str]:
    return {e.id: e.display_name for e in db.scalars(select(Employee).where(Employee.tenant_id == tenant_id))}


# ------------------------------------------------------------------ evidence chains
@router.get("/portfolio/projects/{project_id}/evidence-chains")
def evidence_chains(project_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    pr = _project(db, p, project_id)
    risks = [to_dict(r) for r in db.scalars(select(Risk).where(Risk.project_id == pr.id).order_by(Risk.identified_on))]
    deps = [to_dict(d) for d in db.scalars(select(Dependency).where(Dependency.project_id == pr.id).order_by(Dependency.raised_on))]
    ms = [to_dict(m) for m in db.scalars(select(Milestone).where(Milestone.project_id == pr.id).order_by(Milestone.planned_date))]
    users = {u.id: u.display_name for u in db.scalars(select(User).where(User.tenant_id == p.tenant_id))}
    links = []
    for link in db.scalars(select(EvidenceLink).where(EvidenceLink.tenant_id == p.tenant_id, EvidenceLink.project_id == pr.id)):
        d = to_dict(link)
        d["created_by_name"] = users.get(link.created_by, link.created_by)
        links.append(d)
    names = _names(db, p.tenant_id)
    cache: dict[str, Employee | None] = {}
    attrs = []
    for a in db.scalars(select(Attribution).where(Attribution.tenant_id == p.tenant_id, Attribution.project_id == pr.id)):
        if _visible_attribution(db, p, a, cache):
            d = to_dict(a)
            d["employee_name"] = names.get(a.employee_id)
            attrs.append(d)
    out = build_chains(risks, deps, ms, links, attrs)
    for c in out["chains"]:
        for n in c["nodes"]:
            n["owner_name"] = names.get(n.get("owner_employee_id") or "")
    out["project"] = {"id": pr.id, "name": pr.name, "lead_employee_id": pr.lead_employee_id}
    out["attribution_visibility"] = "You see your own attributions, plus those you are entitled to review (manager / HR)."
    return out


@router.get("/portfolio/projects/{project_id}/dimensions")
def project_dimensions(project_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    pr = _project(db, p, project_id)
    record = {**to_dict(pr), **(pr.dimensions or {})}
    risks_owned = len(db.scalars(select(Risk.id).where(Risk.project_id == pr.id, Risk.owner_employee_id == pr.lead_employee_id)).all())
    record["risks_owned"] = risks_owned
    return {**labelled_dimensions(record), "note": "Operating conditions and responsibility scope are context, never credit."}


class LinkIn(BaseModel):
    project_id: str
    from_type: NodeType
    from_id: str = Field(min_length=1, max_length=96)
    to_type: NodeType
    to_id: str = Field(min_length=1, max_length=96)
    relation: Literal["mitigated_by", "protects", "unblocks", "precedes", "contributed_to"]
    note: str | None = Field(default=None, max_length=1000)


@router.post("/evidence-links")
def add_link(body: LinkIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    pr = _project(db, p, body.project_id)
    a_proj, a_owner = _node(db, p, body.from_type, body.from_id)
    b_proj, b_owner = _node(db, p, body.to_type, body.to_id)
    if a_proj != pr.id or b_proj != pr.id:
        raise HTTPException(422, "Both records must belong to this project")
    if (body.from_type, body.from_id) == (body.to_type, body.to_id):
        raise HTTPException(422, "A record cannot be linked to itself")
    allowed = p.role == "hr_reviewer" or (p.employee_id and p.employee_id in {pr.lead_employee_id, a_owner, b_owner})
    if not allowed:
        raise HTTPException(403, "Links can be recorded by the project lead, the owners of the linked records, or HR reviewers")
    link = EvidenceLink(tenant_id=p.tenant_id, created_by=p.user_id, created_at=audit.now(), **body.model_dump())
    db.add(link)
    db.flush()
    audit.record_principal(db, p, "evidence_link_recorded", "project", pr.id, detail={"link_id": link.id, "relation": body.relation})
    return to_dict(link)


# ------------------------------------------------------------------ attribution
class AttributionIn(BaseModel):
    target_type: TargetType
    target_id: str = Field(min_length=1, max_length=96)
    role: Literal["led", "contributed", "supported", "advised"]
    description: str = Field(min_length=10, max_length=2000)


@router.post("/attributions")
def add_attribution(body: AttributionIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    if not p.employee_id:
        raise HTTPException(403, "Only people with an employee record can describe their own contribution")
    project_id, _ = _node(db, p, body.target_type, body.target_id)
    a = Attribution(tenant_id=p.tenant_id, employee_id=p.employee_id, project_id=project_id, created_at=audit.now(), **body.model_dump())
    db.add(a)
    db.flush()
    audit.record_principal(db, p, "attribution_claimed", body.target_type, body.target_id, detail={"attribution_id": a.id})
    return to_dict(a)


@router.get("/attributions/me")
def my_attributions(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> list[dict]:
    if not p.employee_id:
        return []
    rows = db.scalars(
        select(Attribution)
        .where(Attribution.tenant_id == p.tenant_id, Attribution.employee_id == p.employee_id)
        .order_by(Attribution.created_at.desc())
    )
    return [to_dict(a) for a in rows]


@router.get("/attributions/review")
def attributions_to_review(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> list[dict]:
    if p.role not in ("manager", "hr_reviewer"):
        raise HTTPException(403, "Attribution review is for managers (direct reports) and HR reviewers")
    names = _names(db, p.tenant_id)
    cache: dict[str, Employee | None] = {}
    rows = db.scalars(select(Attribution).where(Attribution.tenant_id == p.tenant_id).order_by(Attribution.created_at.desc()).limit(500))
    out = []
    for a in rows:
        if a.employee_id != p.employee_id and _visible_attribution(db, p, a, cache):
            d = to_dict(a)
            d["employee_name"] = names.get(a.employee_id)
            out.append(d)
    return out


class AttributionReview(BaseModel):
    decision: Literal["confirmed", "disputed"]
    note: str | None = Field(default=None, max_length=2000)


@router.post("/attributions/{attribution_id}/review")
def review_attribution(
    attribution_id: int, body: AttributionReview, p: Principal = Depends(current_principal), db: Session = Depends(get_db)
) -> dict:
    a = db.get(Attribution, attribution_id)
    if a is None or a.tenant_id != p.tenant_id:
        raise HTTPException(404, "Attribution not found")
    emp = db.get(Employee, a.employee_id)
    if emp is None or not can_review(p, emp):
        raise HTTPException(403, "Only the person's manager or an HR reviewer can review this attribution")
    if body.decision == "disputed" and not body.note:
        raise HTTPException(422, "Please explain why the attribution is disputed — the person will see your note")
    a.status, a.review_note, a.reviewed_by, a.reviewed_at = body.decision, body.note, p.user_id, audit.now()
    audit.record_principal(db, p, "attribution_reviewed", "attribution", str(a.id), detail={"decision": body.decision})
    return to_dict(a)


# ------------------------------------------------------------------ responsibility scope
@router.get("/employees/{employee_id}/responsibility-scope")
def employee_scope(employee_id: str, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    emp = get_visible_employee(db, p, employee_id)
    projects = db.scalars(select(Project).where(Project.tenant_id == p.tenant_id, Project.lead_employee_id == emp.id)).all()
    records = [{**to_dict(pr), **(pr.dimensions or {})} for pr in projects]
    risks_owned = len(db.scalars(select(Risk.id).where(Risk.tenant_id == p.tenant_id, Risk.owner_employee_id == emp.id)).all())
    return {"employee_id": emp.id, **responsibility_scope(records, risks_owned)}


# ------------------------------------------------------------------ knowledge retrieval
def _documents(db: Session, p: Principal) -> list[Document]:
    docs: list[Document] = []
    if p.employee_id:
        meetings = my_meetings(db, p)
        ins = {i.meeting_id: i for i in db.scalars(select(MeetingInsight).where(MeetingInsight.meeting_id.in_([m.id for m in meetings])))}
        for m in meetings:
            i = ins.get(m.id)
            when = m.scheduled_at.date().isoformat()
            docs.append(
                Document(
                    m.id, "meeting", m.title, " ".join(filter(None, [i.summary if i else None, m.transcript])), f"/meetings/{m.id}", when
                )
            )
            for k, d in enumerate((i.decisions if i else None) or []):
                docs.append(Document(f"{m.id}#d{k}", "decision", d["text"], d.get("source_line") or d["text"], f"/meetings/{m.id}", when))
    for pr in db.scalars(select(Project).where(Project.tenant_id == p.tenant_id)):
        text = f"{pr.kind} project in {pr.business_unit}; {pr.environment} environment; status {pr.status}"
        docs.append(Document(pr.id, "project", pr.name, text, f"/projects/{pr.id}", pr.start_date.isoformat()))
    for r in db.scalars(select(Risk).where(Risk.tenant_id == p.tenant_id)):
        docs.append(
            Document(
                r.id, "risk", r.title, f"{r.severity} {r.kind} risk, {r.status}", f"/projects/{r.project_id}", r.identified_on.isoformat()
            )
        )
    for d in db.scalars(select(Dependency).where(Dependency.tenant_id == p.tenant_id)):
        docs.append(
            Document(d.id, "dependency", f"Depends on {d.depends_on}", d.description, f"/projects/{d.project_id}", d.raised_on.isoformat())
        )
    return docs


@router.get("/coordinator/search")
def knowledge_search(q: str, limit: int = 10, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    q = q.strip()[:200]
    if len(q) < 2:
        raise HTTPException(422, "Enter at least two characters")
    docs = _documents(db, p)
    return {
        "query": q,
        "searched": len(docs),
        "results": search(docs, q, k=max(1, min(limit, 25))),
        "scope": "Meetings you attended (summaries, decisions, transcripts) and the organisation's project, risk and "
        "dependency registers. Results link to source records; nothing is generated.",
    }
