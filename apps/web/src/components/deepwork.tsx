"use client";

import { useState } from "react";
import { Badge, Button, Card, Empty, ErrorState, Loading, Notice, Table } from "@/components/ui";
import { ApiError, post, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { date, label } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

const NODE_ICON: Record<string, string> = { risk: "▲", mitigation: "◆", milestone: "●", dependency: "⇄" };
const ATTR_TONE: Record<string, "neutral" | "good" | "warn"> = { claimed: "neutral", confirmed: "good", disputed: "warn" };
const input = "rounded-lg border border-line bg-raised px-2 py-1.5 text-sm";

function AttributionForm({ node, onDone }: { node: AnyRec; onDone: () => void }) {
  const [role, setRole] = useState("led");
  const [text, setText] = useState("");
  const [err, setErr] = useState<ApiError | null>(null);
  const targetType = node.type;
  const targetId = node.type === "mitigation" ? String(node.id).replace(/:mitigation$/, "") : node.id;
  return (
    <form className="mt-2 grid gap-1" onSubmit={async (e) => {
      e.preventDefault(); setErr(null);
      try { await post("/attributions", { target_type: targetType, target_id: targetId, role, description: text }); onDone(); } catch (x) { setErr(x as ApiError); }
    }}>
      <ErrorState error={err} />
      <select aria-label="Your role" value={role} onChange={(e) => setRole(e.target.value)} className={input}>
        <option value="led">I led this</option><option value="contributed">I contributed</option>
        <option value="supported">I supported</option><option value="advised">I advised</option>
      </select>
      <textarea aria-label="What you did" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="What did you do? (visible to you, your manager and HR)" className={input} />
      <div><Button type="submit" disabled={text.length < 10}>Save my account</Button></div>
    </form>
  );
}

function Node({ node, canAttribute, onChange }: { node: AnyRec; canAttribute: boolean; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-w-[180px] max-w-[240px] rounded-lg border border-line bg-surface p-2 text-xs">
      <div className="flex items-center gap-1 font-medium"><span aria-hidden>{NODE_ICON[node.type] ?? "•"}</span>{label(node.type)}</div>
      <div className="mt-0.5 text-sm">{node.label}</div>
      <div className="text-muted">{date(node.date)} · {node.outcome}</div>
      {node.owner_name && <div className="text-muted">Owner: {node.owner_name}</div>}
      {(node.attributions ?? []).map((a: AnyRec) => (
        <div key={a.id} className="mt-1 rounded border border-line/70 p-1">
          <Badge tone={ATTR_TONE[a.status]}>{a.status}</Badge> <span className="text-muted">{a.employee_name} · {a.role}</span>
          <div>{a.description}</div>
          {a.review_note && <div className="text-muted">Reviewer: {a.review_note}</div>}
        </div>
      ))}
      {canAttribute && (
        <button type="button" onClick={() => setOpen((o) => !o)} className="mt-1 text-accent hover:underline">{open ? "Cancel" : "Describe my contribution"}</button>
      )}
      {open && <AttributionForm node={node} onDone={() => { setOpen(false); onChange(); }} />}
    </div>
  );
}

/** Risk → mitigation → milestone chains with the provenance of every link. */
export function EvidenceChains({ projectId }: { projectId: string }) {
  const { me } = useAuth();
  const { data, error, loading, reload } = useApi<AnyRec>(`/portfolio/projects/${projectId}/evidence-chains`);
  const [showAll, setShowAll] = useState(false);
  const [link, setLink] = useState({ from: "", to: "", relation: "protects", note: "" });
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading) return <Loading what="Loading evidence chains" />;
  if (error || !data) return <ErrorState error={error} />;
  const chains: AnyRec[] = data.chains;
  const shown = showAll ? chains : chains.filter((c) => c.nodes.length > 1);
  const nodes = new Map<string, AnyRec>();
  chains.forEach((c) => c.nodes.forEach((n: AnyRec) => nodes.set(`${n.type}|${n.id}`, n)));
  const sources = [...nodes.values()].filter((n) => n.type !== "milestone");
  const targets = [...nodes.values()].filter((n) => n.type === "milestone");
  const canLink = !!me?.employee_id && (me.employee_id === data.project.lead_employee_id || me.role === "hr_reviewer");
  return (
    <Card title="Evidence chains" subtitle={data.note} className="lg:col-span-2"
      actions={<button type="button" className="text-xs text-accent hover:underline" onClick={() => setShowAll((s) => !s)}>{showAll ? "Only connected chains" : `Show all ${chains.length}`}</button>}>
      <Notice><strong>Inferred links:</strong> {data.inference_rule} <strong>Manual links</strong> show who recorded them. {data.attribution_visibility}</Notice>
      <div className="mt-3 space-y-3">
        {shown.length ? shown.map((c) => (
          <div key={`${c.kind}-${c.root}`} className="flex flex-wrap items-stretch gap-2">
            {c.nodes.map((n: AnyRec, i: number) => {
              const edge = i > 0 ? c.edges.find((e: AnyRec) => e.to === n.id) : null;
              return (
                <div key={n.id} className="flex items-center gap-2">
                  {i > 0 && (
                    <span className="flex flex-col items-center text-[10px] text-muted" title={edge?.rule ?? edge?.note ?? ""}>
                      <span aria-hidden>→</span>{edge ? `${label(edge.relation)} · ${edge.origin}` : "linked"}
                    </span>
                  )}
                  <Node node={n} canAttribute={!!me?.employee_id} onChange={reload} />
                </div>
              );
            })}
          </div>
        )) : <Empty>No connected chains yet — risks or dependencies without a recorded mitigation or resolution.</Empty>}
      </div>
      {data.manual_links.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase text-muted">Manually recorded links</h3>
          <Table head={["From", "Relation", "To", "Recorded by", "Note"]} rows={data.manual_links.map((l: AnyRec) => [`${label(l.from_type)} ${l.from}`, label(l.relation), `${label(l.to_type)} ${l.to}`, `${l.created_by} · ${l.created_at}`, l.note ?? "—"])} />
        </div>
      )}
      {canLink && sources.length > 0 && targets.length > 0 && (
        <form className="mt-4 grid gap-2 md:grid-cols-4" onSubmit={async (e) => {
          e.preventDefault(); setErr(null);
          const [ft, fid] = link.from.split("|"); const [tt, tid] = link.to.split("|");
          try {
            await post("/evidence-links", { project_id: projectId, from_type: ft, from_id: ft === "mitigation" ? fid.replace(/:mitigation$/, "") : fid, to_type: tt, to_id: tid, relation: link.relation, note: link.note || null });
            setLink({ ...link, note: "" }); reload();
          } catch (x) { setErr(x as ApiError); }
        }}>
          <div className="md:col-span-4 text-xs font-semibold uppercase text-muted">Record a link you know about</div>
          <ErrorState error={err} />
          <select aria-label="From record" value={link.from} onChange={(e) => setLink({ ...link, from: e.target.value })} className={input}>
            <option value="">From…</option>{sources.map((n) => <option key={`${n.type}|${n.id}`} value={`${n.type}|${n.id}`}>{label(n.type)}: {n.label}</option>)}
          </select>
          <select aria-label="Relation" value={link.relation} onChange={(e) => setLink({ ...link, relation: e.target.value })} className={input}>
            {["protects", "unblocks", "mitigated_by", "precedes", "contributed_to"].map((r) => <option key={r} value={r}>{label(r)}</option>)}
          </select>
          <select aria-label="To milestone" value={link.to} onChange={(e) => setLink({ ...link, to: e.target.value })} className={input}>
            <option value="">To milestone…</option>{targets.map((n) => <option key={n.id} value={`${n.type}|${n.id}`}>{n.label}</option>)}
          </select>
          <input aria-label="Note" value={link.note} onChange={(e) => setLink({ ...link, note: e.target.value })} placeholder="Why are they connected?" className={input} />
          <div><Button type="submit" disabled={!link.from || !link.to}>Record link</Button></div>
        </form>
      )}
    </Card>
  );
}

