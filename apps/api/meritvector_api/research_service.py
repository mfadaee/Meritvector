"""Build research datasets from the database and execute/persist research runs."""

from __future__ import annotations

import logging
import traceback
import warnings
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from meritvector_analytics.research import ResearchData, lab
from meritvector_api.audit import now
from meritvector_api.db import session
from meritvector_api.models import (
    DatasetVersion,
    Dependency,
    Milestone,
    ModelRegistryEntry,
    Project,
    ResearchRun,
    Risk,
    Tenant,
)
from meritvector_api.services import to_dict
from meritvector_api.training import load_frames

log = logging.getLogger(__name__)


def _df(db: Session, model, tenant_id: str) -> pd.DataFrame:
    rows = [to_dict(o) for o in db.scalars(select(model).where(model.tenant_id == tenant_id))]
    return pd.DataFrame(rows, columns=[c.name for c in model.__table__.columns])


def research_data(db: Session, tenant_id: str) -> ResearchData:
    t = db.get(Tenant, tenant_id)
    f = load_frames(db, tenant_id)
    projects = _df(db, Project, tenant_id).rename(columns={"id": "project_id"})
    dims = pd.DataFrame([d or {} for d in projects.pop("dimensions")], index=projects.index)
    projects = pd.concat([projects, dims], axis=1)
    milestones = _df(db, Milestone, tenant_id).rename(columns={"id": "milestone_id"})
    risks = _df(db, Risk, tenant_id).rename(columns={"id": "risk_id"})
    deps = _df(db, Dependency, tenant_id).rename(columns={"id": "dependency_id"})
    rd = ResearchData(
        events=f["events"],
        employees=f["employees"],
        projects=projects,
        milestones=milestones,
        risks=risks,
        dependencies=deps,
        ratings=f["ratings"],
        as_of=str(t.as_of),
        seed=0,
        meta={"source": "database"},
    )
    if db.get(DatasetVersion, rd.dataset_version) is None:
        db.add(
            DatasetVersion(
                id=rd.dataset_version,
                tenant_id=tenant_id,
                created_at=now(),
                description="Snapshot of validated evidence and registers used by research runs",
                counts={"events": int(len(rd.events)), "projects": int(len(projects)), "employees": int(len(rd.employees))},
            )
        )
        db.commit()
    return rd


def execute_run(run_id: int) -> None:
    """Execute a queued research run (called in a background thread)."""
    with session() as db:
        run = db.get(ResearchRun, run_id)
        run.status = "running"
        db.commit()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                rd = research_data(db, run.tenant_id)
                rec = lab.run(rd, run.workstream, run.params)
            run.status = "completed"
            run.result = rec["result"]
            run.result_hash = rec["result_hash"]
            run.dataset_version = rec["dataset_version"]
            run.code_version = rec["code_version"]
            run.evidence_status = rec["status"]
            run.duration_s = rec["duration_s"]
            if run.reproduces_run_id:
                orig = db.get(ResearchRun, run.reproduces_run_id)
                run.reproduced_identically = bool(orig and orig.result_hash == run.result_hash)
            if run.workstream == "classification":
                _register_classifier(db, run, rec)
        except Exception as exc:  # noqa: BLE001 - failures are recorded on the run
            db.rollback()
            run = db.get(ResearchRun, run_id)
            run.status, run.error = "failed", f"{exc}\n{traceback.format_exc()[-1500:]}"
            log.exception("research run %s failed", run_id)
        db.commit()


def _register_classifier(db: Session, run: ResearchRun, rec: dict[str, Any]) -> None:
    from meritvector_analytics.research.registry import MILESTONE_RISK_SPEC, ModelSpec

    best = next(m for m in rec["result"]["models"] if m["model"] == rec["result"]["best_by_pr_auc"])
    spec = ModelSpec(version=f"run-{run.id}", **MILESTONE_RISK_SPEC)
    db.add(
        ModelRegistryEntry(
            tenant_id=run.tenant_id,
            name=spec.name,
            version=spec.version,
            spec=spec.model_dump(),
            metrics={k: best[k] for k in ("model", "pr_auc", "roc_auc", "precision", "recall", "f1", "brier")},
            dataset_version=run.dataset_version,
            status="registered",
            registered_at=now(),
        )
    )


def register_context_model(db: Session, tenant_id: str, run_id: str, metrics: dict[str, Any]) -> None:
    from meritvector_analytics.research.registry import CONTEXT_MODEL_SPEC, ModelSpec

    spec = ModelSpec(version=run_id, **CONTEXT_MODEL_SPEC)
    oot = metrics.get("validation", {}).get("out_of_time", {}).get("models", {}).get("context_plus_employee_mixed", {})
    db.add(
        ModelRegistryEntry(
            tenant_id=tenant_id,
            name=spec.name,
            version=spec.version,
            spec=spec.model_dump(),
            metrics={"oot_mae": oot.get("mae"), "oot_r2": oot.get("r2"), "conclusion_counts": metrics.get("conclusion_counts")},
            dataset_version=None,
            status="registered",
            registered_at=now(),
        )
    )
