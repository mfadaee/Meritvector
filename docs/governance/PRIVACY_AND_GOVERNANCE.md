# Privacy and governance

## Commitments
* Transparent, disclosed processing. A configurable workplace notice and assessment-purpose disclosure are shown in
  *Administration & Privacy* and can be acknowledged (audited).
* **No covert monitoring.** Never collected: e-mail/chat content, keystrokes, screens, browsing, location,
  webcam/microphone outside meetings a user chooses to transcribe.
* No automated adverse employment actions; no rankings; human review required.
* Protected characteristics never enter individual estimates.

## Three separated purposes
| Purpose | Data | Used for assessment |
|---|---|---|
| Productivity assistance | Transcripts, summaries, coordinator tasks, drafts, reminders, goals | **Never** |
| Organisational reporting | Project registers: milestones, risks, dependencies, health | Never directly |
| Performance-assessment evidence | Validated work evidence events | Only after governance approval |

Enforcement: features are built only from `data_category = assessment_evidence`; the coordinator package does not
import analytics; completing a coordinator task creates no evidence (tested); transcripts are visible to attendees
only. Synthetic activity metadata is tagged `diagnostic_activity` and excluded from estimates.

## Governance gate
Assessment features (contribution pages, contextual analysis, development insights, model validation, training) are
disabled per tenant until an **administrator requests** and an **HR reviewer approves** a stated purpose. Either role
can revoke immediately. The synthetic demo tenant carries a seeded approval record; the sandbox tenant does not.

## Roles
| Role | Can | Cannot |
|---|---|---|
| Employee | Own workspace, own evidence (all of it), challenge records, own development record, see review notes about them | Other people's evidence; analysis pages |
| Manager | Above + contribution detail and team insights for **direct reports**; record reviews; resolve challenges for reports | Anyone outside their team; fairness audit |
| HR reviewer | Contribution detail across the tenant; governance approval; aggregated fairness audit; resolve challenges; trigger retraining | Change settings; view transcripts |
| Administrator | Settings, notice, retention, jobs, roles, audit log, governance request, aggregated validation and fairness | **Any individual performance evidence** (data minimisation) |

Tenant separation: every query is scoped to the caller's tenant; cross-tenant identifiers return 404.

## Correction workflow
An employee challenges any of their assessment records → the record becomes `disputed` and leaves the analysis →
their manager or HR resolves it as *upheld (retract)*, *upheld (corrected)* or *rejected* with a note → status
updates; the next training run reflects it. Every step is audited.

## Human review
Managers and HR record append-only review notes with agreement level, their own judgement, reasons for disagreeing
with the data (required when disagreeing) and context the data misses. There is no edit or delete endpoint.

## Retention
Per-category retention (days) is configurable; the `retention_enforcement` job deletes meeting insights, clears
transcripts and outbox messages past the assistance retention period, deletes diagnostic activity past its period and
prunes the audit log past its period.

## Outbound messages
Disabled by default per organisation. When enabled, each message still needs explicit sender confirmation; in v0.1
mock connectors record messages locally and nothing leaves the process.

## Credentials and secrets
No enterprise credentials are needed. `MV_SECRET_KEY` comes from the environment (never hard-coded; an ephemeral key
is generated if missing). `.env` is git-ignored; CI runs a secret scan over tracked files.

## Fairness auditing
Runs inside the training pipeline on a controlled table; outputs group aggregates only with small-cell suppression
(n < 20) and bootstrap intervals; visible to HR reviewers and administrators only.

## Before any real deployment
SSO, DPIA and works-council consultation, purpose-limitation review, retention sign-off, security review and an
independent validation on the organisation's own data (see [ROADMAP](../ROADMAP.md)).
