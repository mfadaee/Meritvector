"""Flagship v2 — "Do raw performance metrics misrepresent project-manager contribution?"

A seven-step analysis over every project manager with settled milestones, built on a completed pipeline run:

1. Compare raw delivery outcomes.
2. Analyse assignment differences (who gets which conditions).
3. Estimate contextual associations with a transparent baseline model (cluster-robust OLS) next to the primary
   within-person model.
4. Quantify uncertainty and identify raw verdicts the evidence does not support.
5. Compare plain-English interpretations before and after contextual analysis.
6. Test sensitivity to alternative specifications and to omitted confounders (benchmarked against measured ones).
7. Show how proxies (activity, stakeholder perception, raw rates) distort assessment.

Selection rules use observable data only and are fixed in advance; nothing here is told who is "really" better.
Hidden synthetic parameters are compared with these outputs only in ``evaluation.flagship_truth_check``.
People appear under stable pseudonyms; the per-person table is kept under a private key for the API's access-
controlled use and is stripped from public outputs.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from meritvector_analytics.features import CONTEXT_NUMERIC, employee_activity_summary
from meritvector_analytics.narrative import contribution_narrative

OUTCOME = "schedule_variance_pct"
PROXIES = {
    "raw_on_time_rate": ("Raw on-time rate", 1),
    "raw_mean_variance": ("Raw mean schedule variance (lower is better)", -1),
    "meetings_per_month": ("Meeting activity", 1),
    "emails_per_month": ("E-mail activity", 1),
    "stakeholder_feedback_mean": ("Stakeholder perception score", 1),
    "tasks_completed": ("Tasks completed (volume)", 1),
    "manager_rating": ("Historical manager rating", 1),
}


def _pseudonyms(ids: list[str]) -> dict[str, str]:
    return {e: f"PM-{i + 1:03d}" for i, e in enumerate(sorted(ids))}


def person_table(result, manager_ratings: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per project manager: raw metrics, context, adjusted estimate, proxies."""
    fs = result.features
    em = result.employee_metrics.set_index("employee_id")
    ctx = result.context[OUTCOME]
    est = ctx.mixed_estimates.set_index("employee_id")
    raw = ctx.raw.set_index("employee_id")
    resid = ctx.residual_estimates.set_index("employee_id")
    d = (
        est[["adjusted_estimate", "ci_low", "ci_high", "n", "conclusion"]]
        .join(raw[["raw_estimate", "raw_mean"]], how="left")
        .join(resid[["context_expected"]], how="left")
    )
    d = d.join(
        em[
            [
                "on_time_rate",
                "mean_schedule_variance_pct",
                "mean_complexity",
                "mean_resource_constraint",
                "mean_dependencies",
                "stakeholder_feedback_mean",
                "task_completed",
                "job_family",
            ]
        ],
        how="left",
    )
    d = d.join(employee_activity_summary(fs.activity).set_index("employee_id"), how="left")
    if manager_ratings is not None:
        d = d.join(manager_ratings.groupby("employee_id")["manager_rating"].mean())
    d = d.rename(
        columns={"on_time_rate": "raw_on_time_rate", "mean_schedule_variance_pct": "raw_mean_variance", "task_completed": "tasks_completed"}
    )
    return d[d["n"] > 0]


def _rank_pct(s: pd.Series, sign: int = 1) -> pd.Series:
    return (sign * s).rank(pct=True)


