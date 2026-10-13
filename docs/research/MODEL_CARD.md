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
1. Context OLS (cluster-robust by project). R² = 0.43.
2. Linear mixed model with employee random intercept and project variance component (REML; converged without
   warnings). Variance shares: employee 30%, project 18%, residual 52% — most variation is *not* attributable to
   individuals.

Selected context associations (pp of schedule variance, 95% CI): resource constraint (0→1) **+17.7** [14.2, 21.2];
each approved scope change **+4.4** [3.8, 5.0]; greenfield **+5.0** [3.6, 6.3]; regulated environment **+3.1**
[1.4, 4.9]; each complexity level **+2.6** [1.9, 3.4]; each dependency **+2.3** [1.9, 2.7].

## Validation
| Check | Result |
|---|---|
| Out-of-time (train ≤ 2026-01-14, 1,181 test milestones), MAE pp | global mean 12.63 · employee history only 12.17 · context GBM 10.69 · context OLS 9.56 · **context + employee mixed 8.39** (R² 0.53) |
| Grouped 5-fold CV (by project), MAE | ridge 9.22 ± 0.59 · GBM 9.58 ± 0.51 |
| Leakage checks | 5/5 pass (forbidden columns, outcome-derived fields, chronology, single-feature dominance max \|r\| 0.46, permuted-target skill ≈ 0) |
| Calibration, P(slip > 10%) | Brier 0.183 vs climatology 0.250; ECE 0.035 |
| Cluster bootstrap (200 resamples) | median interval width 10.9 pp; 75% agreement with mixed-model intervals on direction of evidence |
| Drift (train vs test) | all PSI < 0.05 — stable |
| Missing data | quality scores missing 11%; not MCAR (19% internal vs 6% elsewhere, χ² p ≈ 5e-34) |

### Sensitivity (agreement with base estimates)
| Specification | Spearman ρ | Conclusions changed |
|---|---|---|
| No project variance component | 0.99 | 21% |
| + business-unit fixed effects | 0.98 | 7% |
| Drop resource constraint | 0.93 | 14% |
| Drop complexity and dependencies | 0.73 | 23% |
| Winsorised outcome (5–95%) | 0.99 | 2% |
| No context adjustment | 0.53 | 27% |
| Huber robust residuals | 0.98 | — |

Conclusions are sensitive to which context is measured — the strongest argument for showing context next to every
estimate and for human review.

### Ground-truth recovery (synthetic only; hidden parameters read after training)
| Signal | Spearman ρ with true contribution |
|---|---|
| Context-adjusted estimate | **0.77** |
| Raw delivery metric | 0.28 |
| Historical manager rating | 0.07 |
| Meeting activity | −0.24 |

95% intervals contain the true effect for 90% of employees. Of 72 strong conclusions, 96% have the correct sign.
By archetype (mean raw → adjusted → true effect, pp): strong people on difficult projects −9.7 → +3.1 → +8.2;
average people on favourable projects +13.0 → −0.3 → −1.5; low-visibility strong +4.3 → +6.0 → +7.8;
high-activity weaker −5.3 → −5.3 → −8.0. Adjustment removes most of the circumstance effect but shrinks estimates
towards zero.

## Conclusions and abstention
within expected range 211 · above context expectation 35 · below context expectation 37 · insufficient evidence 15.
Longitudinal: no employee flagged after FDR control (26 with insufficient history) — the layer is under-powered at
this evidence density even though 25 synthetic employees improve over time.

## Historical labels and fairness (aggregated)
* Manager ratings correlate with raw outcomes (ρ 0.31) and meeting volume (0.34) more than with adjusted evidence
  (0.15): they reward circumstances and visibility.
* Fairness audit (synthetic protected attribute, cells ≥ 20): group G1 is rated 0.26 points higher than G2
  [0.08, 0.44] and promoted 9 points more often, while G2's mean adjusted evidence is *higher* by 1.7 pp
  [0.5, 2.9]. The audit flags a pattern consistent with rating bias (the generator applies a penalty to G2 in
  ratings only). The adjusted-evidence gap arises from sampling in this draw — the group was assigned independently of
  contribution — and illustrates why audits report intervals and why group results say nothing about individuals.

## Flagship experiment
A (simple, well-resourced projects; on-time 95%) vs B (complexity 4.6, resource constraint 0.57, 5.2 dependencies;
on-time 0%). Unadjusted, A is 23 pp ahead. Adjusted B−A = −0.6 pp, bootstrap 95% interval −13.4 to +5.2;
specifications disagree on direction; operating conditions barely overlap. **Verdict: inconclusive.** Hidden truth:
B is the stronger contributor (+6.2 vs −1.4 pp). Adjustment removed a misleading 23 pp gap; the remaining evidence
for two individuals was too thin to claim the reverse.

## Limitations
* Synthetic data with a known, simpler-than-reality generating process; results on real data will be weaker.
* Non-random assignment: adjustment removes *measured* context only.
* Overdue milestones are excluded rather than modelled.
* Heavy-tailed residuals (excess kurtosis 3.6): analytic intervals assume approximate normality; bootstrap and robust
  checks are reported alongside.
* One narrow facet of contribution; much valuable work leaves no record.
