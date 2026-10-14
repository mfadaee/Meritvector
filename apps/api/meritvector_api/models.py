"""SQLAlchemy ORM models.

Tables are grouped by processing purpose (see PRIVACY_AND_GOVERNANCE.md):

* identity & governance — tenants, users, settings, approvals, audit log
* organisational reporting — projects, milestones, risks, dependencies
* assistance — meetings, insights, coordinator tasks, outbox, goals
* assessment evidence — evidence events (raw), challenges, model runs and outputs,
  review notes, historical labels
* controlled — protected attributes (aggregated fairness audit only)

Hidden synthetic ground truth is **never** stored in the database.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------- identity & governance
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    assessment_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    as_of: Mapped[date] = mapped_column(Date)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32))
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class GovernanceApproval(Base):
    __tablename__ = "governance_approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    purpose: Mapped[str] = mapped_column(Text)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str] = mapped_column(String(64))
    admin_approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hr_approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | approved | revoked
    created_at: Mapped[datetime] = mapped_column(DateTime)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_user_id: Mapped[str] = mapped_column(String(64))
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime, index=True)


# --------------------------------------------------------------- organisation
class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    job_family: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(8))
    business_unit: Mapped[str] = mapped_column(String(64))
    manager_id: Mapped[str] = mapped_column(String(64), index=True)
    joined_on: Mapped[date] = mapped_column(Date)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    business_unit: Mapped[str] = mapped_column(String(64))
    lead_employee_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[date] = mapped_column(Date)
    planned_end: Mapped[date] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    technical_complexity: Mapped[int] = mapped_column(Integer)
    dependency_count: Mapped[int] = mapped_column(Integer)
    resource_constraint: Mapped[float] = mapped_column(Float)
    size_band: Mapped[int] = mapped_column(Integer)
    team_size: Mapped[int] = mapped_column(Integer)
    environment: Mapped[str] = mapped_column(String(32))
    maturity: Mapped[str] = mapped_column(String(32))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    # v0.2: recorded context and responsibility dimensions from the PMO specification (not modelled).
    dimensions: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    owner_employee_id: Mapped[str] = mapped_column(String(64))
    planned_date: Mapped[date] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32))


class Risk(Base):
    __tablename__ = "risks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    owner_employee_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(16))
    identified_on: Mapped[date] = mapped_column(Date)
    mitigated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32), default="pmo_register")


class Dependency(Base):
    __tablename__ = "dependencies"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    owner_employee_id: Mapped[str] = mapped_column(String(64))
    depends_on: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300))
    raised_on: Mapped[date] = mapped_column(Date)
    resolved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16))


# --------------------------------------------------------------- assistance
class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    attendees: Mapped[list] = mapped_column(JSON, default=list)
    organiser_id: Mapped[str] = mapped_column(String(64))
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="mock:ms_teams")
    data_category: Mapped[str] = mapped_column(String(32), default="assistance")


class MeetingInsight(Base):
    __tablename__ = "meeting_insights"
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    decisions: Mapped[list] = mapped_column(JSON, default=list)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    generator: Mapped[str] = mapped_column(String(64))
    disclosure: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    data_category: Mapped[str] = mapped_column(String(32), default="assistance")


class CoordinatorTask(Base):
    __tablename__ = "coordinator_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    owner_employee_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    source_meeting_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    source_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    data_category: Mapped[str] = mapped_column(String(32), default="assistance")


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    delivered_in_app: Mapped[bool] = mapped_column(Boolean, default=True)


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    author_user_id: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    recipient: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    status_detail: Mapped[str | None] = mapped_column(String(400), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    authorised_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DevelopmentGoal(Base):
    __tablename__ = "development_goals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    competency: Mapped[str] = mapped_column(String(64))
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime)


# --------------------------------------------------------------- assessment evidence
class EvidenceEventRow(Base):
    """Raw evidence records as ingested. Engineered features are derived, never stored here."""

    __tablename__ = "evidence_events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    source_system: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32), index=True)
    data_category: Mapped[str] = mapped_column(String(32))
    evidence_ref: Mapped[str] = mapped_column(String(128))
    quality_indicators: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_status: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(DateTime)


Index("ix_evidence_tenant_employee_category", EvidenceEventRow.tenant_id, EvidenceEventRow.employee_id, EvidenceEventRow.category)


class EvidenceChallenge(Base):
    __tablename__ = "evidence_challenges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("evidence_events.event_id"))
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(Text)
    proposed_correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_status: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ManagerRating(Base):
    """Historical rating labels — treated as potentially biased, never as features."""

    __tablename__ = "historical_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    rater_id: Mapped[str] = mapped_column(String(64))
    period: Mapped[str] = mapped_column(String(8))
    rating: Mapped[int] = mapped_column(Integer)


class Promotion(Base):
    __tablename__ = "historical_promotions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    cycle: Mapped[str] = mapped_column(String(8))
    promoted: Mapped[bool] = mapped_column(Boolean)


class ProtectedAttribute(Base):
    """Access-controlled. Read only by the aggregated fairness audit."""

    __tablename__ = "protected_attributes"
    employee_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    protected_group: Mapped[str] = mapped_column(String(16))


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # version string
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16))
    data_hash: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    experiment: Mapped[dict] = mapped_column(JSON, default=dict)
    fairness: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    portfolio: Mapped[dict] = mapped_column(JSON, default=dict)
    synthetic_evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flagship: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_card: Mapped[str] = mapped_column(Text, default="")
    artifact_path: Mapped[str] = mapped_column(String(400))


class EmployeeRunOutput(Base):
    __tablename__ = "employee_run_outputs"
    run_id: Mapped[str] = mapped_column(ForeignKey("model_runs.id"), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ReviewNote(Base):
    """Append-only human review record. There is no update or delete endpoint."""

    __tablename__ = "review_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    author_user_id: Mapped[str] = mapped_column(String(64))
    author_role: Mapped[str] = mapped_column(String(32))
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agreement: Mapped[str] = mapped_column(String(32))
    judgement: Mapped[str] = mapped_column(Text)
    disagreement_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


# --------------------------------------------------------------- workflows
class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(String(300))
    interval_minutes: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(64), index=True)
    trigger: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


# --------------------------------------------------------------- research laboratory (v0.2)
class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    description: Mapped[str] = mapped_column(String(300))
    counts: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchRun(Base):
    __tablename__ = "research_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    workstream: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16))  # queued | running | completed | failed
    evidence_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # exploratory | confirmatory
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reproduces_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reproduced_identically: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ModelRegistryEntry(Base):
    __tablename__ = "model_registry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(64))
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="registered")
    registered_at: Mapped[datetime] = mapped_column(DateTime)


# --------------------------------------------------------------- deep work intelligence (v0.2)
class EvidenceLink(Base):
    """A person-recorded link between two register records (e.g. a mitigation that protected a milestone)."""

    __tablename__ = "evidence_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    from_type: Mapped[str] = mapped_column(String(16))
    from_id: Mapped[str] = mapped_column(String(96))
    to_type: Mapped[str] = mapped_column(String(16))
    to_id: Mapped[str] = mapped_column(String(96))
    relation: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Attribution(Base):
    """A person's own account of their contribution to a record. Self-reported narrative — never model input."""

    __tablename__ = "attributions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(96))
    role: Mapped[str] = mapped_column(String(16))  # led | contributed | supported | advised
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="claimed")  # claimed | confirmed | disputed
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_category: Mapped[str] = mapped_column(String(32), default="self_reported")
