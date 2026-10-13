"use client";

import { IntervalPlot, RawAdjustedScatter } from "@/components/charts";
import { Badge, Card, ErrorState, Loading, Notice, PageHeader, Table } from "@/components/ui";
import { useApi } from "@/lib/api";
import { CONCLUSION_TEXT, label, num, pct, signed } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

const TERM: Record<string, string> = {
  technical_complexity: "Technical complexity (per level)",
  dependency_count: "Dependencies (each)",
  resource_constraint: "Resource constraint (0→1)",
  scope_changes_to_date: "Approved scope changes (each)",
  team_size: "Team size (per person)",
  size_band: "Size band",
  month_index: "Time (per month)",
  "C(environment)[T.internal]": "Environment: internal",
  "C(environment)[T.regulated]": "Environment: regulated",
  "C(maturity)[T.greenfield]": "Maturity: greenfield",
  "C(job_family)[T.project_manager]": "Job family: PM",
  "C(job_family)[T.technical_project_manager]": "Job family: TPM",
};

export default function AnalysisPage() {
  const ctx = useApi<AnyRec>("/analysis/context");
  const exp = useApi<AnyRec>("/analysis/experiment");
  if (ctx.loading) return <Loading />;
  if (ctx.error || !ctx.data) return <ErrorState error={ctx.error} />;
  const sched = ctx.data.models.schedule_variance_pct;
  const coefs = sched.coefficients.filter((c: AnyRec) => c.term !== "Intercept");
  const vc = sched.variance_components;
  return (
    <div>
      <PageHeader title="Contextual Analysis" subtitle={ctx.data.explanation} />
      <Notice tone="warn">Adjusted estimates are associations after accounting for measured context — not proof of individual causal impact. Points are shown unordered; MeritVector does not rank people.</Notice>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="How operating conditions relate to schedule variance" subtitle={`Context OLS, project-clustered 95% intervals. Positive = more slippage. R² ${num(sched.diagnostics.ols_r2, 2)}.`}>
          <IntervalPlot items={coefs.map((c: AnyRec) => ({ label: TERM[c.term] ?? c.term, estimate: c.estimate, low: c.ci_low, high: c.ci_high }))} zeroLabel="no association" />
        </Card>
        <Card title="Raw vs context-adjusted outcomes" subtitle={`${ctx.data.points.length} people (${ctx.data.scope}). Positive = less slippage than comparison point.`}>
          <RawAdjustedScatter points={ctx.data.points} />
        </Card>
        <Card title="Where the variation comes from" subtitle="Mixed-model variance decomposition (schedule variance)">
          <Table head={["Component", "Variance", "Share"]} rows={[
            ["Employee (between people)", num(vc.employee_intercept_var), pct(vc.employee_share_of_variance)],
            ["Project (between projects, same person)", num(vc.project_var), pct(vc.project_var / (vc.employee_intercept_var + vc.project_var + vc.residual_var))],
            ["Residual (milestone-level noise)", num(vc.residual_var), pct(vc.residual_var / (vc.employee_intercept_var + vc.project_var + vc.residual_var))],
          ]} />
          <p className="mt-2 text-xs text-muted">Most variation is not attributable to individuals — a reason for caution with any person-level reading.</p>
        </Card>
        <Card title="Sensitivity to modelling assumptions" subtitle="Agreement of employee estimates with the base model">
          <Table head={["Specification", "Spearman ρ", "Conclusions changed"]} rows={Object.entries(ctx.data.sensitivity ?? {}).map(([k, v]) => {
            const s = v as AnyRec;
            return [label(k), num(s.spearman_with_base, 3), s.share_conclusions_changed === null ? "—" : pct(s.share_conclusions_changed, 1)];
          })} />
        </Card>
      </div>
      <Experiment exp={exp} />
    </div>
  );
}

