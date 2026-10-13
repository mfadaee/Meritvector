# Metrics framework

## Unit of analysis
An **achieved milestone** led by an employee. Its primary outcome is

    schedule variance % = 100 × (actual − planned date) / planned interval

(negative = early). *On time* means schedule variance ≤ 5%. Milestones planned within 90 days of the as-of date are
excluded (right-censoring guard). The secondary outcome is the deliverable review score (1–5), missing for ~11% of
reviews.

## Layer A — descriptive (raw, unadjusted)
| Metric | Definition |
|---|---|
| Milestone performance | on-time rate; mean schedule variance |
| Delivery consistency | SD of schedule variance |
| Quality of deliverables | mean review score; first-pass approval rate |
| Risk mitigation effectiveness | risks mitigated ÷ risks identified; share identified before impact |
| Dependency resolution | median days a dependency stayed open |
| Blocker resolution | median days to resolve |
| Stakeholder feedback | mean survey score (perception-based, noisy, visibility-biased) |
| Contribution trend | quarterly evidence volume and signal |
| Normalisation | z-scores within job family for on-time rate, schedule variance, quality |
| Project health | **red** if any overdue milestone or ≥ 2 open high-severity risks/issues; **amber** if the latest milestone slipped > 15%, ≥ 2 open dependencies, or any open high-severity risk/issue; otherwise **green**; completed projects are **closed** |

Task counts are shown as volume, never as performance: in the synthetic data they scale with activity propensity,
not contribution.

## Layer B — contextual adjustment
Context variables (from the PMO kick-off assessment and change log): technical complexity, dependency count,
resource constraint, scope changes to date, team size, size band, delivery environment, project maturity, job
family, time.

* **Context OLS** with project-clustered standard errors — how much conditions matter.
* **Linear mixed model**: same fixed effects + employee random intercept + project variance component. The employee
  intercept (BLUP, sign-adjusted so positive = better than context predicts) with its conditional 95% interval is
  the **adjusted estimate**.
* **Raw estimate**: employee mean minus organisation mean (sign-adjusted).
* **Conclusion**: *insufficient evidence* if n < 6 or the interval is wider than 22 pp (schedule) / 1.1 points
  (quality); else *above* / *below context expectation* when the interval excludes 0; else *within expected range*.

## Layer C — longitudinal
Residuals from the context OLS (no employee term) are averaged per half-year. A weighted slope is tested for each
employee with ≥ 3 half-years of ≥ 2 milestones; flags (*sustained improvement*, *area requiring investigation*) need
Benjamini–Hochberg FDR q < 0.10. *Sustained delivery quality*: every eligible half-year averages ≥ 3.8.

## Layer D — competency evidence
A configurable framework (`packages/analytics/meritvector_analytics/config/competency_framework.json`) maps evidence
rules to seven competencies and sets per-level minimum evidence counts over 12 months. Output per competency:
*demonstrated*, *emerging*, *evidence gap*, *not expected at level* or *demonstrated beyond level*, with example
evidence references and opportunity notes (e.g. no complex projects assigned). No readiness score is computed.

## Layer E — validation
See [MODEL_CARD](MODEL_CARD.md). Out-of-time comparison of five models, grouped CV by project, five leakage checks,
cluster bootstrap over projects, calibration of P(slip > 10%), seven sensitivity specifications, missing-data
diagnostics, PSI/KS drift, error analysis by group, label audit of historical ratings, aggregated fairness audit with
small-cell suppression (n < 20).

## What is deliberately not a metric
Meeting count, e-mail volume, working hours, message content, keystrokes, presence. In the synthetic data, meeting
volume correlates *negatively* with adjusted contribution (ρ ≈ −0.23) and *positively* with manager ratings
(ρ ≈ 0.34).
