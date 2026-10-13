"use client";

import { useState } from "react";
import { Badge, Button, Card, EmployeeLink, Empty, ErrorState, Loading, Notice, PageHeader, Table, Tabs } from "@/components/ui";
import { ApiError, post, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { date, label } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

type Tab = "mine" | "team" | "challenges";

export default function EvidencePage() {
  const { me } = useAuth();
  const canTeam = !!(me?.permissions.team_contribution || me?.permissions.all_contribution);
  const [tab, setTab] = useState<Tab>(me?.employee_id ? "mine" : "team");
  const tabs: { id: Tab; label: string }[] = [
    ...(me?.employee_id ? [{ id: "mine" as Tab, label: "My evidence" }] : []),
    ...(canTeam ? [{ id: "team" as Tab, label: me?.role === "hr_reviewer" ? "All employees" : "My team" }] : []),
    ...(me?.role !== "admin" ? [{ id: "challenges" as Tab, label: "Correction requests" }] : []),
  ];
  return (
    <div>
      <PageHeader title="Contribution Evidence" subtitle="Validated work records that may inform development conversations. Every employee can see every record held about them and challenge anything inaccurate." />
      {me?.role === "admin" && <Notice>Administrators manage the platform but, by design, have no access to individual performance evidence.</Notice>}
      {tabs.length > 0 && <Tabs<Tab> value={tabs.some((t) => t.id === tab) ? tab : tabs[0].id} onChange={setTab} tabs={tabs} />}
      {tab === "mine" && me?.employee_id && <Mine />}
      {tab === "team" && canTeam && <Team />}
      {tab === "challenges" && me?.role !== "admin" && <Challenges canResolve={canTeam} />}
    </div>
  );
}

function Mine() {
  const [cat, setCat] = useState("");
  const [page, setPage] = useState(0);
  const { data, error, loading, reload } = useApi<AnyRec>(`/evidence/me?limit=25&offset=${page * 25}${cat ? `&category=${cat}` : ""}`);
  const [challenging, setChallenging] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <Card title={`${data.total} records`} subtitle="Raw evidence as ingested, with source and provenance">
      <ErrorState error={err} />
      <div className="mb-3 flex flex-wrap gap-1">
        <button onClick={() => { setCat(""); setPage(0); }} className={`rounded-full border px-2 py-0.5 text-xs ${!cat ? "border-accent text-accent" : "border-line text-muted"}`}>All</button>
        {Object.entries(data.category_counts as Record<string, number>).map(([k, v]) => (
          <button key={k} onClick={() => { setCat(k); setPage(0); }} className={`rounded-full border px-2 py-0.5 text-xs ${cat === k ? "border-accent text-accent" : "border-line text-muted"}`}>{label(k)} ({v})</button>
        ))}
      </div>
      <Table head={["Date", "Category", "Source", "Reference", "Details", "Status", ""]} rows={data.items.map((e: AnyRec) => [
        date(e.occurred_at), label(e.category), e.source_system, <code key="r" className="text-xs">{e.evidence_ref}</code>,
        <span key="p" className="text-xs text-muted">{Object.entries(e.payload).filter(([k]) => !k.endsWith("_id")).map(([k, v]) => `${label(k)}: ${String(v)}`).join(" · ")}</span>,
        <Badge key="s" tone={e.validation_status === "disputed" ? "warn" : e.validation_status === "retracted" ? "critical" : "neutral"}>{e.validation_status}</Badge>,
        e.data_category === "assessment_evidence" && e.validation_status !== "disputed" ? <Button key="c" variant="secondary" onClick={() => { setChallenging(e.event_id); setReason(""); }}>Challenge</Button> : null,
      ])} />
      {challenging && (
        <div className="mt-3 rounded-lg border border-accent/40 p-3">
          <div className="text-sm font-medium">Challenge record {challenging}</div>
          <p className="text-xs text-muted">The record is excluded from analysis until your manager or HR resolves the challenge.</p>
          <textarea aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} placeholder="What is inaccurate and why?" className="mt-2 w-full rounded-lg border border-line bg-raised p-2 text-sm" />
          <div className="mt-2 flex gap-2">
            <Button disabled={reason.length < 10} onClick={async () => { try { await post(`/evidence/${challenging}/challenge`, { reason }); setChallenging(null); reload(); } catch (e) { setErr(e as ApiError); } }}>Submit challenge</Button>
            <Button variant="secondary" onClick={() => setChallenging(null)}>Cancel</Button>
          </div>
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-sm">
        <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
        <span className="text-muted">Page {page + 1} of {Math.max(1, Math.ceil(data.total / 25))}</span>
        <Button variant="secondary" disabled={(page + 1) * 25 >= data.total} onClick={() => setPage(page + 1)}>Next</Button>
      </div>
    </Card>
  );
}

function Team() {
  const [q, setQ] = useState("");
  const { data, error, loading } = useApi<AnyRec>(`/employees?q=${encodeURIComponent(q)}`);
  const insights = useApi<AnyRec>("/team/insights");
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="People" subtitle={data?.ordering} className="lg:col-span-2">
        <input aria-label="Filter people" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by name" className="mb-2 w-full rounded-lg border border-line bg-raised px-2 py-1.5 text-sm" />
        {loading ? <Loading /> : error ? <ErrorState error={error} /> : (
          <Table head={["Name", "Role", "Level", "Unit", "Milestones evidenced", "Evidence"]} rows={(data?.items ?? []).slice(0, 100).map((e: AnyRec) => [
            <EmployeeLink key="n" id={e.id} name={e.display_name} />, label(e.job_family), e.level, e.business_unit, e.milestones_evidenced,
            e.evidence_sufficient ? <Badge key="b">sufficient</Badge> : <Badge key="b" tone="warn">insufficient</Badge>,
          ])} />
        )}
      </Card>
      <Card title="Team development insights" subtitle={insights.data?.note}>
        {insights.data ? (
          <div className="space-y-3 text-sm">
            <div>Team size: <strong>{insights.data.team_size}</strong></div>
            {Object.entries(insights.data.competency_status as Record<string, Record<string, number>>).map(([k, v]) => (
              <div key={k}>
                <div className="font-medium">{k}</div>
                <div className="flex flex-wrap gap-1">{Object.entries(v).map(([s, n]) => <Badge key={s}>{label(s)}: {n}</Badge>)}</div>
              </div>
            ))}
          </div>
        ) : insights.error ? <ErrorState error={insights.error} /> : <Loading />}
      </Card>
    </div>
  );
}

