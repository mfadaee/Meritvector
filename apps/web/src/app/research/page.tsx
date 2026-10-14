"use client";

import { useEffect, useState } from "react";
import { Headlines, ResultView } from "@/components/explain";
import { Badge, Button, Card, Empty, ErrorState, Loading, Notice, PageHeader, Table, Tabs } from "@/components/ui";
import { api, ApiError, apiText, post, useApi } from "@/lib/api";
import { label } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

type Tab = "lab" | "public" | "questions" | "measurement" | "dags" | "library";
const SCENARIOS = ["A", "B", "C", "D", "E", "F"];
const STATUS_TONE: Record<string, "neutral" | "good" | "warn" | "critical" | "accent"> = { queued: "neutral", running: "accent", completed: "good", failed: "critical" };

function StatusBadge({ run }: { run: AnyRec }) {
  return <Badge tone={STATUS_TONE[run.status] ?? "neutral"}>{run.status}</Badge>;
}

function EvidenceBadge({ status }: { status?: string | null }) {
  if (!status) return null;
  return <Badge tone={status === "confirmatory" ? "accent" : "warn"} title={status === "exploratory" ? "Computed, not validated — do not act on it" : "Pre-registered test on synthetic data"}>{status}</Badge>;
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function RunDetail({ id, onReproduce }: { id: number; onReproduce: (id: number) => void }) {
  const [run, setRun] = useState<AnyRec | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const r = await api<AnyRec>(`/research/runs/${id}`);
        if (stop) return;
        setRun(r);
        if (r.status === "queued" || r.status === "running") timer = setTimeout(poll, 1500);
      } catch (e) { if (!stop) setErr(e as ApiError); }
    };
    void poll();
    return () => { stop = true; clearTimeout(timer); };
  }, [id]);
  if (err) return <ErrorState error={err} />;
  if (!run) return <Loading />;
  return (
    <Card title={`${run.title} · run ${run.id}`} subtitle={`Dataset ${run.dataset_version ?? "…"} · code ${run.code_version ?? "…"} · result hash ${run.result_hash ?? "…"}${run.duration_s ? ` · ${run.duration_s}s` : ""}`}
      actions={<span className="flex flex-wrap items-center gap-2"><StatusBadge run={run} /><EvidenceBadge status={run.evidence_status} />
        {run.reproduces_run_id && <Badge tone={run.reproduced_identically ? "good" : run.reproduced_identically === false ? "critical" : "neutral"}>{run.reproduced_identically === null || run.reproduced_identically === undefined ? `reproducing run ${run.reproduces_run_id}` : run.reproduced_identically ? `● identical to run ${run.reproduces_run_id}` : `■ differs from run ${run.reproduces_run_id}`}</Badge>}
      </span>}>
      {run.status === "failed" && <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-critical">{run.error}</pre>}
      {(run.status === "queued" || run.status === "running") && <Loading what="Running — results appear when complete" />}
      {run.status === "completed" && run.result && (
        <div className="space-y-3">
          <Notice tone="warn">{run.evidence_status === "confirmatory" ? "Pre-registered analysis on synthetic data." : "Exploratory result — computed, not validated. Do not act on it."} Synthetic data: results show how the method behaves, not real-world findings.</Notice>
          <Headlines result={run.result} />
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => onReproduce(run.id)}>Reproduce</Button>
            <Button variant="secondary" onClick={async () => download(`research-run-${run.id}.md`, await apiText(`/research/runs/${run.id}/report`))}>Export report (Markdown)</Button>
          </div>
          <ResultView value={run.result} />
        </div>
      )}
    </Card>
  );
}

