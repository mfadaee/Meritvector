"""Layer A — descriptive analytics.

Transparent, unadjusted metrics. They describe what happened; they do not account
for the conditions under which it happened (that is Layer B).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from meritvector_analytics.features import FeatureSet, safe_rate


def _payload_col(ev: pd.DataFrame, key: str) -> pd.Series:
    return ev["payload"].map(lambda p: p.get(key) if isinstance(p, dict) else None)


def employee_metrics(fs: FeatureSet) -> pd.DataFrame:
    """Raw per-employee delivery metrics, plus within-job-family z-scores."""
    m, ev = fs.milestones, fs.events
    g = m.groupby("employee_id")
    out = pd.DataFrame(
        {
            "milestones": g.size(),
            "projects_led": g["project_id"].nunique(),
            "on_time_rate": g["on_time"].mean(),
            "mean_schedule_variance_pct": g["schedule_variance_pct"].mean(),
            "schedule_variance_sd": g["schedule_variance_pct"].std(),
            "quality_mean": g["quality_score"].mean(),
            "quality_observations": g["quality_score"].count(),
            "first_pass_approval_rate": g["approved_first_pass"].mean(),
            "mean_complexity": g["technical_complexity"].mean(),
            "mean_resource_constraint": g["resource_constraint"].mean(),
            "mean_dependencies": g["dependency_count"].mean(),
        }
    )
    cat = ev.groupby(["employee_id", "category"]).size().unstack(fill_value=0)
    for c in (
        "risk_identified",
        "risk_mitigated",
        "issue_raised",
        "blocker_resolved",
        "dependency_resolved",
        "task_completed",
        "stakeholder_feedback",
        "scope_change_approved",
    ):
        out[c] = cat[c] if c in cat.columns else 0
    out = out.fillna({c: 0 for c in cat.columns if c in out.columns})
    out["risk_mitigation_rate"] = safe_rate(out["risk_mitigated"], out["risk_identified"])

    ri = ev[ev["category"] == "risk_identified"]
    proactive = ri.assign(p=_payload_col(ri, "proactive").astype(float)).groupby("employee_id")["p"].mean()
    out["proactive_risk_rate"] = proactive

    br = ev[ev["category"] == "blocker_resolved"]
    out["blocker_median_days"] = (
        br.assign(d=_payload_col(br, "days_to_resolve").astype(float)).groupby("employee_id")["d"].median()
    )
    dr = ev[ev["category"] == "dependency_resolved"]
    out["dependency_median_days"] = dr.assign(d=_payload_col(dr, "days_open").astype(float)).groupby("employee_id")["d"].median()
    sf = ev[ev["category"] == "stakeholder_feedback"]
    out["stakeholder_feedback_mean"] = sf.assign(s=_payload_col(sf, "score").astype(float)).groupby("employee_id")["s"].mean()

    out = out.reset_index().merge(fs.employees[["employee_id", "job_family", "business_unit"]], on="employee_id", how="right")
    for col, sign in (("on_time_rate", 1), ("mean_schedule_variance_pct", -1), ("quality_mean", 1)):
        grp = out.groupby("job_family")[col]
        out[f"{col}_z"] = sign * (out[col] - grp.transform("mean")) / grp.transform("std")
    return out


def portfolio_trend(m: pd.DataFrame) -> pd.DataFrame:
    """Delivery performance by quarter across the portfolio."""
    g = m.groupby("quarter")
    return pd.DataFrame(
        {
            "milestones": g.size(),
            "on_time_rate": g["on_time"].mean(),
            "mean_schedule_variance_pct": g["schedule_variance_pct"].mean(),
            "quality_mean": g["quality_score"].mean(),
            "mean_complexity": g["technical_complexity"].mean(),
        }
    ).reset_index()


def complexity_distribution(projects: pd.DataFrame) -> pd.DataFrame:
    return projects.groupby(["technical_complexity", "business_unit"]).size().rename("projects").reset_index()


def project_health(
    projects: pd.DataFrame, milestones: pd.DataFrame, risks: pd.DataFrame, dependencies: pd.DataFrame, as_of
) -> pd.DataFrame:
    """Rule-based RAG health from organisational reporting registers.

    Rules (documented in METRICS_FRAMEWORK.md):
      red   — any overdue milestone, or >=2 open high-severity risks/issues
      amber — latest achieved milestone slipped >15% of its interval, or >=2 open
              dependencies, or any open high-severity risk/issue
      green — otherwise
    """
    as_of = pd.Timestamp(as_of)
    ms = milestones.copy()
    for c in ("planned_date", "actual_date"):
        ms[c] = pd.to_datetime(ms[c])
    ms["slip_days"] = (ms["actual_date"] - ms["planned_date"]).dt.days
    overdue = ms[ms["status"] == "overdue"].groupby("project_id").size()
    ach = ms[ms["status"] == "achieved"].sort_values("actual_date").groupby("project_id").tail(1)
    p = projects.set_index("project_id")
    dur = (pd.to_datetime(p["planned_end"]) - pd.to_datetime(p["start_date"])).dt.days
    n_ms = ms.groupby("project_id").size()
    interval = (dur / n_ms).reindex(ach["project_id"]).to_numpy()
    latest_slip_pct = pd.Series(100 * ach["slip_days"].to_numpy() / np.maximum(interval, 1), index=ach["project_id"].to_numpy())
    rk = risks[risks["status"].isin(["open", "issue"])]
    high_open = rk[rk["severity"] == "high"].groupby("project_id").size()
    open_risks = rk.groupby("project_id").size()
    open_deps = dependencies[dependencies["status"] == "open"].groupby("project_id").size()

    out = pd.DataFrame(index=p.index)
    out["overdue_milestones"] = overdue.reindex(out.index).fillna(0).astype(int)
    out["open_high_risks"] = high_open.reindex(out.index).fillna(0).astype(int)
    out["open_risks"] = open_risks.reindex(out.index).fillna(0).astype(int)
    out["open_dependencies"] = open_deps.reindex(out.index).fillna(0).astype(int)
    out["latest_slip_pct"] = latest_slip_pct.reindex(out.index)
    red = (out["overdue_milestones"] > 0) | (out["open_high_risks"] >= 2)
    amber = (out["latest_slip_pct"] > 15) | (out["open_dependencies"] >= 2) | (out["open_high_risks"] >= 1)
    out["health"] = np.where(red, "red", np.where(amber, "amber", "green"))
    out.loc[p["status"] == "completed", "health"] = "closed"
    return out.reset_index()


def risk_trends(events: pd.DataFrame) -> pd.DataFrame:
    ev = events[events["category"].isin(["risk_identified", "risk_mitigated", "issue_raised"])].copy()
    ev["month"] = pd.to_datetime(ev["occurred_at"]).dt.to_period("M").astype(str)
    return ev.groupby(["month", "category"]).size().unstack(fill_value=0).reset_index()
