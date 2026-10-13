"""Integration connectors.

v0.1 ships **mock** connectors only. They serve realistic records from the synthetic
dataset so the full pipeline runs without enterprise credentials. Each connector
documents the real API surface and least-privilege scopes it would need (v0.3).

Outbound delivery (Teams, Outlook, Slack) is disabled by default and requires both
an organisation-level setting *and* an explicit, per-message user authorisation.
Even then, mock connectors only record the message in an outbox — nothing leaves
the process.
"""

from meritvector_connectors.base import (
    Authorisation,
    Connector,
    DeliveryNotAuthorised,
    DeliveryPolicy,
    DeliveryReceipt,
    OutboundMessage,
)
from meritvector_connectors.mock import MockDataSource, build_connectors

__all__ = [
    "Authorisation",
    "Connector",
    "DeliveryNotAuthorised",
    "DeliveryPolicy",
    "DeliveryReceipt",
    "MockDataSource",
    "OutboundMessage",
    "build_connectors",
]
