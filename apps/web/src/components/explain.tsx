"use client";

import { useState, type ReactNode } from "react";
import { Badge, Empty, ErrorState, Loading, Table } from "@/components/ui";
import { useApi } from "@/lib/api";
import { label } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

const EVIDENCE_STATUS: Record<string, string> = {
  established: "Established in research",
  reasonable_hypothesis: "Reasonable hypothesis",
  product_assumption: "Product assumption — not yet validated",
};

/** "How was this assessed?" — the metric's definition, sources, assumptions and prohibited interpretations. */
export function HowAssessed({ metric, family = "pmo" }: { metric: string; family?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="text-xs font-medium text-accent hover:underline">
        {open ? "Hide explanation" : "How was this assessed?"}
      </button>
      {open && <HowAssessedPanel metric={metric} family={family} />}
    </div>
  );
}

function List({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</div>
      <ul className="mt-0.5 list-disc space-y-0.5 pl-4">{items.map((i) => <li key={i}>{i}</li>)}</ul>
    </div>
  );
}

function HowAssessedPanel({ metric, family }: { metric: string; family: string }) {
  const { data, error, loading } = useApi<AnyRec>(`/measurement/metrics/${metric}?family_id=${family}`);
  if (loading) return <Loading what="Loading definition" />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div role="region" aria-label={`How ${data.label} was assessed`} className="mt-2 space-y-2 rounded-lg border border-line bg-bg p-3 text-xs">
      <p className="text-sm">{data.plain_language}</p>
      <div className="flex flex-wrap gap-1">
        <Badge>{data.construct_label}</Badge>
        {data.evidence_status && <Badge tone={data.evidence_status === "established" ? "good" : "warn"}>{EVIDENCE_STATUS[data.evidence_status] ?? data.evidence_status}</Badge>}
        <Badge>Unit: {data.unit}</Badge>
      </div>
      <p><strong>Definition.</strong> {data.definition}</p>
      <p><strong>How it is computed.</strong> {data.computation}</p>
      <List title="Data sources" items={data.data_sources} />
      <List title="Assumptions" items={data.assumptions} />
      <List title="Limitations" items={data.limitations} />
      <List title="Do not interpret this as" items={data.prohibited_interpretations} />
    </div>
  );
}

/** Generic, readable renderer for research results: headline text first, then tables for record lists. */
export function ResultView({ value, depth = 0 }: { value: unknown; depth?: number }): ReactNode {
  if (value === null || value === undefined) return <span className="text-muted">—</span>;
  if (typeof value === "number") return <span className="tabular-nums">{Number.isInteger(value) ? value : value.toFixed(Math.abs(value) < 0.01 && value !== 0 ? 4 : 3)}</span>;
  if (typeof value === "boolean") return <span>{value ? "yes" : "no"}</span>;
  if (typeof value === "string") return <span>{value}</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <Empty>None.</Empty>;
    if (value.every((v) => v && typeof v === "object" && !Array.isArray(v))) {
      const cols = Array.from(new Set(value.flatMap((v) => Object.keys(v as AnyRec)))).slice(0, 10);
      return <Table head={cols.map(label)} rows={(value as AnyRec[]).slice(0, 50).map((r) => cols.map((c) => <ResultView key={c} value={r[c]} depth={depth + 1} />))} />;
    }
    return <span>{value.map((v) => (typeof v === "object" ? JSON.stringify(v) : String(v))).join(", ")}</span>;
  }
  const entries = Object.entries(value as AnyRec);
  if (depth >= 3) return <code className="break-all text-[11px] text-muted">{JSON.stringify(value).slice(0, 400)}</code>;
  return (
    <dl className={depth ? "space-y-1" : "space-y-3"}>
      {entries.map(([k, v]) => (
        <div key={k} className={v && typeof v === "object" ? "rounded-lg border border-line/70 p-2" : "flex flex-wrap gap-x-2"}>
          <dt className="text-xs font-semibold text-muted">{label(k)}</dt>
          <dd className="text-sm"><ResultView value={v} depth={depth + 1} /></dd>
        </div>
      ))}
    </dl>
  );
}

const HEADLINE_KEYS = ["plain_language", "conclusion", "interpretation", "finding", "summary", "note"];

/** Plain-English headline sentences pulled from a result, shown above the detail. */
export function Headlines({ result }: { result: AnyRec }) {
  const lines = HEADLINE_KEYS.map((k) => result[k]).filter((v): v is string => typeof v === "string");
  if (!lines.length) return null;
  return <div className="space-y-1 rounded-lg border border-accent/30 bg-accent/5 p-3 text-sm">{lines.map((l) => <p key={l}>{l}</p>)}</div>;
}
