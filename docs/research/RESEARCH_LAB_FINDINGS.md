# Research laboratory — findings on the synthetic organisation

> **Status: exploratory, synthetic.** Every number below comes from the reference synthetic organisation (seed
> 20261013) and describes how the methods behave under a known data-generating process. None is a real-world finding.
> Reproduce any result in the Research Laboratory (or `meritvector_analytics.research.lab.run`) — each run records its
> dataset version, code version and a result hash.

## Workstream results

| Workstream | Question | Result (plain language) | Key numbers |
|---|---|---|---|
| EDA / RQ1 | Are some people assigned harder projects? | Yes — assignment is far from random; people whose early raw results were *worse* tend to keep getting harder work (because their early work was also hard). | ICC(1) of context-predicted difficulty 0.52; ρ(early raw on-time, later difficulty) −0.24 (p < 0.001) |
| RQ4 / H3 | Is activity volume informative? | Activity rewards visibility, not contribution. | ρ(meetings, adjusted signal) −0.21; ρ(meetings, rating) +0.34 |
| H2 | Do business units differ after adjustment? | No clear difference. | Kruskal–Wallis p = 0.11 (Holm-adjusted); η² 0.03 |
| H4 / RQ5 | Do ratings depend on the rater? | Yes — rater identity explains rating variance beyond evidence. | ANCOVA F = 4.4, p ≈ 2e-15; partial η² 0.12 |
| H5 / RQ2 | Is resource shortfall associated with slippage? | Yes. | +17.7 pp per unit (cross-person OLS, clustered CI 14.2–21.2); robustness value reported |
| H6 | Regulated vs internal projects | Regulated projects slip more — but they also differ in other conditions; this describes conditions, not causes. | Hedges g 0.37 on project means; Mann–Whitney check reported |
| Regression / RQ2 | Do complex models help? | No — a transparent linear model is within 0.0 pp of the best; gradient boosting overfits (generalisation gap 4.0 pp). | OOT MAE: OLS 9.56, ridge 9.56, lasso 9.56, splines 9.68, GBM 10.69; baseline 12.63 |
| Negative controls | Do dimensions with no true effect sneak in? | No, with correct (clustered) inference; yes if repeated milestones are treated as independent. | Clustered joint p = 0.65; naive i.i.d. p = 0.034 |
| Classification / RQ6 | Can milestone slips be flagged 30 days ahead? | Yes, usefully for projects. Logistic regression is as good as tree ensembles and better calibrated than gradient boosting. | Test PR-AUC 0.85 (base rate 0.48), recall 0.92 at the cost-optimal threshold, Brier 0.16 vs 0.25; heuristic "last milestone slipped": F1 0.64 vs 0.74 |
| Clustering / RQ7 | Recurring project environments? | Two stable but weakly separated environments: large/visible programmes vs typical projects. Treat as tendencies. | k = 2, bootstrap ARI 0.82, silhouette 0.13; k ≥ 4 unstable |
| Growth / RQ8 / H8 | Does growth vary between people? | Yes at population level; individual slopes remain uncertain and are shrunk. | Random-slope LRT p ≈ 4e-29; slope SD 6.4 pp/year; 18 people with slope CI > 0 |
| Causal / RQ9 | Does more resourcing *cause* better delivery? | Associations are confounded by who gets which project; the within-person design removes stable latent contribution and moves the estimate towards the generator's true effect. | Naive 25.8, measured-context 16.2, within-person 20.8 pp per unit (true 22); back-door fails with measured context only |
| Raw KPIs and difficulty | Are PMs on hard projects disadvantaged by raw KPIs? | Yes. | Hardest quartile: raw −9.8 pp vs adjusted +0.8; easiest: raw +7.3 vs adjusted −2.4 |
| Experiment / RQ10 / H7 | Does the coordinator improve on-time reporting? (simulated, consented) | The simulated randomised trial recovers the configured effect; the study is only just powered. | +5.6 pp [1.1, 10.2], permutation p = 0.013; CUPED cuts variance 27%; MDE 6.6 pp with 135/arm; DiD +4.9 pp (5 clusters — indicative only); true effect 6.0 |

## Scenario lab A–F

| Scenario | What it shows | Result |
|---|---|---|
| A — easy vs hard conditions | Raw gap explained by conditions | Raw on-time favours A by 93%; adjusted B−A −3.8 pp [−8.8, +1.3] → "not supported" (truth: equal) |
| B — activity vs quality | Activity counts mislead | A has 4.5× the meetings, B's deliverables score +0.43 higher; population ρ(meetings, quality) 0.08 |
| C — equivalent work, different raters | Rater bias | Same evidence, +1.75 rating gap; rater effect F = 21, estimated gap 1.14 (true 1.2) |
| D — improving while taking harder work | Longitudinal evidence | Raw slope +19.7 pp/yr (looks worse); adjusted +6.5 pp/yr (truth +10.5) — right direction, interval includes 0 with 24 milestones |
| E — high-profile assignment | Visibility ≠ contribution | Ratings +0.74 [0.33, 1.15] and feedback +0.74 after assignment; delivery evidence −0.05 [−0.63, 0.54] |
| F — shared programme outcome | Limits of attribution | Fixed team: design rank 1 for 4 people (unidentifiable); rotating teams ρ 0.77 with wide intervals; + verified workstream evidence ρ 0.80 |

## What changed in the product because of these findings
1. **Within-person context model** became the primary estimator (ADR-011) after Scenarios A/D showed cross-person
   adjustment under-credits people on difficult projects.
2. **Cluster-aware inference** for project-level variables (ADR-012) after the negative-control false discovery.
3. **Programme outcomes are never attributed to one person**; evidence chains require manual attribution (WP-C).
4. **Ratings and activity** stay out of every estimate; label audits show why.

## Unvalidated
Everything above is validated only against the simulation. External validity requires a consented pilot with
pre-registered success criteria (see `docs/product/`).
