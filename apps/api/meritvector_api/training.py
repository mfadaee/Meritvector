"""Train the analytics pipeline from the database and persist a versioned model run."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from meritvector_analytics.evaluation import recovery_report
from meritvector_analytics.pipeline import run_pipeline, save_artifacts
from meritvector_api.audit import now
from meritvector_api.models import (
    Employee,
    EmployeeRunOutput,
    EvidenceEventRow,
    ManagerRating,
    ModelRun,
    Promotion,
    ProtectedAttribute,
    Tenant,
)
from meritvector_api.settings import get_settings

log = logging.getLogger(__name__)


def _rows(db: Session, model, tenant_id: str) -> pd.DataFrame:
    objs = db.scalars(select(model).where(model.tenant_id == tenant_id)).all()
    cols = [c.name for c in model.__table__.columns]
    return pd.DataFrame([{c: getattr(o, c) for c in cols} for o in objs], columns=cols)


def _json(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_json(x) for x in v]
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def load_frames(db: Session, tenant_id: str) -> dict[str, pd.DataFrame]:
    events = _rows(db, EvidenceEventRow, tenant_id)
    employees = _rows(db, Employee, tenant_id).rename(columns={"id": "employee_id"})
    ratings = _rows(db, ManagerRating, tenant_id).rename(columns={"rating": "manager_rating"})
    promos = _rows(db, Promotion, tenant_id)
    return {"events": events, "employees": employees, "ratings": ratings, "promotions": promos}


def train_tenant(db: Session, tenant_id: str, n_boot: int | None = None) -> ModelRun:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError(f"unknown tenant {tenant_id}")
    if not tenant.assessment_enabled:
        raise PermissionError("Assessment is not enabled for this tenant; training is blocked pending governance approval.")
    s = get_settings()
    f = load_frames(db, tenant_id)
    # Protected attributes are loaded only for the aggregated fairness audit inside the pipeline.
    protected = _rows(db, ProtectedAttribute, tenant_id)
    result = run_pipeline(
        f["events"],
        f["employees"],
        str(tenant.as_of),
        manager_ratings=f["ratings"],
        promotions=f["promotions"],
        protected_attributes=protected,
        n_boot=n_boot or s.bootstrap_n_boot,
    )
    out_dir = save_artifacts(result, s.artifact_dir / tenant_id)

    synthetic_eval = None
    gt_path = Path(s.data_dir) / tenant_id / "hidden" / "ground_truth.csv"
    if tenant.is_synthetic and gt_path.exists():
        # Evaluation harness only: hidden parameters are compared with outputs *after* training.
        synthetic_eval = _json(recovery_report(result, pd.read_csv(gt_path), f["ratings"]))
        (out_dir / "synthetic_evaluation.json").write_text(json.dumps(synthetic_eval, indent=2))

    portfolio = {
        "delivery_trend": _json(result.portfolio_trend.to_dict("records")),
        "risk_trends": _json(result.risk_trends.to_dict("records")),
    }
    run = ModelRun(
        id=result.version,
        tenant_id=tenant_id,
        created_at=now(),
        status="completed",
        data_hash=result.data_hash,
        config=_json(result.config),
        metrics=_json(result.metrics),
        experiment=_json(result.experiment),
        fairness=_json(result.fairness),
        portfolio=portfolio,
        synthetic_evaluation=synthetic_eval,
        model_card=result.model_card,
        artifact_path=str(out_dir),
    )
    db.add(run)
    db.flush()

    est = result.estimates
    metrics = result.employee_metrics.set_index("employee_id")
    trend = result.trend_summary.set_index("employee_id")
    series = result.trend_series
    comp = result.competencies
    boot = result.validation["_bootstrap_table"].set_index("employee_id")
    db.execute(delete(EmployeeRunOutput).where(EmployeeRunOutput.run_id == run.id))
    rows = []
    for emp_id in f["employees"]["employee_id"]:
        e = est[est["employee_id"] == emp_id]
        payload = {
            "estimates": {
                r["outcome"]: _json(
                    {
                        k: r[k]
                        for k in (
                            "adjusted_estimate",
                            "adjusted_se",
                            "ci_low",
                            "ci_high",
                            "n",
                            "conclusion",
                            "raw_estimate",
                            "raw_mean",
                            "raw_se",
                            "residual_estimate",
                            "context_expected",
                        )
                    }
                )
                for r in e.to_dict("records")
            },
            "raw_metrics": _json(metrics.loc[emp_id].to_dict()) if emp_id in metrics.index else {},
            "trend": _json(trend.loc[emp_id].to_dict()) if emp_id in trend.index else {"trend_status": "insufficient_history"},
            "trend_series": _json(series[series["employee_id"] == emp_id].drop(columns="employee_id").to_dict("records")),
            "competencies": _json(comp[comp["employee_id"] == emp_id].drop(columns="employee_id").to_dict("records")),
            "bootstrap_ci": _json(boot.loc[emp_id].to_dict()) if emp_id in boot.index else None,
        }
        rows.append(EmployeeRunOutput(run_id=run.id, employee_id=emp_id, tenant_id=tenant_id, payload=payload))
    db.add_all(rows)
    db.commit()
    log.info("model run %s saved to %s", run.id, out_dir)
    return run


def latest_run(db: Session, tenant_id: str) -> ModelRun | None:
    return db.scalars(
        select(ModelRun)
        .where(ModelRun.tenant_id == tenant_id, ModelRun.status == "completed")
        .order_by(ModelRun.created_at.desc())
    ).first()
