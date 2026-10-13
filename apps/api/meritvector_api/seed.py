"""Bootstrap: generate synthetic organisations, load them, ingest evidence, train.

Evidence is not inserted directly: it is served by the mock connectors and passes
through the same validated ingestion path a real integration would use.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from meritvector_analytics.synthetic import SANDBOX_CONFIG, SyntheticConfig, SyntheticDataset, generate
from meritvector_api import audit
from meritvector_api.db import create_all
from meritvector_api.ingestion import ingest
from meritvector_api.models import (
    Dependency,
    Employee,
    GovernanceApproval,
    ManagerRating,
    Meeting,
    Milestone,
    Project,
    Promotion,
    ProtectedAttribute,
    Risk,
    Tenant,
    User,
)
from meritvector_api.services import process_meeting
from meritvector_api.settings import get_settings
from meritvector_api.workflows import register_default_jobs
from meritvector_connectors import MockDataSource, build_connectors

log = logging.getLogger(__name__)


def _recorded_fields() -> list[str]:
    from meritvector_analytics.measurement import load_job_family

    spec = load_job_family("pmo")
    return [
        d.field
        for d in spec.context_dimensions + spec.responsibility_dimensions
        if d.status == "recorded" and d.field and d.field != "risks_owned"
    ]


RECORDED_DIMENSION_FIELDS = _recorded_fields()

DEFAULT_NOTICE = (
    "MeritVector processes work records from approved business systems (project tools, the PMO register, "
    "document approvals and stakeholder surveys). It does not read e-mail or chat content, record keystrokes, "
    "capture screens, track browsing or monitor location. Meeting transcripts are processed only to help you "
    "with follow-ups and are never used to assess your performance."
)
DEFAULT_PURPOSE = (
    "Performance-evidence analysis summarises validated work evidence in the context of project conditions to "
    "support fair, evidence-based development conversations. It does not make or recommend promotion, pay, "
    "dismissal or hiring decisions, does not rank employees, and every employment-related use requires review by "
    "a qualified person. You can see all evidence held about you and challenge anything inaccurate."
)


def default_settings() -> dict[str, Any]:
    return {
        "notice_text": DEFAULT_NOTICE,
        "assessment_purpose": DEFAULT_PURPOSE,
        "external_delivery_enabled": False,
        "transcript_processing_enabled": True,
        "retention_days": {
            "assistance": 180,
            "diagnostic_activity": 800,
            "org_reporting": 1095,
            "assessment_evidence": 1095,
            "audit_log": 2555,
        },
        "data_minimisation": {
            "collect_message_content": False,
            "collect_keystrokes": False,
            "collect_browsing": False,
            "collect_location": False,
        },
    }


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for r in df.to_dict("records"):
        out.append({k: (None if (not isinstance(v, list | dict) and pd.isna(v)) else v) for k, v in r.items()})
    return out


def _d(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def load_dataset(db: Session, ds: SyntheticDataset, *, enable_assessment: bool) -> dict[str, Any]:
    cfg = ds.config
    tid = cfg.tenant_id
    db.add(
        Tenant(
            id=tid,
            name=cfg.tenant_name,
            is_synthetic=True,
            assessment_enabled=False,
            as_of=cfg.as_of,
            settings=default_settings(),
        )
    )
    db.flush()
    db.execute(
        insert(Employee),
        [
            {
                "id": r["employee_id"],
                "tenant_id": tid,
                "display_name": r["display_name"],
                "job_family": r["job_family"],
                "level": r["level"],
                "business_unit": r["business_unit"],
                "manager_id": r["manager_id"],
                "joined_on": _d(r["joined_on"]),
                "is_synthetic": True,
            }
            for r in _records(ds.employees)
        ],
    )
    db.execute(
        insert(Project),
        [
            {
                "id": r["project_id"],
                "tenant_id": tid,
                "name": r["name"],
                "business_unit": r["business_unit"],
                "lead_employee_id": r["lead_employee_id"],
                "kind": r["kind"],
                "start_date": _d(r["start_date"]),
                "planned_end": _d(r["planned_end"]),
                "actual_end": _d(r["actual_end"]),
                "status": r["status"],
                "technical_complexity": int(r["technical_complexity"]),
                "dependency_count": int(r["dependency_count"]),
                "resource_constraint": float(r["resource_constraint"]),
                "size_band": int(r["size_band"]),
                "team_size": int(r["team_size"]),
                "environment": r["environment"],
                "maturity": r["maturity"],
                "is_synthetic": True,
                "dimensions": {k: r[k] for k in RECORDED_DIMENSION_FIELDS if k in r},
            }
            for r in _records(ds.projects)
        ],
    )
    db.execute(
        insert(Milestone),
        [
            {
                "id": r["milestone_id"],
                "tenant_id": tid,
                "project_id": r["project_id"],
                "name": r["name"],
                "owner_employee_id": r["owner_employee_id"],
                "planned_date": _d(r["planned_date"]),
                "actual_date": _d(r["actual_date"]),
                "status": r["status"],
            }
            for r in _records(ds.milestones)
        ],
    )
    db.execute(
        insert(Risk),
        [
            {
                "id": r["risk_id"],
                "tenant_id": tid,
                "project_id": r["project_id"],
                "owner_employee_id": r["owner_employee_id"],
                "title": r["title"],
                "severity": r["severity"],
                "identified_on": _d(r["identified_on"]),
                "mitigated_on": _d(r["mitigated_on"]),
                "status": r["status"],
                "kind": r["kind"],
            }
            for r in _records(ds.risks)
        ],
    )
    if len(ds.dependencies):
        db.execute(
            insert(Dependency),
            [
                {
                    "id": r["dependency_id"],
                    "tenant_id": tid,
                    "project_id": r["project_id"],
                    "owner_employee_id": r["owner_employee_id"],
                    "depends_on": r["depends_on"],
                    "description": r["description"],
                    "raised_on": _d(r["raised_on"]),
                    "resolved_on": _d(r["resolved_on"]),
                    "status": r["status"],
                }
                for r in _records(ds.dependencies)
            ],
        )
    db.execute(
        insert(ManagerRating),
        [
            {
                "tenant_id": tid,
                "employee_id": r["employee_id"],
                "rater_id": r["rater_id"],
                "period": r["period"],
                "rating": int(r["manager_rating"]),
            }
            for r in _records(ds.manager_ratings)
        ],
    )
    db.execute(
        insert(Promotion),
        [
            {"tenant_id": tid, "employee_id": r["employee_id"], "cycle": r["cycle"], "promoted": bool(r["promoted"])}
            for r in _records(ds.promotions)
        ],
    )
    db.execute(
        insert(ProtectedAttribute),
        [
            {"employee_id": r["employee_id"], "tenant_id": tid, "protected_group": r["protected_group"]}
            for r in _records(ds.protected_attributes)
        ],
    )

    # Users: every employee signs in as themselves; programme managers hold the manager role.
    users = [
        {
            "id": f"u-{r['employee_id']}",
            "tenant_id": tid,
            "employee_id": r["employee_id"],
            "display_name": r["display_name"],
            "role": "manager" if r["job_family"] == "program_manager" else "employee",
            "preferences": {},
        }
        for r in _records(ds.employees)
    ]
    prefix = cfg.id_prefix
    users += [
        {
            "id": f"u-{prefix}-HR1",
            "tenant_id": tid,
            "employee_id": None,
            "display_name": "HR Reviewer One (synthetic)",
            "role": "hr_reviewer",
            "preferences": {},
        },
        {
            "id": f"u-{prefix}-HR2",
            "tenant_id": tid,
            "employee_id": None,
            "display_name": "HR Reviewer Two (synthetic)",
            "role": "hr_reviewer",
            "preferences": {},
        },
        {
            "id": f"u-{prefix}-ADMIN",
            "tenant_id": tid,
            "employee_id": None,
            "display_name": "Platform Administrator (synthetic)",
            "role": "admin",
            "preferences": {},
        },
        {
            "id": f"u-{prefix}-RES",
            "tenant_id": tid,
            "employee_id": None,
            "display_name": "Research Analyst (synthetic)",
            "role": "researcher",
            "preferences": {},
        },
    ]
    db.execute(insert(User), users)
    db.commit()

    # Meetings are assistance data from the (mock) Teams and Outlook connectors.
    source = MockDataSource(events=_records(ds.events), meetings=_records(ds.meetings))
    connectors = build_connectors(source)
    meetings = connectors["ms_teams"].fetch_meetings() + connectors["outlook"].fetch_meetings()
    db.execute(
        insert(Meeting),
        [
            {
                "id": m["meeting_id"],
                "tenant_id": tid,
                "project_id": m["project_id"],
                "title": m["title"],
                "scheduled_at": datetime.fromisoformat(m["scheduled_at"]),
                "attendees": list(m["attendees"]),
                "organiser_id": m["organiser_id"],
                "transcript": m.get("transcript"),
                "source": m["source"],
                "data_category": "assistance",
            }
            for m in meetings
        ],
    )
    db.commit()

    # Evidence enters through connectors -> validated ingestion.
    reports = []
    batch = f"bootstrap-{cfg.seed}"
    for name, conn in connectors.items():
        recs = conn.fetch_events()
        if recs:
            reports.append(ingest(db, recs, connector=name, tenant_id=tid, batch=batch).__dict__)

    # Coordinator processes the latest transcripts and creates follow-up tasks.
    sys_user = f"u-{prefix}-ADMIN"
    n_processed = 0
    for m in db.scalars(select(Meeting).where(Meeting.tenant_id == tid, Meeting.transcript.is_not(None))):
        process_meeting(db, m, actor_user_id=sys_user)
        n_processed += 1

    if enable_assessment:
        # Seeded governance approval for the synthetic demo tenant (clearly recorded as such).
        db.add(
            GovernanceApproval(
                tenant_id=tid,
                purpose=DEFAULT_PURPOSE,
                scope={
                    "features": ["contribution_evidence", "contextual_analysis", "development_insights", "model_validation"],
                    "note": "Seeded approval for the synthetic demonstration tenant.",
                },
                requested_by=f"u-{prefix}-ADMIN",
                admin_approved_by=f"u-{prefix}-ADMIN",
                hr_approved_by=f"u-{prefix}-HR1",
                status="approved",
                created_at=audit.now(),
                decided_at=audit.now(),
            )
        )
        db.get(Tenant, tid).assessment_enabled = True
    audit.record(
        db,
        tenant_id=tid,
        actor_user_id="system",
        actor_role="system",
        action="bootstrap",
        resource_type="tenant",
        resource_id=tid,
        detail={
            "seed": cfg.seed,
            "ingest": reports,
            "transcripts_processed": n_processed,
            "assessment_enabled": enable_assessment,
        },
    )
    return {"tenant": tid, "ingest": reports, "transcripts_processed": n_processed}


def bootstrap(
    db: Session, *, train: bool = True, config: SyntheticConfig | None = None, sandbox: bool = True, n_boot: int | None = None
) -> dict[str, Any]:
    create_all()
    register_default_jobs(db)
    s = get_settings()
    cfg = config or SyntheticConfig()
    summary: dict[str, Any] = {}
    plans = [(cfg, True)] + ([(SANDBOX_CONFIG, False)] if sandbox else [])
    for c, enable in plans:
        if db.get(Tenant, c.tenant_id) is not None:
            summary[c.tenant_id] = "already loaded"
            continue
        ds = generate(c)
        ds.write(s.data_dir / c.tenant_id)
        summary[c.tenant_id] = load_dataset(db, ds, enable_assessment=enable)
        log.info("loaded tenant %s: %s", c.tenant_id, ds.metadata["counts"])
    if train:
        from meritvector_api.training import latest_run, train_tenant

        for c, enable in plans:
            if enable and latest_run(db, c.tenant_id) is None:
                run = train_tenant(db, c.tenant_id, n_boot=n_boot)
                summary[f"{c.tenant_id}:model_run"] = run.id
    return summary