/** Labelled operating conditions and responsibility scope of one project (context, never credit). */
export function ProjectDimensions({ projectId }: { projectId: string }) {
  const { data, error, loading } = useApi<AnyRec>(`/portfolio/projects/${projectId}/dimensions`);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const rows = (xs: AnyRec[]) => xs.map((d) => [<span key="l" title={d.description}>{d.label}</span>, d.display, <Badge key="s" tone={d.status === "modelled" ? "accent" : "neutral"}>{d.status === "modelled" ? "used in adjustment" : "recorded only"}</Badge>]);
  return (
    <>
      <Card title="Operating conditions" subtitle="From the PMO register. 'Used in adjustment' dimensions enter the context model.">
        <Table head={["Condition", "Value", "Use"]} rows={rows(data.context)} />
      </Card>
      <Card title="Responsibility scope" subtitle={data.note}>
        <Table head={["Responsibility", "Value", "Use"]} rows={rows(data.responsibility)} />
      </Card>
    </>
  );
}

/** Aggregated responsibility scope over the projects a person has led. */
export function ResponsibilityScope({ employeeId }: { employeeId: string }) {
  const { data, error, loading } = useApi<AnyRec>(`/employees/${employeeId}/responsibility-scope`);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <Card title="Responsibility scope" subtitle={`${data.projects_led} projects led. ${data.note}`}>
      <Table head={["Responsibility", "Across projects led"]} rows={data.dimensions.map((d: AnyRec) => [<span key="l" title={d.description}>{d.label}</span>, d.summary])} />
    </Card>
  );
}

