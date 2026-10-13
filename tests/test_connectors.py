import pytest

from meritvector_connectors import (
    Authorisation,
    DeliveryNotAuthorised,
    DeliveryPolicy,
    MockDataSource,
    OutboundMessage,
    build_connectors,
)
from meritvector_shared import EvidenceEvent


def _msg():
    return OutboundMessage("1", "ms_teams", "team", "Status", "Hello")


def test_delivery_disabled_by_default():
    src = MockDataSource()
    teams = build_connectors(src)["ms_teams"]
    with pytest.raises(DeliveryNotAuthorised):
        teams.deliver(_msg(), policy=DeliveryPolicy(), authorisation=Authorisation("1", "u", True))
    assert src.outbox == []


def test_delivery_requires_explicit_per_message_authorisation():
    src = MockDataSource()
    teams = build_connectors(src)["ms_teams"]
    on = DeliveryPolicy(external_delivery_enabled=True)
    with pytest.raises(DeliveryNotAuthorised):
        teams.deliver(_msg(), policy=on, authorisation=None)
    with pytest.raises(DeliveryNotAuthorised):
        teams.deliver(_msg(), policy=on, authorisation=Authorisation("other", "u", True))
    receipt = teams.deliver(_msg(), policy=on, authorisation=Authorisation("1", "u", True))
    assert receipt.status == "recorded_by_mock" and "nothing was sent" in receipt.detail
    assert len(src.outbox) == 1


def test_connectors_serve_valid_evidence(small_dataset):
    src = MockDataSource(events=small_dataset.events.to_dict("records"), meetings=small_dataset.meetings.to_dict("records"))
    conns = build_connectors(src)
    total = 0
    for c in conns.values():
        for rec in c.fetch_events():
            EvidenceEvent.model_validate(rec)
            assert rec["provenance"]["mock"] is True
            total += 1
    assert total == len(small_dataset.events)
    assert all(m["transcript"] for m in conns["ms_teams"].fetch_meetings())
    assert all("transcript" not in m for m in conns["outlook"].fetch_meetings())


def test_slack_never_ingests_messages():
    slack = build_connectors(MockDataSource())["slack"]
    assert slack.ingests == () and "messages" in slack.never_collects
    assert slack.fetch_events() == []


def test_evidence_schema_rejects_bad_records():
    base = dict(
        event_id="E-1",
        tenant_id="t",
        employee_id="e",
        occurred_at="2026-01-01T00:00:00",
        source_system="jira",
        category="milestone_achieved",
        data_category="assessment_evidence",
        evidence_ref="JIRA-1",
        provenance={"connector": "x", "ingest_batch": "b"},
    )
    EvidenceEvent.model_validate(base)
    for bad in ({"source_system": "keylogger"}, {"category": "browsing_history"}, {"provenance": {}}):
        with pytest.raises(ValueError):
            EvidenceEvent.model_validate(base | bad)
