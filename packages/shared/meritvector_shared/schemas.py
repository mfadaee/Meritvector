"""Pydantic schema for evidence records entering the evidence pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from meritvector_shared.constants import DATA_CATEGORIES, EVENT_CATEGORIES, SOURCE_SYSTEMS


class ValidationStatus(StrEnum):
    VALIDATED = "validated"  # confirmed by the system of record
    UNVALIDATED = "unvalidated"  # ingested but not yet confirmed
    DISPUTED = "disputed"  # under an open employee challenge — excluded from features
    CORRECTED = "corrected"  # challenge upheld and the record corrected
    RETRACTED = "retracted"  # challenge upheld and the record withdrawn — excluded


class EvidenceEvent(BaseModel):
    """One evidence record. Every field in Module 2's contract is mandatory except
    quality indicators, which are optional because not every source provides them."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=3)
    tenant_id: str
    employee_id: str
    project_id: str | None = None
    occurred_at: datetime
    source_system: str
    category: str
    data_category: str
    evidence_ref: str = Field(min_length=3, description="Pointer to the record in the source system")
    quality_indicators: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any]
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_system")
    @classmethod
    def _known_source(cls, v: str) -> str:
        if v not in SOURCE_SYSTEMS:
            raise ValueError(f"unknown source system {v!r}")
        return v

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in EVENT_CATEGORIES:
            raise ValueError(f"unknown event category {v!r}")
        return v

    @field_validator("data_category")
    @classmethod
    def _known_data_category(cls, v: str) -> str:
        if v not in DATA_CATEGORIES:
            raise ValueError(f"unknown data category {v!r}")
        return v

    @field_validator("provenance")
    @classmethod
    def _provenance_complete(cls, v: dict[str, Any]) -> dict[str, Any]:
        missing = {"connector", "ingest_batch"} - set(v)
        if missing:
            raise ValueError(f"provenance missing {sorted(missing)}")
        return v
