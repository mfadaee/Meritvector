"""Synthetic ground-truth evaluation harness.

This module is the *only* place that reads hidden ground truth, and it does so only
after a model has been trained, to measure how well the estimates recover the known
data-generating parameters. It is never imported by the training pipeline (a test
enforces this).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

# Effect of one unit of latent contribution on schedule variance in the generator.
GENERATOR_SCHEDULE_COEF = 8.0


def recovery_report(result, ground_truth: pd.DataFrame, manager_ratings: pd.DataFrame | None = None) -> dict[str, Any]:
    m = result.features.milestones
    est = result.estimates[result.estimates["outcome"] == "schedule_variance_pct"].set_index("employee_id")
    gt = ground_truth.set_index("employee_id")
    # True contribution averaged over the times the person's milestones were planned.
    mm = m[["employee_id", "month_index"]].join(gt[["true_contribution", "growth_per_year"]], on="employee_id")
    mm["skill_t"] = mm["true_contribution"] + mm["growth_per_year"] * mm["month_index"] / 12
    true_avg = mm.groupby("employee_id")["skill_t"].mean()
    d = est.join(true_avg.rename("truth"), how="inner").join(gt[["archetype", "activity_propensity"]])
    if manager_ratings is not None:
        d = d.join(manager_ratings.groupby("employee_id")["manager_rating"].mean().rename("rating"))
    d["true_effect"] = GENERATOR_SCHEDULE_COEF * (d["truth"] - d["truth"].mean())

    def rho(col: str) -> float:
        x = d[[col, "truth"]].dropna()
        return float(stats.spearmanr(x[col], x["truth"]).statistic)

    enough = d[d["conclusion"] != "insufficient_evidence"]
    covered = ((enough["true_effect"] >= enough["ci_low"]) & (enough["true_effect"] <= enough["ci_high"])).mean()
    strong = enough[enough["conclusion"].isin(["above_context_expectation", "below_context_expectation"])]
    correct_sign = (np.sign(strong["adjusted_estimate"]) == np.sign(strong["true_effect"])).mean() if len(strong) else np.nan
    report = {
        "spearman_truth_vs_adjusted": rho("adjusted_estimate"),
        "spearman_truth_vs_raw": rho("raw_estimate"),
        "spearman_truth_vs_manager_rating": rho("rating") if "rating" in d else None,
        "spearman_truth_vs_activity": rho("activity_propensity"),
        "interval_coverage_of_true_effect": float(covered),
        "directional_accuracy_of_strong_conclusions": float(correct_sign),
        "n_strong_conclusions": int(len(strong)),
        "n_evaluated": int(len(d)),
        "by_archetype": (
            d.groupby("archetype")
            .agg(
                n=("truth", "size"),
                mean_raw=("raw_estimate", "mean"),
                mean_adjusted=("adjusted_estimate", "mean"),
                mean_true_effect=("true_effect", "mean"),
            )
            .round(2)
            .reset_index()
            .to_dict("records")
        ),
        "note": "Evaluation only — hidden synthetic parameters never enter training features.",
    }
    exp = result.experiment
    if exp.get("status") == "insufficient_data":
        return report
    a, b = exp["employees"]["A"], exp["employees"]["B"]
    report["experiment_truth"] = {
        "A_true_effect": float(d.loc[a, "true_effect"]),
        "B_true_effect": float(d.loc[b, "true_effect"]),
        "A_archetype": str(d.loc[a, "archetype"]),
        "B_archetype": str(d.loc[b, "archetype"]),
    }
    return report


def flagship_truth_check(result, flagship: dict[str, Any], ground_truth: pd.DataFrame) -> dict[str, Any]:
    """Compare the flagship's signals with hidden synthetic contribution — evaluation only, after modelling."""
    from meritvector_analytics.flagship import PROXIES

    m = result.features.milestones
    gt = ground_truth.set_index("employee_id")
    mm = m[["employee_id", "month_index"]].join(gt[["true_contribution", "growth_per_year"]], on="employee_id")
    mm["skill_t"] = mm["true_contribution"] + mm["growth_per_year"] * mm["month_index"] / 12
    people = flagship["_people"].join(mm.groupby("employee_id")["skill_t"].mean().rename("truth"), how="inner")
    people["true_effect"] = GENERATOR_SCHEDULE_COEF * (people["truth"] - people["truth"].mean())
    true_top = people["truth"] >= people["truth"].quantile(0.75)

    signals = {"adjusted_estimate": ("MeritVector context-adjusted estimate", 1), **PROXIES}
    rows = []
    for col, (label, sign) in signals.items():
        if col not in people or people[col].notna().sum() < 10:
            continue
        x = people[[col, "truth"]].dropna()
        rho = stats.spearmanr(sign * x[col], x["truth"]).statistic
        pct = (sign * people[col]).rank(pct=True)
        misplaced = float((pct[true_top] < 0.5).mean())
        rows.append({"signal": label, "spearman_with_truth": float(rho), "true_top_quartile_placed_in_bottom_half": misplaced})
    raw_pct = people["raw_on_time_rate"].rank(pct=True)
    top_raw = people[raw_pct >= 0.8]
    above = people[people["conclusion"] == "above_context_expectation"]
    below = people[people["conclusion"] == "below_context_expectation"]
    examples = {
        e["person"]: float(people.loc[people["pseudonym"] == e["person"], "true_effect"].iloc[0])
        for e in flagship["steps"]["5_interpretations"]["examples"]
    }
    return {
        "signals": rows,
        "raw_top_quintile_truly_above_average": float((top_raw["true_effect"] > 0).mean()),
        "adjusted_above_truly_above_average": float((above["true_effect"] > 0).mean()) if len(above) else None,
        "adjusted_below_truly_below_average": float((below["true_effect"] < 0).mean()) if len(below) else None,
        "example_true_effects_pp": examples,
        "note": "Evaluation only — possible because the organisation is synthetic. Hidden parameters never entered the analysis.",
    }