function Laboratory({ overview }: { overview: AnyRec }) {
  const runs = useApi<AnyRec[]>("/research/runs");
  const [selected, setSelected] = useState<number | null>(null);
  const [scenario, setScenario] = useState("A");
  const [level, setLevel] = useState("employee");
  const [err, setErr] = useState<ApiError | null>(null);
  const start = async (workstream: string) => {
    setErr(null);
    const params = workstream === "scenario" ? { scenario } : workstream.startsWith("eda_") && workstream !== "eda_missingness" ? { level } : {};
    try { const r = await post<AnyRec>("/research/runs", { workstream, params }); setSelected(r.id); runs.reload(); } catch (e) { setErr(e as ApiError); }
  };
  const reproduce = async (id: number) => {
    try { const r = await post<AnyRec>(`/research/runs/${id}/reproduce`, {}); setSelected(r.id); runs.reload(); } catch (e) { setErr(e as ApiError); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="Workstreams" subtitle="Each run is recorded with its dataset version, code version and a result hash, so it can be reproduced.">
        <ErrorState error={err} />
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          <label className="flex items-center gap-1">EDA level
            <select aria-label="EDA level" value={level} onChange={(e) => setLevel(e.target.value)} className="rounded border border-line bg-raised px-1 py-0.5">
              {["employee", "project", "milestone"].map((l) => <option key={l}>{l}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1">Scenario
            <select aria-label="Scenario" value={scenario} onChange={(e) => setScenario(e.target.value)} className="rounded border border-line bg-raised px-1 py-0.5">
              {SCENARIOS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <ul className="space-y-1">
          {overview.workstreams.map((w: AnyRec) => (
            <li key={w.id} className="flex items-center justify-between gap-2 text-sm">
              <span>{w.title}</span>
              <button type="button" onClick={() => start(w.id)} className="shrink-0 rounded-md border border-line px-2 py-0.5 text-xs text-accent hover:bg-bg">Run</button>
            </li>
          ))}
        </ul>
      </Card>
      <div className="space-y-4 lg:col-span-2">
        {selected ? <RunDetail key={selected} id={selected} onReproduce={reproduce} /> : <Empty>Run a workstream, or open a previous run below.</Empty>}
        <Card title="Run history" actions={<button type="button" className="text-xs text-accent hover:underline" onClick={runs.reload}>Refresh</button>}>
          <Table head={["Run", "Workstream", "Started", "Status", "Evidence", "Reproduction"]} empty="No runs yet."
            rows={(runs.data ?? []).map((r) => [
              <button key="o" type="button" className="text-accent hover:underline" onClick={() => setSelected(r.id)}>#{r.id}</button>,
              r.title, String(r.created_at).slice(0, 19).replace("T", " "), <StatusBadge key="s" run={r} />, <EvidenceBadge key="e" status={r.evidence_status} />,
              r.reproduces_run_id ? `of #${r.reproduces_run_id}: ${r.reproduced_identically === null ? "…" : r.reproduced_identically ? "identical" : "differs"}` : "—",
            ])} />
        </Card>
        <Card title="Model registry" subtitle="No model is registered without its research question, target, baseline, leakage controls, limitations and prohibited uses.">
          <Table head={["Model", "Version", "Registered", "Key metrics", "Prohibited uses"]} empty="No registered models."
            rows={overview.model_registry.map((m: AnyRec) => [m.name, <code key="v" className="text-xs">{m.version}</code>, String(m.registered_at).slice(0, 10),
              <span key="m" className="text-xs">{Object.entries(m.metrics ?? {}).filter(([, v]) => typeof v === "number" || typeof v === "string").map(([k, v]) => `${label(k)} ${typeof v === "number" ? v.toFixed(3) : v}`).join(" · ")}</span>,
              <span key="p" className="text-xs text-muted">{(m.spec?.prohibited_uses ?? []).join("; ")}</span>])} />
        </Card>
        <Card title="Dataset versions">
          <Table head={["Version", "Created", "Counts", "Description"]} empty="No dataset snapshots yet — the first run creates one."
            rows={overview.datasets.map((d: AnyRec) => [<code key="v" className="text-xs">{d.id}</code>, String(d.created_at).slice(0, 19).replace("T", " "), Object.entries(d.counts ?? {}).map(([k, v]) => `${k} ${v}`).join(", "), d.description])} />
        </Card>
      </div>
    </div>
  );
}

function Questions({ overview }: { overview: AnyRec }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Research questions">
        <ul className="space-y-3 text-sm">{overview.questions.map((q: AnyRec) => (
          <li key={q.id}><strong>{q.id}.</strong> {q.title} <Badge>{label(q.type)}</Badge>
            <span className="block text-xs text-muted">{q.detail}{q.workstream ? ` · workstream: ${label(q.workstream)}` : ""}</span></li>
        ))}</ul>
      </Card>
      <Card title="Registered hypotheses" subtitle={`α = ${overview.alpha}; family-wise correction as registered`}>
        <ul className="space-y-3 text-sm">{overview.hypotheses.map((h: AnyRec) => (
          <li key={h.id}><strong>{h.id}.</strong> {h.question} <Badge tone={h.status === "confirmatory" ? "accent" : "warn"}>{h.status}</Badge>
            <span className="block text-xs"><strong>H0:</strong> {h.h0} <strong>H1:</strong> {h.h1}</span>
            <span className="block text-xs text-muted">Test: {label(h.test)}{h.unit ? ` · unit: ${h.unit}` : ""}</span></li>
        ))}</ul>
      </Card>
    </div>
  );
}

function Measurement() {
  const onto = useApi<AnyRec>("/measurement/ontology");
  const fams = useApi<AnyRec[]>("/measurement/job-families");
  const [fam, setFam] = useState("pmo");
  const spec = useApi<AnyRec>(`/measurement/job-families/${fam}`);
  if (onto.loading) return <Loading />;
  if (onto.error || !onto.data) return <ErrorState error={onto.error} />;
  const dimRows = (xs: AnyRec[] = []) => xs.map((d) => [d.label, label(d.construct), <Badge key="s" tone={d.status === "modelled" ? "accent" : d.status === "planned" ? "warn" : "neutral"}>{d.status}</Badge>, d.source ?? "—", <span key="d" className="text-xs text-muted">{d.description}</span>]);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Measurement ontology" subtitle={onto.data.conceptual_model.statement} className="lg:col-span-2">
        <p className="mb-3 text-xs text-muted">{onto.data.conceptual_model.caveat}</p>
        <Table head={["Construct", "Definition", "Evidence status", "May increase merit", "Prohibited interpretations"]}
          rows={Object.entries(onto.data.constructs as Record<string, AnyRec>).map(([, c]) => [c.label, <span key="d" className="text-xs">{c.definition}</span>,
            <Badge key="e" tone={c.evidence_status === "established" ? "good" : "warn"}>{label(c.evidence_status)}</Badge>, c.may_increase_merit ? "yes" : "no",
            <span key="p" className="text-xs text-muted">{c.prohibited_interpretations.join("; ")}</span>])} />
      </Card>
      <Card title="Job-family specification" className="lg:col-span-2"
        actions={<select aria-label="Job family" value={fam} onChange={(e) => setFam(e.target.value)} className="rounded border border-line bg-raised px-2 py-1 text-sm">
          {(fams.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name ?? f.id}{f.status ? ` (${f.status})` : ""}</option>)}
        </select>}>
        {spec.loading ? <Loading /> : spec.error || !spec.data ? <ErrorState error={spec.error} /> : (
          <div className="space-y-4">
            {spec.data.status && spec.data.status !== "active" && <Notice tone="warn">This job family is {spec.data.status}: definitions only, no models are trained on it.</Notice>}
            <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Context dimensions</h3><Table head={["Dimension", "Construct", "Status", "Source", "Description"]} rows={dimRows(spec.data.context_dimensions)} /></div>
            <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Responsibility dimensions</h3><Table head={["Dimension", "Construct", "Status", "Source", "Description"]} rows={dimRows(spec.data.responsibility_dimensions)} /></div>
            <div><h3 className="mb-1 text-xs font-semibold uppercase text-muted">Outcome dimensions</h3><Table head={["Dimension", "Construct", "Status", "Source", "Description"]} rows={dimRows(spec.data.outcome_dimensions)} /></div>
          </div>
        )}
      </Card>
    </div>
  );
}

/** Layered drawing of a causal DAG: unobserved variables are dashed. */
function DagDrawing({ dag }: { dag: AnyRec }) {
  const nodes = Object.keys(dag.nodes);
  const edges: [string, string][] = dag.edges;
  const layer: Record<string, number> = {};
  const visit = (n: string, seen: Set<string> = new Set()): number => {
    if (layer[n] !== undefined) return layer[n];
    if (seen.has(n)) return 0;
    seen.add(n);
    const parents = edges.filter(([, b]) => b === n).map(([a]) => a);
    layer[n] = parents.length ? Math.max(...parents.map((p) => visit(p, seen) + 1)) : 0;
    return layer[n];
  };
  nodes.forEach((n) => visit(n));
  const layers: string[][] = [];
  nodes.forEach((n) => { (layers[layer[n]] ??= []).push(n); });
  const W = 170, H = 64, pos: Record<string, { x: number; y: number }> = {};
  layers.forEach((ns, i) => ns.forEach((n, j) => { pos[n] = { x: 10 + i * W, y: 10 + j * H }; }));
  const width = layers.length * W + 20, height = Math.max(...layers.map((l) => l.length)) * H + 20;
  return (
    <div className="overflow-x-auto">
      <svg width={width} height={height} role="img" aria-label={`Causal diagram: ${dag.question}`} className="text-ink">
        <defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="currentColor" /></marker></defs>
        {edges.map(([a, b]) => (
          <line key={`${a}-${b}`} x1={pos[a].x + 140} y1={pos[a].y + 18} x2={pos[b].x} y2={pos[b].y + 18} stroke="currentColor" strokeOpacity={0.45} strokeWidth={1.5} markerEnd="url(#arrow)" />
        ))}
        {nodes.map((n) => {
          const meta = dag.nodes[n];
          const role = n === dag.treatment ? "treatment" : n === dag.outcome ? "outcome" : "";
          return (
            <g key={n} transform={`translate(${pos[n].x},${pos[n].y})`}>
              <rect width={140} height={36} rx={6} fill="var(--color-surface, white)" stroke="currentColor" strokeOpacity={role ? 0.9 : 0.4} strokeWidth={role ? 2 : 1} strokeDasharray={meta.observed ? undefined : "4 3"} />
              <text x={70} y={15} textAnchor="middle" fontSize={10} fill="currentColor">{(meta.label ?? n).slice(0, 26)}</text>
              <text x={70} y={28} textAnchor="middle" fontSize={9} fill="currentColor" fillOpacity={0.6}>{role || (meta.observed ? "observed" : "unobserved")}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function Dags() {
  const { data, error, loading } = useApi<AnyRec>("/research/dags");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div className="space-y-4">
      <Notice>Causal diagrams make assumptions explicit. A dashed box is a variable the organisation does not measure; adjustment cannot remove bias that flows through it. Run the causal workstreams in the Laboratory tab to see the back-door analysis and estimates.</Notice>
      {Object.entries(data.dags as Record<string, AnyRec>).map(([k, d]) => (
        <Card key={k} title={d.question} subtitle={`Treatment: ${label(d.treatment)} · Outcome: ${label(d.outcome)}`}>
          <DagDrawing dag={d} />
          <Table head={["Variable", "Observed", "Causes"]} rows={Object.entries(d.nodes as Record<string, AnyRec>).map(([n, m]) => [m.label ?? label(n), m.observed ? "yes" : "no — unmeasured", (d.edges as [string, string][]).filter(([a]) => a === n).map(([, b]) => label(b)).join(", ") || "—"])} />
        </Card>
      ))}
    </div>
  );
}

function Library() {
  const { data, error, loading } = useApi<AnyRec>("/research/library");
  const [q, setQ] = useState("");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const entries = (data.entries as AnyRec[]).filter((e) => !q || JSON.stringify(e).toLowerCase().includes(q.toLowerCase()));
  return (
    <Card title="Evidence library" subtitle={`${data.entries.length} sources, each with a recorded verification status (library v${data.version}).`}
      actions={<input aria-label="Search library" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="rounded-lg border border-line bg-raised px-2 py-1 text-sm" />}>
      <Table head={["Source", "Year", "Main finding", "Relevance", "Verification"]} rows={entries.map((e) => [
        <span key="t"><span className="font-medium">{e.title}</span><span className="block text-xs text-muted">{Array.isArray(e.authors) ? e.authors.join(", ") : e.authors}{e.venue ? ` · ${e.venue}` : ""}</span>
          {e.doi ? <a className="text-xs text-accent hover:underline" href={`https://doi.org/${e.doi}`} target="_blank" rel="noreferrer">doi:{e.doi}</a> : e.url ? <a className="text-xs text-accent hover:underline" href={e.url} target="_blank" rel="noreferrer">source</a> : null}</span>,
        e.year, <span key="f" className="text-xs">{e.main_finding}</span>, <span key="r" className="text-xs text-muted">{e.relevance}</span>, <Badge key="v">{label(e.verification)}</Badge>,
      ])} />
    </Card>
  );
}

function PublicData() {
  const { data, error, loading } = useApi<AnyRec>("/research/public-data");
  const [selected, setSelected] = useState<number | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const ready = (data.sources as AnyRec[]).every((s) => s.available);
  const start = async (study: string) => {
    setErr(null);
    try { const r = await post<AnyRec>("/research/runs", { workstream: "public_data", params: { study } }); setSelected(r.id); } catch (e) { setErr(e as ApiError); }
  };
  const reproduce = async (id: number) => {
    try { const r = await post<AnyRec>(`/research/runs/${id}/reproduce`, {}); setSelected(r.id); } catch (e) { setErr(e as ApiError); }
  };
  return (
    <div className="space-y-4">
      <Notice>
        Real project records from public research datasets test the product&apos;s core claims outside synthetic data: that raw delivery
        metrics mostly reflect conditions, that comparisons between delivery units change once context is accounted for, and that
        team or capability signals are smaller and less certain than context. Units are projects and organisations — no dataset
        identifies people, and nothing here evaluates anyone.
      </Notice>
      {!ready && <Notice tone="warn">Some datasets have not been downloaded yet. An administrator can run <code>{data.fetch_command}</code> (downloads from a pinned public commit and verifies checksums).</Notice>}
      <ErrorState error={err} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Studies" subtitle="Each run records the dataset checksums it used.">
          <ul className="space-y-1">
            {[{ id: "all", title: "All studies + cross-dataset summary (about 2 minutes)" }, ...data.studies].map((s: AnyRec) => (
              <li key={s.id} className="flex items-center justify-between gap-2 text-sm">
                <span>{s.title}</span>
                <button type="button" disabled={!ready} onClick={() => start(s.id)} className="shrink-0 rounded-md border border-line px-2 py-0.5 text-xs text-accent hover:bg-bg disabled:opacity-40">Run</button>
              </li>
            ))}
          </ul>
        </Card>
        <div className="lg:col-span-2">{selected ? <RunDetail key={selected} id={selected} onReproduce={reproduce} /> : <Empty>Run a study to see its results.</Empty>}</div>
      </div>
      <Card title="Datasets" subtitle={<>Downloaded from <a className="text-accent hover:underline" href={data.mirror.repository} target="_blank" rel="noreferrer">{data.mirror.repository}</a> at commit <code>{String(data.mirror.commit).slice(0, 12)}</code> — {data.mirror.licence}</>}>
        <Table head={["Dataset", "Origin", "Terms of use", "Limitations", "Status"]} rows={(data.sources as AnyRec[]).map((s) => [
          <span key="t"><span className="font-medium">{s.title}</span><span className="block text-xs text-muted">{s.description}</span></span>,
          <span key="o" className="text-xs">{s.origin}</span>, <span key="u" className="text-xs text-muted">{s.terms}</span>,
          <span key="l" className="text-xs text-muted">{(s.limitations ?? []).join(" ")}</span>,
          <Badge key="s" tone={s.available ? "good" : "warn"}>{s.available ? "● verified" : "▲ not downloaded"}</Badge>,
        ])} />
      </Card>
    </div>
  );
}

export default function ResearchPage() {
  const { data, error, loading } = useApi<AnyRec>("/research/overview");
  const [tab, setTab] = useState<Tab>("lab");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div>
      <PageHeader title="Research Laboratory" subtitle="Reproducible analyses behind the product: exploratory data analysis, registered hypothesis tests, model comparison, causal diagrams and simulated scenarios. Aggregates and pseudonymised identifiers only." />
      <Notice tone="warn">{Object.entries(data.status_legend as Record<string, string>).map(([k, v]) => `${label(k)}: ${v}.`).join(" ")} Nothing here is a finding about a real organisation.</Notice>
      <div className="mt-4">
        <Tabs<Tab> value={tab} onChange={setTab} tabs={[
          { id: "lab", label: "Laboratory" }, { id: "public", label: "Real-world data" }, { id: "questions", label: "Questions & hypotheses" }, { id: "measurement", label: "Measurement framework" },
          { id: "dags", label: "Causal diagrams" }, { id: "library", label: "Evidence library" },
        ]} />
        {tab === "lab" && <Laboratory overview={data} />}
        {tab === "public" && <PublicData />}
        {tab === "questions" && <Questions overview={data} />}
        {tab === "measurement" && <Measurement />}
        {tab === "dags" && <Dags />}
        {tab === "library" && <Library />}
      </div>
    </div>
  );
}