function Challenges({ canResolve }: { canResolve: boolean }) {
  const { data, error, loading, reload } = useApi<AnyRec[]>("/evidence/challenges");
  const [note, setNote] = useState<Record<number, string>>({});
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;
  if (!data?.length) return <Empty>No correction requests.</Empty>;
  const resolve = async (id: number, decision: string) => {
    try { await post(`/evidence/challenges/${id}/resolve`, { decision, note: note[id] ?? "" }); reload(); } catch (e) { setErr(e as ApiError); }
  };
  return (
    <Card title="Correction requests">
      <ErrorState error={err} />
      <Table head={["Employee", "Record", "Reason", "Status", ""]} rows={data.map((c) => [
        c.employee_name, <span key="r" className="text-xs">{c.event ? `${label(c.event.category)} · ${c.event.evidence_ref}` : c.event_id}</span>, c.reason,
        <span key="s"><Badge tone={c.status === "pending" ? "warn" : "neutral"}>{label(c.status)}</Badge>{c.resolution_note && <span className="block text-xs text-muted">{c.resolution_note}</span>}</span>,
        canResolve && c.status === "pending" ? (
          <div key="a" className="flex min-w-56 flex-col gap-1">
            <input aria-label="Resolution note" placeholder="Resolution note" value={note[c.id] ?? ""} onChange={(e) => setNote({ ...note, [c.id]: e.target.value })} className="rounded border border-line bg-raised px-2 py-1 text-xs" />
            <div className="flex gap-1">
              <Button variant="secondary" disabled={(note[c.id] ?? "").length < 5} onClick={() => resolve(c.id, "upheld_retract")}>Uphold — retract</Button>
              <Button variant="secondary" disabled={(note[c.id] ?? "").length < 5} onClick={() => resolve(c.id, "rejected")}>Reject</Button>
            </div>
          </div>
        ) : null,
      ])} />
    </Card>
  );
}
