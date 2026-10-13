# Architecture

```
                        ┌──────────────────────── apps/web (Next.js, TypeScript, Tailwind) ───────────────────────┐
                        │  10 pages · role-aware navigation · charts fed only by API responses                     │
                        └───────────────────────────────────────────┬──────────────────────────────────────────────┘
                                                                    │ HTTPS/JSON, bearer token
┌───────────────────────────────────────────── apps/api (FastAPI) ──┴──────────────────────────────────────────────┐
│ routers: auth · workspace · coordinator/meetings · portfolio · evidence · employees · analysis · admin/privacy    │
│ security.py (tokens, RBAC, tenant scoping, governance gate) · audit.py (append-only log)                         │
│ ingestion.py (schema validation, dedup, provenance) · training.py (pipeline → model_runs) · workflows.py (jobs)  │
└──────┬───────────────────────┬──────────────────────────────┬───────────────────────────────┬────────────────────┘
       │                       │                              │                               │
packages/connectors     packages/coordinator          packages/analytics               packages/shared
mock Jira/Asana/        deterministic meeting         synthetic generator · features   vocabulary: data categories,
monday/Graph/Teams/     intelligence, briefings,      · layers A–E · experiment ·      roles, event categories,
Outlook/Slack/PMO/      reports; LLMProvider          validation · model card ·         EvidenceEvent schema,
survey; delivery        interface (deterministic      evaluation harness (only module   forbidden model columns
policy                  default)                      allowed to read hidden truth)
       │                                                      │
       └──────────────────────────── PostgreSQL (SQLite for local tests) ──────────── artifacts/models/<tenant>/<version>/
```

## Modules

| Module | Responsibility | Depends on |
|---|---|---|
| `packages/shared` | Shared constants and the `EvidenceEvent` schema | pydantic |
| `packages/analytics` | All statistics. Pure Python, no DB, no LLM, independently testable | shared, pandas, numpy, scipy, statsmodels, scikit-learn |
| `packages/coordinator` | Employee-facing assistance; **does not import analytics** (tested) | — |
| `packages/connectors` | Mock integrations + outbound-delivery safety policy | — |
| `apps/api` | Persistence, access control, workflows, HTTP API | all packages, SQLAlchemy |
| `apps/web` | User interface | API only |

## Key flows

**Evidence ingestion.** Mock connectors serve records → `ingestion.ingest()` validates each against
`EvidenceEvent` (known source/category/data category, provenance present), rejects cross-tenant records, skips
duplicates by `event_id` and stamps the ingest batch → raw rows in `evidence_events`. Raw rows are never modified
except for `validation_status` changes driven by the correction workflow.

**Training.** `training.train_tenant()` refuses unless the tenant's assessment is governance-approved. It reads raw
events and employees, passes protected attributes only to the aggregated fairness audit, runs
`analytics.pipeline.run_pipeline()` and writes (1) a versioned artifact directory and (2) a `model_runs` row plus one
`employee_run_outputs` row per person. Hidden synthetic truth is read only afterwards by the evaluation harness, and
only aggregate results are stored.

**Workflows.** `scheduled_jobs` holds the schedule; `job_runs` records every execution. The `worker` process polls
`run_due_jobs()`; admins can trigger jobs from the UI. Jobs: `deadline_reminders`, `process_new_transcripts`,
`retention_enforcement`, `retrain_models`.

**Access control.** Every request resolves a `Principal` (user, tenant, role, employee). All queries filter by
tenant. Assessment endpoints additionally require `tenant.assessment_enabled`. Person-level evidence is visible to
the person, their manager (direct reports only) and HR reviewers; administrators get configuration and aggregates
only. Meeting transcripts are visible to attendees only.

## Deployment

`docker-compose.yml` runs PostgreSQL 16, the API (bootstraps idempotently, then serves), the worker (same image) and
the web app (Next.js standalone). No message broker, cache or orchestrator is needed for v0.1.

## Synthetic clock

All demo data is anchored to the tenant's `as_of` date (2026-10-12). "Today" in the workspace, reminders and
retention use that clock so the demo is stable over time.
