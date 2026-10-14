# Real-world validation on public project data

MeritVector's models are developed on synthetic data, where the truth is known. This study checks the product's
core measurement claims against **real project records** from public research datasets. The data can test claims
about *projects and organisations*. No public dataset can validate estimates about *individual people*, and these
studies make no such claim.

Reproduce: `python scripts/fetch_public_data.py` (pinned commit, SHA-256 verified), then run the
`public_data` workstream in the Research Laboratory (*Real-world data* tab), or call
`meritvector_analytics.public_data.studies.run_all()`. Sources, terms of use and variable roles are listed in
[`config/public_data/sources.yaml`](../../config/public_data/sources.yaml). The data files are not committed.

| Dataset | Records | Unit compared | Origin | Terms |
|---|---|---|---|---|
| EBSPM | 492 projects; 488 used from 3 organisations (a 4-project organisation is excluded) | organisation | Huijgens (2017), 4TU.ResearchData, doi:10.4121/uuid:42fd1be1-325f-47a4-ba39-31af35ca7f75 | 4TU General Terms of Use |
| Maxwell | 63 bank projects (the book reports 62) | — | Maxwell (2002), *Applied Statistics for Software Managers* | book appendix data, PROMISE copy |
| NASA93 | 93 projects; 2 centres have ≥ 20 projects | NASA centre | PROMISE repository | public research data |
| Desharnais | 77 complete of 81 | — | Desharnais (1989) thesis, PROMISE copy | public research data |
| China | 499 projects | — | PROMISE repository (2010) | public research data |

All files come from the CC0 mirror `danrodgar/DASE` at commit `37945fb`.

## Claim 1 — measured context explains far more of raw outcomes than team or capability signals

The table shows a Shapley decomposition of in-sample R² for log productivity (cost or effort per unit of size), with
95% bootstrap intervals.

| Dataset | Size + measured context | Team / capability indicators | Delivery unit | Total R² |
|---|---|---|---|---|
| EBSPM (cost per FP) | **23%** | 5% [3, 9] (team-stability flags) | 6% [4, 9] (organisation) | 0.34 |
| Maxwell | **31%** | 8% [1, 22] (staff-skill ratings) | — | 0.39 |
| NASA93 | **53%** | 4% [0, 12] (capability ratings) | 8% [4, 17] (centre) | 0.65 |
| Desharnais | **62%** | 2% [1, 6] (team and manager experience) | — | 0.64 |

In four independent datasets, team or capability indicators account for a small and uncertain share of the variation.
Size and measured context account for roughly 4–30 times as much. This is the empirical basis for MeritVector's rule: adjust for
context before any comparison, and treat person-level signals as small and uncertain.

## Claim 2 — raw team comparisons overstate effects (EBSPM)

Percentages are differences in cost per function point (or duration) for projects with each flag. "Adjusted" controls
for size, development class, method, year, context flags and organisation.

| Flag | Cost: raw | Cost: adjusted | Duration: raw | Duration: adjusted |
|---|---|---|---|---|
| Fixed, experienced team | −47% [−56, −36] | **−9% [−38, +32]** | −32% [−40, −23] | −23% [−37, −4] |
| Many team changes / inexperienced team | +95% [+32, +189] | +67% [−2, +183] | +87% [+56, +123] | +27% [−9, +78] |
| Steady heartbeat (regular release rhythm) | −45% [−55, −33] | −19% [−44, +18] | −36% [−44, −28] | −7% [−26, +16] |

A raw comparison would credit stable, experienced teams with costing half as much. Most of that gap comes from the
kind of projects they were given. Once those conditions are accounted for, the cost difference is small and not
distinguishable from zero. A shorter duration remains.

This is the pattern MeritVector's synthetic flagship is built around, seen here in real records.

## Claim 3 — comparisons between delivery units change once context is accounted for

Each figure is the difference from the average organisation or centre. The tables are in alphabetical order and are
not rankings.

**EBSPM, cost per function point**

| Organisation | Projects | Raw | Adjusted |
|---|---|---|---|
| Bank A | 206 | +15% [+3, +24] | +17% [−2, +40] |
| Bank B | 125 | +30% [+14, +47] | +44% [+16, +81] |
| Beltel | 157 | −33% [−40, −24] | −41% [−57, −20] |

**EBSPM, duration**