/** A person's own attributions, and (for managers / HR) the attributions awaiting their review. */
export function AttributionPanel() {
  const { me } = useAuth();
  const mine = useApi<AnyRec[]>(me?.employee_id ? "/attributions/me" : null);
  const review = useApi<AnyRec[]>(me?.permissions.attribution_review ? "/attributions/review" : null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [err, setErr] = useState<ApiError | null>(null);
  const decide = async (id: number, decision: string) => {
    setErr(null);
    try { await post(`/attributions/${id}/review`, { decision, note: notes[id] || null }); review.reload(); } catch (x) { setErr(x as ApiError); }
  };
  return (
    <>
      {me?.employee_id && (
        <Card title="My contribution accounts" subtitle="Your own descriptions of what you did. Self-reported narrative — shown to your manager and HR, never used by the models.">
          <Table head={["Record", "Role", "What you did", "Status"]} empty="You have not described any contributions yet. Use 'Describe my contribution' on a project's evidence chains."
            rows={(mine.data ?? []).map((a) => [`${label(a.target_type)} ${a.target_id}`, label(a.role), a.description, <span key="s"><Badge tone={ATTR_TONE[a.status]}>{a.status}</Badge>{a.review_note && <span className="block text-xs text-muted">{a.review_note}</span>}</span>])} />
        </Card>
      )}
      {me?.permissions.attribution_review && (
        <Card title="Contribution accounts to review" subtitle="Confirm what matches the records, or dispute with a reason the person will see.">
          <ErrorState error={err} />
          <Table head={["Person", "Record", "Account", "Status", "Review"]} empty="Nothing to review."
            rows={(review.data ?? []).map((a) => [a.employee_name, `${label(a.target_type)} ${a.target_id}`, `${label(a.role)}: ${a.description}`, <Badge key="s" tone={ATTR_TONE[a.status]}>{a.status}</Badge>,
              a.status === "claimed" ? (
                <div key="r" className="grid gap-1">
                  <input aria-label="Review note" value={notes[a.id] ?? ""} onChange={(e) => setNotes({ ...notes, [a.id]: e.target.value })} placeholder="Note (required to dispute)" className={input} />
                  <div className="flex gap-1"><Button onClick={() => decide(a.id, "confirmed")}>Confirm</Button><Button variant="secondary" onClick={() => decide(a.id, "disputed")}>Dispute</Button></div>
                </div>
              ) : <span key="r" className="text-xs text-muted">{a.review_note ?? "—"}</span>])} />
        </Card>
      )}
    </>
  );
}
