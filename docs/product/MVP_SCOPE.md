# MVP scope and pilot plan

## What the MVP is

A single-tenant PMO edition that a delivery organisation could pilot on its own project register and work records,
with assessment features switched off until governance approval. Capability decisions follow
[PRIORITISATION](../PRIORITISATION.md) (NOW / RESEARCH / LATER).

| In scope (exists in v0.2) | Out of scope until a pilot shows value |
|---|---|
| Portfolio, risk and bottleneck analytics; 30-day milestone-risk early warning | Production connectors beyond the mock interfaces; SSO |
| Context-adjusted delivery evidence with intervals and abstention | Composite scores, rankings, pay or promotion outputs (never in scope) |
| Plain-English narratives, "How was this assessed?", evidence chains, contribution accounts | LLM-generated explanations |
| Employee workspace and coordinator (deterministic) | Additional job families beyond PMO/TPM |
| Governance gate, audit log, fairness audit, correction workflow | Cross-tenant benchmarking (models do not transfer — see public-data findings) |
| Research Laboratory, flagship study, public-data validation | |

## Demo readiness

A business demonstration can run today on the synthetic organisation. The suggested order:

1. Overview
2. Project Portfolio
3. Flagship Study
4. Employee detail, showing "How was this assessed?"
5. Contribution Evidence
6. Research Laboratory, *Real-world data* tab

Everything shown is labelled synthetic, except the public-data studies, which are labelled real and project-level.

## Pilot design (proposal)

| Item | Proposal |
|---|---|
| Duration | 12 weeks: 2 weeks setup and governance, 10 weeks running |
| Scope | One PMO with at least 30 project managers and at least 100 projects with milestone history. Aggregated analytics first; person-level views only after governance approval and works-council agreement. |
| Data | Project register (complexity assessment, dependencies, staffing), milestone plan vs actual, RAID log, change log. No e-mail or chat content. |
| Comparison | Staggered rollout of coordinator features across teams, to estimate time savings (difference-in-differences or randomised by team). |
| Governance | Administrator and HR approval, published notice, employee access and correction, retention settings, legal review. |

## Pilot success criteria

These are defined before the pilot starts and measured, not asserted.

| # | Criterion | Measure | Threshold (proposed) |
|---|---|---|---|
| S1 | Context data quality | Share of projects with a complete kick-off complexity assessment; inter-rater agreement on a double-scored sample | ≥ 80% complete; weighted κ ≥ 0.6 |
| S2 | Model validity in this organisation | Out-of-time error of the context model vs a global-mean baseline, on the pilot's own data | Context model beats the baseline, with the gap's interval excluding zero |
| S3 | Early warning value | PR-AUC of the 30-day milestone-risk model vs base rate, out of time | PR-AUC ≥ 1.5× base rate |
| S4 | Usefulness to delivery leads | Decisions or escalations attributed to the analytics, recorded in a decision log | ≥ 5 documented uses in 10 weeks |
| S5 | Perceived fairness | Pre/post survey of project managers on perceived fairness of delivery reviews (validated scale chosen during setup) | Improvement, or no deterioration, with the interval reported |
| S6 | Coordinator benefit | Self-reported and logged time on coordination tasks, staggered rollout | Reduction with the interval excluding zero |
| S7 | Safety | Correction requests resolved; complaints; any use outside the stated purpose | 100% of corrections resolved within 10 working days; zero out-of-purpose uses |
| S8 | Willingness to pay | Sponsor's decision at week 12 | A written decision to continue on paid terms, or documented reasons not to |

If S1 fails, person-level analysis stays switched off. The context cannot then be trusted, and the public-data
findings on recording practice show why.
