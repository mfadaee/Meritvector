# MeritVector

**Evidence-based workforce intelligence for programme and project management offices — v0.1 (MVP).**

MeritVector combines two things that are kept deliberately separate:

1. **A work coordinator** that helps employees run their day: meeting summaries, action and decision extraction,
   follow-up tasks, deadline reminders, status reports, RAID logs and management summaries.
2. **A performance-evidence engine** that asks a research question — *can we distinguish genuine contribution from
   superficial activity, favourable circumstances, project complexity, organisational bias and noise?* — and answers
   it with statistics, explicit uncertainty and the willingness to say "insufficient evidence".

It is **decision support**, not an automated promotion, pay, dismissal or hiring system. It does not rank people.
Every employment-related use requires qualified human review.

> **All data in this repository is synthetic.** Every person, project, meeting and number is generated from a
> fixed seed. No real employee data is included, and no real surveillance is possible: there are no live connectors.

## Who it serves

Project managers, technical project managers, programme managers, PMO and portfolio managers — with roles for
employees, managers, HR reviewers and administrators. The architecture supports other functions later
(see [ROADMAP](docs/ROADMAP.md)).

## What works in v0.1

| Area | Working capability |
|---|---|
| Synthetic organisation | 300 employees (30 programme, 200 project, 70 technical project managers), 5 business units, ~850 projects, 24 months, hidden ground truth kept out of the database |
| Evidence pipeline | Mock Jira/Asana/monday.com/Graph/PMO/survey connectors → schema-validated ingestion with provenance → raw `evidence_events` → engineered features |
| Analytics (Python) | Descriptive metrics · context OLS + mixed-effects adjustment · longitudinal trends with FDR control · competency evidence mapping · validation suite (out-of-time, CV, leakage, bootstrap, calibration, sensitivity, missingness, drift, error analysis, fairness) |
| Flagship experiment | Two-employee context experiment with sensitivity analysis and an explicit verdict; reproducible notebook |
| Coordinator | Deterministic meeting intelligence, briefings, reports, reminders, dependency checks; optional LLM interface (no LLM required) |
| Product | FastAPI + PostgreSQL backend, Next.js dashboard with 10 pages, RBAC, governance gate, audit log, correction workflow, append-only review notes, retention jobs |

## Quick start (Docker)

```bash
cp .env.example .env
python3 -c "import secrets; print('MV_SECRET_KEY=' + secrets.token_urlsafe(48))" >> .env
docker compose up --build
```

Open **http://localhost:3000**. The first start generates the synthetic organisation, ingests its evidence and trains
the models (about 1–2 minutes; watch `docker compose logs -f api`). Sign in by choosing a persona — Employee, Manager,
HR reviewer or Administrator — for either tenant:

* **Synthetic PMO** — assessment features approved (seeded governance approval).
* **Synthetic sandbox** — assessment *not* approved: demonstrates tenant separation and the governance gate.

Services: `db` (PostgreSQL 16) · `api` (FastAPI, port 8000, OpenAPI docs at `/docs`) · `worker` (scheduled jobs) ·
`web` (port 3000). To start again from scratch: `docker compose down -v`.

## Local development (without Docker)

Requires Python ≥ 3.11 and Node 22.

```bash
pip install -e ".[dev]"
export MV_SECRET_KEY=dev-only-secret          # any string locally
python -m meritvector_api.cli bootstrap       # SQLite at artifacts/meritvector.db; ~1 minute
python -m meritvector_api.cli serve           # http://localhost:8000
cd apps/web && npm ci && npm run dev          # http://localhost:3000
```

Set `DATABASE_URL=postgresql+psycopg://user:pass@host/db` to use PostgreSQL instead of SQLite.

## Common tasks

| Task | Command |
|---|---|
| Generate synthetic data only | `python -m meritvector_api.cli generate --out data/synthetic/export` (hidden truth goes to `hidden/`) |
| Load data + train | `python -m meritvector_api.cli bootstrap` |
| Retrain (new model version) | `python -m meritvector_api.cli train --tenant synthetic-pmo` — or *Model Validation → Retrain* as HR/admin |
| Run a scheduled job | `python -m meritvector_api.cli run-job retention_enforcement` |
| Run the job worker | `python -m meritvector_api.cli worker` |
| Flagship notebook | `python scripts/build_notebook.py --execute` → `experiments/notebooks/flagship_context_experiment.ipynb` |
| Backend tests | `pytest` (includes full-size model validation, ~1 min) |
| Frontend checks | `cd apps/web && npm run lint && npm run typecheck && npm test && npm run build` |
| Lint / secret scan | `ruff check . && ruff format --check . && python scripts/check_secrets.py` |

Each training run writes a versioned directory `artifacts/models/<tenant>/mv-<timestamp>-<data-hash>/` with
estimates, metrics, the experiment, the fairness audit, a generated model card and a manifest, and records the run in
the `model_runs` table.

## Exploring the dashboards

| Page | Try this |
|---|---|
| Overview | Delivery trend, project health, complexity distribution, evidence coverage |
| Employee Workspace | As **Employee**: Today, My projects, My coordinator, My development, My data |
| AI Coordinator | Paste a transcript → actions/decisions/risks with source lines; draft reports; outbox (delivery blocked by default) |
| Meeting Intelligence | Processed meetings; transcripts visible to attendees only |
| Project Portfolio | Filter, open a project, tick 2–4 projects to compare outcomes *and* conditions |
| Risk Intelligence | Risk trends, materialisation, dependency bottlenecks, resource constraint vs delivery |
| Contribution Evidence | As **Employee**: every record held about you, with *Challenge*. As **Manager/HR**: people (alphabetical), correction requests |
| Employee detail | Raw vs adjusted, intervals, trend, competencies, missing information, human review notes |
| Contextual Analysis | Context coefficients, raw-vs-adjusted scatter, variance decomposition, the flagship experiment |
| Model Validation | Baselines, calibration, leakage, sensitivity, drift, fairness (HR/admin), ground-truth recovery, model card |
| Administration & Privacy | Notice, governance approval, retention, audit log, jobs, integrations, RBAC |

