# Model card — MeritVector performance-evidence models v0.1

*Numbers below are from the reference run on the synthetic organisation (seed 20261013, as of 2026-10-12). Every
training run also generates its own model card (`artifacts/models/<tenant>/<version>/model_card.md`, shown on the
Model Validation page).*

## Intended use
Summarise validated delivery evidence in the context of operating conditions, with uncertainty, to support
development conversations led by qualified people.

**Out of scope:** automated or recommended promotion, compensation, dismissal or hiring decisions; ranking employees;
any use without human review; any use on data collected without disclosure.

## Data
* 3,751 settled, achieved milestones from 819 projects led by 298 synthetic employees (2 have no milestones);
  505 recent milestones excluded by the right-censoring guard.
* Features: project complexity, dependencies, resource constraint, scope changes to date, team size, size band,
  environment, maturity, job family, time. **Excluded:** hidden ground truth, protected attributes, historical
  ratings and promotions, activity metadata, assistance content, disputed/retracted records.

## Models
1. Context OLS (cluster-robust by project). R² = 0.43. Cross-person, so its coefficients are biased by assignment
   (stronger people get harder work): e.g. complexity +2.6 pp/level against the generator's +5.5.
2. **v0.2 primary — within-person (Mundlak / correlated random effects) linear mixed model**: the same fixed effects
   plus each person's mean conditions, an employee random intercept and a project variance component (REML; converged
   without warnings). Context effects are estimated from the same person's different projects and recover the
   generator: complexity **+5.2** (true 5.5), resource shortfall **+21.4** (true 22), dependencies **+2.2** (true 2.2),
   scope changes **+4.2** (true 4.0). The adjusted estimate is the shrunk random intercept plus the between-person
   component, with an interval that includes the uncertainty of the person-mean coefficients.
3. The v0.1 random-intercept model is retained as a sensitivity specification (Spearman 0.93 with v0.2).

Variance shares (v0.2): employee 27%, project 18%, residual 55% — most variation is *not* attributable to individuals.

## Validation
| Check | Result |
|---|---|
| Out-of-time (train ≤ 2026-01-14, 1,181 test milestones), MAE pp | global mean 12.63 · employee history only 12.17 · context GBM 10.69 · context OLS 9.56 · **context + employee mixed 8.39** (R² 0.53; predictive comparison uses the random-intercept form) |
| Grouped 5-fold CV (by project), MAE | ridge 9.22 ± 0.59 · GBM 9.58 ± 0.51 |
| Leakage checks | 5/5 pass (forbidden columns, outcome-derived fields, chronology, single-feature dominance max \|r\| 0.46, permuted-target skill ≈ 0) |
| Calibration, P(slip > 10%) | Brier 0.183 vs climatology 0.250; ECE 0.035 |
| Cluster bootstrap (200 resamples, within-person coefficients re-estimated per resample) | median interval width 10.8 pp; 74% agreement with mixed-model intervals on direction of evidence |
| Drift (train vs test) | all PSI < 0.05 — stable |
| Missing data | quality scores missing 11%; not MCAR (19% internal vs 6% elsewhere, χ² p ≈ 5e-34) |

### Sensitivity (agreement with v0.2 base estimates)
| Specification | Spearman ρ | Conclusions changed |
|---|---|---|
| No project variance component | 0.99 | 16% |
| + business-unit fixed effects | 0.99 | 6% |
| Drop resource constraint | 0.91 | 19% |
| Drop complexity and dependencies | 0.45 | 31% |
| Winsorised outcome (5–95%) | 0.99 | 2% |
| Random-intercept only (v0.1 model) | 0.93 | 14% |
| No context adjustment | 0.27 | 34% |
| Huber robust residuals (cross-person) | 0.88 | — |

Conclusions are sensitive to which context is measured — the strongest argument for showing context next to every
estimate and for human review.

### Ground-truth recovery (synthetic only; hidden parameters read after training)
| Signal | Spearman ρ with true contribution |
|---|---|
| Context-adjusted estimate (v0.2) | **0.79** (v0.1: 0.77) |
| Raw delivery metric | 0.28 |
| Historical manager rating | 0.07 |
| Meeting activity | −0.24 |

95% intervals contain the true effect for 90% of employees. Of 88 strong conclusions, **99%** have the correct sign
(v0.1: 96% of 72). Mean raw → adjusted → true effect by archetype (pp):

| Archetype | Raw | v0.2 adjusted | True | (v0.1 adjusted) |
|---|---|---|---|---|
| Strong people on difficult projects | −9.7 | **+6.7** | +8.2 | (+3.1) |
| Average people on favourable projects | +13.0 | −3.2 | −1.5 | (−0.3) |
| Low-visibility strong | +4.3 | +7.0 | +7.8 | (+6.0) |
| High-activity, weaker outcomes | −5.3 | −5.6 | −8.0 | (−5.3) |
| Resource-constrained | −6.7 | −0.5 | −1.0 | (−1.4) |

The within-person model removes most of the under-crediting of people on difficult projects that v0.1 retained.

## Conclusions and abstention
within expected range 195 · above context expectation 45 · below context expectation 43 · insufficient evidence 15.
Per-person trend flags: none after FDR control (26 insufficient history). The population growth model (random
slopes) does detect between-person variation in growth (LRT p ≈ 4e-29; SD ≈ 6.4 pp/year) — see
[RESEARCH_LAB_FINDINGS](RESEARCH_LAB_FINDINGS.md).

## Historical labels and fairness (aggregated)
* Manager ratings correlate with raw outcomes (ρ 0.31) and meeting volume (0.34) far more than with adjusted evidence
  (0.06): they reward circumstances and visibility.
* Fairness audit (synthetic protected attribute, cells ≥ 20): group G1 is rated 0.26 points higher than G2
  [0.08, 0.44] and promoted 9 points more often, while G2's mean adjusted evidence is *higher* by 2.0 pp
  [0.5, 3.4]. The audit flags a pattern consistent with rating bias (the generator applies a penalty to G2 in
  ratings only). The adjusted-evidence gap arises from sampling in this draw — the group was assigned independently of
  contribution — and illustrates why audits report intervals and why group results say nothing about individuals.

## Flagship experiment (two-person, v0.1 design)
A (simple, well-resourced projects; on-time 95%) vs B (complexity 4.6, resource shortfall 0.57, 5.2 dependencies;
on-time 0%). Unadjusted, A is 23 pp ahead. With the v0.2 model, B's estimate is +8.1 pp [1.2, 14.9] ("above context
expectation") and A's −0.7 [−6.7, 5.3]; hidden truth: B +6.2, A −1.4. The verdict nevertheless remains
**inconclusive** because the two records barely overlap in conditions and the direction flips when complexity and
dependencies are omitted. The multi-person flagship (Phase 2) is in [FLAGSHIP_REPORT](FLAGSHIP_REPORT.md).

## Limitations
* Synthetic data with a known, simpler-than-reality generating process; results on real data will be weaker.
* Non-random assignment: adjustment removes *measured* context only.
* Overdue milestones are excluded rather than modelled.
* Heavy-tailed residuals (excess kurtosis 3.6): analytic intervals assume approximate normality; bootstrap and robust
  checks are reported alongside.
* One narrow facet of contribution; much valuable work leaves no record.
