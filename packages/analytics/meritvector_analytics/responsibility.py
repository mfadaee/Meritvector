"""Responsibility scope and labelled operating conditions, driven by the job-family specification.

Responsibility describes the scope of work a person holds (decision authority, budget accountability, teams
coordinated…). It is context for interpreting outcomes — it is not merit and is never added to an estimate.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from meritvector_analytics.measurement import load_job_family
from meritvector_analytics.measurement.spec import Dimension

SCOPE_NOTE = (
    "Describes the scope of work held, as recorded in the PMO register. Scope is context for interpreting outcomes: "
    "a wider scope is not better performance and is not added to any estimate."
)


def _display(dim: Dimension, value: Any) -> str:
    if value is None:
        return "Not recorded"
    if dim.scale and dim.scale.type == "boolean":
        return "Yes" if value else "No"
    if dim.scale and dim.scale.type == "ordinal" and dim.scale.max is not None:
        return f"{value} of {dim.scale.max:g}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _entry(dim: Dimension, value: Any) -> dict[str, Any]:
    return {
        "id": dim.id,
        "label": dim.label,
        "value": value,
        "display": _display(dim, value),
        "description": dim.description,
        "status": dim.status,
        "source": dim.source,
    }


def labelled_dimensions(record: dict[str, Any], family_id: str = "pmo") -> dict[str, list[dict[str, Any]]]:
    """Context and responsibility dimensions of one project record, with labels and plain-language display values."""
    fam = load_job_family(family_id)
    out: dict[str, list[dict[str, Any]]] = {"context": [], "responsibility": []}
    for key, dims in (("context", fam.context_dimensions), ("responsibility", fam.responsibility_dimensions)):
        for d in dims:
            if d.status == "planned" or not d.field:
                continue
            out[key].append(_entry(d, record.get(d.field)))
    return out


def responsibility_scope(projects: list[dict[str, Any]], risks_owned: int, family_id: str = "pmo") -> dict[str, Any]:
    """Summarise the responsibility dimensions over the projects a person has led."""
    fam = load_job_family(family_id)
    rows = []
    for d in fam.responsibility_dimensions:
        if d.status == "planned" or not d.field:
            continue
        if d.field == "risks_owned":
            rows.append({**_entry(d, risks_owned), "summary": f"{risks_owned} risks owned in the RAID log", "n_projects": len(projects)})
            continue
        vals = [p.get(d.field) for p in projects if p.get(d.field) is not None]
        kind = d.scale.type if d.scale else "continuous"
        if not vals:
            summary, value = "Not recorded", None
        elif kind == "boolean":
            value = sum(bool(v) for v in vals) / len(vals)
            summary = f"Yes on {sum(bool(v) for v in vals)} of {len(vals)} projects"
        elif kind == "categorical":
            counts = Counter(str(v) for v in vals)
            value = dict(counts)
            summary = ", ".join(f"{k} {n}" for k, n in counts.most_common())
        else:
            mean = sum(float(v) for v in vals) / len(vals)
            value = {"mean": mean, "max": max(float(v) for v in vals)}
            scale = f" of {d.scale.max:g}" if d.scale and d.scale.max is not None else ""
            summary = f"typically {mean:.1f}{scale} (highest {max(float(v) for v in vals):g})"
        rows.append(
            {
                "id": d.id,
                "label": d.label,
                "value": value,
                "summary": summary,
                "description": d.description,
                "source": d.source,
                "n_projects": len(vals),
            }
        )
    return {"projects_led": len(projects), "dimensions": rows, "note": SCOPE_NOTE}
