"""Evidence ingestion: connector records -> validated raw evidence events.

Every record is validated against :class:`meritvector_shared.EvidenceEvent`. Records
that fail validation are rejected (and counted), duplicates are skipped by
``event_id``, and provenance is stamped with the ingest batch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from meritvector_api.audit import now
from meritvector_api.models import EvidenceEventRow
from meritvector_shared import EvidenceEvent


@dataclass
class IngestReport:
    connector: str
    received: int = 0
    inserted: int = 0
    duplicates: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)


def ingest(db: Session, records: list[dict[str, Any]], *, connector: str, tenant_id: str, batch: str) -> IngestReport:
    rep = IngestReport(connector=connector, received=len(records))
    existing = set(db.scalars(select(EvidenceEventRow.event_id).where(EvidenceEventRow.tenant_id == tenant_id)))
    rows = []
    ts = now()
    for rec in records:
        try:
            rec = dict(rec)
            rec["provenance"] = {**rec.get("provenance", {}), "ingest_batch": batch, "ingested_via": connector}
            ev = EvidenceEvent.model_validate(rec)
        except ValidationError as exc:
            rep.rejected += 1
            if len(rep.errors) < 5:
                rep.errors.append(str(exc).splitlines()[0])
            continue
        if ev.tenant_id != tenant_id:
            rep.rejected += 1
            continue
        if ev.event_id in existing:
            rep.duplicates += 1
            continue
        existing.add(ev.event_id)
        d = ev.model_dump()
        d["occurred_at"] = ev.occurred_at.replace(tzinfo=None) if isinstance(ev.occurred_at, datetime) else ev.occurred_at
        d["validation_status"] = ev.validation_status.value
        d["ingested_at"] = ts
        rows.append(d)
    for i in range(0, len(rows), 5000):
        db.execute(insert(EvidenceEventRow), rows[i : i + 5000])
    db.commit()
    rep.inserted = len(rows)
    return rep