## Headline results (synthetic, seed 20261013)

* Context-adjusted estimates (v0.2 within-person model) correlate **ρ = 0.79** with the hidden contribution
  parameter; raw delivery metrics **0.28**; historical manager ratings **0.07**. 95% intervals cover the true effect
  for **90%** of employees; 99% of strong conclusions have the correct sign.
* Out-of-time (last 6 months of settled milestones held out), MAE: global mean 12.6 → context OLS 9.6 →
  context + employee mixed model **8.4** percentage points.
* Flagship experiment (two-person): unadjusted, Employee A is 23 pp ahead (on-time 95% vs 0%). After adjustment B's
  estimate is +8.1 pp [1.2, 14.9] (truth +6.2) and A's −0.7, but the two people's operating conditions barely overlap,
  so the comparison is reported as **inconclusive** rather than over-claimed.
* **Flagship v2** — *Do raw performance metrics misrepresent project-manager contribution?* (all 298 PMs with settled
  milestones, 7 steps): measured conditions alone predict 46% of the raw spread; only 54% of the raw "top fifth" are
  truly above average, while 100% of "above context expectation" conclusions are (synthetic truth). Activity proxies
  point the wrong way. Report: [FLAGSHIP_REPORT](docs/research/FLAGSHIP_REPORT.md) · dashboard: *Flagship Study* ·
  notebook: `experiments/notebooks/flagship_v2_raw_metrics_vs_contribution.ipynb` · script: `python scripts/run_flagship.py`.
* Research Laboratory: 15 reproducible workstreams (EDA, registered hypotheses with Holm correction, model comparison,
  30-day milestone-risk classifier PR-AUC 0.85, clustering, growth models, causal DAGs, experiment design) and six
  synthetic scenarios with known truth. See [RESEARCH_LAB_FINDINGS](docs/research/RESEARCH_LAB_FINDINGS.md).

* **Real-world check on public data** (EBSPM, Maxwell, NASA93, Desharnais, China; 1,200+ real projects): measured
  context explains roughly 4–30× more of the variation in productivity than team or capability indicators. Raw team
  comparisons overstate effects: "fixed, experienced team" projects cost 47% less per function point on raw figures
  but 9% less [−38%, +32%] after adjustment. Models do not transfer across organisations. See
  [PUBLIC_DATA_VALIDATION](docs/research/PUBLIC_DATA_VALIDATION.md); fetch the data with
  `python scripts/fetch_public_data.py` (pinned, checksum-verified, not committed).

Full details: [MODEL_CARD](docs/research/MODEL_CARD.md).

## Known limitations

* Person-level estimates are validated on synthetic data only. Public real-world data supports the project- and
  organisation-level claims, but no public dataset can validate estimates about individuals.
* Demo sign-in has no passwords; SSO is required before any real use (v0.3).
* Connectors are mocks; no external system is contacted and no message ever leaves the process.
* The coordinator is rule-based; it handles `Speaker: text` transcripts with common phrasings only.
* Milestones still overdue at the as-of date are excluded rather than modelled (survival models are planned for v0.2).
* The longitudinal layer is under-powered at this evidence density: after false-discovery-rate control it flags no
  sustained improvers, although the synthetic data contains 25.
* Estimates are adjusted associations, not causal effects; unmeasured context remains in them.

## Research foundation (Phase 2)

Measurement definitions live outside the code: [ontology](config/measurement/ontology.yaml) (9 constructs),
[PMO specification](config/job_families/pmo/family.yaml) (context, responsibility and outcome dimensions, metric
definitions, competencies), an [illustrative engineering family](config/job_families/engineering_example/family.yaml),
registered [questions](config/research/questions.yaml) and [hypotheses](config/research/hypotheses.yaml), and a
checked [evidence library](research/references/library.json). See
[RESEARCH_FOUNDATION](docs/research/RESEARCH_FOUNDATION.md), [LITERATURE_REVIEW](docs/research/LITERATURE_REVIEW.md),
[MEASUREMENT_THEORY](docs/research/MEASUREMENT_THEORY.md), [VALIDITY_FRAMEWORK](docs/research/VALIDITY_FRAMEWORK.md),
[GAP_ANALYSIS](docs/architecture/GAP_ANALYSIS.md), [PRIORITISATION](docs/PRIORITISATION.md) and
[DEVELOPMENT_PROGRESS](docs/DEVELOPMENT_PROGRESS.md).

## Documentation

[Product vision](docs/PRODUCT_VISION.md) · [Architecture](docs/architecture/ARCHITECTURE.md) ·
[Decisions](docs/architecture/DECISIONS.md) · [Data model](docs/architecture/DATA_MODEL.md) ·
[Metrics framework](docs/research/METRICS_FRAMEWORK.md) · [Model card](docs/research/MODEL_CARD.md) ·
[Privacy & governance](docs/governance/PRIVACY_AND_GOVERNANCE.md) · [Roadmap](docs/ROADMAP.md) ·
[Progress log](docs/PROGRESS.md)

## Licence

Apache-2.0 — see [LICENSE](LICENSE).
