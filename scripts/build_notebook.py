"""Build (and optionally execute) the flagship notebooks.

python scripts/build_notebook.py                    # write both notebooks
python scripts/build_notebook.py --execute          # write and execute them in place
python scripts/build_notebook.py --only v2 --execute
"""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).resolve().parents[1] / "experiments" / "notebooks" / "flagship_context_experiment.ipynb"

CELLS = [
    (
        "md",
        """# Flagship experiment — does context change how we read two delivery records?

**All data in this notebook is synthetic.** It is generated with a fixed seed by `meritvector_analytics.synthetic`.

**Question.** Two employees deliver different projects. Employee A works on relatively simple, well-resourced projects
and is consistently on time. Employee B works on complex, constrained, dependency-heavy projects with more schedule
variability. What do raw metrics say, what does a context-adjusted model say, how uncertain is it, and how sensitive
is the answer to modelling assumptions?

**Ground rules.**
* A and B are chosen from *observable* data by a rule fixed in advance — never from hidden ground truth.
* No winner is predetermined. If the evidence is inadequate or assumptions fail, the notebook says so.
* Adjusted estimates are associations conditional on measured context, not causal effects of a person.""",
    ),
    (
        "code",
        """import warnings
warnings.filterwarnings("ignore")
import json
import numpy as np
import pandas as pd
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)

from meritvector_analytics.synthetic import SyntheticConfig, generate
from meritvector_analytics.features import build_features
from meritvector_analytics.contextual import run_contextual
from meritvector_analytics.validation import sensitivity
from meritvector_analytics.experiment import run_experiment

SEED = 20261013
data = generate(SyntheticConfig(seed=SEED))
data.metadata["counts"]""",
    ),
    (
        "md",
        """## 1. Evidence → engineered features
Only validated `assessment_evidence` records are used. Milestones planned within 90 days of the as-of date are excluded
(right-censoring: recent late milestones are not yet observable, so the recent sample is optimistically biased).""",
    ),
    (
        "code",
        """fs = build_features(data.events, data.employees, data.config.as_of)
m = fs.milestones
print(f"{len(m)} achieved milestones, {m.employee_id.nunique()} employees, {m.project_id.nunique()} projects; "
      f"{fs.censored_excluded} recent milestones excluded for censoring")
m[["technical_complexity", "dependency_count", "resource_constraint", "scope_changes_to_date", "team_size",
   "schedule_variance_pct", "quality_score"]].describe().round(2)""",
    ),
    ("md", "## 2. How much do operating conditions matter? (context OLS, project-clustered SEs)"),
    (
        "code",
        """ctx = run_contextual(m, "schedule_variance_pct")
print(f"R² of context alone: {ctx.ols.rsquared:.3f}")
ctx.coefficients.round(3)""",
    ),
    (
        "code",
        """print("Variance decomposition (mixed model):", {k: round(v, 3) for k, v in ctx.variance_components.items()})
print("Assumption diagnostics:", {k: v for k, v in ctx.diagnostics.items() if k != "fit_warnings"})""",
    ),
    ("md", "## 3. Select A and B (fixed rule, observable data only) and run the experiment"),
    (
        "code",
        """sens = sensitivity(m, ctx.mixed_estimates)
exp = run_experiment(m, ctx, sens["per_spec"], fs.employees)
print(exp["selection_rule"])
print("A =", exp["employees"]["A"], "| B =", exp["employees"]["B"])""",
    ),
    ("md", "### 3.1 Raw performance metrics"),
    ("code", "pd.DataFrame(exp['raw_metrics']).round(3)"),
    ("md", "### 3.2 Differences in operating conditions"),
    ("code", "pd.DataFrame(exp['operating_conditions']).round(2)"),
    (
        "md",
        "### 3.3 Context-adjusted estimates with 95% intervals\n(pp of schedule variance; positive = less slippage)",
    ),
    ("code", """pd.DataFrame(exp["adjusted_estimates"]).T"""),
    ("code", """print("Cluster-bootstrap B−A difference:", exp["difference_bootstrap"])"""),
    ("md", "### 3.4 Sensitivity to modelling assumptions"),
    ("code", "pd.DataFrame(exp['sensitivity']).round(2)"),
    (
        "code",
        """print("Common support:", exp["common_support"])
print("Spec-level agreement with the base model across all employees:")
pd.DataFrame(sens["specifications"]).T.round(3)""",
    ),
    ("md", "## 4. Verdict"),
    (
        "code",
        """print(exp["adjustment_summary"])
print()
print("STATUS:", exp["status"])
print(exp["verdict"])
print()
print(exp["why_raw_can_mislead"])""",
    ),
    (
        "md",
        """## 5. Synthetic ground-truth check (evaluation only)
Possible only because the data is synthetic. The hidden parameters are read *after* the analysis and were never
available to any model.""",
    ),
    (
        "code",
        """gt = data.ground_truth.set_index("employee_id")
mm = m[["employee_id", "month_index"]].join(gt[["true_contribution", "growth_per_year"]], on="employee_id")
mm["skill_t"] = mm.true_contribution + mm.growth_per_year * mm.month_index / 12
truth = mm.groupby("employee_id").skill_t.mean()
true_effect = 8.0 * (truth - truth.mean())  # generator coefficient: 8 pp per unit of latent contribution
a, b = exp["employees"]["A"], exp["employees"]["B"]
print(pd.DataFrame({"archetype (hidden)": gt.loc[[a, b], "archetype"].values,
                    "true effect (pp)": true_effect.loc[[a, b]].round(2).values,
                    "adjusted estimate": [exp["adjusted_estimates"][k]["adjusted_estimate"] for k in "AB"]}, index=["A", "B"]))
est = ctx.mixed_estimates.set_index("employee_id")
raw = ctx.raw.set_index("employee_id")
print("Spearman(truth, adjusted) =", round(truth.corr(est.adjusted_estimate, method="spearman"), 3))
print("Spearman(truth, raw)      =", round(truth.corr(raw.raw_estimate, method="spearman"), 3))""",
    ),
    (
        "md",
        """**Reading the check.** If the verdict was *inconclusive* while the hidden truth shows a difference, that is the
system working as intended: the evidence for these two people (few milestones, little overlap in conditions) was not
strong enough to support a confident individual comparison, even though adjustment moved the estimates in the right
direction across the population.""",
    ),
    ("md", "## 6. Reproducibility"),
    (
        "code",
        """again = run_experiment(m, ctx, sens["per_spec"], fs.employees)
assert json.dumps(again, sort_keys=True, default=str) == json.dumps(exp, sort_keys=True, default=str)
data2 = generate(SyntheticConfig(seed=SEED))
assert data2.events.equals(data.events)
print("Reproducible: identical data and identical experiment output for seed", SEED)""",
    ),
]


