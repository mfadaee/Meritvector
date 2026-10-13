"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Card, ErrorState, Loading, Notice, PageHeader, Table, Tabs } from "@/components/ui";
import { api, ApiError, post, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { date, label } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

type Tab = "privacy" | "governance" | "settings" | "audit" | "jobs" | "connectors" | "access";

export default function AdminPage() {
  const { me } = useAuth();
  const privileged = me?.role === "admin" || me?.role === "hr_reviewer";
  const tabs: { id: Tab; label: string }[] = [
    { id: "privacy", label: "Notice & disclosure" },
    ...(privileged ? [{ id: "governance" as Tab, label: "Governance" }, { id: "settings" as Tab, label: "Settings & retention" }, { id: "audit" as Tab, label: "Audit log" }] : []),
    ...(me?.role === "admin" ? [{ id: "jobs" as Tab, label: "Scheduled jobs" }, { id: "access" as Tab, label: "Access control" }] : []),
    { id: "connectors", label: "Integrations" },
  ];
  const [tab, setTab] = useState<Tab>("privacy");
  return (
    <div>
      <PageHeader title="Administration & Privacy" subtitle="Transparent, disclosed processing. No covert monitoring. Assessment features need explicit governance approval." />
      <Tabs<Tab> value={tab} onChange={setTab} tabs={tabs} />
      {tab === "privacy" && <Privacy />}
      {tab === "governance" && <Governance />}
      {tab === "settings" && <Settings editable={me?.role === "admin"} />}
      {tab === "audit" && <Audit />}
      {tab === "jobs" && <Jobs />}
      {tab === "connectors" && <Connectors />}
      {tab === "access" && <Access />}
    </div>
  );
}

function Privacy() {
  const { data, error, loading } = useApi<AnyRec>("/privacy/notice");
  const inv = useApi<AnyRec>("/privacy/inventory");
  const [ack, setAck] = useState(false);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Workplace data notice">
        <p className="text-sm">{data.notice_text}</p>
        <div className="mt-3">{ack ? <Badge tone="good">● Acknowledged</Badge> : <Button onClick={async () => { await post("/privacy/acknowledge", {}); setAck(true); }}>I have read this notice</Button>}</div>
      </Card>
      <Card title="Assessment purpose disclosure" actions={<Badge tone={data.assessment_enabled ? "warn" : "neutral"}>{data.assessment_enabled ? "Assessment enabled" : "Assessment disabled"}</Badge>}>
        <p className="text-sm">{data.assessment_purpose}</p>
      </Card>
      <Card title="Data categories kept separate" className="lg:col-span-2">
        <Table head={["Category", "What", "Purpose", "Assessment use", "Sources"]} rows={(inv.data?.categories ?? []).map((c: AnyRec) => [c.label, c.what, c.why, c.used_for_assessment ? "Yes, with approval" : "Never", c.sources.join(", ")])} />
        <p className="mt-2 text-xs text-muted"><strong>Never collected:</strong> {data.never_collected.join(" · ")}</p>
      </Card>
    </div>
  );
}

function Governance() {
  const { me, refresh } = useAuth();
  const { data, error, loading, reload } = useApi<AnyRec>("/admin/governance");
  const [purpose, setPurpose] = useState("");
  const [err, setErr] = useState<ApiError | null>(null);
  const act = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); reload(); await refresh(); } catch (e) { setErr(e as ApiError); } };
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div className="space-y-4">
      <ErrorState error={err} />
      <Card title="Assessment features" subtitle={data.rule} actions={<Badge tone={data.assessment_enabled ? "warn" : "neutral"}>{data.assessment_enabled ? "Enabled" : "Disabled"}</Badge>}>
        {data.assessment_enabled ? (
          <Button variant="secondary" onClick={() => act(() => post("/admin/governance/revoke", {}))}>Revoke approval and disable</Button>
        ) : me?.role === "admin" ? (
          <div className="space-y-2">
            <textarea aria-label="Purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} rows={3} placeholder="State the purpose and scope of assessment processing (min 20 characters)" className="w-full rounded-lg border border-line bg-raised p-2 text-sm" />
            <Button disabled={purpose.length < 20} onClick={() => act(() => post("/admin/governance/request", { purpose }))}>Request approval</Button>
          </div>
        ) : <Notice>An administrator must request approval; an HR reviewer then approves.</Notice>}
      </Card>
      <Card title="Approval history">
        <Table head={["#", "Purpose", "Requested by", "Admin", "HR", "Status", ""]} rows={data.approvals.map((g: AnyRec) => [
          g.id, <span key="p" className="text-xs">{g.purpose}</span>, g.requested_by, g.admin_approved_by ?? "—", g.hr_approved_by ?? "—", <Badge key="s">{g.status}</Badge>,
          g.status === "pending" && ((me?.role === "hr_reviewer" && !g.hr_approved_by) || (me?.role === "admin" && !g.admin_approved_by)) ? <Button key="a" onClick={() => act(() => post(`/admin/governance/${g.id}/approve`, {}))}>Approve</Button> : null,
        ])} empty="No approvals recorded." />
      </Card>
    </div>
  );
}

