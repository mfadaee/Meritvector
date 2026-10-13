# Validity framework

Every model and every metric shown to a business user must answer these questions. The model registry
(`meritvector_analytics.research.registry`) refuses to register a model whose specification leaves any of them blank.

| # | Question |
|---|---|
| 1 | What is the research question? |
| 2 | What exactly is the target variable, and how was it defined? |
| 3 | Where does the data come from (sources, dataset version)? |
| 4 | Is the analysis descriptive, predictive or causal? |
| 5 | What assumptions are required? |
| 6 | What is the simplest baseline? |
| 7 | What are the evaluation metrics? |
| 8 | How was leakage prevented? |
| 9 | Is the result stable across samples (CV, bootstrap, seeds)? |
| 10 | What uncertainty remains? |
| 11 | What are the limitations? |
| 12 | What must the result NOT be used for? |

## Evidence types required per construct

| Construct | Content | Convergent / discriminant expectation (synthetic) | Reliability | Fairness |
|---|---|---|---|---|
| Contribution (adjusted delivery) | Covers schedule and quality; not leadership | Correlates with hidden truth more than raw metrics; ~0 or negative with activity volume | ICC from variance components; interval width | Group gaps reported with intervals; assignment differences checked |
| Complexity | 15 PMO dimensions defined | Associated with outcomes; *recorded-only* dimensions act as negative controls (no effect in the generator) | Assessor reliability unmeasured (gap) | Assignment of complex work by group |
| Activity | Defined as context only | Must **not** predict contribution (tested) | n/a | n/a |
| Ratings (label) | n/a — audited | Should track evidence; rater effects tested (H4) | Rater ICC | Rating gaps vs evidence gaps |
| 30-day milestone risk | Project-level only | Beats base-rate and simple baselines out of time | Calibration, bootstrap | Error by business unit/environment |

## Status labels

* **Exploratory** — computed, not pre-registered or not yet validated. Shown with a banner in the Research Laboratory.
* **Validated on synthetic data** — pre-registered test passed and validation requirements met under the simulation.
  This is **not** a claim about real organisations.
* **Externally validated** — reserved for results replicated on consented real data under a pilot protocol. None yet.

## Governance alignment

The framework maps onto NIST AI RMF functions: **Map** (questions, constructs, DAGs), **Measure** (validation suite,
fairness audit, drift), **Manage** (abstention, human review, retention, correction) and **Govern** (governance gate,
audit log, model registry, roles).
