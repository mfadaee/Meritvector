"""Research Laboratory and measurement-definition endpoints.

Measurement definitions ("How was this assessed?") are readable by every signed-in user. Research runs are limited to
researchers, HR reviewers and administrators, require governance-approved assessment, and only ever return
aggregates or pseudonymised identifiers.
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from meritvector_analytics.measurement import find_metric, list_job_families, load_job_family, load_library, load_ontology
from meritvector_analytics.research import lab
from meritvector_api import audit
from meritvector_api.db import get_db
from meritvector_api.models import DatasetVersion, ModelRegistryEntry, ResearchRun
from meritvector_api.research_service import execute_run
from meritvector_api.security import Principal, current_principal, require_assessment_enabled
from meritvector_api.services import to_dict

router = APIRouter(tags=["research"])
RESEARCH_ROLES = ("researcher", "hr_reviewer", "admin")


def _research_role(p: Principal) -> None:
    if p.role not in RESEARCH_ROLES:
        raise HTTPException(403, "The Research Laboratory is available to researchers, HR reviewers and administrators")


# ------------------------------------------------------------------ definitions (all users)
@router.get("/measurement/ontology")
def ontology(p: Principal = Depends(current_principal)) -> dict:
    return load_ontology().model_dump()


@router.get("/measurement/job-families")
def job_families(p: Principal = Depends(current_principal)) -> list[dict]:
    return list_job_families()


@router.get("/measurement/job-families/{family_id}")
def job_family(family_id: str, p: Principal = Depends(current_principal)) -> dict:
    try:
        return load_job_family(family_id).model_dump()
    except KeyError as exc:
        raise HTTPException(404, "Unknown job family") from exc


@router.get("/measurement/metrics/{metric_id}")
def how_assessed(metric_id: str, family_id: str = "pmo", p: Principal = Depends(current_principal)) -> dict:
    """'How was this assessed?' — definition, data sources, assumptions and prohibited interpretations."""
    m = find_metric(metric_id, family_id)
    if m is None:
        raise HTTPException(404, "Unknown metric")
    construct = load_ontology().constructs.get(m.construct)
    return {
        **m.model_dump(),
        "construct_label": construct.label if construct else m.construct,
        "construct_definition": construct.definition if construct else None,
        "evidence_status": construct.evidence_status if construct else None,
    }


@router.get("/research/dags")
def dags(p: Principal = Depends(current_principal)) -> dict:
    """Causal diagrams used by the causal workstream (assumptions made explicit, readable by everyone)."""
    import yaml

    from meritvector_analytics.measurement import config_dir

    return yaml.safe_load((config_dir() / "research" / "dags.yaml").read_text())


@router.get("/research/public-data")
def public_data(p: Principal = Depends(current_principal)) -> dict:
    """Public real-world datasets: provenance, terms of use, checksum and whether they are available locally."""
    from meritvector_analytics.public_data import registry, sources
    from meritvector_analytics.public_data.studies import STUDIES

    reg = registry()
    return {
        "mirror": reg["mirror"],
        "sources": [{"id": k, **s.spec, "available": s.available} for k, s in sources().items()],
        "studies": [{"id": k, "title": t} for k, (t, _) in STUDIES.items()],
        "fetch_command": "python -m meritvector_api.cli fetch-public-data",
    }


@router.get("/research/library")
def library(p: Principal = Depends(current_principal)) -> dict:
    return load_library()


# ------------------------------------------------------------------ laboratory
@router.get("/research/overview")
def overview(p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _research_role(p)
    import yaml

    from meritvector_analytics.measurement import config_dir

    q = yaml.safe_load((config_dir() / "research" / "questions.yaml").read_text())
    h = yaml.safe_load((config_dir() / "research" / "hypotheses.yaml").read_text())
    datasets = db.scalars(
        select(DatasetVersion).where(DatasetVersion.tenant_id == p.tenant_id).order_by(DatasetVersion.created_at.desc())
    ).all()
    registry = db.scalars(
        select(ModelRegistryEntry)
        .where(ModelRegistryEntry.tenant_id == p.tenant_id)
        .order_by(ModelRegistryEntry.registered_at.desc())
        .limit(20)
    ).all()
    return {
        "workstreams": [{"id": k, "title": v[0]} for k, v in lab.WORKSTREAMS.items()],
        "questions": q["questions"],
        "hypotheses": h["hypotheses"],
        "alpha": h["alpha"],
        "datasets": [to_dict(d) for d in datasets],
        "model_registry": [to_dict(r) for r in registry],
        "status_legend": {
            "exploratory": "Computed, not validated — do not act on it",
            "confirmatory": "Pre-registered test on synthetic data — still not a real-world finding",
        },
    }


class RunIn(BaseModel):
    workstream: str
    params: dict[str, Any] = Field(default_factory=dict)


def _start(db: Session, p: Principal, workstream: str, params: dict[str, Any], reproduces: int | None = None) -> ResearchRun:
    if workstream not in lab.WORKSTREAMS:
        raise HTTPException(404, "Unknown workstream")
    allowed = {"level", "scenario", "study"}
    if set(params) - allowed:
        raise HTTPException(422, f"Unsupported parameters: {sorted(set(params) - allowed)}")
    run = ResearchRun(
        tenant_id=p.tenant_id,
        workstream=workstream,
        title=lab.WORKSTREAMS[workstream][0],
        params=params,
        status="queued",
        created_by=p.user_id,
        created_at=audit.now(),
        reproduces_run_id=reproduces,
    )
    db.add(run)
    db.flush()
    audit.record_principal(db, p, "research_run_started", "research_run", str(run.id), detail={"workstream": workstream})
    threading.Thread(target=execute_run, args=(run.id,), daemon=True).start()
    return run


@router.post("/research/runs")
def start_run(body: RunIn, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _research_role(p)
    return to_dict(_start(db, p, body.workstream, body.params))


@router.get("/research/runs")
def runs(workstream: str | None = None, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> list[dict]:
    _research_role(p)
    stmt = select(ResearchRun).where(ResearchRun.tenant_id == p.tenant_id)
    if workstream:
        stmt = stmt.where(ResearchRun.workstream == workstream)
    rows = db.scalars(stmt.order_by(ResearchRun.created_at.desc()).limit(100)).all()
    return [{k: v for k, v in to_dict(r).items() if k != "result"} for r in rows]


def _run(db: Session, p: Principal, run_id: int) -> ResearchRun:
    run = db.get(ResearchRun, run_id)
    if run is None or run.tenant_id != p.tenant_id:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/research/runs/{run_id}")
def get_run(run_id: int, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _research_role(p)
    return to_dict(_run(db, p, run_id))


@router.post("/research/runs/{run_id}/reproduce")
def reproduce(run_id: int, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _research_role(p)
    orig = _run(db, p, run_id)
    return to_dict(_start(db, p, orig.workstream, orig.params, reproduces=orig.id))


@router.get("/research/runs/{run_id}/report", response_class=PlainTextResponse)
def report(run_id: int, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> str:
    _research_role(p)
    run = _run(db, p, run_id)
    if run.status != "completed":
        raise HTTPException(409, f"Run is {run.status}")
    audit.record_principal(db, p, "research_report_exported", "research_run", str(run.id))
    return lab.report_markdown(
        {
            "title": run.title,
            "workstream": run.workstream,
            "status": run.evidence_status,
            "dataset_version": run.dataset_version,
            "code_version": run.code_version,
            "result_hash": run.result_hash,
            "result": run.result,
        }
    )
