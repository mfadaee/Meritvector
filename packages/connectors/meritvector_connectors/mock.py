"""Mock connectors backed by the synthetic dataset. No network calls are made."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from meritvector_connectors.base import Connector, DeliveryReceipt, OutboundMessage


@dataclass
class MockDataSource:
    """In-memory records the mocks serve (events and meetings as plain dicts)."""

    events: list[dict[str, Any]] = field(default_factory=list)
    meetings: list[dict[str, Any]] = field(default_factory=list)
    outbox: list[OutboundMessage] = field(default_factory=list)


class _EventMock(Connector):
    source_systems: tuple[str, ...] = ()

    def __init__(self, source: MockDataSource):
        self.source = source

    def fetch_events(self, since: datetime | None = None) -> list[dict[str, Any]]:
        out = []
        for e in self.source.events:
            if e["source_system"] not in self.source_systems:
                continue
            if since is not None and datetime.fromisoformat(str(e["occurred_at"])) <= since:
                continue
            rec = dict(e)
            rec["provenance"] = {**e.get("provenance", {}), "connector": f"mock:{self.name}", "mock": True}
            out.append(rec)
        return out


class JiraConnector(_EventMock):
    name, vendor = "jira", "Atlassian Jira"
    source_systems = ("jira",)
    ingests = ("task_created", "task_completed", "milestone_achieved", "blocker_raised", "blocker_resolved",
               "scope_change_approved", "dependency_registered", "dependency_resolved")
    never_collects = ("comment text", "attachments")
    real_integration = {"api": "Jira Cloud REST v3", "auth": "OAuth 2.0 (3LO)", "scopes": ["read:jira-work"],
                        "status": "planned for v0.3"}


class AsanaConnector(_EventMock):
    name, vendor = "asana", "Asana"
    source_systems = ("asana",)
    ingests = ("task_created", "task_completed", "milestone_achieved")
    never_collects = ("task comments", "private projects")
    real_integration = {"api": "Asana REST API 1.0", "auth": "OAuth 2.0", "scopes": ["default (read-only PAT not used)"],
                        "status": "planned for v0.3"}


class MondayConnector(_EventMock):
    name, vendor = "monday", "monday.com"
    source_systems = ("monday",)
    ingests = ("task_created", "task_completed", "milestone_achieved")
    never_collects = ("updates/comments",)
    real_integration = {"api": "monday.com GraphQL API v2", "auth": "OAuth 2.0", "scopes": ["boards:read"],
                        "status": "planned for v0.3"}


class GraphConnector(_EventMock):
    name, vendor = "ms_graph", "Microsoft Graph"
    source_systems = ("ms_graph",)
    ingests = ("document_reviewed", "activity_summary (metadata counts only, diagnostic)")
    never_collects = ("e-mail bodies", "chat messages", "keystrokes", "browsing history", "presence", "file contents")
    real_integration = {"api": "Microsoft Graph v1.0", "auth": "Entra ID app, admin consent",
                        "scopes": ["Sites.Read.All (document approval metadata)", "Reports.Read.All (aggregated usage, optional)"],
                        "status": "planned for v0.3"}


class PmoRegisterConnector(_EventMock):
    name, vendor = "pmo_register", "PMO register (internal)"
    source_systems = ("pmo_register",)
    ingests = ("complexity_assessment", "resource_limitation", "risk_identified", "risk_mitigated", "issue_raised",
               "schedule_changed", "project_outcome")
    real_integration = {"api": "CSV/SFTP or database export", "status": "planned for v0.3"}


class StakeholderSurveyConnector(_EventMock):
    name, vendor = "stakeholder_survey", "Stakeholder survey tool"
    source_systems = ("stakeholder_survey",)
    ingests = ("stakeholder_feedback",)
    real_integration = {"api": "Survey export (CSV)", "status": "planned for v0.3"}


class _DeliveryMock(Connector):
    supports_delivery = True

    def __init__(self, source: MockDataSource):
        self.source = source

    def _deliver(self, message: OutboundMessage) -> DeliveryReceipt:
        self.source.outbox.append(message)
        return DeliveryReceipt(message.message_id, self.name, "recorded_by_mock",
                               "Mock connector: message recorded locally; nothing was sent to an external service.")


class TeamsConnector(_DeliveryMock):
    name, vendor = "ms_teams", "Microsoft Teams"
    ingests = ("meeting transcripts for meetings the user organised or attended, with consent (assistance only)",)
    never_collects = ("1:1 chats", "channel messages", "call recordings")
    real_integration = {"api": "Microsoft Graph onlineMeetings/transcripts", "auth": "Delegated (user) consent",
                        "scopes": ["OnlineMeetingTranscript.Read.All (delegated)", "ChannelMessage.Send (delivery)"],
                        "status": "planned for v0.3"}

    def fetch_meetings(self) -> list[dict[str, Any]]:
        return [dict(m, source="mock:ms_teams") for m in self.source.meetings if m.get("transcript")]


class OutlookConnector(_DeliveryMock):
    name, vendor = "outlook", "Microsoft Outlook"
    ingests = ("calendar entries: subject, time, attendees",)
    never_collects = ("mail bodies", "mailbox contents")
    real_integration = {"api": "Microsoft Graph calendar/sendMail", "auth": "Delegated (user) consent",
                        "scopes": ["Calendars.Read", "Mail.Send (delivery, opt-in)"], "status": "planned for v0.3"}

    def fetch_meetings(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in m.items() if k != "transcript"} | {"source": "mock:outlook"}
                for m in self.source.meetings if not m.get("transcript")]


class SlackConnector(_DeliveryMock):
    name, vendor = "slack", "Slack"
    ingests = ()
    never_collects = ("messages", "DMs", "channel history")
    real_integration = {"api": "Slack Web API chat.postMessage", "auth": "OAuth (bot token)", "scopes": ["chat:write"],
                        "status": "planned for v0.3 (delivery only; no message ingestion)"}


CONNECTOR_CLASSES: tuple[type[Connector], ...] = (
    TeamsConnector, OutlookConnector, GraphConnector, SlackConnector, JiraConnector, AsanaConnector, MondayConnector,
    PmoRegisterConnector, StakeholderSurveyConnector,
)


def build_connectors(source: MockDataSource) -> dict[str, Connector]:
    return {cls.name: cls(source) for cls in CONNECTOR_CLASSES}  # type: ignore[call-arg]
