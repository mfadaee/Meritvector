"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { IntervalPlot, TrendLines } from "@/components/charts";
import { ResponsibilityScope } from "@/components/deepwork";
import { HowAssessed } from "@/components/explain";
import { Badge, Button, Card, Empty, ErrorState, Loading, Notice, PageHeader, ProjectLink, Stat, Table } from "@/components/ui";
import { ApiError, post, useApi } from "@/lib/api";
import { CONCLUSION_TEXT, TREND_TEXT, date, label, num, pct, signed } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

export default function ContributionPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading, reload } = useApi<AnyRec>(`/employees/${id}/contribution`);
  const [form, setForm] = useState({ agreement: "agrees_with_evidence", judgement: "", disagreement_reasons: "", context_notes: "" });
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const e = data.employee;
  const s = data.adjusted.schedule_variance_pct;
  const q = data.adjusted.quality_score;
  const rm = data.raw_metrics;
  const intervals = [
    s && { label: "Schedule: mixed model", estimate: s.adjusted_estimate, low: s.ci_low, high: s.ci_high },
    data.bootstrap_ci && s && { label: "Schedule: bootstrap", estimate: s.residual_estimate, low: data.bootstrap_ci.boot_ci_low, high: data.bootstrap_ci.boot_ci_high, note: "cluster bootstrap over projects" },
  ].filter(Boolean) as { label: string; estimate: number; low: number; high: number }[];
  return (
    <div>
      <PageHeader title={e.display_name} subtitle={`${label(e.job_family)} · ${e.level} · ${e.business_unit} · manager ${e.manager_name} · synthetic employee ${e.id}`} />
      <Notice tone="warn">
        Decision support only. {data.interpretation.not_causal} {data.interpretation.human_review} This page does not rank, score for promotion or recommend any employment action.
      </Notice>

      {data.narrative?.length > 0 && (
        <Card title="In plain English" className="mt-4">
          <div className="space-y-1 text-sm">{data.narrative.map((t: string) => <p key={t}>{t}</p>)}</div>
          <HowAssessed metric="adjusted_schedule_estimate" />
        </Card>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Achieved milestones" value={rm.milestones ?? 0} hint={`${rm.projects_led ?? 0} projects led`} />
        <Stat label="Raw on-time rate" value={pct(rm.on_time_rate)} hint="Not adjusted for difficulty" />
        <Stat label="Mean schedule variance" value={`${num(rm.mean_schedule_variance_pct)}%`} hint={`SD ${num(rm.schedule_variance_sd)} — consistency`} />
        <Stat label="Context-expected variance" value={`${num(s?.context_expected)}%`} hint="What operating conditions predict" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Context-adjusted analysis" subtitle={data.interpretation.adjusted_estimate}>
          {s ? (
            <div className="space-y-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span>Schedule: <strong>{signed(s.adjusted_estimate)} pp</strong> (95% {signed(s.ci_low)} to {signed(s.ci_high)}, n={s.n})</span>
                <Badge tone="accent">{CONCLUSION_TEXT[s.conclusion]}</Badge>
              </div>
              <div className="text-muted">Raw comparison would read {signed(s.raw_estimate)} pp vs the organisation mean.</div>
              {q && <div className="flex flex-wrap items-center gap-2"><span>Deliverable quality: <strong>{signed(q.adjusted_estimate, 2)}</strong> points (95% {signed(q.ci_low, 2)} to {signed(q.ci_high, 2)})</span><Badge>{CONCLUSION_TEXT[q.conclusion]}</Badge></div>}
              <div className="pt-2"><IntervalPlot items={intervals} /></div>
              <HowAssessed metric="adjusted_schedule_estimate" />
            </div>
          ) : <Empty>Insufficient historical data.</Empty>}
        </Card>
        <Card title="Changes over time" subtitle={`Quarterly signal relative to context · ${TREND_TEXT[data.trend.trend_status] ?? "—"}`}>
          {data.trend_series.length ? (
            <TrendLines data={data.trend_series.map((r: AnyRec) => ({ quarter: r.quarter, adjusted: Math.round(r.signal_mean * 10) / 10 }))} x="quarter" series={[{ key: "adjusted", label: "Signal vs context (pp)" }]} height={220} />
          ) : <Empty>Insufficient historical data.</Empty>}
          {data.trend.slope !== undefined && data.trend.slope !== null && (
            <p className="mt-2 text-xs text-muted">Half-year slope {signed(data.trend.slope)} pp/period (SE {num(data.trend.slope_se)}, p={num(data.trend.p_value, 2)}); flagged only if significant after false-discovery-rate control across all employees.{data.trend.sustained_quality ? " Sustained deliverable quality ≥ 3.8 in every half-year." : ""}</p>
          )}
        </Card>
        <Card title="Observed evidence" subtitle="Validated records by category">
          <div className="mb-2 flex flex-wrap gap-1">{Object.entries(data.observed_evidence.counts_by_category as Record<string, number>).map(([k, v]) => <Badge key={k}>{label(k)}: {v}</Badge>)}</div>
          <div className="mb-2 flex flex-wrap gap-1">{Object.entries(data.observed_evidence.validation_status as Record<string, number>).map(([k, v]) => <Badge key={k} tone={k === "disputed" ? "warn" : "neutral"}>{k}: {v}</Badge>)}</div>
          <Table head={["Date", "Category", "Reference"]} rows={data.observed_evidence.recent.slice(0, 10).map((r: AnyRec) => [date(r.occurred_at), label(r.category), <code key="c" className="text-xs">{r.evidence_ref}</code>])} />
        </Card>
        <ResponsibilityScope employeeId={id} />
        <Card title="Raw delivery metrics" subtitle="Not adjusted for project difficulty">
          <Table head={["Metric", "Value"]} rows={[
            ["Deliverable quality (mean review score)", num(rm.quality_mean, 2)],
            ["First-pass approval rate", pct(rm.first_pass_approval_rate)],
            ["Risk mitigation rate", pct(rm.risk_mitigation_rate)],
            ["Proactive risk identification", pct(rm.proactive_risk_rate)],
            ["Median blocker resolution (days)", num(rm.blocker_median_days, 0)],
            ["Median dependency resolution (days)", num(rm.dependency_median_days, 0)],
            ["Stakeholder feedback (perception)", num(rm.stakeholder_feedback_mean, 2)],
            ["Mean complexity / resource constraint", `${num(rm.mean_complexity)} / ${num(rm.mean_resource_constraint, 2)}`],
          ]} />
          <HowAssessed metric="on_time_rate" />
        </Card>
        <Card title="Competency evidence" subtitle="Evidence in the last 12 months vs the expectation at this level">
          <Table head={["Competency", "12m", "Expected", "Status", "Examples"]} rows={data.competencies.map((c: AnyRec) => [
            c.label, c.evidence_window, c.expected_at_level ?? "—", <Badge key="s" tone={c.status.startsWith("demonstrated") ? "good" : c.status === "evidence_gap" ? "warn" : "neutral"}>{label(c.status)}</Badge>,
            <span key="e" className="text-xs text-muted">{c.examples.join(", ")}</span>,
          ])} />
        </Card>
        <Card title="Missing information & statistical uncertainty">
          {data.missing_information.length ? <ul className="space-y-1 text-sm">{data.missing_information.map((m: string, i: number) => <li key={i}>• {m}</li>)}</ul> : <p className="text-sm text-muted">No specific gaps flagged. Remember that unmeasured context (team, sponsor, luck) is not in the model.</p>}
          <h3 className="mt-4 text-xs font-semibold uppercase text-muted">Projects led</h3>
          <ul className="mt-1 space-y-1 text-sm">{data.projects.map((p: AnyRec) => <li key={p.id}><ProjectLink id={p.id} name={p.name} /> <span className="text-xs text-muted">complexity {p.technical_complexity}/5 · constraint {p.resource_constraint} · {p.status}</span></li>)}</ul>
        </Card>
        <Card title="Human review notes" subtitle="Append-only and audited. Managers may record disagreement with the data." className="lg:col-span-2">
          {data.review_notes.map((n: AnyRec) => (
            <div key={n.id} className="mb-3 rounded-lg border border-line p-3 text-sm">
              <div className="flex flex-wrap gap-2"><Badge>{label(n.agreement)}</Badge><span className="text-xs text-muted">{label(n.author_role)} · {date(n.created_at)} · run {n.run_id}</span></div>
              <p className="mt-1">{n.judgement}</p>
              {n.disagreement_reasons && <p className="mt-1 text-muted"><strong>Reasons for disagreeing:</strong> {n.disagreement_reasons}</p>}
              {n.context_notes && <p className="mt-1 text-muted"><strong>Context:</strong> {n.context_notes}</p>}
            </div>
          ))}
          {data.can_add_review ? (
            <form className="grid gap-2" onSubmit={async (ev) => { ev.preventDefault(); setErr(null); try { await post(`/employees/${id}/reviews`, form); setForm({ ...form, judgement: "", disagreement_reasons: "", context_notes: "" }); reload(); } catch (x) { setErr(x as ApiError); } }}>
              <ErrorState error={err} />
              <select aria-label="Agreement" value={form.agreement} onChange={(ev) => setForm({ ...form, agreement: ev.target.value })} className="rounded-lg border border-line bg-raised px-2 py-1.5 text-sm">
                <option value="agrees_with_evidence">I agree with the evidence</option>
                <option value="partially_agrees">I partially agree</option>
                <option value="disagrees_with_evidence">I disagree with the evidence</option>
                <option value="not_assessed">Not assessed</option>
              </select>
              <textarea aria-label="Judgement" value={form.judgement} onChange={(ev) => setForm({ ...form, judgement: ev.target.value })} rows={3} placeholder="Your own judgement" className="rounded-lg border border-line bg-raised p-2 text-sm" />
              <textarea aria-label="Reasons for disagreement" value={form.disagreement_reasons} onChange={(ev) => setForm({ ...form, disagreement_reasons: ev.target.value })} rows={2} placeholder="Reasons for disagreeing with the data (required if you disagree)" className="rounded-lg border border-line bg-raised p-2 text-sm" />
              <textarea aria-label="Context notes" value={form.context_notes} onChange={(ev) => setForm({ ...form, context_notes: ev.target.value })} rows={2} placeholder="Context the data does not capture" className="rounded-lg border border-line bg-raised p-2 text-sm" />
              <div><Button type="submit" disabled={form.judgement.length < 10}>Record review</Button></div>
            </form>
          ) : <p className="text-xs text-muted">Only this person’s manager or an HR reviewer can record a review.</p>}
        </Card>
      </div>
    </div>
  );
}
