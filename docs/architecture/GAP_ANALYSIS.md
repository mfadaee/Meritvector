# Phase 2 gap analysis

State of `main` at the start of Phase 2 (merge `75e286a`) mapped against the Phase 2 requirements.
**Have** = working and tested in v0.1. **Gap** = missing. **Plan** = the smallest implementation that closes it.

| Requirement | Have (v0.1) | Gap | Plan (Phase 2) |
|---|---|---|---|
| Research foundation & literature | Model card, metrics framework | No evidence library, ontology, hypotheses | Verified library (JSON + rendered docs), ontology YAML, registered questions/hypotheses, validity framework — **WP-A** |
| Measurement ontology (9 constructs) | Implicit in code | Not defined | `config/measurement/ontology.yaml` + typed loader + generated construct reference — **WP-A** |
| PMO domain model (15/10/10 dimensions) | 7 context fields | Responsibility and most outcome dimensions missing | PMO spec with status per dimension; generator adds recorded dimensions via a separate RNG stream (negative controls) — **WP-A/B** |
| Job-family extensibility | PMO hard-coded | No schema | Versioned `JobFamilySpec` + JSON Schema; PMO + illustrative engineering family; context model reads covariates from spec — **WP-A** |
| EDA, hypothesis tests | Descriptive metrics only | No registered tests, effect sizes, multiplicity | `research.eda`, `research.hypotheses` executing the YAML — **WP-B** |
| Regression comparison | OLS + mixed | No regularised/GLM/interaction comparison | `research.regression` with grouped CV — **WP-B** |
| Classification | Calibration of P(slip>10%) | No valid prediction target | 30-day milestone risk from point-in-time snapshots, imbalance and threshold analysis — **WP-B** |
| Clustering & PCA | — | Missing | Project-environment clusters with bootstrap stability — **WP-B** |
| Longitudinal | Per-person trends (under-powered) | No growth model | Random-slope growth model + recovery check — **WP-B** |
| Causal reasoning | Disclaimers | No DAGs | DAG specs, adjustment sets, E-values/robustness values — **WP-B** |
| Experiment design | — | Missing | Simulated randomised coordinator experiment, power analysis, CUPED, DiD — **WP-B** |
| Scenario lab A–F | Archetypes in one dataset | No targeted scenarios | `simulations.scenarios` — six reproducible scenarios with hidden truth — **WP-B** |
| Model registry, dataset versioning, experiment tracking | `model_runs`, artifact dirs | No registry spec, no research run history | `research_runs`, `dataset_versions`, `model_registry` tables + mandatory specs — **WP-B** |
| Research Laboratory UI | — | Missing | New page with real computed outputs, exploratory labels, reproduce & export — **WP-C** |
| Plain-English explanations, "How was this assessed?" | Technical labels | Missing | Narrative layer from computed values + metric definitions from spec — **WP-C** |
| Evidence chains & attribution | Flat events | No linkage | Risk→mitigation→milestone chains with provenance and manual attribution — **WP-C** |
| Knowledge retrieval | — | Missing | TF-IDF search over the user's accessible meetings/decisions/projects — **WP-C** |
| Flagship v2 (multi-PM, 7 steps) | Two-person experiment | Not multi-person, no proxy distortion step | Script + report + notebook + dashboard + tests — **WP-D** |
| Product/commercial docs | Vision, roadmap | PRD, personas, MVP scope, strategy, pricing hypotheses | **WP-D** |
| Research role | 4 roles | No researcher role | `researcher` role, pseudonymised research access — **WP-C** |
