# Data model

Tables are grouped by processing purpose. The grouping is the basis of the separation rules in
[PRIVACY_AND_GOVERNANCE](../governance/PRIVACY_AND_GOVERNANCE.md).

## Identity & governance
| Table | Key fields |
|---|---|
| `tenants` | `id`, `name`, `is_synthetic`, `assessment_enabled` (default false), `as_of`, `settings` (notice, purpose, retention days, delivery switch, minimisation flags) |
| `users` | `id`, `tenant_id`, `employee_id?`, `role` ∈ employee/manager/hr_reviewer/admin, `preferences` |
| `governance_approvals` | `purpose`, `scope`, `requested_by`, `admin_approved_by`, `hr_approved_by`, `status` |
| `audit_log` | `actor_user_id`, `actor_role`, `action`, `resource_type`, `resource_id`, `detail`, `at` — append-only |

## Organisational reporting
| Table | Key fields |
|---|---|
| `employees` | `job_family`, `level`, `business_unit`, `manager_id`, `joined_on`, `is_synthetic` |
| `projects` | `lead_employee_id`, dates, `status`, context: `technical_complexity` (1–5), `dependency_count`, `resource_constraint` (0–1), `size_band`, `team_size`, `environment`, `maturity` |
| `milestones` | `planned_date`, `actual_date`, `status` ∈ achieved/overdue/planned |
| `risks` | `severity`, `status` ∈ open/mitigated/issue/closed, `kind` ∈ risk/issue |
| `dependencies` | `depends_on` (team), `raised_on`, `resolved_on`, `status` |

## Assistance
`meetings` (transcript, attendees), `meeting_insights` (summary, actions, decisions, risks, dependencies, generator,
disclosure), `coordinator_tasks`, `reminders`, `outbox_messages`, `development_goals`. All carry
`data_category = assistance` where applicable.

## Assessment evidence (raw)
`evidence_events` — one row per ingested record:

| Field | Meaning |
|---|---|
| `event_id` | Stable identifier from the source (dedup key) |
| `employee_id`, `project_id` | Subject and context |
| `occurred_at` | Event timestamp |
| `source_system` | jira, asana, monday, ms_graph, pmo_register, stakeholder_survey, … |
| `category` | task_created/completed, milestone_achieved, schedule_changed, risk_identified/mitigated, issue_raised, blocker_raised/resolved, scope_change_approved, document_reviewed, stakeholder_feedback, project_outcome, resource_limitation, complexity_assessment, dependency_registered/resolved, activity_summary |
| `data_category` | assessment_evidence, or diagnostic_activity (synthetic activity counts; never used for estimates) |
| `evidence_ref` | Pointer into the source system |
| `quality_indicators` | Optional (review score, verification, response scale…) |
| `provenance` | connector, ingest batch, raw hash, ingested via |
| `validation_status` | validated, unvalidated, disputed, corrected, retracted |
| `payload` | Category-specific fields |

Plus `evidence_challenges`, `historical_ratings` and `historical_promotions` (biased labels — audit only), and
`protected_attributes` (controlled — aggregated fairness audit only).

## Engineered features (derived, not stored as tables)
`meritvector_analytics.features.build_features()` produces a milestone-level frame: schedule variance % of interval,
on-time flag, deliverable quality, first-pass approval, project context from the kick-off complexity assessment,
`scope_changes_to_date` (only changes approved *before* the milestone's planned date), job family, time index.

## Model outputs
`model_runs` (version = `mv-<timestamp>-<data-hash>`, metrics, experiment, fairness aggregates, synthetic evaluation
aggregates, model card, artifact path) and `employee_run_outputs` (per-person estimates, raw metrics, trend,
quarterly series, competencies, bootstrap interval). `review_notes` are append-only human judgements linked to a run.

## Workflows
`scheduled_jobs` (name, interval, next/last run, status) and `job_runs` (trigger, timing, status, detail).
