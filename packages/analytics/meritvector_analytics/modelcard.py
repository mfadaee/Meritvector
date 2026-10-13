"""Generate a per-run model card from pipeline outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from meritvector_analytics.pipeline import PipelineResult


def _f(x, nd=2) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def render_model_card(r: PipelineResult) -> str:
    v = r.validation
    sched = r.context["schedule_variance_pct"]
    vc = sched.variance_components
    oot = v["out_of_time"]
    lines = [
        f"# Model card — {r.version}",
        "",
        "> Generated automatically from this training run. All data is **synthetic**.",
        "",
        "## Intended use",
        "Decision *support* for qualified reviewers: summarising work evidence in the context of operating "
        "conditions, with explicit uncertainty. **Not** for automated promotion, compensation, dismissal or "
        "hiring decisions, and not for ranking employees.",
        "",
        "## Models",
        "- Context baseline: OLS of milestone schedule variance (and deliverable quality) on project complexity, "
        "dependencies, resource constraint, scope changes to date, team size, size band, environment, maturity, "
        "job family and time. Cluster-robust (project) standard errors.",
        "- Adjusted estimates (v0.2): within-person (Mundlak / correlated random effects) linear mixed model — the same "
        "fixed effects plus each person's mean conditions, an employee random intercept and a project variance component. "
        "Context effects are therefore estimated from the same person's different projects, so assigning stronger people "
        "to harder work does not bias them. The v0.1 random-intercept model is kept as a sensitivity specification.",
        "",
        "## Data",
        f"- Achieved milestones: {r.metrics['counts']['milestones']} across {r.metrics['counts']['projects']} projects; "
        f"{r.metrics['counts']['employees_with_evidence']} employees with evidence.",
        f"- Data fingerprint: `{r.data_hash[:16]}`; as of {r.config['as_of']}.",
        f"- Right-censoring guard: {r.metrics['counts'].get('right_censored_milestones_excluded', 0)} achieved milestones "
        "planned "
        "within 90 days of the as-of date are excluded, because only early finishers among them are observable yet.",
        "- Excluded: assistance content, diagnostic activity (meetings/e-mail/hours), disputed or retracted records, "
        "protected attributes, historical ratings and promotions.",
        "",
        "## Variance decomposition (schedule variance)",
        f"- Employee intercept variance: {_f(vc.get('employee_intercept_var'))}; project variance: "
        f"{_f(vc.get('project_var'))}; residual variance: {_f(vc.get('residual_var'))}.",
        f"- Share attributable to the employee level: {_f(vc.get('employee_share_of_variance'), 3)}. Most variation is "
        "*not* attributable to individuals.",
        "",
        "## Validation (out-of-time, last 6 months held out)",
        "| Model | MAE | RMSE | R² |",
        "|---|---|---|---|",
    ]
    for name, mm in oot["models"].items():
        lines.append(f"| {name} | {_f(mm['mae'])} | {_f(mm['rmse'])} | {_f(mm['r2'], 3)} |")
    cal = v["calibration"]
    lines += [
        "",
        f"- Calibration ({cal['event']}): Brier {_f(cal['brier'], 3)} vs climatology {_f(cal['brier_climatology'], 3)}; "
        f"ECE {_f(cal['expected_calibration_error'], 3)}.",
        f"- Bootstrap cross-check: {_f(v['bootstrap']['direction_agreement_with_mixed_intervals'] * 100, 0)}% agreement in "
        "direction-of-evidence between cluster-bootstrap and mixed-model intervals.",
        "",
        "## Leakage checks",
    ]
    for c in v["leakage_checks"]:
        lines.append(f"- {'PASS' if c['passed'] else 'FAIL'} — {c['check']} ({c['detail']})")
    lines += ["", "## Sensitivity to modelling assumptions"]
    for name, s in v["sensitivity"].items():
        changed = s["share_conclusions_changed"]
        lines.append(
            f"- {name}: Spearman with base {_f(s['spearman_with_base'], 3)}"
            + (f"; conclusions changed for {_f(changed * 100, 1)}% of employees" if changed is not None else "")
        )
    lines += ["", "## Assumption diagnostics"]
    for note in sched.diagnostics["assumption_notes"]:
        lines.append(f"- {note}")
    if sched.diagnostics["fit_warnings"]:
        lines.append(
            f"- Optimiser warnings recorded during fitting: {len(sched.diagnostics['fit_warnings'])} "
            "(see metrics.json). Estimates are reported because the model converged."
        )
    lines += [
        "",
        "## Abstention",
        "An employee estimate is reported as *insufficient evidence* when fewer than 6 milestones are available or "
        "the interval is wider than the configured maximum. Conclusion counts: "
        + ", ".join(f"{k}: {v_}" for k, v_ in r.metrics["conclusion_counts"].items())
        + ".",
        "",
        "## Historical labels",
    ]
    if r.label_audit:
        la = r.label_audit
        lines.append(
            f"- Manager ratings vs raw outcomes ρ={_f(la['rating_vs_raw_outcome_spearman'], 2)}, vs adjusted "
            f"evidence ρ={_f(la['rating_vs_adjusted_estimate_spearman'], 2)}, vs meeting volume "
            f"ρ={_f(la['rating_vs_meeting_volume_spearman'], 2)}. Ratings are treated as biased labels."
        )
    if r.fairness:
        lines += ["", "## Fairness audit (aggregated)", f"- {r.fairness.get('finding')}"]
    lines += [
        "",
        "## Limitations",
        "- Synthetic data: the data-generating process is known and simpler than reality.",
        "- Unmeasured context (team skill, sponsor quality, luck) is absorbed into individual estimates.",
        "- Non-random assignment: people who are trusted with harder work may differ in unmeasured ways.",
        "- Milestones still overdue at the as-of date are not yet outcomes and are not modelled (a survival model is planned).",
        "- Milestone schedule variance is one narrow facet of contribution; much valuable work leaves no record.",
        "- Estimates are adjusted associations, not causal effects of individuals.",
        "",
    ]
    return "\n".join(lines)