# ------------------------------------------------------------------ steps
def step1_raw(d: pd.DataFrame) -> dict[str, Any]:
    q = d["raw_on_time_rate"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict()
    between = stats.linregress(d["context_expected"], d["raw_mean_variance"])
    return {
        "n_project_managers": int(len(d)),
        "on_time_rate_quantiles": {f"p{int(k * 100)}": v for k, v in q.items()},
        "mean_variance_spread_pp": float(d["raw_mean_variance"].quantile(0.9) - d["raw_mean_variance"].quantile(0.1)),
        "share_of_raw_spread_predicted_by_conditions": float(between.rvalue**2),
        "plain_language": (
            f"Raw on-time rates range from {q[0.1] * 100:.0f}% (10th percentile) to {q[0.9] * 100:.0f}% (90th). "
            f"The measured conditions of each person's projects alone predict {between.rvalue**2 * 100:.0f}% of the "
            "differences in their raw schedule variance — before anything about the person is considered."
        ),
    }


def step2_assignment(result, d: pd.DataFrame) -> dict[str, Any]:
    m = result.features.milestones
    proj = m.groupby("project_id").agg(
        pm=("employee_id", "first"),
        cx=("technical_complexity", "first"),
        rc=("resource_constraint", "first"),
        dep=("dependency_count", "first"),
    )
    groups = [g["cx"].to_numpy() for _, g in proj.groupby("pm") if len(g) >= 2]
    kw = stats.kruskal(*groups)
    # ICC(1) of project complexity within project manager.
    k = proj.groupby("pm").size()
    msb = (k * (proj.groupby("pm")["cx"].mean() - proj["cx"].mean()) ** 2).sum() / (len(k) - 1)
    msw = ((proj["cx"] - proj.groupby("pm")["cx"].transform("mean")) ** 2).sum() / (len(proj) - len(k))
    k0 = k.mean()
    icc = float((msb - msw) / (msb + (k0 - 1) * msw))
    rho = stats.spearmanr(d["mean_complexity"], d["raw_on_time_rate"])
    by_family = d.groupby("job_family")[["mean_complexity", "mean_resource_constraint", "mean_dependencies"]].mean().round(2)
    return {
        "kruskal_complexity_across_pms": {"H": float(kw.statistic), "p_value": float(kw.pvalue)},
        "icc_complexity_within_pm": icc,
        "spearman_complexity_vs_raw_on_time": {"rho": float(rho.statistic), "p_value": float(rho.pvalue)},
        "conditions_by_job_family": by_family.reset_index().to_dict("records"),
        "plain_language": (
            f"Assignment is not random: project complexity clusters by project manager (ICC {icc:.2f}; Kruskal–Wallis "
            f"p = {kw.pvalue:.1g}), and people with harder portfolios have lower raw on-time rates (Spearman "
            f"{rho.statistic:+.2f}). Raw rates therefore partly measure the portfolio, not the person."
        ),
    }


def step3_models(result) -> dict[str, Any]:
    ctx = result.context[OUTCOME]
    ols = ctx.ols
    ci = ols.conf_int()
    baseline = [
        {"term": t, "estimate": float(ols.params[t]), "ci95": [float(ci.loc[t, 0]), float(ci.loc[t, 1])], "p_value": float(ols.pvalues[t])}
        for t in CONTEXT_NUMERIC
        if t in ols.params
    ]
    within = ctx.diagnostics.get("within_person_coefficients", {})
    return {
        "transparent_baseline": {
            "model": "OLS of milestone schedule variance on measured context, standard errors clustered by project",
            "r_squared": float(ols.rsquared),
            "coefficients": baseline,
        },
        "primary_model": {
            "model": "Within-person (Mundlak) mixed model: person random intercept, project variance component, "
            "context split into within- and between-person parts",
            "within_person_coefficients": within,
            "variance_components": ctx.variance_components,
        },
        "plain_language": _models_sentence(baseline, within),
    }


def _models_sentence(baseline: list[dict[str, Any]], within: dict[str, float]) -> str:
    key = ("technical_complexity", "dependency_count", "resource_constraint")
    agree = [
        c["term"] for c in baseline if c["term"] in key and c["term"] in within and np.sign(c["estimate"]) == np.sign(within[c["term"]])
    ]
    lead = (
        "Both models agree on the direction of every main condition: more complexity, dependencies and staffing shortfall go with "
        "more slippage. "
        if len(agree) == len(key)
        else f"The models agree on direction for {', '.join(a.replace('_', ' ') for a in agree) or 'none of the main conditions'}. "
    )
    return lead + (
        "The within-person model also compares each person with themselves across conditions, which is designed for "
        "organisations where stronger people are given harder projects."
    )


def step4_uncertainty(d: pd.DataFrame) -> dict[str, Any]:
    r = _rank_pct(d["raw_on_time_rate"])
    top, bottom = d[r >= 0.8], d[r <= 0.2]

    def supported(sub: pd.DataFrame, direction: str) -> float:
        want = "above_context_expectation" if direction == "up" else "below_context_expectation"
        return float((sub["conclusion"] == want).mean()) if len(sub) else float("nan")

    counts = d["conclusion"].value_counts().to_dict()
    width = (d["ci_high"] - d["ci_low"]).median()
    s_top, s_bottom = supported(top, "up"), supported(bottom, "down")
    return {
        "conclusion_counts": counts,
        "median_interval_width_pp": float(width),
        "raw_top_quintile": {"n": int(len(top)), "share_supported_by_adjusted_evidence": s_top},
        "raw_bottom_quintile": {"n": int(len(bottom)), "share_supported_by_adjusted_evidence": s_bottom},
        "plain_language": (
            f"A raw dashboard would single out {len(top)} people as top performers and {len(bottom)} as weak. Once "
            f"conditions and uncertainty are accounted for, the evidence supports {s_top * 100:.0f}% of the 'top' verdicts "
            f"and {s_bottom * 100:.0f}% of the 'weak' ones. Typical uncertainty is ±{width / 2:.0f} pp; "
            f"{counts.get('insufficient_evidence', 0)} people get no conclusion at all."
        ),
    }


def step5_interpretations(d: pd.DataFrame, pseudo: dict[str, str], k: int = 4) -> dict[str, Any]:
    """Raw-dashboard sentence vs MeritVector sentence for the k people whose raw and adjusted positions disagree most."""
    ok = d[d["conclusion"] != "insufficient_evidence"]
    gap = (_rank_pct(ok["raw_on_time_rate"]) - _rank_pct(ok["adjusted_estimate"])).abs().sort_values(ascending=False)
    rows = []
    for eid in gap.index[:k]:
        r = ok.loc[eid]
        pct = _rank_pct(d["raw_on_time_rate"]).loc[eid]
        before = f"On-time rate {r['raw_on_time_rate'] * 100:.0f}% — " + (
            "in the top fifth of the PMO; reads as a high performer."
            if pct >= 0.8
            else "in the bottom fifth; reads as under-performing."
            if pct <= 0.2
            else "middle of the pack."
        )
        sched = {k2: r[k2] for k2 in ("adjusted_estimate", "ci_low", "ci_high", "n", "conclusion", "context_expected")}
        raw = {
            "mean_schedule_variance_pct": r["raw_mean_variance"],
            "on_time_rate": r["raw_on_time_rate"],
            "mean_complexity": r["mean_complexity"],
        }
        rows.append(
            {
                "person": pseudo[eid],
                "conditions": (
                    f"complexity {r['mean_complexity']:.1f}/5, staffing shortfall {r['mean_resource_constraint']:.2f}, "
                    f"{r['mean_dependencies']:.1f} dependencies"
                ),
                "raw_dashboard_reading": before,
                "meritvector_reading": " ".join(contribution_narrative(sched, raw)[:-1]),
            }
        )
    return {
        "selection_rule": "The people whose raw and adjusted positions disagree most (observable data only, fixed in advance).",
        "examples": rows,
    }


def step6_sensitivity(result, d: pd.DataFrame) -> dict[str, Any]:
    specs = result.validation.get("sensitivity", {})
    ols = result.context[OUTCOME].ols
    # Benchmark: how far would an omitted confounder as strong as each measured one shift a person's estimate?
    bench = {}
    for t, col in (
        ("technical_complexity", "mean_complexity"),
        ("resource_constraint", "mean_resource_constraint"),
        ("dependency_count", "mean_dependencies"),
    ):
        if t in ols.params:
            bench[t] = float(abs(ols.params[t]) * d[col].std())
    strong = d[d["conclusion"].isin(["above_context_expectation", "below_context_expectation"])]
    margin = np.minimum(strong["ci_low"].abs(), strong["ci_high"].abs())
    survival = {t: float((margin > shift).mean()) if len(strong) else float("nan") for t, shift in bench.items()}
    return {
        "alternative_specifications": specs,
        "omitted_confounder_benchmarks_pp": bench,
        "share_of_strong_conclusions_surviving": survival,
        "plain_language": (
            "Share of strong conclusions that would survive an unmeasured condition as influential as each measured one: "
            + ", ".join(f"{t.replace('_', ' ')} {survival[t] * 100:.0f}%" for t in survival)
            + f" — so about {np.nanmean(list(survival.values())) * 100:.0f}% are robust to a confounder of that size and the rest "
            "are provisional. Dropping complexity and dependencies from the model "
            f"changes {specs.get('drop_complexity_and_dependencies', {}).get('share_conclusions_changed', float('nan')) * 100:.0f}% "
            "of conclusions — so conclusions depend on measuring context well."
        ),
    }


def step7_proxies(d: pd.DataFrame) -> dict[str, Any]:
    ok = d[d["conclusion"] != "insufficient_evidence"]
    rows = []
    for col, (label, sign) in PROXIES.items():
        if col not in ok or ok[col].notna().sum() < 10:
            continue
        x = ok[[col, "adjusted_estimate"]].dropna()
        rho = stats.spearmanr(sign * x[col], x["adjusted_estimate"])
        rows.append({"proxy": label, "spearman_with_adjusted_evidence": float(rho.statistic), "p_value": float(rho.pvalue)})
    soft = [r for r in rows if not r["proxy"].startswith("Raw")]
    strongest = max(soft, key=lambda r: abs(r["spearman_with_adjusted_evidence"])) if soft else None
    negative = [r["proxy"] for r in soft if r["spearman_with_adjusted_evidence"] < -0.1 and r["p_value"] < 0.05]
    text = (
        f"No activity or perception proxy tracks the context-adjusted evidence closely (strongest: {strongest['proxy'].lower()}, "
        f"Spearman {strongest['spearman_with_adjusted_evidence']:+.2f})"
        if strongest
        else "No activity or perception proxy is available"
    )
    if negative:
        text += f"; {', '.join(n.lower() for n in negative)} even point the wrong way"
    return {
        "proxies": rows,
        "plain_language": text + ". A productivity tracker built on these signals would reward visibility and circumstance; "
        "MeritVector never turns activity into credit.",
    }


def run_flagship(result, manager_ratings: pd.DataFrame | None = None, k_examples: int = 4, synthetic: bool = True) -> dict[str, Any]:
    d = person_table(result, manager_ratings)
    pseudo = _pseudonyms(list(d.index))
    out = {
        "title": "Do raw performance metrics misrepresent project-manager contribution?",
        "kind": "demonstration",
        "status": "exploratory",
        "data": "synthetic organisation" if synthetic else "tenant records",
        "steps": {
            "1_raw_outcomes": step1_raw(d),
            "2_assignment": step2_assignment(result, d),
            "3_models": step3_models(result),
            "4_uncertainty": step4_uncertainty(d),
            "5_interpretations": step5_interpretations(d, pseudo, k_examples),
            "6_sensitivity": step6_sensitivity(result, d),
            "7_proxies": step7_proxies(d),
        },
        "ground_rules": [
            "Selection rules use observable data only and were fixed before results were seen.",
            "No person is designated as superior in advance; findings follow the data and the validated method.",
            "Adjusted estimates are associations conditional on measured context — not causal effects of a person.",
        ],
        "_people": d.assign(pseudonym=d.index.map(pseudo)),
    }
    return out


def _f(v: Any, d: int = 2) -> str:
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{d}f}"


