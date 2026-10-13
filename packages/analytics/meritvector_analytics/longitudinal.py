"""Layer C — longitudinal analysis.

Works on residuals from the context baseline (fitted *without* employee identity),
so that time-varying conditions — scope changes to date, resource constraints of
the current project, organisation-wide drift (``month_index``) — are removed before
looking at change within a person.

A trend is only reported when there are at least three half-year periods with at
least two milestones each. Improvement/decline flags use a Benjamini–Hochberg false
discovery rate across all employees tested, because testing 300 trends at 5% would
otherwise flag ~15 people by chance alone.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from meritvector_analytics.contextual import OUTCOMES

MIN_PERIODS = 3
MIN_PER_PERIOD = 2
FDR_Q = 0.10


def _bh(p: np.ndarray, q: float) -> np.ndarray:
    n = len(p)
    if n == 0:
        return np.array([], dtype=bool)
    order = np.argsort(p)
    thresh = q * (np.arange(1, n + 1) / n)
    passed = p[order] <= thresh
    k = np.max(np.nonzero(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(n, dtype=bool)
    out[order[:k]] = True
    return out


def period_series(m: pd.DataFrame, ols_res, d: pd.DataFrame, outcome: str) -> pd.DataFrame:
    sign = OUTCOMES[outcome]["sign"]
    r = d.assign(signal=sign * ols_res.resid)
    g = r.groupby(["employee_id", "period"])
    return pd.DataFrame(
        {
            "signal_mean": g["signal"].mean(),
            "signal_se": g["signal"].std() / np.sqrt(g.size()),
            "n": g.size(),
            "raw_mean": g[outcome].mean(),
        }
    ).reset_index()


def quarterly_series(d: pd.DataFrame, ols_res, outcome: str) -> pd.DataFrame:
    sign = OUTCOMES[outcome]["sign"]
    r = d.assign(signal=sign * ols_res.resid)
    g = r.groupby(["employee_id", "quarter"])
    return pd.DataFrame({"signal_mean": g["signal"].mean(), "raw_mean": g[outcome].mean(), "n": g.size()}).reset_index()


def trends(series: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for emp, s in series.groupby("employee_id"):
        s = s[s["n"] >= MIN_PER_PERIOD]
        if len(s) < MIN_PERIODS:
            rows.append({"employee_id": emp, "periods": len(s), "slope": np.nan, "slope_se": np.nan, "p_value": np.nan})
            continue
        x = s["period"].to_numpy(float)
        y = s["signal_mean"].to_numpy(float)
        w = s["n"].to_numpy(float)
        X = np.column_stack([np.ones_like(x), x])
        W = np.diag(w)
        xtwx = X.T @ W @ X
        beta = np.linalg.solve(xtwx, X.T @ W @ y)
        resid = y - X @ beta
        dof = max(len(x) - 2, 1)
        sigma2 = float((w * resid**2).sum() / dof)
        cov = sigma2 * np.linalg.inv(xtwx)
        se = float(np.sqrt(max(cov[1, 1], 1e-12)))
        t = beta[1] / se
        p = float(2 * stats.t.sf(abs(t), dof))
        rows.append(
            {
                "employee_id": emp,
                "periods": len(s),
                "slope": float(beta[1]),
                "slope_se": se,
                "p_value": p,
                "first_period_signal": float(y[0]),
                "last_period_signal": float(y[-1]),
            }
        )
    out = pd.DataFrame(rows)
    tested = out["p_value"].notna()
    out["significant_fdr"] = False
    out.loc[tested, "significant_fdr"] = _bh(out.loc[tested, "p_value"].to_numpy(), FDR_Q)
    out["trend_status"] = np.select(
        [
            ~tested,
            out["significant_fdr"] & (out["slope"] > 0),
            out["significant_fdr"] & (out["slope"] < 0),
        ],
        ["insufficient_history", "sustained_improvement", "requires_investigation"],
        default="no_detectable_change",
    )
    return out


def sustained_quality(m: pd.DataFrame, threshold: float = 3.8) -> pd.Series:
    """True when every half-year with >=2 reviewed deliverables averages >= threshold (>=3 such periods)."""
    q = m.dropna(subset=["quality_score"]).groupby(["employee_id", "period"])["quality_score"].agg(["mean", "size"])
    q = q[q["size"] >= 2]
    agg = q.groupby("employee_id")["mean"].agg(["min", "size"])
    return (agg["size"] >= 3) & (agg["min"] >= threshold)
