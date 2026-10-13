"""Domain constants shared by the API, analytics, coordinator and connectors."""

from __future__ import annotations

from enum import StrEnum


class DataCategory(StrEnum):
    """The three processing purposes MeritVector keeps strictly separate.

    ``diagnostic_activity`` is a fourth, synthetic-only category used to show that
    activity volume (meetings, e-mails, hours) is *not* a measure of merit. It is
    never an input to individual estimates.
    """

    ASSISTANCE = "assistance"  # productivity help: transcripts, drafts, coordinator tasks
    ORG_REPORTING = "org_reporting"  # project registers, status, risks, dependencies
    ASSESSMENT_EVIDENCE = "assessment_evidence"  # validated work evidence for performance analysis
    DIAGNOSTIC_ACTIVITY = "diagnostic_activity"  # synthetic activity metadata, diagnostics only


DATA_CATEGORIES = tuple(c.value for c in DataCategory)


class Role(StrEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR_REVIEWER = "hr_reviewer"
    ADMIN = "admin"


ROLES = tuple(r.value for r in Role)

JOB_FAMILIES = ("program_manager", "project_manager", "technical_project_manager")

SOURCE_SYSTEMS = (
    "jira",
    "asana",
    "monday",
    "ms_teams",
    "outlook",
    "ms_graph",
    "slack",
    "pmo_register",
    "stakeholder_survey",
)

# Evidence event categories (Module 2).
EVENT_CATEGORIES = (
    "task_created",
    "task_completed",
    "milestone_achieved",
    "schedule_changed",
    "risk_identified",
    "risk_mitigated",
    "issue_raised",
    "blocker_raised",
    "blocker_resolved",
    "scope_change_approved",
    "document_reviewed",
    "stakeholder_feedback",
    "project_outcome",
    "resource_limitation",
    "complexity_assessment",
    "dependency_registered",
    "dependency_resolved",
    "activity_summary",
)

# Categories that may feed performance analysis. activity_summary is deliberately absent.
ASSESSMENT_EVENT_CATEGORIES = tuple(c for c in EVENT_CATEGORIES if c != "activity_summary")

# Records whose accuracy was successfully challenged (or that are under challenge)
# are excluded from engineered features.
EXCLUDED_VALIDATION_STATUSES = ("disputed", "retracted")

# Protected characteristics are held in a separate, access-controlled table and are
# only ever used for aggregated fairness auditing.
PROTECTED_ATTRIBUTE_COLUMNS = ("protected_group",)

# Columns that must never appear in a model's feature matrix. The hidden synthetic
# ground truth exists only to evaluate models in tests and the evaluation harness.
HIDDEN_GROUND_TRUTH_COLUMNS = (
    "true_contribution",
    "growth_per_year",
    "activity_propensity",
    "visibility",
    "archetype",
    "rater_leniency",
)

FORBIDDEN_MODEL_COLUMNS = (
    HIDDEN_GROUND_TRUTH_COLUMNS
    + PROTECTED_ATTRIBUTE_COLUMNS
    + (
        # Historical labels are potentially biased and must not be used as features.
        "manager_rating",
        "promoted",
        # Activity volume is diagnostic only.
        "meetings_attended",
        "emails_sent",
        "working_hours",
    )
)
