"""Contextual analysis, flagship experiment, model validation and model runs."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from meritvector_api import audit
from meritvector_api.db import get_db, session
from meritvector_api.models import Employee, EmployeeRunOutput, ModelRun
from meritvector_api.routers.employees import visible_employees
from meritvector_api.security import Principal, require_assessment_enabled
from meritvector_api.training import latest_run
from meritvector_api.workflows import run_job

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _run(db: Session, p: Principal, run_id: str | None = None) -> ModelRun:
    run = db.get(ModelRun, run_id) if run_id else latest_run(db, p.tenant_id)
    if run is None or run.tenant_id != p.tenant_id:
        raise HTTPException(404, "No model run available yet — run model training first")
    return run


def _roles(p: Principal, *roles: str) -> None:
    if p.role not in roles:
        raise HTTPException(403, f"Requires role: {', '.join(roles)}")


@router.get("/context")
def context(p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _roles(p, "manager", "hr_reviewer")
    run = _run(db, p)
    emps = {e.id: e for e in visible_employees(db, p)}
    outs = db.scalars(
        select(EmployeeRunOutput).where(EmployeeRunOutput.run_id == run.id, EmployeeRunOutput.employee_id.in_(list(emps)))
    ).all()
    points = []
    for o in outs:
        s = o.payload.get("estimates", {}).get("schedule_variance_pct")
        if not s:
            continue
        points.append(
            {
                "employee_id": o.employee_id,
                "job_family": emps[o.employee_id].job_family,
                "raw_estimate": s.get("raw_estimate"),
                "adjusted_estimate": s.get("adjusted_estimate"),
                "ci_low": s.get("ci_low"),
                "ci_high": s.get("ci_high"),
                "n": s.get("n"),
                "context_expected": s.get("context_expected"),
                "conclusion": s.get("conclusion"),
            }
        )
    points.sort(key=lambda x: x["employee_id"])  # stable, non-ranked order
    cm = run.metrics.get("context_models", {})
    return {
        "run_id": run.id,
        "models": cm,
        "points": points,
        "scope": "direct reports" if p.role == "manager" else "all employees",
        "sensitivity": run.metrics.get("validation", {}).get("sensitivity"),
        "label_audit": run.metrics.get("label_audit"),
        "explanation": "Raw estimate: the person's mean schedule variance relative to the organisation. Adjusted estimate: "
        "mixed-model employee effect after accounting for complexity, dependencies, resourcing, scope "
        "changes, team size, environment, maturity, job family and time. Positive = less slippage.",
    }


@router.get("/experiment")
def experiment(p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _roles(p, "manager", "hr_reviewer")
    run = _run(db, p)
    exp = dict(run.experiment)
    # Identities are pseudonymised for anyone who is not authorised to view both people.
    ids = exp.get("employees", {})
    visible = {e.id for e in visible_employees(db, p)}
    if not all(i in visible for i in ids.values()):
        exp["employees"] = {k: f"Employee {k}" for k in ids}
        exp["display_names"] = {k: f"Employee {k} (pseudonymised)" for k in ids}
        exp["pseudonymised"] = True
    audit.record_principal(db, p, "viewed_experiment", "model_run", run.id)
    return {"run_id": run.id, **exp}


@router.get("/validation")
def validation(p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _roles(p, "manager", "hr_reviewer", "admin")
    run = _run(db, p)
    m = run.metrics
    return {
        "run_id": run.id,
        "created_at": run.created_at,
        "data_hash": run.data_hash,
        "config": run.config,
        "validation": m.get("validation"),
        "counts": m.get("counts"),
        "conclusion_counts": m.get("conclusion_counts"),
        "trend_counts": m.get("trend_counts"),
        "label_audit": m.get("label_audit"),
        "variance_components": {k: v.get("variance_components") for k, v in m.get("context_models", {}).items()},
        "diagnostics": {k: v.get("diagnostics") for k, v in m.get("context_models", {}).items()},
        "fairness": run.fairness if p.role in ("hr_reviewer", "admin") else "restricted to HR reviewers and administrators",
        "synthetic_evaluation": run.synthetic_evaluation,
        "model_card": run.model_card,
    }


@router.get("/runs")
def runs(p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> list[dict]:
    _roles(p, "manager", "hr_reviewer", "admin")
    rows = db.scalars(select(ModelRun).where(ModelRun.tenant_id == p.tenant_id).order_by(ModelRun.created_at.desc())).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "status": r.status,
            "data_hash": r.data_hash[:16],
            "artifact_path": r.artifact_path,
            "conclusion_counts": r.metrics.get("conclusion_counts"),
            "best_model": r.metrics.get("validation", {}).get("out_of_time", {}).get("best_by_mae"),
        }
        for r in rows
    ]


def _train_bg() -> None:
    with session() as db:
        run_job(db, "retrain_models", trigger="manual")


@router.post("/train")
def train(bg: BackgroundTasks, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    _roles(p, "hr_reviewer", "admin")
    audit.record_principal(db, p, "training_requested", "model_run")
    bg.add_task(_train_bg)
    return {"queued": "retrain_models", "note": "Training runs in the background; refresh Model Validation in ~1 minute."}


@router.get("/employees/{employee_id}/name")
def name(employee_id: str, p: Principal = Depends(require_assessment_enabled), db: Session = Depends(get_db)) -> dict:
    e = db.get(Employee, employee_id)
    if e is None or e.tenant_id != p.tenant_id or e.id not in {x.id for x in visible_employees(db, p)}:
        raise HTTPException(404, "Not found")
    return {"employee_id": e.id, "display_name": e.display_name}
