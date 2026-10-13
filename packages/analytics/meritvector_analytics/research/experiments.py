"""Workstream 9 — experiment design (simulated, consented).

Simulates a randomised evaluation of the AI coordinator on administrative follow-through. The true effect is a
configured, hidden parameter used only for the synthetic check. Real evaluation needs a consented pilot.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.power import TTestIndPower

from meritvector_analytics.research.data import jsonable


def simulate_coordinator_trial(
    employees: pd.DataFrame, *, seed: int = 7, true_effect_pp: float = 6.0, weeks_pre: int = 8, weeks_post: int = 12
) -> pd.DataFrame:
    """One row per employee: pre/post on-time weekly status-report rate and follow-up completion.

    Assignment is randomised 1:1 within business unit. ``true_effect_pp`` (percentage points) is hidden ground truth.
    """
    rng = np.random.default_rng(seed)
    e = employees[employees["job_family"] != "program_manager"][["employee_id", "business_unit"]].copy()
    e["arm"] = 0
    for _, idx in e.groupby("business_unit").groups.items():
        idx = list(idx)
        rng.shuffle(idx)
        e.loc[idx[: len(idx) // 2], "arm"] = 1
    base = np.clip(rng.beta(6, 3, len(e)), 0.05, 0.98)  # person-level propensity (admin load, habits)
    e["pre_on_time"] = rng.binomial(weeks_pre, base) / weeks_pre
    p_post = np.clip(base + e["arm"] * true_effect_pp / 100 + rng.normal(0, 0.03, len(e)), 0.01, 0.99)
    e["report_on_time_rate"] = rng.binomial(weeks_post, p_post) / weeks_post
    e["followups_completed_rate"] = np.clip(rng.binomial(20, np.clip(0.55 + 0.4 * (base - 0.67) + e["arm"] * 0.04, 0.01, 0.99)) / 20, 0, 1)
    e["consented"] = True
    return e


def power_analysis(sd: float, n_per_arm: int, alpha: float = 0.05) -> dict[str, Any]:
    pw = TTestIndPower()
    mde_d = pw.solve_power(nobs1=n_per_arm, alpha=alpha, power=0.8, ratio=1.0)
    n_for = {f"{d_pp:.0f}pp": int(np.ceil(pw.solve_power(effect_size=(d_pp / 100) / sd, alpha=alpha, power=0.8))) for d_pp in (3, 5, 8, 10)}
    return {
        "n_per_arm": n_per_arm,
        "outcome_sd": sd,
        "minimum_detectable_effect_pp": float(mde_d * sd * 100),
        "required_n_per_arm_for_80pct_power": n_for,
    }


def analyse_trial(trial: pd.DataFrame, outcome: str = "report_on_time_rate", n_perm: int = 2000, seed: int = 0) -> dict[str, Any]:
    t, c = trial[trial["arm"] == 1], trial[trial["arm"] == 0]
    diff = t[outcome].mean() - c[outcome].mean()
    w = stats.ttest_ind(t[outcome], c[outcome], equal_var=False)
    se = np.sqrt(t[outcome].var() / len(t) + c[outcome].var() / len(c))
    rng = np.random.default_rng(seed)
    y, a = trial[outcome].to_numpy(), trial["arm"].to_numpy()
    perm = np.array([y[p == 1].mean() - y[p == 0].mean() for p in (rng.permutation(a) for _ in range(n_perm))])
    p_perm = float((np.abs(perm) >= abs(diff)).mean())
    # CUPED: adjust for pre-period behaviour to reduce variance (Deng et al. 2013).
    x = trial["pre_on_time"].to_numpy()
    theta = np.cov(y, x)[0, 1] / np.var(x, ddof=1)
    yc = y - theta * (x - x.mean())
    diff_c = yc[a == 1].mean() - yc[a == 0].mean()
    se_c = np.sqrt(yc[a == 1].var(ddof=1) / (a == 1).sum() + yc[a == 0].var(ddof=1) / (a == 0).sum())
    balance = float(t["pre_on_time"].mean() - c["pre_on_time"].mean())
    return {
        "outcome": outcome,
        "n_treatment": int(len(t)),
        "n_control": int(len(c)),
        "difference_pp": float(diff * 100),
        "ci_pp": [float((diff - 1.96 * se) * 100), float((diff + 1.96 * se) * 100)],
        "welch_p": float(w.pvalue),
        "permutation_p": p_perm,
        "cuped_difference_pp": float(diff_c * 100),
        "cuped_ci_pp": [float((diff_c - 1.96 * se_c) * 100), float((diff_c + 1.96 * se_c) * 100)],
        "variance_reduction": float(1 - (se_c / se) ** 2),
        "pre_period_balance_pp": balance * 100,
    }


def difference_in_differences(
    employees: pd.DataFrame, *, seed: int = 11, true_effect_pp: float = 6.0, weeks: int = 24, rollout_week: int = 12
) -> dict[str, Any]:
    """Quasi-experiment: two business units adopt the coordinator at ``rollout_week``; others do not."""
    rng = np.random.default_rng(seed)
    bus = sorted(employees["business_unit"].unique())
    adopters = set(bus[:2])
    rows = []
    for bu in bus:
        level = rng.normal(0.68, 0.04)
        for w in range(weeks):
            trend = 0.002 * w
            treated = bu in adopters and w >= rollout_week
            rate = level + trend + (true_effect_pp / 100 if treated else 0) + rng.normal(0, 0.02)
            rows.append({"business_unit": bu, "week": w, "adopter": int(bu in adopters), "post": int(w >= rollout_week), "rate": rate})
    df = pd.DataFrame(rows)
    res = smf.ols("rate ~ adopter + adopter:post + C(week)", df).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(df["business_unit"])[0]}
    )
    did = float(res.params["adopter:post"])
    ci = res.conf_int().loc["adopter:post"].tolist()
    pre = df[df["post"] == 0]
    pre_trend = smf.ols("rate ~ adopter * week", pre).fit()
    return {
        "design": f"{len(adopters)} adopting vs {len(bus) - len(adopters)} comparison business units, rollout at week {rollout_week}",
        "did_estimate_pp": did * 100,
        "ci_pp": [ci[0] * 100, ci[1] * 100],
        "pre_trend_difference_per_week_pp": float(pre_trend.params["adopter:week"] * 100),
        "pre_trend_p": float(pre_trend.pvalues["adopter:week"]),
        "caveat": f"Only {len(bus)} clusters: cluster-robust standard errors are unreliable with so few clusters; "
        "treat the interval as indicative.",
    }


def coordinator_experiment(employees: pd.DataFrame, *, seed: int = 7, true_effect_pp: float = 6.0) -> dict[str, Any]:
    trial = simulate_coordinator_trial(employees, seed=seed, true_effect_pp=true_effect_pp)
    sd = float(trial["report_on_time_rate"].std())
    res = {
        "kind": "experimental",
        "status": "exploratory",
        "question": "Does access to the AI coordinator improve on-time status reporting and follow-up completion?",
        "data": "Simulated, consented participants; randomised 1:1 within business unit.",
        "power": power_analysis(sd, int((trial["arm"] == 1).sum())),
        "primary": analyse_trial(trial, "report_on_time_rate"),
        "secondary": analyse_trial(trial, "followups_completed_rate"),
        "quasi_experiment": difference_in_differences(employees, true_effect_pp=true_effect_pp),
        "use_restriction": "Experiment outcomes evaluate the tool, never individual employees.",
        "_synthetic_truth": {"true_effect_pp": true_effect_pp},
    }
    return jsonable(res)
