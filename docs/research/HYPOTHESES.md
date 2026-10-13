# Hypotheses

> Generated from `config/research/hypotheses.yaml`. Results are produced by `meritvector_analytics.research.hypotheses` and shown in the Research Laboratory; they are not edited here.

Significance level α = 0.05. Multiple-testing families:

- `context_family` (holm): H2, H5, H6
- `measurement_family` (holm): H1, H3, H4

## H1 — confirmatory (answers RQ1)

- **H0:** A person's raw on-time rate in their first year is not associated with the context-expected difficulty of their later projects.
- **H1:** Earlier raw results are associated with later assignment difficulty.
- **Unit of analysis:** employee
- **Test:** `spearman` on x=first_year_on_time, y=later_context_expected
- **Assumptions:** Monotone relationship; employees with projects in both periods.
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

## H2 — confirmatory (answers RQ3)

- **H0:** After contextual adjustment, employee-level delivery signal does not differ between business units.
- **H1:** It differs between business units.
- **Unit of analysis:** employee
- **Test:** `kruskal_anova` on value=adjusted_signal, group=business_unit
- **Assumptions:** Independent employees; ANOVA reported alongside Kruskal–Wallis with Levene check.
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

## H3 — confirmatory (answers RQ4)

- **H0:** Meeting volume is not associated with context-adjusted delivery signal.
- **H1:** Meeting volume is associated with it.
- **Unit of analysis:** employee
- **Test:** `spearman` on x=meetings_per_month, y=adjusted_signal
- **Assumptions:** Activity data are synthetic metadata counts.
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

## H4 — confirmatory (answers RQ5)

- **H0:** Manager ratings do not differ between raters after adjusting for the ratee's context-adjusted delivery evidence.
- **H1:** Rater identity explains rating variance beyond evidence (leniency).
- **Unit of analysis:** rating
- **Test:** `rater_effect_anova` on rating=manager_rating, covariate=adjusted_signal, group=rater_id
- **Assumptions:** Ratings nested in raters; ANCOVA with rater as factor; partial eta² reported.
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

## H5 — confirmatory (answers RQ2)

- **H0:** Resource constraint is not associated with milestone schedule variance after adjusting for other measured conditions.
- **H1:** It is associated (direction not pre-specified).
- **Unit of analysis:** milestone (clustered by project)
- **Test:** `ols_cluster_coefficient` on outcome=schedule_variance_pct, term=resource_constraint
- **Assumptions:** Linear association; project-clustered SEs; association not causation.
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

## H6 — confirmatory (answers RQ2)

- **H0:** Mean project-level schedule variance does not differ between regulated and internal delivery environments.
- **H1:** It differs.
- **Unit of analysis:** project (milestones aggregated to avoid repeated measures)
- **Test:** `welch_t` on value=project_mean_schedule_variance, group=environment, levels=['regulated', 'internal']
- **Assumptions:** Project means approximately normal; unequal variances allowed; Mann–Whitney reported as a robustness check.
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

## H7 — confirmatory (answers RQ10)

- **H0:** Coordinator access does not change on-time status-report submission.
- **H1:** It changes the on-time rate.
- **Unit of analysis:** employee (randomised)
- **Test:** `experiment_difference` on outcome=report_on_time_rate, arm=coordinator_access
- **Assumptions:** Randomised assignment in the simulation; consented participants; CUPED with pre-period covariate.
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

## H8 — exploratory (answers RQ8)

- **H0:** There is no between-person variance in the growth of the context-adjusted signal.
- **H1:** Growth varies between people.
- **Unit of analysis:** milestone (nested in employee)
- **Test:** `random_slope_lrt` on outcome=context_residual, time=years
- **Assumptions:** Linear growth; boundary-corrected likelihood-ratio test (50:50 chi-square mixture).
- **Reporting:** effect size with confidence interval, assumption checks and adjusted p-value — not a p-value alone.

