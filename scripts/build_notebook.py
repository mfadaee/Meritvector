"""Build (and optionally execute) the flagship experiment notebook.

python scripts/build_notebook.py            # write the notebook
python scripts/build_notebook.py --execute  # write and execute it in place
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


def build() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in CELLS]
    return nb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    nb = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if args.execute:
        from nbconvert.preprocessors import ExecutePreprocessor

        ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(OUT.parent)}})
    nbf.write(nb, OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
