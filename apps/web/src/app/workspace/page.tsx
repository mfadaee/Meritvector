"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, Empty, ErrorState, HealthBadge, Loading, Markdown, Notice, PageHeader, ProjectLink, SeverityBadge, Table, Tabs } from "@/components/ui";
import { api, ApiError, post, useApi } from "@/lib/api";
import { CONCLUSION_TEXT, TREND_TEXT, date, label, signed } from "@/lib/format";

type Tab = "today" | "projects" | "coordinator" | "development" | "data";

export default function WorkspacePage() {
  const [tab, setTab] = useState<Tab>("today");
  return (
    <div>
      <PageHeader title="Employee Workspace" subtitle="Your day, your projects, your coordinator, your development record and your data." />
      <Tabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "today", label: "Today" }, { id: "projects", label: "My projects" }, { id: "coordinator", label: "My coordinator" },
        { id: "development", label: "My development" }, { id: "data", label: "My data" },
      ]} />
      {tab === "today" && <Today />}
      {tab === "projects" && <Projects />}
      {tab === "coordinator" && <MyCoordinator />}
      {tab === "development" && <Development />}
      {tab === "data" && <MyData />}
    </div>
  );
}

import type { AnyRec } from "@/lib/types";

function Today() {
  const { data, error, loading } = useApi<AnyRec>("/workspace/today");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Upcoming meetings" subtitle="Next 7 days">
        <Table head={["When", "Meeting"]} rows={data.upcoming_meetings.map((m: AnyRec) => [m.scheduled_at.replace("T", " ").slice(0, 16), m.title])} empty="No meetings scheduled." />
      </Card>
      <Card title="Open actions" subtitle="From meetings and your own list">
        <Table head={["Action", "Due", ""]} rows={data.open_actions.map((t: AnyRec) => [t.title, date(t.due_date), t.overdue ? <Badge tone="critical">overdue</Badge> : null])} empty="No open actions." />
      </Card>
      <Card title="Deadlines" subtitle="Milestones due in 30 days or overdue">
        <Table head={["Milestone", "Project", "Planned"]} rows={data.deadlines.map((m: AnyRec) => [m.name, <ProjectLink key={m.id} id={m.project_id} name={m.project_name} />, <span key="d" className={m.overdue ? "text-critical" : ""}>{date(m.planned_date)}{m.overdue ? " (overdue)" : ""}</span>])} empty="No deadlines in the next 30 days." />
      </Card>
      <Card title="Risks on your projects">
        <Table head={["Risk", "Severity", "Status"]} rows={data.risks.slice(0, 8).map((r: AnyRec) => [r.title, <SeverityBadge key="s" severity={r.severity} />, label(r.status)])} empty="No open risks." />
      </Card>
      <Card title="Recent decisions" subtitle="Extracted from your meetings in the last 14 days" className="lg:col-span-2">
        {data.recent_decisions.length ? (
          <ul className="space-y-1 text-sm">{data.recent_decisions.map((d: AnyRec, i: number) => <li key={i}>• {d.text} <span className="text-xs text-muted">— {d.meeting}, {d.date}</span></li>)}</ul>
        ) : <Empty>No decisions recorded.</Empty>}
      </Card>
    </div>
  );
}

