# Research foundation

MeritVector exists to answer one question well:

> How can organisations understand genuine human contribution, performance, growth and capability from reliable
> evidence — rather than from superficial activity indicators or managerial impressions — and know when they cannot?

This document states the scientific commitments that constrain the product. The evidence behind them is in
[LITERATURE_REVIEW](LITERATURE_REVIEW.md); the constructs are defined in [MEASUREMENT_THEORY](MEASUREMENT_THEORY.md)
and [CONSTRUCTS](CONSTRUCTS.md); validity standards are in [VALIDITY_FRAMEWORK](VALIDITY_FRAMEWORK.md).

## Three layers

| Layer | Purpose | Where it lives |
|---|---|---|
| **A. Scientific foundation** | What to measure, why, whether measures are valid, what conclusions evidence can support | `docs/research/`, `research/references/`, `config/measurement/ontology.yaml`, `config/research/` |
| **B. Intelligence & measurement engine** | Turn appropriately collected evidence into contextualised, uncertain, explainable analysis | `packages/analytics/` (features, models, validation, research workstreams, simulation), `config/job_families/` |
| **C. Business product** | Plain-language answers with evidence and uncertainty; advanced detail on request | `apps/api`, `apps/web` |

## Commitments derived from the literature

1. **Performance ≠ results ≠ activity.** Results are contaminated by conditions outside the person's control;
   activity measures busyness and culture. Each is a separate construct with separate indicators.
2. **No single merit score.** Performance is multidimensional; composite scores hide trade-offs and invite gaming.
3. **Context first.** Every person-level reading is accompanied by the conditions of the work and an estimate of
   what those conditions alone predict.
4. **Uncertainty and abstention.** Intervals are always shown; "insufficient evidence" is a legitimate answer.
5. **Ratings are biased labels.** They are audited against evidence; they are never training targets.
6. **Explicit causal reasoning.** Causal language requires a DAG, an adjustment set and a sensitivity analysis;
   otherwise results are labelled associations.
7. **Measurement can change behaviour.** Avoid targets, avoid surveillance, separate assistance from assessment.
8. **Synthetic success is not real-world validity.** Simulation results establish software correctness and method
   behaviour under a known data-generating process — not that the method works in a real organisation.

## Three kinds of correctness (never conflated)

| Kind | Question | Evidence in this repository |
|---|---|---|
| Software correctness | Does the code do what it says? | Unit, integration and API tests |
| Simulation performance | Do the methods recover known truth when assumptions roughly hold? | Ground-truth recovery, scenario lab, validation suite |
| External validity | Do the measures mean anything in a real organisation? | **Not established.** Requires a consented pilot with pre-registered criteria (see product docs). |

## Research workflow

Question (`config/research/questions.yaml`) → hypothesis with pre-specified test (`config/research/hypotheses.yaml`)
→ analysis in `meritvector_analytics.research` → stored run with dataset version, configuration and code version →
labelled **exploratory** until a confirmatory test and validation requirements pass.