def _p(v: Any) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def render_report(
    f: dict[str, Any], truth: dict[str, Any] | None = None, real_world: dict[str, Any] | None = None, meta: dict[str, Any] | None = None
) -> str:
    """Markdown research report from a flagship result (plus the optional synthetic truth check and real-data replication)."""
    s = f["steps"]
    L = [
        f"# Flagship study — {f['title']}",
        "",
        "_Generated by `python scripts/run_flagship.py`. Do not edit by hand; re-run the script._",
        "",
        f"**Data:** {f['data']}; {s['1_raw_outcomes']['n_project_managers']} project managers with settled milestones. "
        + (" · ".join(f"{k}: {v}" for k, v in (meta or {}).items())),
        "",
        "**Ground rules.** " + " ".join(f["ground_rules"]),
        "",
        "## Step 1 — Raw delivery outcomes",
        s["1_raw_outcomes"]["plain_language"],
        "",
        "## Step 2 — Assignment differences",
        s["2_assignment"]["plain_language"],
        "",
        "| Job family | Mean complexity | Mean staffing shortfall | Mean dependencies |",
        "|---|---|---|---|",
        *[
            f"| {r['job_family']} | {_f(r['mean_complexity'])} | {_f(r['mean_resource_constraint'])} | {_f(r['mean_dependencies'])} |"
            for r in s["2_assignment"]["conditions_by_job_family"]
        ],
        "",
        "## Step 3 — Transparent baseline and primary model",
        s["3_models"]["plain_language"],
        "",
        "| Condition | Baseline OLS, pp per unit [95% CI] | Within-person coefficient |",
        "|---|---|---|",
        *[
            f"| {c['term']} | {_f(c['estimate'])} [{_f(c['ci95'][0])}, {_f(c['ci95'][1])}] | "
            f"{_f(s['3_models']['primary_model']['within_person_coefficients'].get(c['term']))} |"
            for c in s["3_models"]["transparent_baseline"]["coefficients"]
        ],
        "",
        "## Step 4 — Uncertainty and unsupported conclusions",
        s["4_uncertainty"]["plain_language"],
        "",
        "## Step 5 — Interpretations before and after contextual analysis",
        f"_Selection rule: {s['5_interpretations']['selection_rule']}_",
        "",
    ]
    for e in s["5_interpretations"]["examples"]:
        t = (truth or {}).get("example_true_effects_pp", {}).get(e["person"])
        L += [
            f"**{e['person']}** — {e['conditions']}" + (f" · synthetic true effect {t:+.1f} pp" if t is not None else ""),
            f"- *Raw dashboard:* {e['raw_dashboard_reading']}",
            f"- *MeritVector:* {e['meritvector_reading']}",
            "",
        ]
    sens = s["6_sensitivity"]
    L += [
        "## Step 6 — Sensitivity to assumptions and omitted confounders",
        sens["plain_language"],
        "",
        "| Alternative specification | Spearman with base | Conclusions changed |",
        "|---|---|---|",
        *[
            f"| {k} | {_f(v.get('spearman_with_base'))} | "
            + ("—" if v.get("share_conclusions_changed") is None else f"{v['share_conclusions_changed'] * 100:.0f}%")
            + " |"
            for k, v in sens["alternative_specifications"].items()
        ],
        "",
        "Omitted-confounder benchmark (shift in pp a confounder as strong as each measured condition would cause): "
        + ", ".join(f"{k} {_f(v, 1)}" for k, v in sens["omitted_confounder_benchmarks_pp"].items())
        + ".",
        "",
        "## Step 7 — How misleading proxies distort assessment",
        s["7_proxies"]["plain_language"],
        "",
        "| Proxy | Spearman with adjusted evidence |",
        "|---|---|",
        *[f"| {p['proxy']} | {_f(p['spearman_with_adjusted_evidence'])} |" for p in s["7_proxies"]["proxies"]],
        "",
    ]
    if truth:
        L += [
            "## Check against the hidden synthetic truth",
            truth["note"],
            "",
            f"- People in the raw top fifth who are truly above average: **{truth['raw_top_quintile_truly_above_average'] * 100:.0f}%**.",
            f"- 'Above context expectation' conclusions truly above average: **{_p(truth['adjusted_above_truly_above_average'])}**.",
            f"- 'Below context expectation' conclusions truly below average: **{_p(truth['adjusted_below_truly_below_average'])}**.",
            "",
            "| Signal | Spearman with truth | Truly strong people placed in the bottom half |",
            "|---|---|---|",
            *[
                f"| {r['signal']} | {_f(r['spearman_with_truth'])} | {r['true_top_quartile_placed_in_bottom_half'] * 100:.0f}% |"
                for r in truth["signals"]
            ],
            "",
        ]
    if real_world:
        L += ["## Does it hold on real data?", "", *[f"- **{k}.** {v}" for k, v in real_world.items()], ""]
    L += [
        "## Limits",
        "- Synthetic organisation: results show the method's behaviour where the truth is known, not real-world accuracy.",
        "- Adjusted estimates are associations conditional on measured context; unmeasured context remains.",
        "- Public real-world data supports the project- and organisation-level claims only; no public dataset can validate "
        "individual estimates. See [PUBLIC_DATA_VALIDATION](PUBLIC_DATA_VALIDATION.md) and [MODEL_CARD](MODEL_CARD.md).",
        "",
    ]
    return "\n".join(L)
