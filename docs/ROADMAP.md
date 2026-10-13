# Roadmap

## v0.1 — Synthetic data and working MVP (this release)
* Synthetic 300-person PMO with hidden ground truth; reproducible seeds.
* Evidence ingestion through mock connectors; raw events separated from engineered features.
* Analytics layers A–E, flagship experiment and notebook, versioned model runs and generated model cards.
* Coordinator (deterministic), employee and manager dashboards, RBAC, governance gate, audit, corrections,
  retention jobs, Docker Compose, CI.

## v0.2 — Advanced statistical modelling
* Survival / time-to-event models for milestones so overdue work is modelled rather than excluded (removes the
  current right-censoring guard).
* Random slopes for time within employees; Bayesian hierarchical models with partial pooling across business units.
* Multiple outcomes jointly (schedule, quality, risk mitigation) with correlated random effects.
* Rater-effect models for stakeholder and manager feedback (leniency, halo) to de-bias perception data.
* Sensitivity analysis for unmeasured confounding (E-values, Rosenbaum-style bounds).
* Power analysis: minimum evidence per person for a given interval width; adaptive abstention thresholds.
* Better-powered longitudinal change detection (v0.1 flags no improvers after FDR control).

## v0.3 — Real integrations with proper authorisation
* SSO (OIDC/SAML) replacing demo sign-in; SCIM provisioning; per-tenant key management.
* Production connectors: Jira Cloud, Asana, monday.com, Microsoft Graph (calendar, document approvals),
  Teams transcripts (delegated consent), Slack delivery — least-privilege scopes documented in the connector classes.
* Optional LLM provider for summaries behind the existing `LLMProvider` interface, with disclosure on every output.
* Incremental ingestion with watermarks, idempotent retries and dead-letter handling.

## v0.4 — Enterprise governance and model validation
* Works-council / DPIA workflow artefacts; configurable purpose limitation per data category.
* Model registry with approval gates, champion/challenger runs and automatic drift alerts.
* Independent validation reports; external fairness audit exports with small-cell suppression.
* Row-level security in PostgreSQL for tenant separation in depth; encrypted columns for sensitive fields.
* Data-subject request tooling (export, rectification, erasure) and legal-hold support.

## v1.0 — Commercial pilot readiness
* Pilot playbook with pre-registered evaluation of decision quality (not just model fit).
* Hardening: penetration test, SOC 2 controls, backup/restore, HA deployment, observability.
* Accessibility audit (WCAG 2.2 AA) and localisation.
* Pricing, support and customer success processes.
