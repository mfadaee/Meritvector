"""End-to-end analytics pipeline: events -> features -> layers A–E -> versioned artifacts.

The pipeline is pure Python with no database or LLM dependency, so it can be run and
tested independently of the application.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from meritvector_analytics import __version__
from meritvector_analytics.competency import competency_evidence, load_framework
from meritvector_analytics.contextual import OUTCOMES, ContextResult, run_contextual
from meritvector_analytics.descriptive import employee_metrics, portfolio_trend, risk_trends
from meritvector_analytics.experiment import run_experiment
from meritvector_analytics.features import FeatureSet, build_features, employee_activity_summary
from meritvector_analytics.longitudinal import period_series, quarterly_series, sustained_quality, trends
from meritvector_analytics.modelcard import render_model_card
from meritvector_analytics.validation import fairness_audit, label_audit, run_validation


@dataclass
class PipelineResult:
    version: str
    created_at: str
    data_hash: str
    config: dict[str, Any]
    features: FeatureSet
    employee_metrics: pd.DataFrame
    portfolio_trend: pd.DataFrame
    risk_trends: pd.DataFrame
    context: dict[str, ContextResult]
    estimates: pd.DataFrame
    trend_summary: pd.DataFrame
    trend_series: pd.DataFrame
    competencies: pd.DataFrame
    validation: dict[str, Any]
    experiment: dict[str, Any]
    label_audit: dict[str, Any] | None
    fairness: dict[str, Any] | None
    model_card: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def data_fingerprint(events: pd.DataFrame) -> str:
    h = hashlib.sha256()
    for eid, status in sorted(zip(events["event_id"], events["validation_status"], strict=True)):
        h.update(f"{eid}:{status};".encode())
    return h.hexdigest()


def _clean(o: Any) -> Any:
    """JSON-safe conversion (NaN -> None, numpy scalars -> Python)."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list | tuple):
        return [_clean(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


def run_pipeline(
    events: pd.DataFrame,
    employees: pd.DataFrame,
    as_of: str,
    *,
    manager_ratings: pd.DataFrame | None = None,
    promotions: pd.DataFrame | None = None,
    protected_attributes: pd.DataFrame | None = None,
    n_boot: int = 200,
    framework_path: str | None = None,
) -> PipelineResult:
    created = datetime.now(UTC)
    fingerprint = data_fingerprint(events)
    version = f"mv-{created:%Y%m%d%H%M%S}-{fingerprint[:8]}"
    fs = build_features(events, employees, as_of)
    m = fs.milestones

    desc = employee_metrics(fs)
    ctx = {o: run_contextual(m, o) for o in OUTCOMES}

    # Assemble per-employee estimates (long format: one row per employee x outcome).
    parts = []
    for o, c in ctx.items():
        e = c.mixed_estimates.merge(c.raw[["employee_id", "raw_estimate", "raw_se", "raw_mean"]], on="employee_id", how="left")
        e = e.merge(c.residual_estimates, on="employee_id", how="left")
        e["outcome"] = o
        parts.append(e)
    estimates = pd.concat(parts, ignore_index=True)

    sched = ctx["schedule_variance_pct"]
    ser = period_series(m, sched.ols, m.dropna(subset=["schedule_variance_pct"]), "schedule_variance_pct")
    tr = trends(ser)
    sq = sustained_quality(m)
    tr["sustained_quality"] = tr["employee_id"].map(sq).fillna(False).astype(bool)
    qser = quarterly_series(m.dropna(subset=["schedule_variance_pct"]), sched.ols, "schedule_variance_pct")

    fw = load_framework(framework_path)
    comp = competency_evidence(fs, fw)

    base = sched.mixed_estimates
    validation = run_validation(m, fs.events, fs.employees, base, n_boot=n_boot)
    experiment = run_experiment(m, sched, validation["_sensitivity_tables"], fs.employees)

    act = employee_activity_summary(fs.activity)
    audit = label_audit(base, manager_ratings, sched.raw, act) if manager_ratings is not None else None
    fair = None
    if protected_attributes is not None and manager_ratings is not None and promotions is not None:
        fair = fairness_audit(protected_attributes, base, sched.raw, manager_ratings, promotions)

    conclusions = base["conclusion"].value_counts().to_dict()
    metrics = _clean(
        {
            "version": version,
            "analytics_version": __version__,
            "data_hash": fingerprint,
            "as_of": as_of,
            "counts": {"milestones": len(m), "employees_with_evidence": int(m["employee_id"].nunique()),
                       "projects": int(m["project_id"].nunique()), "eligible_events": int(len(fs.events))},
            "context_models": {
                o: {"coefficients": c.coefficients.to_dict("records"), "variance_components": c.variance_components,
                    "diagnostics": c.diagnostics}
                for o, c in ctx.items()
            },
            "conclusion_counts": conclusions,
            "trend_counts": tr["trend_status"].value_counts().to_dict(),
            "validation": validation,
            "label_audit": audit,
        }
    )
    result = PipelineResult(
        version=version, created_at=created.isoformat(), data_hash=fingerprint,
        config={"n_boot": n_boot, "framework": fw.get("version"), "as_of": as_of},
        features=fs, employee_metrics=desc, portfolio_trend=portfolio_trend(m), risk_trends=risk_trends(fs.events),
        context=ctx, estimates=estimates, trend_summary=tr, trend_series=qser, competencies=comp,
        validation=validation, experiment=_clean(experiment), label_audit=audit, fairness=_clean(fair) if fair else None,
        metrics=metrics,
    )
    result.model_card = render_model_card(result)
    return result


def save_artifacts(result: PipelineResult, root: str | Path) -> Path:
    """Persist a versioned, self-describing artifact directory."""
    out = Path(root) / result.version
    out.mkdir(parents=True, exist_ok=True)
    result.estimates.to_csv(out / "employee_estimates.csv", index=False)
    result.employee_metrics.to_csv(out / "employee_metrics.csv", index=False)
    result.trend_summary.to_csv(out / "trend_summary.csv", index=False)
    result.trend_series.to_csv(out / "trend_series.csv", index=False)
    result.competencies.to_csv(out / "competency_evidence.csv", index=False)
    result.portfolio_trend.to_csv(out / "portfolio_trend.csv", index=False)
    (out / "metrics.json").write_text(json.dumps(result.metrics, indent=2, default=str))
    (out / "experiment.json").write_text(json.dumps(result.experiment, indent=2, default=str))
    if result.fairness:
        (out / "fairness_audit.json").write_text(json.dumps(result.fairness, indent=2, default=str))
    (out / "model_card.md").write_text(result.model_card)
    manifest = {"version": result.version, "created_at": result.created_at, "data_hash": result.data_hash,
                "config": result.config, "files": sorted(p.name for p in out.iterdir())}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return out
