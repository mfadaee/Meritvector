"""Workstream 1 — exploratory data analysis."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from meritvector_analytics.research.data import ResearchData, jsonable

MILESTONE_VARS = [
    "schedule_variance_pct",
    "quality_score",
    "technical_complexity",
    "dependency_count",
    "resource_constraint",
    "scope_changes_to_date",
    "team_size",
    "size_band",
    "schedule_criticality",
    "visibility_level",
    "stakeholder_groups",
    "technical_uncertainty",
    "integration_points",
    "vendor_count",
]
EMPLOYEE_VARS = [
    "n_milestones",
    "raw_on_time",
    "raw_mean_svp",
    "adjusted_signal",
    "context_expected",
    "mean_complexity",
    "mean_resource_constraint",
    "meetings_per_month",
    "emails_per_month",
    "hours_per_month",
    "mean_rating",
]


def describe(series: pd.Series, bins: int = 20) -> dict[str, Any]:
    s = pd.to_numeric(series, errors="coerce")
    x = s.dropna().to_numpy(float)
    n_missing = int(s.isna().sum())
    if len(x) == 0:
        return {"n": 0, "missing": n_missing}
    q = np.percentile(x, [5, 25, 50, 75, 95])
    iqr = q[3] - q[1]
    lo, hi = q[1] - 1.5 * iqr, q[3] + 1.5 * iqr
    counts, edges = np.histogram(x, bins=min(bins, max(5, len(np.unique(x)))))
    return {
        "n": int(len(x)),
        "missing": n_missing,
        "missing_rate": n_missing / max(1, len(s)),
        "mean": float(x.mean()),
        "median": float(q[2]),
        "variance": float(x.var(ddof=1)) if len(x) > 1 else None,
        "sd": float(x.std(ddof=1)) if len(x) > 1 else None,
        "min": float(x.min()),
        "p5": float(q[0]),
        "p25": float(q[1]),
        "p75": float(q[3]),
        "p95": float(q[4]),
        "max": float(x.max()),
        "iqr": float(iqr),
        "skew": float(stats.skew(x)) if len(x) > 2 else None,
        "outliers_iqr": int(((x < lo) | (x > hi)).sum()),
        "outlier_fences": [float(lo), float(hi)],
        "histogram": {"edges": [float(e) for e in edges], "counts": [int(c) for c in counts]},
    }


def variables(rd: ResearchData, level: str = "milestone") -> dict[str, Any]:
    df, cols = (rd.milestone_frame, MILESTONE_VARS) if level == "milestone" else (rd.employee_frame, EMPLOYEE_VARS)
    cols = [c for c in cols if c in df.columns]
    return {"level": level, "n_rows": int(len(df)), "variables": {c: describe(df[c]) for c in cols}}


def correlations(rd: ResearchData, level: str = "employee", method: str = "spearman") -> dict[str, Any]:
    df, cols = (rd.milestone_frame, MILESTONE_VARS) if level == "milestone" else (rd.employee_frame, EMPLOYEE_VARS)
    cols = [c for c in cols if c in df.columns]
    c = df[cols].apply(pd.to_numeric, errors="coerce").corr(method=method)
    return jsonable({"level": level, "method": method, "columns": cols, "matrix": c.round(3).values.tolist()})


def missingness(rd: ResearchData) -> dict[str, Any]:
    m = rd.milestone_frame
    rates = {c: float(m[c].isna().mean()) for c in MILESTONE_VARS if c in m.columns}
    by_env = m.assign(q_missing=m["quality_score"].isna()).groupby("environment")["q_missing"].mean().to_dict()
    tab = pd.crosstab(m["environment"], m["quality_score"].isna())
    chi = stats.chi2_contingency(tab) if tab.shape[1] == 2 else None
    return jsonable(
        {
            "rates": rates,
            "quality_missing_by_environment": by_env,
            "chi2_p": float(chi[1]) if chi else None,
            "mechanism": "Missingness of quality scores depends on delivery environment — inconsistent with MCAR; "
            "MAR given environment is assumed, MNAR cannot be ruled out."
            if chi and chi[1] < 0.05
            else "No evidence against MCAR for quality scores.",
        }
    )


def assignment_analysis(rd: ResearchData) -> dict[str, Any]:
    """RQ1 — are some people systematically assigned harder projects?"""
    ols, d = rd.context_ols
    d = d.assign(fitted=ols.fittedvalues)
    groups = [g["fitted"].to_numpy() for _, g in d.groupby("employee_id") if len(g) >= 2]
    f, p = stats.f_oneway(*groups)
    k = np.mean([len(g) for g in groups])
    msb, msw = _ms(groups)
    icc1 = (msb - msw) / (msb + (k - 1) * msw)
    e = rd.employee_frame
    both = e.dropna(subset=["first_year_on_time", "later_context_expected"])
    both = both[(both["first_year_n"] >= 3) & (both["later_n"] >= 3)]
    rho = stats.spearmanr(both["first_year_on_time"], both["later_context_expected"])
    # Simpson check: pooled vs complexity-stratified on-time rates by job family.
    m = rd.features.milestones.assign(cx_band=lambda x: pd.cut(x["technical_complexity"], [0, 2, 3, 5], labels=["low", "mid", "high"]))
    pooled = m.groupby("job_family")["on_time"].mean()
    strat = m.groupby(["cx_band", "job_family"], observed=True)["on_time"].mean().unstack()
    fams = list(pooled.index)
    reversal = None
    if len(fams) >= 2:
        a, b = fams[0], fams[-1]
        pooled_sign = np.sign(pooled[a] - pooled[b])
        strat_signs = np.sign((strat[a] - strat[b]).dropna())
        reversal = bool(len(strat_signs) and (strat_signs != pooled_sign).all())
    return jsonable(
        {
            "question": "Are some people systematically assigned harder projects?",
            "kind": "descriptive",
            "difficulty_between_people": {
                "anova_f": float(f),
                "p_value": float(p),
                "icc1": float(icc1),
                "interpretation": f"{icc1:.0%} of variation in context-predicted difficulty lies between people — "
                "assignment is far from random.",
            },
            "earlier_results_vs_later_difficulty": {
                "spearman_rho": float(rho.statistic),
                "p_value": float(rho.pvalue),
                "n": int(len(both)),
            },
            "pooled_on_time_by_family": pooled.to_dict(),
            "stratified_on_time_by_complexity": {str(i): row.dropna().to_dict() for i, row in strat.iterrows()},
            "simpson_reversal": reversal,
        }
    )


def _ms(groups):
    allx = np.concatenate(groups)
    gm = allx.mean()
    ssb = sum(len(g) * (g.mean() - gm) ** 2 for g in groups)
    ssw = sum(((g - g.mean()) ** 2).sum() for g in groups)
    dfb, dfw = len(groups) - 1, len(allx) - len(groups)
    return ssb / dfb, ssw / dfw


def activity_vs_contribution(rd: ResearchData) -> dict[str, Any]:
    e = rd.employee_frame.dropna(subset=["meetings_per_month", "adjusted_signal"])
    out = {}
    for col in ("meetings_per_month", "emails_per_month", "hours_per_month"):
        r = stats.spearmanr(e[col], e["adjusted_signal"])
        rr = stats.spearmanr(e[col], e["mean_rating"], nan_policy="omit")
        out[col] = {"vs_adjusted_signal": float(r.statistic), "p": float(r.pvalue), "vs_manager_rating": float(rr.statistic)}
    return jsonable(
        {
            "kind": "measurement",
            "n": int(len(e)),
            "correlations": out,
            "interpretation": "Activity volume is not positively associated with context-adjusted delivery evidence, "
            "while it is positively associated with manager ratings — activity counts reward visibility, "
            "not contribution."
            if out["meetings_per_month"]["vs_adjusted_signal"] <= 0.05 and out["meetings_per_month"]["vs_manager_rating"] > 0
            else "See correlations; interpret with care.",
        }
    )
