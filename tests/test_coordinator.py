import ast
from datetime import date
from pathlib import Path

from meritvector_coordinator import daily_briefing, extract, get_provider, reminders, resolve_date, unresolved_dependencies

TRANSCRIPT = """Priya: Thanks all. Quick status on the migration.
Tomasz: We are on track for the cutover rehearsal.
Priya: There's a risk that the vendor misses the hardware delivery date.
Tomasz: We're still waiting on Security Architecture for the firewall rule review.
Priya: So we've agreed to run the rehearsal on the staging cluster.
ACTION: Priya to send the revised estimate to the sponsor by Friday.
Tomasz: I'll update the runbook by tomorrow.
Priya: Tomasz, can you book the rehearsal room before 2026-10-20? Tomasz: Yes, will do.
Decision: freeze scope for release 2."""


def test_extracts_structured_items():
    ins = extract(TRANSCRIPT, date(2026, 10, 12), known_people={"Priya": "E1", "Tomasz": "E2"})
    acts = {(a.owner, a.description, a.due_date) for a in ins.actions}
    assert ("E1", "Send the revised estimate to the sponsor", "2026-10-16") in acts
    assert ("E2", "Update the runbook", "2026-10-13") in acts
    assert ("E2", "Book the rehearsal room", "2026-10-20") in acts
    assert {d["text"] for d in ins.decisions} == {"Run the rehearsal on the staging cluster", "Freeze scope for release 2"}
    assert ins.risks and "vendor" in ins.risks[0]["text"]
    assert ins.dependencies[0]["team"] == "Security Architecture"
    assert all(a.source_line for a in ins.actions)  # every item is traceable


def test_output_is_labelled_as_not_llm():
    ins = extract(TRANSCRIPT, date(2026, 10, 12))
    assert ins.generator == "deterministic"
    assert "no language model" in ins.disclosure
    assert get_provider("some-unavailable-llm").name == "deterministic"


def test_relative_dates():
    ref = date(2026, 10, 12)  # Monday
    assert resolve_date("tomorrow", ref) == "2026-10-13"
    assert resolve_date("Friday", ref) == "2026-10-16"
    assert resolve_date("end of week", ref) == "2026-10-16"
    assert resolve_date("2026-11-01", ref) == "2026-11-01"
    assert resolve_date("someday", ref) is None


def test_briefing_reminders_dependencies():
    today = date(2026, 10, 12)
    tasks = [
        {"id": 1, "title": "A", "due_date": "2026-10-10", "status": "open"},
        {"id": 2, "title": "B", "due_date": "2026-10-13", "status": "open"},
        {"id": 3, "title": "C", "due_date": "2026-10-01", "status": "done"},
    ]
    r = reminders(tasks, today)
    assert {x["kind"] for x in r} == {"overdue", "due_soon"} and len(r) == 2
    b = daily_briefing(person="Avery X", today=today, meetings=[], tasks=tasks, milestones=[], risks=[], decisions=[])
    assert b["counts"]["overdue_actions"] == 1 and "Avery" in b["text"]
    deps = unresolved_dependencies(
        [{"status": "open", "raised_on": "2026-09-01"}, {"status": "resolved", "raised_on": "2026-09-01"}], today
    )
    assert len(deps) == 1 and deps[0]["stale"]


def test_coordinator_is_independent_of_analytics():
    root = Path(__file__).resolve().parents[1] / "packages" / "coordinator" / "meritvector_coordinator"
    for f in root.glob("*.py"):
        mods = {n.module for n in ast.walk(ast.parse(f.read_text())) if isinstance(n, ast.ImportFrom) and n.module}
        mods |= {a.name for n in ast.walk(ast.parse(f.read_text())) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.startswith("meritvector_analytics") for m in mods), f.name