| Organisation | Raw | Adjusted |
|---|---|---|
| Bank A | +5% [−2, +13] | +1% [−9, +13] |
| Bank B | −12% [−19, −5] | −19% [−28, −9] |
| Beltel | +7% [+1, +14] | **+23% [+5, +42]** |

**NASA93, effort per KLOC**

| Centre | Projects | Raw | Adjusted |
|---|---|---|---|
| Centre 2 | 37 | −5% [−19, +14] | +12% [−15, +64] |
| Centre 5 | 39 | +5% [−12, +23] | −11% [−39, +18] |

Adjustment can widen gaps as well as narrow them. In EBSPM the adjusted cost gaps are 1.3 times the raw ones,
because the cheapest organisation also took on harder work. In NASA93 the direction reverses for both centres,
though both intervals are wide.

Raw figures can understate differences as well as overstate them. Either way, they are not a sound basis for comparison.

**Measurement practice differs between organisations.** Bank B never records ten of the EBSPM flags, including
every team-stability flag, while the other two organisations use them regularly. A flag one organisation never sets
is probably a recording practice, not an absent condition. Adjustment cannot repair this. The study reports it, and
it reinforces MeritVector's requirement that context be recorded consistently, using a shared rubric, before any
cross-unit comparison.

## Claim 4 — experience and tenure are weak proxies for contribution (Desharnais, Maxwell)

- **Manager experience (Desharnais, 77 projects).** The raw Spearman correlation with hours per function point is
  −0.06 [−0.26, +0.17]. After adjusting for size, language, complexity, year and team experience, each extra year of
  manager experience goes with **+6.4%** hours per function point [−1.2%, +14.7%]. No clear relationship in either
  direction.
- **Team experience** goes with −4.7% per year [−13%, +5%] after the same adjustment, which is also unclear.
- **Staff-skill ratings (Maxwell).** The raw Spearman correlation is −0.33 (p = 0.008). After adjustment,
  −33% hours per FP per rating point [−56%, +2%]: plausibly real but uncertain.
- **Maxwell context effects.** Requirements volatility (+22% per point [+4, +42]) and quality requirements
  (+38% [+7, +79]) are the clearest drivers.
- **Maxwell, leave-one-out.** Context reduces error by more than staff ratings do: size alone gives LOO R² −0.01;
  adding context gives 0.12; adding staff skills on top gives 0.17.

MeritVector does not use tenure or years of experience as a contribution signal. These results support that choice.

## Claim 5 — simple models generalise as well as complex ones; models do not transfer across organisations

Errors are typical multiplicative errors, exp(mean |log error|): "1.91" means estimates are typically off by a factor
of 1.91.

| Data, validation | Median baseline | Linear context | Random forest | Gradient boosting |
|---|---|---|---|---|
| EBSPM cost, random 5-fold | 2.08 | 1.91 | 1.89 | 1.92 |
| EBSPM cost, leave-one-organisation-out | **2.14** | 2.40 | 2.10 | 2.24 |
| EBSPM duration, leave-one-organisation-out | **1.59** | 1.63 | 1.65 | 1.62 |
| NASA93, random 5-fold (MAE, log) | 0.56 | 0.45 | 0.38 | 0.44 |
| NASA93, leave-one-centre-out (MAE, log) | **0.56** | 1.20 | 0.59 | 0.63 |
| China, 10-fold (MAE, log) | 1.01 | **0.73** | 0.76 | 0.79 |

- **Within an organisation**, a transparent linear model is about as good as random forests and boosting. In China
  it is the best model, and its learning curve flattens by about 100 projects.
- **Across organisations or centres**, no model beats a simple median. Context models must be calibrated within each
  organisation. A model built in one organisation is not evidence about another, and MeritVector does not pool
  tenants.
- **Leakage.** Adding project duration, which is known only after delivery, lowers China's error from 0.73 to 0.67.
  That is exactly the kind of illegitimate gain the leakage checks exist to block.

## What this does and does not show

**It shows** that in real project portfolios:

- measured conditions dominate raw outcomes
- raw comparisons of teams and delivery units are distorted
- recording practice differs between units
- simple models are adequate within an organisation and unreliable across organisations

**It does not show** that MeritVector's individual estimates are accurate. No public dataset links people to project
outcomes with a known truth. That remains a question for a governed pilot: see the validation framework and
pilot criteria in [VALIDITY_FRAMEWORK](VALIDITY_FRAMEWORK.md).

All results are associations in observational data. They are exploratory and were not pre-registered.
