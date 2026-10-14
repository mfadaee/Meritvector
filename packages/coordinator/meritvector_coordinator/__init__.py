"""MeritVector Work Coordinator — employee-facing assistance.

Independent of the performance-analysis engine: it imports nothing from
``meritvector_analytics`` and its outputs are stored as *assistance* data, which is
never reused for evaluation.
"""

from meritvector_coordinator.extraction import ActionItem, MeetingInsights, extract, resolve_date
from meritvector_coordinator.llm import DeterministicProvider, GenerationResult, LLMProvider, get_provider, register_provider
from meritvector_coordinator.reports import (
    daily_briefing,
    management_summary,
    project_documentation,
    reminders,
    unresolved_dependencies,
    weekly_status_report,
)
from meritvector_coordinator.retrieval import Document, search

__all__ = [
    "ActionItem",
    "DeterministicProvider",
    "Document",
    "GenerationResult",
    "LLMProvider",
    "MeetingInsights",
    "daily_briefing",
    "extract",
    "get_provider",
    "management_summary",
    "project_documentation",
    "register_provider",
    "reminders",
    "resolve_date",
    "search",
    "unresolved_dependencies",
    "weekly_status_report",
]