function Settings({ editable }: { editable: boolean }) {
  const { data, error, loading, reload } = useApi<AnyRec>("/admin/settings");
  const [s, setS] = useState<AnyRec | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (data) setS(data.settings); }, [data]);
  if (loading || !s) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const save = async () => {
    setErr(null); setSaved(false);
    try {
      await api("/admin/settings", { method: "PUT", body: JSON.stringify({ notice_text: s.notice_text, assessment_purpose: s.assessment_purpose, external_delivery_enabled: s.external_delivery_enabled, transcript_processing_enabled: s.transcript_processing_enabled, retention_days: s.retention_days }) });
      setSaved(true); reload();
    } catch (e) { setErr(e as ApiError); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ErrorState error={err} />
      <Card title="Surveillance notice & purpose disclosure (configurable)" className="lg:col-span-2">
        <label className="text-xs font-medium text-muted" htmlFor="notice">Notice shown to every user</label>
        <textarea id="notice" disabled={!editable} value={s.notice_text} onChange={(e) => setS({ ...s, notice_text: e.target.value })} rows={4} className="mb-3 w-full rounded-lg border border-line bg-raised p-2 text-sm" />
        <label className="text-xs font-medium text-muted" htmlFor="purpose">Assessment-purpose disclosure</label>
        <textarea id="purpose" disabled={!editable} value={s.assessment_purpose} onChange={(e) => setS({ ...s, assessment_purpose: e.target.value })} rows={4} className="w-full rounded-lg border border-line bg-raised p-2 text-sm" />
      </Card>
      <Card title="Processing switches">
        <label className="mb-2 flex items-center gap-2 text-sm"><input type="checkbox" disabled={!editable} checked={!!s.external_delivery_enabled} onChange={(e) => setS({ ...s, external_delivery_enabled: e.target.checked })} /> Allow external message delivery (still requires per-message user authorisation)</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!editable} checked={!!s.transcript_processing_enabled} onChange={(e) => setS({ ...s, transcript_processing_enabled: e.target.checked })} /> Allow meeting transcript processing (assistance only)</label>
        <h3 className="mt-4 text-xs font-semibold uppercase text-muted">Data minimisation (fixed)</h3>
        <ul className="text-sm">{Object.entries(s.data_minimisation ?? {}).map(([k, v]) => <li key={k}>{label(k)}: <strong>{v ? "yes" : "no"}</strong></li>)}</ul>
      </Card>
      <Card title="Retention policies (days)" subtitle="Enforced by the retention_enforcement job">
        {Object.entries(s.retention_days as Record<string, number>).map(([k, v]) => (
          <label key={k} className="mb-2 flex items-center justify-between gap-2 text-sm">{label(k)}
            <input type="number" min={1} disabled={!editable} value={v} onChange={(e) => setS({ ...s, retention_days: { ...s.retention_days, [k]: Number(e.target.value) } })} className="w-28 rounded-lg border border-line bg-raised px-2 py-1 text-right" />
          </label>
        ))}
      </Card>
      {editable ? <div><Button onClick={save}>Save settings</Button>{saved && <span className="ml-2 text-sm text-good">Saved and audited.</span>}</div> : <Notice>Read-only for HR reviewers.</Notice>}
    </div>
  );
}

function Audit() {
  const [action, setAction] = useState("");
  const { data, error, loading } = useApi<AnyRec>(`/admin/audit?limit=100${action ? `&action=${action}` : ""}`);
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <Card title={`Audit trail (${data.total} entries)`} subtitle="Append-only record of access, reviews, challenges, configuration and governance changes">
      <select aria-label="Filter action" value={action} onChange={(e) => setAction(e.target.value)} className="mb-2 rounded-lg border border-line bg-raised px-2 py-1.5 text-sm">
        <option value="">All actions</option>{data.actions.map((a: string) => <option key={a} value={a}>{label(a)}</option>)}
      </select>
      <Table head={["When", "Actor", "Role", "Action", "Resource", "Detail"]} rows={data.entries.map((e: AnyRec) => [String(e.at).replace("T", " ").slice(0, 19), e.actor_user_id, label(e.actor_role), label(e.action), `${e.resource_type}${e.resource_id ? `:${e.resource_id}` : ""}`, <code key="d" className="text-[10px]">{JSON.stringify(e.detail).slice(0, 120)}</code>])} />
    </Card>
  );
}

