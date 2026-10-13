"""Flagship experiment: does context change how we read two delivery records?

Employee A and Employee B are chosen *from observable data only* by a fixed,
documented rule — never from hidden ground truth and never to produce a chosen
winner:

* **A** — among people with >= 8 achieved milestones, raw on-time rate in the top
  quartile, choose the one whose work had the *lowest* context-expected slippage
  (simple projects, good resourcing).
* **B** — among people with >= 8 achieved milestones, raw on-time rate at or below
  the median, choose the one whose work had the *highest* context-expected
  slippage (complex, constrained, dependency-heavy projects).

The experiment then reports raw metrics, operating conditions, adjusted estimates
with uncertainty, the B−A difference under several modelling assumptions, and an
explicit verdict that may be "inconclusive".
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from meritvector_analytics.contextual import ContextResult
from meritvector_analytics.features import CONTEXT_NUMERIC, design_matrix

MIN_MS = 8


def select_pair(m: pd.DataFrame, ctx: ContextResult) -> tuple[str, str]:
    stats_ = m.groupby("employee_id").agg(n=("on_time", "size"), on_time=("on_time", "mean"))
    stats_ = stats_.join(ctx.residual_estimates.set_index("employee_id")["context_expected"])
    elig = stats_[stats_["n"] >= MIN_MS]
    a_pool = elig[elig["on_time"] >= elig["on_time"].quantile(0.75)]
    b_pool = elig[elig["on_time"] <= elig["on_time"].median()]
    a = a_pool["context_expected"].idxmin()
    b = b_pool.drop(index=a, errors="ignore")["context_expected"].idxmax()
    return str(a), str(b)


def _pair_difference_bootstrap(m: pd.DataFrame, a: str, b: str, n_boot: int = 400, seed: int = 1) -> dict[str, float]:
    """Cluster bootstrap (projects) of the B−A difference in mean context residuals."""
    rng = np.random.default_rng(seed)
    d = m.dropna(subset=["schedule_variance_pct"]).reset_index(drop=True)
    X = np.column_stack([np.ones(len(d)), design_matrix(d).to_numpy()])
    y = d["schedule_variance_pct"].to_numpy()
    proj_codes, proj_index = pd.factorize(d["project_id"])
    rows = [np.nonzero(proj_codes == i)[0] for i in range(len(proj_index))]
    # Always keep the two people's own projects in each resample (resampled among themselves).
    own = {e: [i for i, p in enumerate(proj_index) if (d.loc[rows[i], "employee_id"] == e).any()] for e in (a, b)}
    others = [i for i in range(len(rows)) if i not in own[a] and i not in own[b]]
    diffs = []
    emp = d["employee_id"].to_numpy()
    for _ in range(n_boot):
        pick = list(rng.choice(others, len(others)))
        for e in (a, b):
            pick += list(rng.choice(own[e], len(own[e])))
        idx = np.concatenate([rows[i] for i in pick])
        beta, *_ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
        r = y[idx] - X[idx] @ beta
        ra, rb = r[emp[idx] == a].mean(), r[emp[idx] == b].mean()
        diffs.append(-(rb - ra))  # positive => B better than A relative to context
    return {"difference": float(np.mean(diffs)), "ci_low": float(np.percentile(diffs, 2.5)),
            "ci_high": float(np.percentile(diffs, 97.5)), "n_boot": n_boot}


def run_experiment(m: pd.DataFrame, ctx: ContextResult, sensitivity_tables: dict[str, pd.DataFrame],
                   employees: pd.DataFrame) -> dict[str, Any]:
    a, b = select_pair(m, ctx)
    sub = m[m["employee_id"].isin([a, b])]
    label = {a: "A", b: "B"}

    raw = {}
    conditions = {}
    for e in (a, b):
        s = sub[sub["employee_id"] == e]
        raw[label[e]] = {
            "milestones": int(len(s)),
            "projects": int(s["project_id"].nunique()),
            "on_time_rate": float(s["on_time"].mean()),
            "mean_schedule_variance_pct": float(s["schedule_variance_pct"].mean()),
            "schedule_variance_sd": float(s["schedule_variance_pct"].std()),
            "quality_mean": float(s["quality_score"].mean()) if s["quality_score"].notna().any() else None,
        }
        conditions[label[e]] = {c: float(s[c].mean()) for c in CONTEXT_NUMERIC}
        conditions[label[e]]["regulated_share"] = float((s["environment"] == "regulated").mean())
        conditions[label[e]]["greenfield_share"] = float((s["maturity"] == "greenfield").mean())
        conditions[label[e]]["context_expected_variance_pct"] = float(
            ctx.residual_estimates.set_index("employee_id").loc[e, "context_expected"])

    mixed = ctx.mixed_estimates.set_index("employee_id")
    adjusted = {label[e]: {k: float(mixed.loc[e, k]) for k in ("adjusted_estimate", "ci_low", "ci_high")} | {
        "conclusion": str(mixed.loc[e, "conclusion"])} for e in (a, b)}

    sens_rows = []
    for name, t in {"base_mixed_model": ctx.mixed_estimates.set_index("employee_id"), **sensitivity_tables}.items():
        if a in t.index and b in t.index:
            sens_rows.append({"specification": name, "A": float(t.loc[a, "adjusted_estimate"]),
                              "B": float(t.loc[b, "adjusted_estimate"]),
                              "B_minus_A": float(t.loc[b, "adjusted_estimate"] - t.loc[a, "adjusted_estimate"])})
    boot = _pair_difference_bootstrap(m, a, b)

    # Overlap / common support: are their operating conditions even comparable?
    Xa = design_matrix(sub[sub["employee_id"] == a])[CONTEXT_NUMERIC]
    Xb = design_matrix(sub[sub["employee_id"] == b])[CONTEXT_NUMERIC]
    overlap = {}
    for c in CONTEXT_NUMERIC:
        lo, hi = max(Xa[c].min(), Xb[c].min()), min(Xa[c].max(), Xb[c].max())
        overlap[c] = bool(lo <= hi)
    support_ok = sum(overlap.values()) >= len(overlap) - 1

    raw_gap = raw["A"]["mean_schedule_variance_pct"] - raw["B"]["mean_schedule_variance_pct"]  # negative => A slips less
    adj_diffs = [r["B_minus_A"] for r in sens_rows if r["specification"] != "no_context_adjustment"]
    consistent_sign = len(adj_diffs) > 0 and (all(x > 0 for x in adj_diffs) or all(x < 0 for x in adj_diffs))
    boot_sig = boot["ci_low"] > 0 or boot["ci_high"] < 0
    mixed_sig = (adjusted["B"]["ci_low"] > adjusted["A"]["ci_high"]) or (adjusted["A"]["ci_low"] > adjusted["B"]["ci_high"])

    reasons = []
    if not support_ok:
        reasons.append("Operating conditions barely overlap, so the adjustment extrapolates beyond observed data.")
    if not consistent_sign:
        reasons.append("The direction of the adjusted difference changes across reasonable model specifications.")
    if not boot_sig:
        reasons.append("The bootstrap interval for the adjusted B−A difference includes zero.")
    if consistent_sign and boot_sig and support_ok:
        direction = "B" if boot["difference"] > 0 else "A"
        verdict = (f"Evidence supports a context-adjusted difference favouring Employee {direction}. "
                   "This is an adjusted association, not proof of individual causal impact.")
        status = "supported_difference"
    else:
        verdict = "Inconclusive: the evidence does not support a confident comparison. " + " ".join(reasons)
        status = "inconclusive"
    raw_favours = "A" if raw["A"]["on_time_rate"] > raw["B"]["on_time_rate"] else "B"
    interpretation_changed = status == "supported_difference" and direction != raw_favours

    base_diff = next((r["B_minus_A"] for r in sens_rows if r["specification"] == "base_mixed_model"), float("nan"))
    unadj_diff = next((r["B_minus_A"] for r in sens_rows if r["specification"] == "no_context_adjustment"), float("nan"))
    adjustment_summary = (
        f"Without context adjustment the model puts Employee A ahead by {abs(unadj_diff):.1f} pp of schedule variance "
        if unadj_diff < 0 else
        f"Without context adjustment the model puts Employee B ahead by {abs(unadj_diff):.1f} pp of schedule variance "
    ) + (
        f"(raw on-time rates {raw['A']['on_time_rate']:.0%} vs {raw['B']['on_time_rate']:.0%}). After adjusting for "
        f"operating conditions the B−A difference is {base_diff:+.1f} pp (bootstrap 95% CI "
        f"{boot['ci_low']:+.1f} to {boot['ci_high']:+.1f})."
    )
    return {
        "adjustment_summary": adjustment_summary,
        "selection_rule": __doc__.split("The experiment then")[0].strip(),
        "employees": {"A": a, "B": b},
        "display_names": {label[e]: str(employees.set_index("employee_id").loc[e, "display_name"]) for e in (a, b)},
        "raw_metrics": raw,
        "operating_conditions": conditions,
        "adjusted_estimates": adjusted,
        "adjusted_units": "percentage points of schedule variance; positive = less slippage than context predicts",
        "difference_bootstrap": boot,
        "sensitivity": sens_rows,
        "common_support": {"by_feature": overlap, "adequate": support_ok},
        "raw_gap_schedule_variance_pp": float(raw_gap),
        "raw_metrics_favour": raw_favours,
        "status": status,
        "verdict": verdict,
        "interpretation_changed_by_adjustment": bool(interpretation_changed),
        "mixed_intervals_separate": bool(mixed_sig),
        "why_raw_can_mislead": (
            "Raw on-time rates mix the person's contribution with the difficulty of the work they were given. "
            "Employee B's projects carried higher complexity, tighter resourcing and more dependencies, each of "
            "which the context model associates with additional slippage. Comparing raw rates therefore "
            "penalises whoever is assigned harder work."
        ),
    }
