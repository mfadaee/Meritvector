"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorState, Loading, PageHeader, ProjectLink, Table } from "@/components/ui";
import { ApiError, post, useApi } from "@/lib/api";
import { date } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

export default function MeetingDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading, reload } = useApi<AnyRec>(`/meetings/${encodeURIComponent(decodeURIComponent(id))}`);
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const ins = data.insight;
  return (
    <div>
      <PageHeader title={data.title} subtitle={<>{data.scheduled_at.replace("T", " ").slice(0, 16)} · {data.project_id && <ProjectLink id={data.project_id} />} · attendees: {Object.values(data.attendee_names).join(", ")}</>}
        actions={data.has_transcript && <Button onClick={async () => { try { await post(`/meetings/${encodeURIComponent(data.id)}/process`, {}); reload(); } catch (e) { setErr(e as ApiError); } }}>Re-run extraction</Button>} />
      <ErrorState error={err} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Summary" subtitle={ins?.disclosure}>{ins ? <p className="text-sm">{ins.summary}</p> : <p className="text-sm text-muted">No insight yet.</p>}</Card>
        <Card title="Decisions">{ins?.decisions.length ? <ul className="space-y-1 text-sm">{ins.decisions.map((d: AnyRec, i: number) => <li key={i}>• {d.text}<div className="text-xs text-muted">“{d.source_line}”</div></li>)}</ul> : <p className="text-sm text-muted">None.</p>}</Card>
        <Card title="Actions" className="lg:col-span-2">
          <Table head={["Owner", "Action", "Due", "Source line"]} rows={(ins?.actions ?? []).map((a: AnyRec) => [data.attendee_names[a.owner] ?? a.owner, a.description, date(a.due_date), <span key="s" className="text-xs text-muted">{a.source_line}</span>])} />
          <p className="mt-2 text-xs text-muted">{data.tasks_created.length} follow-up task(s) created for attendees.</p>
        </Card>
        <Card title="Risks raised">{ins?.risks.length ? <ul className="text-sm">{ins.risks.map((r: AnyRec, i: number) => <li key={i}>• {r.text}</li>)}</ul> : <p className="text-sm text-muted">None.</p>}</Card>
        <Card title="Unresolved dependencies">{ins?.dependencies.length ? <ul className="text-sm">{ins.dependencies.map((d: AnyRec, i: number) => <li key={i}>• <strong>{d.team}</strong>: {d.text}</li>)}</ul> : <p className="text-sm text-muted">None.</p>}</Card>
        {data.transcript && <Card title="Transcript" subtitle="Assistance data — visible to attendees only" className="lg:col-span-2"><pre className="whitespace-pre-wrap text-xs">{data.transcript}</pre></Card>}
      </div>
    </div>
  );
}
