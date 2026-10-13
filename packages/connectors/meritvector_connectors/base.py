"""Connector contracts and the outbound-delivery safety policy."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar


class DeliveryNotAuthorised(PermissionError):
    """Raised whenever an outbound message lacks organisational or user authorisation."""


@dataclass(frozen=True)
class OutboundMessage:
    message_id: str
    channel: str  # "teams" | "outlook" | "slack"
    recipient: str
    subject: str
    body: str


@dataclass(frozen=True)
class DeliveryPolicy:
    """Organisation-level switch. Off by default."""

    external_delivery_enabled: bool = False


@dataclass(frozen=True)
class Authorisation:
    """Explicit, per-message authorisation given by the sending user."""

    message_id: str
    authorised_by: str
    confirmed: bool
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DeliveryReceipt:
    message_id: str
    channel: str
    status: str
    detail: str


class Connector(ABC):
    """Base connector. Subclasses declare what they ingest and whether they can deliver."""

    name: ClassVar[str]
    vendor: ClassVar[str]
    mode: ClassVar[str] = "mock"
    ingests: ClassVar[tuple[str, ...]] = ()
    supports_delivery: ClassVar[bool] = False
    never_collects: ClassVar[tuple[str, ...]] = ()
    # Documentation of the production integration planned for v0.3 (not implemented).
    real_integration: ClassVar[dict[str, Any]] = {}

    def fetch_events(self, since: datetime | None = None) -> list[dict[str, Any]]:
        return []

    def fetch_meetings(self) -> list[dict[str, Any]]:
        return []

    def deliver(
        self, message: OutboundMessage, *, policy: DeliveryPolicy, authorisation: Authorisation | None
    ) -> DeliveryReceipt:
        if not self.supports_delivery:
            raise DeliveryNotAuthorised(f"{self.name} does not support outbound delivery")
        if not policy.external_delivery_enabled:
            raise DeliveryNotAuthorised("External delivery is disabled for this organisation (default).")
        if authorisation is None or not authorisation.confirmed or authorisation.message_id != message.message_id:
            raise DeliveryNotAuthorised("Explicit per-message authorisation from the sender is required.")
        return self._deliver(message)

    def _deliver(self, message: OutboundMessage) -> DeliveryReceipt:  # pragma: no cover - overridden
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "mode": self.mode,
            "ingests": list(self.ingests),
            "supports_delivery": self.supports_delivery,
            "never_collects": list(self.never_collects),
            "real_integration_plan": self.real_integration,
        }
