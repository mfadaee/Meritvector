"""Plain-English narratives for business users. Every sentence is derived from computed values — no new numbers."""

from __future__ import annotations

from typing import Any


def _pp(v: float) -> str:
    return f"{abs(v):.1f} percentage points"


def contribution_narrative(sched: dict[str, Any] | None, raw: dict[str, Any] | None) -> list[str]:
    raw = raw or {}
    if not sched or sched.get("adjusted_estimate") is None:
        return [
            "There is not yet enough settled milestone evidence to compare this person's delivery with what their "
            "project conditions would predict. No conclusion is drawn."
        ]
    out = []
    n = sched.get("n")
    expected = sched.get("context_expected")
    actual = raw.get("mean_schedule_variance_pct")
    if expected is not None and actual is not None:
        out.append(
            f"Across {n} settled milestones, this person's projects slipped on average {actual:.1f}% of the planned "
            f"interval. A simple comparison with similar projects across the organisation would expect {expected:.1f}%."
        )
    est, lo, hi = sched["adjusted_estimate"], sched.get("ci_low"), sched.get("ci_high")
    conclusion = sched.get("conclusion")
    primary = (
        "The primary model also compares the person with themselves across easier and harder projects, which corrects "
        "for harder work tending to go to particular people. "
    )
    if conclusion == "above_context_expectation":
        out.append(
            primary + f"It estimates delivery was better than these conditions predict, by about {_pp(est)} — and the "
            f"uncertainty range ({lo:+.1f} to {hi:+.1f}) does not include zero."
        )
    elif conclusion == "below_context_expectation":
        out.append(
            primary + f"It estimates delivery was weaker than these conditions predict, by about {_pp(est)} (range "
            f"{lo:+.1f} to {hi:+.1f}). "
            "Before drawing any conclusion, check for context the data does not capture — team changes, sponsor "
            "issues, or work outside the register."
        )
    elif conclusion == "insufficient_evidence":
        out.append("The evidence is too thin or too variable to say whether delivery differs from what conditions predict.")
    else:
        out.append(
            primary + f"It finds delivery in line with what these conditions predict (best estimate {est:+.1f}, range "
            f"{lo:+.1f} to {hi:+.1f}, which includes zero)."
        )
    on_time = raw.get("on_time_rate")
    if on_time is not None and raw.get("mean_complexity") is not None:
        out.append(
            f"The raw on-time rate is {on_time * 100:.0f}% on projects of average complexity "
            f"{raw['mean_complexity']:.1f} of 5. Raw rates mostly reflect project difficulty, which is why the "
            "adjusted comparison is shown."
        )
    out.append("This is one facet of contribution, an association rather than proof of impact, and needs human review.")
    return out