function Jobs() {
  const { data, error, loading, reload } = useApi<AnyRec>("/admin/jobs");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div className="space-y-4">
      <Card title="Scheduled jobs" subtitle="Persistent schedule in the database; executed by the local worker" actions={<Button variant="secondary" onClick={reload}>Refresh</Button>}>
        <Table head={["Job", "Description", "Every", "Next run", "Last", ""]} rows={data.jobs.map((j: AnyRec) => [
          <code key="n" className="text-xs">{j.name}</code>, j.description, `${j.interval_minutes} min`, String(j.next_run_at).replace("T", " ").slice(0, 16),
          j.last_status ? <Badge key="s" tone={j.last_status === "succeeded" ? "good" : "critical"}>{j.last_status}</Badge> : "—",
          <Button key="r" variant="secondary" onClick={async () => { await post(`/admin/jobs/${j.name}/run`, {}); setTimeout(reload, 1500); }}>Run now</Button>,
        ])} />
      </Card>
      <Card title="Recent job runs">
        <Table head={["Job", "Trigger", "Started", "Status", "Detail"]} rows={data.runs.map((r: AnyRec) => [r.job_name, r.trigger, String(r.started_at).replace("T", " ").slice(0, 19), label(r.status), <code key="d" className="text-[10px]">{JSON.stringify(r.detail).slice(0, 140)}</code>])} />
      </Card>
    </div>
  );
}

function Connectors() {
  const { data, error, loading } = useApi<AnyRec[]>("/admin/connectors");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <Card title="Integrations" subtitle="v0.1 uses realistic mock connectors only — no enterprise credentials are needed or stored">
      <Table head={["Connector", "Mode", "Ingests", "Never collects", "Delivery", "Records", "Production plan"]} rows={data.map((c) => [
        c.vendor, <Badge key="m" tone="warn">{c.mode}</Badge>, <span key="i" className="text-xs">{c.ingests.join(", ") || "—"}</span>, <span key="n" className="text-xs">{c.never_collects.join(", ") || "—"}</span>,
        c.supports_delivery ? "Opt-in, per message" : "—", c.records_ingested, <span key="p" className="text-xs text-muted">{c.real_integration_plan.api} · {(c.real_integration_plan.scopes ?? []).join(", ")}</span>,
      ])} />
    </Card>
  );
}

function Access() {
  const [q, setQ] = useState("");
  const { data, error, loading, reload } = useApi<AnyRec>(`/admin/users?q=${encodeURIComponent(q)}`);
  const [err, setErr] = useState<ApiError | null>(null);
  return (
    <Card title="Role-based access control" subtitle="Employee · Manager (direct reports) · HR reviewer (tenant-wide, aggregated fairness) · Administrator (configuration, no individual evidence)">
      {data && <div className="mb-3 flex flex-wrap gap-1">{Object.entries(data.role_counts as Record<string, number>).map(([k, v]) => <Badge key={k}>{label(k)}: {v}</Badge>)}</div>}
      <ErrorState error={err} />
      <input aria-label="Search users" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search users" className="mb-2 w-full rounded-lg border border-line bg-raised px-2 py-1.5 text-sm" />
      {loading ? <Loading /> : error ? <ErrorState error={error} /> : (
        <Table head={["User", "Employee", "Role"]} rows={(data?.users ?? []).map((u: AnyRec) => [u.display_name, u.employee_id ?? "—",
          <select key="r" aria-label={`Role for ${u.display_name}`} value={u.role} onChange={async (e) => { setErr(null); try { await api(`/admin/users/${u.user_id}/role`, { method: "PUT", body: JSON.stringify({ role: e.target.value }) }); reload(); } catch (x) { setErr(x as ApiError); } }} className="rounded border border-line bg-raised px-1 py-0.5 text-xs">
            {["employee", "manager", "hr_reviewer", "admin"].map((r) => <option key={r} value={r}>{label(r)}</option>)}
          </select>])} />
      )}
      <p className="mt-2 text-xs text-muted">Role changes are audited. Tenant separation: every query is scoped to the signed-in user’s organisation. Last updated {date(new Date().toISOString())}.</p>
    </Card>
  );
}
