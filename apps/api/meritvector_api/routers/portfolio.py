"""Portfolio, project and risk intelligence (organisational-reporting data)."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meritvector_api.db import get_db
from meritvector_api.models import Dependency, Employee, Milestone, Project, Risk, Tenant
from meritvector_api.security import Principal, current_principal
from meritvector_api.services import health_map, tenant_today, to_dict
from meritvector_api.training import latest_run

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _df(db: Session, model, tenant_id: str) -> pd.DataFrame:
    rows = [to_dict(o) for o in db.scalars(select(model).where(model.tenant_id == tenant_id))]
    return pd.DataFrame(rows, columns=[c.name for c in model.__table__.columns])


def _clean(records: list[dict]) -> list[dict]:
    return [{k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in r.items()} for r in records]


def _milestone_frame(db: Session, tenant_id: str) -> pd.DataFrame:
    ms = _df(db, Milestone, tenant_id)
    pr = _df(db, Project, tenant_id).rename(columns={"id": "project_id"})
    ms = ms.merge(pr[["project_id", "start_date", "planned_end", "technical_complexity", "resource_constraint", "business_unit",
                      "dependency_count", "environment"]], on="project_id")
    for c in ("planned_date", "actual_date", "start_date", "planned_end"):
        ms[c] = pd.to_datetime(ms[c])
    n = ms.groupby("project_id")["id"].transform("size")
    interval = (ms["planned_end"] - ms["start_date"]).dt.days / n
    ms["slip_pct"] = 100 * (ms["actual_date"] - ms["planned_date"]).dt.days / interval.clip(lower=1)
    ms["on_time"] = ms["slip_pct"] <= 5
    ms["quarter"] = ms["planned_date"].dt.to_period("Q").astype(str)
    return ms


@router.get("/overview")
def overview(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    projects = _df(db, Project, p.tenant_id)
    health = health_map(db, p.tenant_id)
    active = projects[projects["status"] == "active"]
    hcounts = pd.Series([health[i]["health"] for i in active["id"]]).value_counts().to_dict() if len(active) else {}
    ms = _milestone_frame(db, p.tenant_id)
    ach = ms[ms["status"] == "achieved"]
    trend = ach.groupby("quarter").agg(milestones=("id", "size"), on_time_rate=("on_time", "mean"),
                                       mean_slip_pct=("slip_pct", "mean"), mean_complexity=("technical_complexity", "mean")).reset_index()
    complexity = projects.groupby(["technical_complexity", "status"]).size().rename("projects").reset_index()
    risks = _df(db, Risk, p.tenant_id)
    deps = _df(db, Dependency, p.tenant_id)
    run = latest_run(db, p.tenant_id) if t.assessment_enabled else None
    coverage = None
    if run is not None and p.role in ("manager", "hr_reviewer", "admin"):
        cc = run.metrics.get("conclusion_counts", {})
        total = sum(cc.values()) or 1
        coverage = {"employees": total, "insufficient_evidence": cc.get("insufficient_evidence", 0),
                    "share_with_sufficient_evidence": 1 - cc.get("insufficient_evidence", 0) / total, "run_id": run.id}
    recent = ach[ach["planned_date"] >= pd.Timestamp(tenant_today(db, p.tenant_id)) - pd.DateOffset(months=6)]
    return {
        "tenant": {"name": t.name, "is_synthetic": t.is_synthetic, "as_of": str(t.as_of)},
        "kpis": {
            "employees": int(db.scalar(select(func.count()).select_from(Employee).where(Employee.tenant_id == p.tenant_id)) or 0),
            "projects_total": int(len(projects)), "projects_active": int(len(active)),
            "business_units": int(projects["business_unit"].nunique()),
            "on_time_rate_6m": float(recent["on_time"].mean()) if len(recent) else None,
            "open_high_risks": int(((risks["status"].isin(["open", "issue"])) & (risks["severity"] == "high")).sum()),
            "open_dependencies": int((deps["status"] == "open").sum()),
        },
        "health_counts": hcounts,
        "delivery_trend": _clean(trend.to_dict("records")),
        "complexity_distribution": complexity.to_dict("records"),
        "evidence_coverage": coverage,
        "notes": "Organisational reporting. On-time = milestone achieved within 5% of its planned interval.",
    }


@router.get("/projects")
def projects(status: str | None = None, business_unit: str | None = None, health: str | None = None, q: str | None = None,
             limit: int = Query(50, le=500), offset: int = 0, p: Principal = Depends(current_principal),
             db: Session = Depends(get_db)) -> dict:
    stmt = select(Project).where(Project.tenant_id == p.tenant_id)
    if status:
        stmt = stmt.where(Project.status == status)
    if business_unit:
        stmt = stmt.where(Project.business_unit == business_unit)
    if q:
        stmt = stmt.where(Project.name.ilike(f"%{q}%"))
    rows = db.scalars(stmt.order_by(Project.status, Project.name)).all()
    hm = health_map(db, p.tenant_id, [r.id for r in rows])
    items = [to_dict(r) | {"health": hm.get(r.id, {}).get("health")} for r in rows]
    if health:
        items = [i for i in items if i["health"] == health]
    leads = {e.id: e.display_name for e in db.scalars(select(Employee).where(Employee.id.in_({i["lead_employee_id"] for i in items})))}
    for i in items:
        i["lead_name"] = leads.get(i["lead_employee_id"])
    bus = sorted(set(db.scalars(select(Project.business_unit).where(Project.tenant_id == p.tenant_id).distinct())))
    return {"total": len(items), "items": items[offset: offset + limit], "business_units": bus}


def _project(db: Session, p: Principal, project_id: str) -> Project:
    pr = db.get(Project, project_id)
    if pr is None or pr.tenant_id != p.tenant_id:
        raise HTTPException(404, "Project not found")
    return pr


@router.get("/projects/{project_id}")
def project(project_id: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    pr = _project(db, p, project_id)
    lead = db.get(Employee, pr.lead_employee_id)
    ms = db.scalars(select(Milestone).where(Milestone.project_id == pr.id).order_by(Milestone.planned_date)).all()
    n = max(1, len(ms))
    interval = max(1, (pr.planned_end - pr.start_date).days / n)
    milestones = []
    for m in ms:
        d = to_dict(m)
        d["slip_days"] = (m.actual_date - m.planned_date).days if m.actual_date else None
        d["slip_pct"] = round(100 * d["slip_days"] / interval, 1) if d["slip_days"] is not None else None
        milestones.append(d)
    return {
        **to_dict(pr),
        "lead": {"employee_id": lead.id, "display_name": lead.display_name, "job_family": lead.job_family} if lead else None,
        "health": health_map(db, p.tenant_id, [pr.id]).get(pr.id),
        "milestones": milestones,
        "risks": [to_dict(r) for r in db.scalars(select(Risk).where(Risk.project_id == pr.id).order_by(Risk.identified_on))],
        "dependencies": [to_dict(d) for d in db.scalars(select(Dependency).where(Dependency.project_id == pr.id))],
        "context_note": "Operating conditions come from the PMO complexity assessment recorded at kick-off.",
    }


@router.get("/compare")
def compare(ids: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    """Side-by-side outcomes and operating conditions for 2–4 projects."""
    pids = [x for x in ids.split(",") if x][:4]
    if len(pids) < 2:
        raise HTTPException(422, "Provide at least two project ids")
    out = []
    for pid in pids:
        d = project(pid, p, db)
        ach = [m for m in d["milestones"] if m["slip_pct"] is not None]
        out.append({
            "project_id": pid, "name": d["name"], "status": d["status"], "lead": d["lead"]["display_name"] if d["lead"] else None,
            "conditions": {k: d[k] for k in ("technical_complexity", "dependency_count", "resource_constraint", "team_size",
                                             "size_band", "environment", "maturity")},
            "outcomes": {"milestones_achieved": len(ach), "milestones_total": len(d["milestones"]),
                         "on_time_rate": float(np.mean([m["slip_pct"] <= 5 for m in ach])) if ach else None,
                         "mean_slip_pct": float(np.mean([m["slip_pct"] for m in ach])) if ach else None,
                         "risks": len(d["risks"]), "issues": sum(r["kind"] == "issue" for r in d["risks"]),
                         "open_dependencies": sum(x["status"] == "open" for x in d["dependencies"])},
            "health": (d["health"] or {}).get("health"),
        })
    return {"projects": out, "note": "Outcomes differ partly because operating conditions differ; compare both."}


@router.get("/risks")
def risks(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    r = _df(db, Risk, p.tenant_id)
    pr = _df(db, Project, p.tenant_id).rename(columns={"id": "project_id"})
    r = r.merge(pr[["project_id", "business_unit", "technical_complexity", "name"]], on="project_id")
    r["month"] = pd.to_datetime(r["identified_on"]).dt.to_period("M").astype(str)
    monthly = r.groupby("month").agg(identified=("id", "size"), became_issue=("kind", lambda s: int((s == "issue").sum())),
                                     mitigated=("status", lambda s: int((s == "mitigated").sum()))).reset_index()
    by_bu = r.groupby("business_unit").agg(risks=("id", "size"), issues=("kind", lambda s: int((s == "issue").sum())),
                                           open_high=("severity", lambda s: 0)).reset_index()
    open_high = r[(r["status"].isin(["open", "issue"])) & (r["severity"] == "high")]
    by_bu["open_high"] = by_bu["business_unit"].map(open_high.groupby("business_unit").size()).fillna(0).astype(int)
    by_bu["materialisation_rate"] = by_bu["issues"] / by_bu["risks"]
    by_cx = r.groupby("technical_complexity").agg(risks=("id", "size"), issues=("kind", lambda s: int((s == "issue").sum())),
                                                  projects=("project_id", "nunique")).reset_index()
    by_cx["risks_per_project"] = by_cx["risks"] / by_cx["projects"]
    themes = r.groupby("title").agg(count=("id", "size"), issues=("kind", lambda s: int((s == "issue").sum()))).reset_index()
    themes = themes.sort_values("count", ascending=False).head(12)
    register = open_high.sort_values("identified_on", ascending=False).head(50)
    return {
        "monthly": monthly.to_dict("records"),
        "by_business_unit": _clean(by_bu.to_dict("records")),
        "by_complexity": _clean(by_cx.to_dict("records")),
        "themes": themes.to_dict("records"),
        "status_counts": r["status"].value_counts().to_dict(),
        "severity_counts": r["severity"].value_counts().to_dict(),
        "open_high_register": [{k: (str(v) if k.endswith("_on") and v is not None else v) for k, v in row.items()}
                               for row in _clean(register[["id", "project_id", "name", "title", "severity", "status",
                                                           "identified_on", "business_unit"]].to_dict("records"))],
    }


@router.get("/bottlenecks")
def bottlenecks(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    today_ = pd.Timestamp(tenant_today(db, p.tenant_id))
    d = _df(db, Dependency, p.tenant_id)
    d["raised_on"] = pd.to_datetime(d["raised_on"])
    d["resolved_on"] = pd.to_datetime(d["resolved_on"])
    d["days_open"] = ((d["resolved_on"].fillna(today_)) - d["raised_on"]).dt.days
    by_team = d.groupby("depends_on").agg(dependencies=("id", "size"), open=("status", lambda s: int((s == "open").sum())),
                                          median_days_to_resolve=("days_open", "median")).reset_index()
    by_team = by_team.sort_values("open", ascending=False)
    ms = _milestone_frame(db, p.tenant_id)
    ach = ms[ms["status"] == "achieved"].copy()
    ach["resource_band"] = pd.cut(ach["resource_constraint"], [-0.01, 0.3, 0.6, 1.0], labels=["low", "medium", "high"]).astype(str)
    res = ach.groupby(["resource_band", "technical_complexity"]).agg(
        milestones=("id", "size"), on_time_rate=("on_time", "mean"), mean_slip_pct=("slip_pct", "mean")).reset_index()
    by_bu = ach.groupby("business_unit").agg(milestones=("id", "size"), on_time_rate=("on_time", "mean"),
                                             mean_resource_constraint=("resource_constraint", "mean"),
                                             mean_dependencies=("dependency_count", "mean")).reset_index()
    overdue = ms[(ms["status"] == "overdue")]
    stale = d[(d["status"] == "open") & (d["raised_on"] < today_ - timedelta(days=21))]
    return {
        "dependencies_by_team": _clean(by_team.to_dict("records")),
        "resource_constraint_analysis": _clean(res.to_dict("records")),
        "business_units": _clean(by_bu.to_dict("records")),
        "overdue_milestones": int(len(overdue)),
        "stale_dependencies": int(len(stale)),
        "note": "Aggregated operating conditions. Resource constraint is the PMO-assessed staffing shortfall (0–1).",
    }