function Projects() {
  const { data, error, loading } = useApi<AnyRec[]>("/workspace/projects");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  if (!data.length) return <Empty>You are not leading an active project.</Empty>;
  return (
    <div className="space-y-4">
      {data.map((p) => (
        <Card key={p.id} title={<ProjectLink id={p.id} name={p.name} />} subtitle={`${p.business_unit} · complexity ${p.technical_complexity}/5 · ${p.dependency_count} dependencies · resource constraint ${p.resource_constraint}`}
          actions={<HealthBadge health={p.health?.health} />}>
          <div className="grid gap-4 lg:grid-cols-3">
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted">Milestones</h3>
              <ul className="space-y-1 text-sm">{p.milestones.map((m: AnyRec) => <li key={m.id} className="flex justify-between gap-2"><span>{m.name}</span><span className="text-muted">{m.status === "achieved" ? `✓ ${date(m.actual_date)}` : `${label(m.status)} · ${date(m.planned_date)}`}</span></li>)}</ul>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted">Blockers & dependencies</h3>
              {p.blockers.length ? <ul className="space-y-1 text-sm">{p.blockers.map((b: AnyRec, i: number) => <li key={i}>• {b.title}</li>)}</ul> : <p className="text-sm text-muted">No blockers.</p>}
              <ul className="mt-2 space-y-1 text-sm">{p.dependencies.map((d: AnyRec) => <li key={d.id} className="flex justify-between"><span>{d.depends_on}</span><span className="text-muted">{d.status}</span></li>)}</ul>
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-muted">Documents</h3>
              <ul className="space-y-1 text-sm">{p.documents.map((d: AnyRec) => <li key={d.milestone_id} className="flex justify-between gap-2"><span>{d.title}</span><span className="text-muted">{d.status}</span></li>)}</ul>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function MyCoordinator() {
  const { data, error, loading } = useApi<AnyRec>("/workspace/coordinator");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Daily briefing" subtitle={data.briefing.disclosure} className="lg:col-span-2">
        <p className="text-sm">{data.briefing.text}</p>
      </Card>
      <Card title="Meeting summaries">
        {data.meeting_summaries.length ? data.meeting_summaries.map((m: AnyRec) => (
          <div key={m.id} className="mb-3 border-b border-line pb-3 last:border-0">
            <Link href={`/meetings/${encodeURIComponent(m.id)}`} className="text-sm font-medium text-accent hover:underline">{m.title}</Link>
            <p className="mt-1 text-sm text-muted">{m.insight.summary}</p>
          </div>
        )) : <Empty>No processed meetings yet.</Empty>}
      </Card>
      <Card title="Suggested follow-ups" subtitle="For overdue actions">
        {data.suggested_follow_ups.length ? data.suggested_follow_ups.map((f: AnyRec) => (
          <div key={f.task_id} className="mb-2 rounded-lg border border-line p-2 text-sm">
            <div>{f.suggestion}</div>
            <div className="mt-1 text-xs italic text-muted">Draft: “{f.draft_message}”</div>
          </div>
        )) : <Empty>Nothing overdue.</Empty>}
      </Card>
      <Card title="Outstanding actions">
        <Table head={["Action", "Due", "Status"]} rows={data.outstanding_actions.map((t: AnyRec) => [t.title, date(t.due_date), label(t.status)])} />
      </Card>
      <Card title="Draft reports" subtitle="Weekly status, ready to review — nothing is sent automatically">
        {data.draft_reports.length ? data.draft_reports.map((r: AnyRec) => (
          <details key={r.project_id} className="mb-2 rounded-lg border border-line p-2">
            <summary className="cursor-pointer text-sm font-medium">{r.project_name}</summary>
            <div className="mt-2"><Markdown text={r.markdown} /></div>
            <p className="mt-1 text-xs text-muted">{r.disclosure}</p>
          </details>
        )) : <Empty>No active projects to report on.</Empty>}
      </Card>
    </div>
  );
}

function Development() {
  const { data, error, loading, reload } = useApi<AnyRec>("/workspace/development");
  const [goal, setGoal] = useState({ competency: "risk_leadership", goal: "" });
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const sched = data.estimates?.schedule_variance_pct;
  return (
    <div className="space-y-4">
      <Notice>{data.disclaimer}</Notice>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Demonstrated competencies" subtitle="Validated evidence in the last 12 months vs the expectation at your level">
          <Table head={["Competency", "Evidence (12m)", "Expected", "Status"]} rows={data.competencies.map((c: AnyRec) => [
            c.label, c.evidence_window, c.expected_at_level ?? "—",
            <Badge key="s" tone={c.status.startsWith("demonstrated") ? "good" : c.status === "evidence_gap" ? "warn" : "neutral"}>{label(c.status)}</Badge>,
          ])} />
        </Card>
        <Card title="Contribution evidence" subtitle="Context-adjusted delivery summary (not a rating)">
          {sched ? (
            <div className="space-y-2 text-sm">
              <div><span className="text-muted">Delivery relative to context: </span><strong>{signed(sched.adjusted_estimate)} pp</strong> (95% interval {signed(sched.ci_low)} to {signed(sched.ci_high)})</div>
              <div><Badge tone="accent">{CONCLUSION_TEXT[sched.conclusion]}</Badge></div>
              <div className="text-muted">Based on {sched.n} achieved milestones. Trend: {TREND_TEXT[data.trend?.trend_status] ?? "—"}.</div>
            </div>
          ) : <Empty>No estimate available yet.</Empty>}
          <h3 className="mt-4 text-xs font-semibold uppercase text-muted">Evidence by category</h3>
          <div className="mt-1 flex flex-wrap gap-1">{Object.entries(data.evidence_counts).map(([k, v]) => <Badge key={k}>{label(k)}: {String(v)}</Badge>)}</div>
        </Card>
        <Card title="Missing evidence" subtitle="Gaps may reflect the work you were given, not your capability">
          {data.missing_evidence.length ? <ul className="space-y-1 text-sm">{data.missing_evidence.map((c: AnyRec) => <li key={c.competency}>• <strong>{c.label}</strong>: {c.evidence_window} of {c.expected_at_level ?? "—"} expected{c.opportunity_note ? ` — ${c.opportunity_note}` : ""}</li>)}</ul> : <Empty>No gaps against your level’s expectations.</Empty>}
        </Card>
        <Card title="Development goals">
          <ul className="mb-3 space-y-1 text-sm">{data.goals.map((g: AnyRec) => <li key={g.id}>• <strong>{label(g.competency)}</strong>: {g.goal}</li>)}</ul>
          <form className="flex flex-col gap-2" onSubmit={async (e) => { e.preventDefault(); await post("/workspace/goals", goal); setGoal({ ...goal, goal: "" }); reload(); }}>
            <select aria-label="Competency" value={goal.competency} onChange={(e) => setGoal({ ...goal, competency: e.target.value })} className="rounded-lg border border-line bg-raised px-2 py-1.5 text-sm">
              {data.competencies.map((c: AnyRec) => <option key={c.competency} value={c.competency}>{c.label}</option>)}
            </select>
            <input aria-label="Goal" value={goal.goal} onChange={(e) => setGoal({ ...goal, goal: e.target.value })} placeholder="e.g. Lead the risk review on my next complex project" className="rounded-lg border border-line bg-raised px-2 py-1.5 text-sm" />
            <div><Button type="submit" disabled={goal.goal.length < 5}>Add goal</Button></div>
          </form>
        </Card>
        <Card title="Feedback history" subtitle="Stakeholder surveys — perception-based and noisy">
          <Table head={["Date", "Score", "Respondent"]} rows={data.feedback_history.map((f: AnyRec) => [f.date, `${f.score}/5`, label(f.respondent_role)])} empty="No survey responses." />
        </Card>
        <Card title="Review notes about you" subtitle="Recorded by your manager or HR; you can always see them">
          {data.review_notes.length ? data.review_notes.map((n: AnyRec) => <div key={n.id} className="mb-2 text-sm"><Badge>{label(n.agreement)}</Badge> <span className="text-xs text-muted">{date(n.created_at)}</span><p className="mt-1">{n.judgement}</p></div>) : <Empty>No review notes.</Empty>}
        </Card>
      </div>
    </div>
  );
}

function MyData() {
  const { data, error, loading, reload } = useApi<AnyRec>("/workspace/data");
  const inv = useApi<AnyRec>("/privacy/inventory");
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading || inv.loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const toggle = async (k: string, v: boolean) => {
    try { await api("/workspace/preferences", { method: "PUT", body: JSON.stringify({ [k]: v }) }); reload(); } catch (e) { setErr(e as ApiError); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="What is collected, why, and how it is used" className="lg:col-span-2">
        <Table head={["Category", "What", "Why", "Used for assessment?", "Retention"]} rows={(inv.data?.categories ?? []).map((c: AnyRec) => [
          c.label, c.what, c.why, c.used_for_assessment ? <Badge key="y" tone="warn">Yes — after governance approval</Badge> : <Badge key="n" tone="good">No</Badge>, c.retention_days ? `${c.retention_days} days` : "—"])} />
        <div className="mt-3 text-xs text-muted"><strong>Never collected:</strong> {(inv.data?.never_collected ?? []).join(" · ")}</div>
      </Card>
      <Card title="Records held about you" subtitle="By category and source">
        <Table head={["Category", "Source", "Records"]} rows={data.records.map((r: AnyRec) => [label(r.data_category), r.source_system, r.count])} />
        <Link href="/evidence" className="mt-2 block text-xs text-accent hover:underline">Inspect every record and challenge inaccuracies →</Link>
      </Card>
      <Card title="Privacy controls">
        <ErrorState error={err} />
        {[["transcript_processing", "Process my meeting transcripts to suggest follow-ups"], ["daily_briefing", "Prepare a daily briefing"]].map(([k, t]) => (
          <label key={k} className="mb-2 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!data.privacy_preferences[k]} onChange={(e) => toggle(k, e.target.checked)} /> {t}
          </label>
        ))}
        <p className="mt-2 text-xs text-muted">Assistance data is never reused for performance evaluation.</p>
        <h3 className="mt-4 text-xs font-semibold uppercase text-muted">Your correction requests</h3>
        <Table head={["Record", "Status", "Raised"]} rows={data.challenges.map((c: AnyRec) => [c.event_id, label(c.status), date(c.created_at)])} empty="No correction requests." />
      </Card>
    </div>
  );
}