OUT_V2 = OUT.with_name("flagship_v2_raw_metrics_vs_contribution.ipynb")

CELLS_V2 = [
    (
        "md",
        """# Flagship v2 — do raw performance metrics misrepresent project-manager contribution?

**All data in the first part is synthetic** (fixed seed). Every project manager with settled milestones is included.
The seven steps follow the study protocol: raw outcomes → assignment → transparent and primary models → uncertainty →
interpretations before/after → sensitivity and omitted confounders → misleading proxies. Hidden synthetic parameters
are read only at the end, by the evaluation harness, to check the method. The last part repeats the key comparison on
**public real-world project data** when it has been fetched (`python scripts/fetch_public_data.py`).

Ground rules: selection rules use observable data only and are fixed in advance; nobody is designated as superior;
adjusted estimates are associations, not causal effects of a person.""",
    ),
    (
        "code",
        """import warnings
warnings.filterwarnings("ignore")
import pandas as pd
pd.set_option("display.width", 140)
from meritvector_analytics.synthetic import generate
from meritvector_analytics.pipeline import run_pipeline
from meritvector_analytics.flagship import run_flagship

ds = generate()
result = run_pipeline(ds.events, ds.employees, str(ds.config.as_of), manager_ratings=ds.manager_ratings,
                      promotions=ds.promotions, protected_attributes=ds.protected_attributes, n_boot=100)
f = run_flagship(result, ds.manager_ratings)
steps = f["steps"]
print(f["title"]); print(len(f["_people"]), "project managers")""",
    ),
    ("md", "## Step 1 — Raw delivery outcomes"),
    (
        "code",
        """print(steps["1_raw_outcomes"]["plain_language"])
pd.Series(steps["1_raw_outcomes"]["on_time_rate_quantiles"], name="raw on-time rate")""",
    ),
    ("md", "## Step 2 — Who gets which conditions"),
    (
        "code",
        """print(steps["2_assignment"]["plain_language"])
pd.DataFrame(steps["2_assignment"]["conditions_by_job_family"])""",
    ),
    ("md", "## Step 3 — Transparent baseline (cluster-robust OLS) and the primary within-person model"),
    (
        "code",
        """print(steps["3_models"]["plain_language"])
b = pd.DataFrame(steps["3_models"]["transparent_baseline"]["coefficients"]).set_index("term")
b["within_person"] = pd.Series(steps["3_models"]["primary_model"]["within_person_coefficients"])
b""",
    ),
    ("md", "## Step 4 — Uncertainty and unsupported conclusions"),
    (
        "code",
        """print(steps["4_uncertainty"]["plain_language"])
pd.Series(steps["4_uncertainty"]["conclusion_counts"], name="people")""",
    ),
    ("md", "## Step 5 — The same records, read before and after contextual analysis"),
    (
        "code",
        """print("Selection rule:", steps["5_interpretations"]["selection_rule"], "\\n")
for e in steps["5_interpretations"]["examples"]:
    print(e["person"], "|", e["conditions"])
    print("  raw dashboard:", e["raw_dashboard_reading"])
    print("  MeritVector:  ", e["meritvector_reading"], "\\n")""",
    ),
    ("md", "## Step 6 — Sensitivity to assumptions and omitted confounders"),
    (
        "code",
        """print(steps["6_sensitivity"]["plain_language"])
pd.DataFrame(steps["6_sensitivity"]["alternative_specifications"]).T""",
    ),
    ("md", "## Step 7 — How misleading proxies distort assessment"),
    (
        "code",
        """print(steps["7_proxies"]["plain_language"])
pd.DataFrame(steps["7_proxies"]["proxies"])""",
    ),
    (
        "md",
        """## Check against the hidden synthetic truth (evaluation only)

Possible only because the organisation is synthetic. The hidden parameters were not used anywhere above.""",
    ),
    (
        "code",
        """from meritvector_analytics.evaluation import flagship_truth_check
t = flagship_truth_check(result, f, ds.ground_truth)
print(f"Raw top fifth truly above average: {t['raw_top_quintile_truly_above_average']:.0%}")
print(f"'Above expectation' conclusions truly above average: {t['adjusted_above_truly_above_average']:.0%}")
print("True effects of the step-5 examples (pp):", {k: round(v, 1) for k, v in t["example_true_effects_pp"].items()})
pd.DataFrame(t["signals"])""",
    ),
    ("md", "## Does it hold on real data? (public project datasets)"),
    (
        "code",
        """from meritvector_analytics.public_data import sources
if all(s.available for k, s in sources().items() if k in ("ebspm", "desharnais")):
    from meritvector_analytics.public_data.studies import desharnais, ebspm
    e = ebspm(n_boot=100)
    print(e["plain_language"], "\\n")
    print(desharnais(n_boot=500)["plain_language"])
    team = e["results"]["log_cost_per_fp"]["team_indicators"]
    display(pd.DataFrame({k: {"raw %": v["raw_pct"], "adjusted %": v["adjusted_pct"]} for k, v in team.items()}).T.round(1))
else:
    print("Public datasets not fetched — run: python scripts/fetch_public_data.py")""",
    ),
    (
        "md",
        """## Reading the result

Raw metrics mostly describe the portfolio a person was given. Adjusting for measured conditions — and saying "no
conclusion" when the evidence is thin — changes most raw verdicts, and the adjusted reading tracks the (synthetic)
truth far better than raw rates, activity, perception scores or historical ratings. On real projects the same
distortion appears for team indicators. None of this validates individual estimates in a real organisation; that
requires a governed pilot.""",
    ),
]


def build(cells: list[tuple[str, str]] | None = None) -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in (cells or CELLS)]
    return nb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--only", choices=["v1", "v2"])
    args = ap.parse_args()
    for name, cells, out in (("v1", CELLS, OUT), ("v2", CELLS_V2, OUT_V2)):
        if args.only and args.only != name:
            continue
        nb = build(cells)
        out.parent.mkdir(parents=True, exist_ok=True)
        if args.execute:
            from nbconvert.preprocessors import ExecutePreprocessor

            ExecutePreprocessor(timeout=1200, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(out.parent)}})
        nbf.write(nb, out)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
