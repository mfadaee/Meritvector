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
            .agg(n=("truth", "size"), mean_raw=("raw_estimate", "mean"), mean_adjusted=("adjusted_estimate", "mean"),
                 mean_true_effect=("true_effect", "mean"))
            .round(2).reset_index().to_dict("records")
        ),
        "note": "Evaluation only — hidden synthetic parameters never enter training features.",
    }
    exp = result.experiment
    a, b = exp["employees"]["A"], exp["employees"]["B"]
    report["experiment_truth"] = {"A_true_effect": float(d.loc[a, "true_effect"]), "B_true_effect": float(d.loc[b, "true_effect"]),
                                  "A_archetype": str(d.loc[a, "archetype"]), "B_archetype": str(d.loc[b, "archetype"])}
    return report
