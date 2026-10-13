# Architecture decision records

## ADR-001 — Monorepo with installable Python packages
One `pyproject.toml` installs `meritvector_shared`, `_analytics`, `_coordinator`, `_connectors` and `_api` from their
own directories. Boundaries are enforced by tests (e.g. coordinator must not import analytics) rather than by
separate distributions — simpler for an MVP, splittable later.

## ADR-002 — Statistics before machine learning, and no LLM in the core
The core question is about attribution under confounding, which calls for interpretable models with uncertainty
(OLS with cluster-robust errors, linear mixed models, bootstrap). Gradient boosting appears only as a predictive
baseline. The engine runs without any AI service; LLMs are an optional coordinator convenience behind
`LLMProvider`, and v0.1 ships only a clearly labelled deterministic provider.

## ADR-003 — Milestone schedule variance as the primary unit of analysis
Milestones are frequent, verifiable in systems of record, and comparable when expressed as a percentage of the
planned interval. Deliverable review scores are a secondary outcome. Activity counts are explicitly excluded.

## ADR-004 — Hidden truth never enters the database
Synthetic ground truth lives in `data/synthetic/<tenant>/hidden/` and is read only by
`meritvector_analytics.evaluation` after training. Forbidden columns are asserted absent at feature-build time and in
the design matrix.

## ADR-005 — Abstention is a first-class output
Person-level conclusions require ≥ 6 settled milestones and an interval narrower than a configured width; otherwise
"insufficient evidence". Longitudinal flags require three half-years and pass Benjamini–Hochberg FDR control.

## ADR-006 — Right-censoring guard
Milestones planned within 90 days of the as-of date are excluded from analysis because only those finishing early or
on time are observable yet. Found during visual review of trends (late quarters looked artificially good).
Replaced by survival models in v0.2.

## ADR-007 — Governance gate implemented in the API, not the UI
Assessment endpoints depend on `require_assessment_enabled`; training refuses for unapproved tenants. Enabling
requires one administrator and one HR reviewer approval; either can revoke immediately.

## ADR-008 — Signed stateless tokens and demo sign-in
HMAC-signed bearer tokens with expiry; the key comes from `MV_SECRET_KEY` (an ephemeral key is generated if unset so
nothing is ever hard-coded). Demo sign-in is controlled by `MV_DEMO_AUTH` and is replaced by SSO in v0.3.

## ADR-009 — Simple persistent job table instead of a queue
`scheduled_jobs` + `job_runs` + a polling worker. Adequate for minutes-scale schedules and fully inspectable.

## ADR-010 — PostgreSQL in deployment, SQLite in tests
SQLAlchemy models use portable types (JSON, Date, DateTime) so the same code runs on both. Docker Compose uses
PostgreSQL 16; the test suite uses temporary SQLite databases for speed.
