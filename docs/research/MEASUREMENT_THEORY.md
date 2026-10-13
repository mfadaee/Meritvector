# Measurement theory

## From events to constructs

```
raw evidence events  ──►  indicators  ──►  constructs  ──►  interpretations
(system of record)        (metric definitions,    (ontology)     (plain language + uncertainty,
                           config/job_families)                    prohibited uses stated)
```

Each step can introduce error. MeritVector documents it rather than hiding it.

## Classical view and its limits

An observed indicator *X* is modelled as true score plus error, *X = T + E*. For delivery outcomes the "error"
is not just noise: it contains **systematic, construct-irrelevant variance** (Messick 1995) — project complexity,
resourcing, dependencies, team, sponsor and luck. Raw outcome metrics therefore have poor construct validity for
*contribution* even when they are recorded perfectly.

The conceptual model (see [CONSTRUCTS](CONSTRUCTS.md)):

> Observed results = individual contribution + team contribution + organisational environment + project conditions
> + opportunity + random variation + measurement error.

Only some terms are measured. Contextual adjustment removes the *measured* part of the environment and conditions;
mixed models separate stable person-level variance from project-level and residual variance; the rest stays in the
estimate and is reported as uncertainty or as an explicit limitation.

## Reliability

* **Of person-level aggregates.** How consistent is someone's evidence across projects? Reported as ICC(1) and
  ICC(k) (Shrout & Fleiss 1979) from the mixed model's variance components. In the synthetic organisation about
  30% of schedule-variance variance sits between people, so ~6+ milestones are needed before an individual estimate
  is reported.
* **Of ratings.** Supervisory ratings have low interrater reliability (~.52; Viswesvaran 1996) and large rater
  effects (Scullen 2000). Ratings are not used as criteria.
* **Of perception data.** Single-respondent stakeholder surveys are flagged as such and never decide a competency.

## Validity concerns and how the design responds

| Threat | Example | Response |
|---|---|---|
| Construct-irrelevant variance | Hard projects lower raw on-time rates | Context adjustment; context-expected outcome shown |
| Construct under-representation | Leadership leaves few records | Evidence gaps reported as gaps, not deficits |
| Common-method bias | Same stakeholder rates several projects | Source flagged; perception data never stands alone |
| Goodhart / Campbell's law | Optimising task counts | Activity is never merit; no single target metric |
| Selection bias | Strong people assigned harder work | Stated in DAGs; sensitivity to omitted confounding |
| Simpson's paradox | Pooled rates reverse within strata | Stratified views in EDA |
| Regression to the mean | "Improvement" after a bad quarter | Shrinkage, FDR, RTM caveat in trend explanations |
| Non-random missingness | Quality scores missing more on internal projects | Missingness diagnostics; MAR assumption stated |
| Measurement non-invariance | Indicators behave differently across groups | Exploratory indicator-structure comparison in fairness audit |
| Right-censoring | Late milestones not yet observed | 90-day guard (v0.1); survival models planned |

## Composite indicators

v0.2 introduces **no** composite merit index. If a composite is ever proposed it must document its weighting
rationale, show sensitivity of conclusions to weights, report uncertainty, and pass the validity checks in
[VALIDITY_FRAMEWORK](VALIDITY_FRAMEWORK.md).

## Responsibility is not contribution; scale is not performance

Responsibility dimensions (decision authority, budget accountability, teams coordinated, …) describe **scope** so
outcomes are read in proportion. They are recorded, shown, and deliberately **not** used to increase any estimate:
a small project can require exceptional judgement, and a large one can succeed through team support.
