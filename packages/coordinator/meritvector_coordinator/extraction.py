"""Deterministic meeting intelligence: summaries, actions, decisions, risks, dependencies.

Transcripts are expected as ``Speaker: utterance`` lines (the format exported by
Teams/Zoom transcript connectors). Extraction is rule-based and explainable: every
extracted item carries the source line it came from.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from meritvector_coordinator.llm import get_provider

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DATE = (
    r"(\d{4}-\d{2}-\d{2}|tomorrow|today|end of (?:the )?week|next week|(?:next )?(?:monday|tuesday|wednesday|thursday|friday))"
)

_ACTION_PATTERNS = [
    # "ACTION: Avery to update the plan by 2026-10-20."
    re.compile(rf"^action:\s*(?P<owner>[A-Z][\w'-]+)\s+to\s+(?P<task>.+?)(?:\s+(?:by|before)\s+{_DATE})?[.!]?$", re.I),
    # "Avery: I'll update the plan by Friday."
    re.compile(rf"^(?P<owner>[A-Z][\w'-]+):\s*I(?:'ll| will)\s+(?P<task>.+?)(?:\s+(?:by|before)\s+{_DATE})?[.!]?$", re.I),
    # "Lead: Avery, can you update the plan before 2026-10-20? Avery: Yes, will do."
    re.compile(
        rf"^[A-Z][\w'-]+:\s*(?P<owner>[A-Z][\w'-]+),\s*(?:can|could) you\s+(?P<task>.+?)(?:\s+(?:by|before)\s+{_DATE})?\?", re.I
    ),
]
_DECISION_PATTERNS = [
    re.compile(r"(?:^|:\s*)decision:\s*(?P<text>.+?)[.!]?$", re.I),
    re.compile(r"we(?:'ve| have)? agreed to\s+(?P<text>.+?)[.!]?$", re.I),
    re.compile(r"let's go with\s+(?P<text>.+?)(?:,|\.|$)", re.I),
]
_RISK_PATTERNS = [
    re.compile(r"there(?:'s| is) a risk that\s+(?P<text>.+?)[.!]?$", re.I),
    re.compile(r"i'm worried (?:that )?(?P<text>.+?)[.!]?$", re.I),
]
_DEPENDENCY_PATTERNS = [
    re.compile(r"(?:still )?waiting on\s+(?P<team>[A-Z][\w& ]+?)\s+for\s+(?P<text>.+?)[.!]?$", re.I),
    re.compile(r"blocked by\s+(?P<team>[A-Z][\w& ]+?)\s+(?P<text>(?:approving|signing|delivering|providing).+?)[.!]?$", re.I),
]


@dataclass
class ActionItem:
    owner: str
    description: str
    due_date: str | None
    source_line: str


@dataclass
class MeetingInsights:
    summary: str
    actions: list[ActionItem] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    generator: str = ""
    disclosure: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def resolve_date(token: str | None, reference: date) -> str | None:
    if not token:
        return None
    t = token.strip().lower()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return t
    if t == "today":
        return str(reference)
    if t == "tomorrow":
        return str(reference + timedelta(days=1))
    if t.startswith("end of"):
        return str(reference + timedelta(days=(4 - reference.weekday()) % 7))
    if t == "next week":
        return str(reference + timedelta(days=7 - reference.weekday()))
    nxt = t.startswith("next ")
    day = t.replace("next ", "")
    if day in _WEEKDAYS:
        delta = (_WEEKDAYS.index(day) - reference.weekday()) % 7 or 7
        return str(reference + timedelta(days=delta + (7 if nxt and delta < 7 else 0)))
    return None


def _split_lines(transcript: str) -> list[str]:
    # Split compound lines such as "A: can you X? B: Yes" into separate utterances, keeping the question intact.
    out = []
    for raw in transcript.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = re.split(r"(?<=[?.!])\s+(?=[A-Z][\w'-]+:\s)", raw)
        out.extend(p.strip() for p in parts if p.strip())
    return out


def extract(transcript: str, meeting_date: date, known_people: dict[str, str] | None = None) -> MeetingInsights:
    """Extract structured insights. ``known_people`` maps first names to employee IDs."""
    lines = _split_lines(transcript)
    participants = sorted(
        {ln.split(":", 1)[0].strip() for ln in lines if ":" in ln and not ln.lower().startswith(("action:", "decision:"))}
    )
    actions: list[ActionItem] = []
    decisions, risks, deps = [], [], []
    seen_actions = set()
    for ln in lines:
        for pat in _ACTION_PATTERNS:
            mt = pat.search(ln)
            if mt:
                task = mt.group("task").strip().rstrip(".")
                key = (mt.group("owner").lower(), task.lower())
                if key not in seen_actions:
                    seen_actions.add(key)
                    groups = [g for g in mt.groups()[2:] if g] if len(mt.groups()) > 2 else []
                    actions.append(
                        ActionItem(
                            owner=mt.group("owner"),
                            description=task[0].upper() + task[1:],
                            due_date=resolve_date(groups[-1] if groups else None, meeting_date),
                            source_line=ln,
                        )
                    )
                break
        for pat in _DECISION_PATTERNS:
            mt = pat.search(ln)
            if mt:
                txt = mt.group("text").strip().rstrip(".")
                if txt.lower() not in {d["text"].lower() for d in decisions}:
                    decisions.append({"text": txt[0].upper() + txt[1:], "source_line": ln})
                break
        for pat in _RISK_PATTERNS:
            mt = pat.search(ln)
            if mt:
                risks.append({"text": mt.group("text").strip()[0].upper() + mt.group("text").strip()[1:], "source_line": ln})
                break
        for pat in _DEPENDENCY_PATTERNS:
            mt = pat.search(ln)
            if mt:
                deps.append({"team": mt.group("team").strip(), "text": mt.group("text").strip(), "source_line": ln})
                break
    if known_people:
        for a in actions:
            a.owner = known_people.get(a.owner, a.owner)
    summary_text = _summarise(lines, actions, decisions, risks, deps)
    gen = get_provider().generate(transcript, purpose="meeting_summary", fallback_text=summary_text)
    return MeetingInsights(
        summary=gen.text,
        actions=actions,
        decisions=decisions,
        risks=risks,
        dependencies=deps,
        participants=participants,
        generator=gen.provider,
        disclosure=gen.disclosure,
    )


def _summarise(lines, actions, decisions, risks, deps) -> str:
    status = next(
        (
            ln.split(":", 1)[1].strip()
            for ln in lines
            if re.search(r"on track|behind schedule|delayed|slipp", ln, re.I)
            and ":" in ln
            and not ln.lower().startswith("action")
        ),
        None,
    )
    parts = []
    if status:
        parts.append(f"Status: {status}")
    if decisions:
        parts.append(f"{len(decisions)} decision(s): " + "; ".join(d["text"] for d in decisions) + ".")
    if actions:
        parts.append(f"{len(actions)} action(s) assigned.")
    if risks:
        parts.append(f"{len(risks)} risk(s) raised: " + "; ".join(r["text"].rstrip(".") for r in risks) + ".")
    if deps:
        parts.append(f"{len(deps)} external dependency(ies) outstanding (" + ", ".join(sorted({d["team"] for d in deps})) + ").")
    return " ".join(parts) or "No structured items detected."
