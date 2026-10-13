"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { ApiError } from "@/lib/api";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ title, subtitle, children, className = "", actions }: {
  title?: ReactNode; subtitle?: ReactNode; children: ReactNode; className?: string; actions?: ReactNode;
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-4 shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-sm font-semibold">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

const TONE: Record<string, string> = {
  neutral: "border-line text-muted",
  accent: "border-accent/40 text-accent",
  good: "border-good/50 text-good",
  warn: "border-warn/60 text-ink",
  serious: "border-serious/60 text-ink",
  critical: "border-critical/50 text-critical",
};

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: keyof typeof TONE; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${TONE[tone]}`}>
      {children}
    </span>
  );
}

const HEALTH: Record<string, { tone: keyof typeof TONE; icon: string; text: string }> = {
  green: { tone: "good", icon: "●", text: "On track" },
  amber: { tone: "warn", icon: "▲", text: "At risk" },
  red: { tone: "critical", icon: "■", text: "Off track" },
  closed: { tone: "neutral", icon: "○", text: "Closed" },
};

/** Status colour always ships with an icon and a text label — never colour alone. */
export function HealthBadge({ health }: { health?: string | null }) {
  const h = HEALTH[health ?? ""] ?? { tone: "neutral" as const, icon: "–", text: "Unknown" };
  return (
    <Badge tone={h.tone}>
      <span aria-hidden>{h.icon}</span>
      {h.text}
    </Badge>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone = severity === "high" ? "critical" : severity === "medium" ? "serious" : "neutral";
  return <Badge tone={tone}>{severity}</Badge>;
}

export function Loading({ what = "Loading" }: { what?: string }) {
  return <div className="animate-pulse py-8 text-center text-sm text-muted">{what}…</div>;
}

export function ErrorState({ error }: { error: ApiError | null }) {
  if (!error) return null;
  const gated = error.status === 403;
  return (
    <div className={`rounded-xl border p-4 text-sm ${gated ? "border-warn/60 bg-warn/10" : "border-critical/40 bg-critical/5"}`}>
      <div className="font-medium">{gated ? "Not available for your role or organisation" : "Something went wrong"}</div>
      <div className="mt-1 text-muted">{error.message}</div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">{children}</div>;
}

export function Table({ head, rows, empty = "Nothing to show." }: { head: ReactNode[]; rows: ReactNode[][]; empty?: string }) {
  if (!rows.length) return <Empty>{empty}</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
            {head.map((h, i) => (
              <th key={i} className="px-2 py-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line/60 last:border-0 hover:bg-bg/60">
              {r.map((c, j) => (
                <td key={j} className="px-2 py-2 align-top">{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="mb-4 flex flex-wrap gap-1 border-b border-line">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={`-mb-px border-b-2 px-3 py-2 text-sm ${value === t.id ? "border-accent font-medium text-ink" : "border-transparent text-muted hover:text-ink"}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Notice({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warn" }) {
  return (
    <div className={`rounded-lg border px-3 py-2 text-xs ${tone === "warn" ? "border-warn/60 bg-warn/10" : "border-line bg-bg"} text-muted`}>
      {children}
    </div>
  );
}

export function Button({ children, onClick, disabled, variant = "primary", type = "button" }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; variant?: "primary" | "secondary"; type?: "button" | "submit";
}) {
  const cls = variant === "primary"
    ? "bg-accent text-white hover:opacity-90"
    : "border border-line bg-raised text-ink hover:bg-bg";
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${cls}`}>
      {children}
    </button>
  );
}

export function EmployeeLink({ id, name }: { id: string; name?: string | null }) {
  return <Link href={`/employees/${id}`} className="text-accent hover:underline">{name ?? id}</Link>;
}

export function ProjectLink({ id, name }: { id: string; name?: string | null }) {
  return <Link href={`/projects/${id}`} className="text-accent hover:underline">{name ?? id}</Link>;
}

/** Minimal Markdown renderer for coordinator output (headings, lists, tables, bold/italic). */
export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const out: ReactNode[] = [];
  let list: string[] = [];
  let table: string[][] = [];
  const inline = (s: string, k: number) => {
    const parts = s.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    return parts.map((p, i) =>
      p.startsWith("**") ? <strong key={`${k}-${i}`}>{p.slice(2, -2)}</strong> : p.startsWith("*") && p.length > 2 ? <em key={`${k}-${i}`}>{p.slice(1, -1)}</em> : p,
    );
  };
  const flush = (k: number) => {
    if (list.length) {
      out.push(<ul key={`ul${k}`}>{list.map((l, i) => <li key={i}>{inline(l, i)}</li>)}</ul>);
      list = [];
    }
    if (table.length) {
      const [h, ...body] = table.filter((r) => !r.every((c) => /^-+$/.test(c.trim())));
      out.push(
        <table key={`t${k}`}>
          <thead><tr>{h.map((c, i) => <th key={i}>{c}</th>)}</tr></thead>
          <tbody>{body.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
        </table>,
      );
      table = [];
    }
  };
  lines.forEach((l, k) => {
    if (l.startsWith("- ")) { list.push(l.slice(2)); return; }
    if (l.startsWith("|")) { table.push(l.split("|").slice(1, -1).map((c) => c.trim())); return; }
    flush(k);
    if (l.startsWith("# ")) out.push(<h1 key={k}>{inline(l.slice(2), k)}</h1>);
    else if (l.startsWith("## ")) out.push(<h2 key={k}>{inline(l.slice(3), k)}</h2>);
    else if (/^\*[^*].*\*$/.test(l)) out.push(<p key={k}><em>{inline(l.slice(1, -1), k)}</em></p>);
    else if (l.trim()) out.push(<p key={k}>{inline(l, k)}</p>);
  });
  flush(lines.length);
  return <div className="prose-md text-sm">{out}</div>;
}