function Experiment({ exp }: { exp: { data: AnyRec | null; error: unknown; loading: boolean } }) {
  if (exp.loading) return <Loading what="Loading flagship experiment" />;
  if (!exp.data) return null;
  const e = exp.data;
  if (e.status === "insufficient_data") return <div className="mt-8"><Notice>{e.verdict}</Notice></div>;
  const conds = ["technical_complexity", "dependency_count", "resource_constraint", "scope_changes_to_date", "team_size", "regulated_share", "greenfield_share", "context_expected_variance_pct"];
  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold">Flagship experiment: does context change the reading of two records?</h2>
      <p className="mt-1 max-w-4xl text-sm text-muted">{e.why_raw_can_mislead}</p>
      <div className="mt-3 rounded-xl border border-line bg-surface p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={e.status === "inconclusive" ? "warn" : "good"}>{e.status === "inconclusive" ? "▲ Inconclusive" : "● Supported difference"}</Badge>
          <span className="text-sm font-medium">{e.verdict}</span>
        </div>
        <p className="mt-2 text-sm">{e.adjustment_summary}</p>
        {e.pseudonymised && <p className="mt-1 text-xs text-muted">Identities are pseudonymised because you are not authorised to view both people.</p>}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="1. Raw performance metrics">
          <Table head={["Metric", e.display_names.A, e.display_names.B]} rows={[
            ["Achieved milestones", e.raw_metrics.A.milestones, e.raw_metrics.B.milestones],
            ["Projects", e.raw_metrics.A.projects, e.raw_metrics.B.projects],
            ["On-time rate", pct(e.raw_metrics.A.on_time_rate), pct(e.raw_metrics.B.on_time_rate)],
            ["Mean schedule variance", `${num(e.raw_metrics.A.mean_schedule_variance_pct)}%`, `${num(e.raw_metrics.B.mean_schedule_variance_pct)}%`],
            ["Schedule variability (SD)", num(e.raw_metrics.A.schedule_variance_sd), num(e.raw_metrics.B.schedule_variance_sd)],
            ["Deliverable quality", num(e.raw_metrics.A.quality_mean, 2), num(e.raw_metrics.B.quality_mean, 2)],
          ]} />
        </Card>
        <Card title="2. Differences in operating conditions" subtitle="Mean across each person’s milestones">
          <Table head={["Condition", "A", "B"]} rows={conds.map((c) => [label(c), num(e.operating_conditions.A[c], 2), num(e.operating_conditions.B[c], 2)])} />
          <p className="mt-2 text-xs text-muted">Common support: {e.common_support.adequate ? "adequate" : "poor — the conditions barely overlap, so adjustment extrapolates"}.</p>
        </Card>
        <Card title="3–4. Context-adjusted estimates with uncertainty" subtitle={e.adjusted_units}>
          <IntervalPlot items={["A", "B"].map((k) => ({ label: `Employee ${k}`, estimate: e.adjusted_estimates[k].adjusted_estimate, low: e.adjusted_estimates[k].ci_low, high: e.adjusted_estimates[k].ci_high, note: CONCLUSION_TEXT[e.adjusted_estimates[k].conclusion] }))} />
          <p className="mt-2 text-sm">Bootstrap B−A difference: <strong>{signed(e.difference_bootstrap.difference)} pp</strong> (95% {signed(e.difference_bootstrap.ci_low)} to {signed(e.difference_bootstrap.ci_high)}; {e.difference_bootstrap.n_boot} project-cluster resamples).</p>
        </Card>
        <Card title="5. Sensitivity to modelling assumptions" subtitle="B−A under alternative specifications (positive favours B)">
          <IntervalPlot items={e.sensitivity.map((s: AnyRec) => ({ label: label(s.specification).slice(0, 26), estimate: s.B_minus_A, low: s.B_minus_A, high: s.B_minus_A }))} zeroLabel="no difference" />
        </Card>
      </div>
      <details className="mt-3 text-xs text-muted"><summary className="cursor-pointer">Selection rule (fixed in advance, observable data only)</summary><pre className="mt-2 whitespace-pre-wrap">{e.selection_rule}</pre></details>
    </section>
  );
}
