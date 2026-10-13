"""Briefings, status reports, documentation, reminders and dependency checks.

Inputs are plain dictionaries supplied by the caller (the API reads them from the
organisational-reporting and assistance tables). The coordinator never reads
performance-assessment outputs.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from meritvector_coordinator.llm import get_provider


def _d(x: Any) -> date | None:
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def daily_briefing(
    *,
    person: str,
    today: date,
    meetings: list[dict],
    tasks: list[dict],
    milestones: list[dict],
    risks: list[dict],
    decisions: list[dict],
) -> dict[str, Any]:
    todays = [m for m in meetings if _d(m["scheduled_at"]) == today]
    upcoming = [
        m for m in meetings if _d(m["scheduled_at"]) and today < _d(m["scheduled_at"]) <= date.fromordinal(today.toordinal() + 7)
    ]
    open_tasks = [t for t in tasks if t.get("status") != "done"]
    overdue = [t for t in open_tasks if _d(t.get("due_date")) and _d(t["due_date"]) < today]
    due_soon = [
        t for t in open_tasks if _d(t.get("due_date")) and today <= _d(t["due_date"]) <= date.fromordinal(today.toordinal() + 3)
    ]
    ms_soon = [
        m
        for m in milestones
        if m.get("status") != "achieved"
        and _d(m.get("planned_date"))
        and _d(m["planned_date"]) <= date.fromordinal(today.toordinal() + 14)
    ]
    high_risks = [r for r in risks if r.get("severity") == "high" and r.get("status") in ("open", "issue")]
    lines = [f"Good morning {person.split()[0]}. Briefing for {today:%A %d %B %Y}."]
    lines.append(f"Meetings today: {len(todays)}; in the next 7 days: {len(upcoming)}.")
    if overdue:
        lines.append(
            f"{len(overdue)} action(s) are overdue — oldest: “{sorted(overdue, key=lambda t: t['due_date'])[0]['title']}”."
        )
    if due_soon:
        lines.append(f"{len(due_soon)} action(s) due within 3 days.")
    if ms_soon:
        lines.append(f"{len(ms_soon)} milestone(s) due or overdue within 14 days.")
    if high_risks:
        lines.append(f"{len(high_risks)} high-severity risk(s)/issue(s) open on your projects.")
    if decisions:
        lines.append(f"Recent decision: {decisions[0]['text']}.")
    text = " ".join(lines)
    gen = get_provider().generate(text, purpose="daily_briefing", fallback_text=text)
    return {
        "text": gen.text,
        "generator": gen.provider,
        "disclosure": gen.disclosure,
        "counts": {
            "meetings_today": len(todays),
            "meetings_next_7_days": len(upcoming),
            "overdue_actions": len(overdue),
            "actions_due_soon": len(due_soon),
            "milestones_due_14d": len(ms_soon),
            "high_risks": len(high_risks),
        },
        "overdue": overdue,
        "due_soon": due_soon,
    }


def weekly_status_report(
    *,
    project: dict,
    milestones: list[dict],
    risks: list[dict],
    dependencies: list[dict],
    actions: list[dict],
    decisions: list[dict],
    health: str | None,
    today: date,
) -> dict[str, Any]:
    done = [m for m in milestones if m.get("status") == "achieved"]
    nxt = sorted([m for m in milestones if m.get("status") != "achieved"], key=lambda m: str(m["planned_date"]))
    open_r = [r for r in risks if r.get("status") in ("open", "issue")]
    open_d = [d for d in dependencies if d.get("status") == "open"]
    md = [
        f"# Weekly status — {project['name']}",
        f"*Week ending {today:%d %B %Y} · Overall health: **{(health or 'n/a').upper()}***",
        "",
        "## Progress",
        f"- Milestones achieved: {len(done)} of {len(milestones)}.",
    ]
    if nxt:
        md.append(f"- Next milestone: {nxt[0]['name']} (planned {str(nxt[0]['planned_date'])[:10]}, status {nxt[0]['status']}).")
    md += ["", "## Risks and issues"]
    md += [f"- [{r['severity'].upper()}] {r['title']} ({r['status']})" for r in open_r[:8]] or ["- None open."]
    md += ["", "## Dependencies"]
    md += [f"- Waiting on {d['depends_on']} since {str(d['raised_on'])[:10]}" for d in open_d] or ["- None outstanding."]
    md += ["", "## Decisions this period"]
    md += [f"- {d['text']}" for d in decisions[:6]] or ["- None recorded."]
    md += ["", "## Open actions"]
    md += [
        f"- {a['title']} — {a.get('owner_name', a.get('owner_employee_id', ''))}, due {a.get('due_date') or 'n/a'}"
        for a in actions[:10]
    ] or ["- None."]
    text = "\n".join(md)
    gen = get_provider().generate(text, purpose="weekly_status", fallback_text=text)
    return {"markdown": gen.text, "generator": gen.provider, "disclosure": gen.disclosure}


def management_summary(*, projects: list[dict], health: dict[str, str]) -> str:
    counts: dict[str, int] = {}
    for p in projects:
        h = health.get(p["project_id"], "n/a")
        counts[h] = counts.get(h, 0) + 1
    reds = [p["name"] for p in projects if health.get(p["project_id"]) == "red"]
    s = f"{len(projects)} projects: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + "."
    if reds:
        s += " Needing attention: " + "; ".join(reds[:5]) + ("…" if len(reds) > 5 else "") + "."
    return s


def project_documentation(*, project: dict, milestones: list[dict], risks: list[dict], dependencies: list[dict]) -> str:
    md = [
        f"# Project brief and RAID log — {project['name']}",
        f"Business unit: {project['business_unit']} · Lead: {project.get('lead_name', project['lead_employee_id'])} · "
        f"Start {str(project['start_date'])[:10]} · Planned end {str(project['planned_end'])[:10]}",
        "",
        "## Operating context (PMO assessment)",
        f"- Technical complexity: {project['technical_complexity']}/5; dependencies: {project['dependency_count']}; "
        f"team size: {project['team_size']}; resource constraint: {project['resource_constraint']:.2f}; "
        f"environment: {project['environment']}; maturity: {project['maturity']}.",
        "",
        "## Milestone plan",
        "| Milestone | Planned | Actual | Status |",
        "|---|---|---|---|",
    ]
    md += [
        f"| {m['name']} | {str(m['planned_date'])[:10]} | {str(m.get('actual_date') or '')[:10]} | {m['status']} |"
        for m in milestones
    ]
    md += ["", "## Risks (R) and issues (I)"]
    md += [f"- {'I' if r['kind'] == 'issue' else 'R'} · {r['title']} · {r['severity']} · {r['status']}" for r in risks] or [
        "- None."
    ]
    md += ["", "## Dependencies (D)"]
    md += [f"- {d['depends_on']}: {d['description']} · {d['status']}" for d in dependencies] or ["- None."]
    return "\n".join(md)


def reminders(tasks: list[dict], today: date, horizon_days: int = 2) -> list[dict]:
    out = []
    for t in tasks:
        due = _d(t.get("due_date"))
        if t.get("status") == "done" or not due:
            continue
        delta = (due - today).days
        if delta < 0:
            out.append({"task_id": t["id"], "kind": "overdue", "message": f"Overdue by {-delta} day(s): {t['title']}"})
        elif delta <= horizon_days:
            out.append({"task_id": t["id"], "kind": "due_soon", "message": f"Due in {delta} day(s): {t['title']}"})
    return out


def unresolved_dependencies(dependencies: list[dict], today: date, stale_days: int = 21) -> list[dict]:
    out = []
    for d in dependencies:
        raised = _d(d.get("raised_on"))
        if d.get("status") == "open" and raised:
            age = (today - raised).days
            out.append({**d, "age_days": age, "stale": age > stale_days})
    return sorted(out, key=lambda d: -d["age_days"])
