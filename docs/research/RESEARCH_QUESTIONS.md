# Research questions

> Generated from `config/research/questions.yaml`. Each question states its type — descriptive, predictive, causal, measurement or experimental — because the type determines which conclusions are allowed.

| ID | Question | Type | Workstream | Hypotheses |
|---|---|---|---|---|
| RQ1 | **Are some people systematically assigned harder projects?** Does the context-expected difficulty of a person's projects differ between people more than chance, and is it associated with their earlier raw results? | descriptive | eda | H1 |
| RQ2 | **How do project conditions relate to delivery outcomes?** Which measured conditions are associated with schedule variance, and do simple and advanced models agree? | descriptive | regression | H5, H6 |
| RQ3 | **Do raw delivery metrics misrepresent individual contribution?** How far do raw and context-adjusted readings disagree, and for whom? | measurement | flagship | H2 |
| RQ4 | **Is activity volume informative about contribution?** Are meetings, e-mails and hours associated with context-adjusted delivery evidence? | measurement | eda | H3 |
| RQ5 | **Are manager ratings influenced by who the rater is?** After accounting for context-adjusted evidence, do ratings differ by rater (leniency) — Scenario C? | measurement | hypothesis_testing | H4 |
| RQ6 | **Which projects are at elevated risk of missing a milestone in the next 30 days?** Project-level early warning from point-in-time features; never an assessment of people. | predictive | classification | — |
| RQ7 | **Are there recurring project operating environments?** Do stable clusters of project conditions exist, and what bottlenecks characterise them? | descriptive | clustering | — |
| RQ8 | **Does individual growth vary, and can it be detected?** Is there between-person variance in growth of the context-adjusted signal (random slopes)? | descriptive | longitudinal | H8 |
| RQ9 | **Does more resource availability cause better delivery?** Under an explicit DAG, what adjustment set is needed and how robust is the estimate to unmeasured confounding? | causal | causal | H5 |
| RQ10 | **Does access to the AI coordinator improve administrative follow-through?** Randomised (simulated, consented) experiment on reporting timeliness and follow-up completion; power analysis first. | experimental | experiments | H7 |

## What each type may conclude

- **Descriptive** — what happened and how it is distributed. No causal language.
- **Predictive** — how well something can be forecast out of time. Prediction is not explanation.
- **Causal** — only with an explicit DAG, a stated adjustment set, and sensitivity to unmeasured confounding.
- **Measurement** — whether an indicator measures the intended construct (validity, reliability, bias).
- **Experimental** — effects of randomised interventions on consented participants, with pre-specified power and outcomes. Never used for employment decisions.

