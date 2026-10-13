"""Persistent scheduled-job abstraction with a local runner.

Jobs are rows in ``scheduled_jobs``; each execution is recorded in ``job_runs``.
``run_due_jobs`` executes whatever is due; the ``worker`` CLI command calls it in a
loop. No distributed infrastructure is required.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from meritvector_api.audit import now
from meritvector_api.models import (
    AuditLog,
    CoordinatorTask,
    EvidenceEventRow,
    JobRun,
    Meeting,
    MeetingInsight,
    OutboxMessage,
    Reminder,
    ScheduledJob,
    Tenant,
)
from meritvector_api.services import process_meeting, tenant_today
from meritvector_coordinator import reminders

log = logging.getLogger(__name__)
JobFn = Callable[[Session], dict[str, Any]]
REGISTRY: dict[str, tuple[str, int, JobFn]] = {}


def job(name: str, description: str, interval_minutes: int):
    def deco(fn: JobFn) -> JobFn:
        REGISTRY[name] = (description, interval_minutes, fn)
        return fn

    return deco


@job("deadline_reminders", "Create in-app reminders for coordinator tasks due within 2 days or overdue", 60)
def _reminders(db: Session) -> dict[str, Any]:
    created = 0
    for tenant in db.scalars(select(Tenant)):
        today = tenant_today(db, tenant.id)
        tasks = db.scalars(select(CoordinatorTask).where(CoordinatorTask.tenant_id == tenant.id,
                                                         CoordinatorTask.status != "done")).all()
        db.execute(delete(Reminder).where(Reminder.tenant_id == tenant.id))
        by_id = {t.id: t for t in tasks}
        for r in reminders([{"id": t.id, "title": t.title, "due_date": t.due_date, "status": t.status} for t in tasks], today):
            t = by_id[r["task_id"]]
            db.add(Reminder(tenant_id=tenant.id, employee_id=t.owner_employee_id, task_id=t.id, kind=r["kind"],
                            message=r["message"], created_at=now()))
            created += 1
    db.commit()
    return {"reminders": created}


@job("process_new_transcripts", "Run meeting intelligence on transcripts that have no insights yet", 30)
def _transcripts(db: Session) -> dict[str, Any]:
    done = 0
    for tenant in db.scalars(select(Tenant)):
        if not tenant.settings.get("transcript_processing_enabled", True):
            continue
        processed = set(db.scalars(select(MeetingInsight.meeting_id).where(MeetingInsight.tenant_id == tenant.id)))
        for m in db.scalars(select(Meeting).where(Meeting.tenant_id == tenant.id, Meeting.transcript.is_not(None))):
            if m.id not in processed:
                process_meeting(db, m, actor_user_id="system")
                done += 1
    return {"processed": done}


@job("retention_enforcement", "Delete data older than each tenant's configured retention period", 1440)
def _retention(db: Session) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tenant in db.scalars(select(Tenant)):
        ret = tenant.settings.get("retention_days", {})
        today = tenant_today(db, tenant.id)
        stats: dict[str, int] = {}
        if "assistance" in ret:
            cutoff = datetime.combine(today - timedelta(days=int(ret["assistance"])), time.min)
            old = [m.id for m in db.scalars(select(Meeting).where(Meeting.tenant_id == tenant.id, Meeting.scheduled_at < cutoff))]
            stats["meeting_insights"] = db.execute(delete(MeetingInsight).where(MeetingInsight.meeting_id.in_(old))).rowcount
            stats["transcripts_cleared"] = db.execute(
                update(Meeting).where(Meeting.id.in_(old), Meeting.transcript.is_not(None)).values(transcript=None)).rowcount
            stats["outbox"] = db.execute(delete(OutboxMessage).where(OutboxMessage.tenant_id == tenant.id,
                                                                     OutboxMessage.created_at < cutoff)).rowcount
        if "diagnostic_activity" in ret:
            cutoff = datetime.combine(today - timedelta(days=int(ret["diagnostic_activity"])), time.min)
            stats["diagnostic_events"] = db.execute(delete(EvidenceEventRow).where(
                EvidenceEventRow.tenant_id == tenant.id, EvidenceEventRow.data_category == "diagnostic_activity",
                EvidenceEventRow.occurred_at < cutoff)).rowcount
        if "audit_log" in ret:
            cutoff = now() - timedelta(days=int(ret["audit_log"]))
            stats["audit_entries"] = db.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant.id, AuditLog.at < cutoff)).rowcount
        out[tenant.id] = stats
    db.commit()
    return out


@job("retrain_models", "Retrain analytics for tenants with governance-approved assessment", 10080)
def _retrain(db: Session) -> dict[str, Any]:
    from meritvector_api.training import train_tenant

    runs = {}
    for tenant in db.scalars(select(Tenant).where(Tenant.assessment_enabled.is_(True))):
        runs[tenant.id] = train_tenant(db, tenant.id).id
    return {"runs": runs}


def register_default_jobs(db: Session) -> None:
    for name, (desc, interval, _) in REGISTRY.items():
        if db.get(ScheduledJob, name) is None:
            db.add(ScheduledJob(name=name, description=desc, interval_minutes=interval, enabled=True,
                                next_run_at=now() + timedelta(minutes=interval)))
    db.commit()


def run_job(db: Session, name: str, trigger: str = "manual") -> JobRun:
    if name not in REGISTRY:
        raise KeyError(name)
    run = JobRun(job_name=name, trigger=trigger, started_at=now(), status="running", detail={})
    db.add(run)
    db.commit()
    try:
        detail = REGISTRY[name][2](db)
        run.status, run.detail = "succeeded", detail
    except Exception as exc:  # noqa: BLE001 - job failures are recorded, not raised
        db.rollback()
        run = db.get(JobRun, run.id)
        run.status, run.detail = "failed", {"error": str(exc), "trace": traceback.format_exc()[-2000:]}
        log.exception("job %s failed", name)
    run.finished_at = now()
    sj = db.get(ScheduledJob, name)
    if sj is not None:
        sj.last_run_at, sj.last_status = run.finished_at, run.status
        sj.next_run_at = run.finished_at + timedelta(minutes=sj.interval_minutes)
    db.commit()
    return run


def run_due_jobs(db: Session) -> list[JobRun]:
    due = db.scalars(select(ScheduledJob).where(ScheduledJob.enabled.is_(True), ScheduledJob.next_run_at <= now())).all()
    return [run_job(db, j.name, trigger="schedule") for j in due]
