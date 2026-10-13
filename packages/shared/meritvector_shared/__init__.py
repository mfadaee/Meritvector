"""Shared domain vocabulary for MeritVector.

Everything that more than one module must agree on lives here: data categories,
roles, evidence event categories, the evidence record schema and the list of
columns that must never reach a model.
"""

from meritvector_shared.constants import (
    ASSESSMENT_EVENT_CATEGORIES,
    DATA_CATEGORIES,
    EVENT_CATEGORIES,
    EXCLUDED_VALIDATION_STATUSES,
    FORBIDDEN_MODEL_COLUMNS,
    JOB_FAMILIES,
    PROTECTED_ATTRIBUTE_COLUMNS,
    ROLES,
    SOURCE_SYSTEMS,
    DataCategory,
    Role,
)
from meritvector_shared.schemas import EvidenceEvent, ValidationStatus

__all__ = [
    "ASSESSMENT_EVENT_CATEGORIES",
    "DATA_CATEGORIES",
    "EVENT_CATEGORIES",
    "EXCLUDED_VALIDATION_STATUSES",
    "FORBIDDEN_MODEL_COLUMNS",
    "JOB_FAMILIES",
    "PROTECTED_ATTRIBUTE_COLUMNS",
    "ROLES",
    "SOURCE_SYSTEMS",
    "DataCategory",
    "EvidenceEvent",
    "Role",
    "ValidationStatus",
]
