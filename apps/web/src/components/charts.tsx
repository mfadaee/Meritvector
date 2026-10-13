"use client";

/**
 * Chart primitives. Every chart is fed by API data (seeded records or model outputs).
 * Conventions (dataviz method): one y-axis, thin 2px lines, rounded bar ends, recessive
 * grid, hover tooltips, a legend whenever there are >=2 series, and a table view.
 */

import { useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

export const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
const AXIS = { stroke: "var(--chart-axis)", fontSize: 11, tickLine: false } as const;
const TT = {
  contentStyle: {
    background: "rgb(var(--raised))",
    border: "1px solid rgb(var(--line))",
    borderRadius: 8,
    fontSize: 12,
    color: "rgb(var(--ink))",
  },
  labelStyle: { color: "rgb(var(--muted))" },
};

type Row = Record<string, string | number | null | undefined>;

export function ChartFrame({ children, table, height = 260 }: { children: ReactNode; table: { head: string[]; rows: (string | number)[][] }; height?: number }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div>
      <div className="mb-1 flex justify-end">
        <button className="text-xs text-muted underline-offset-2 hover:underline" onClick={() => setShowTable((s) => !s)}>
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {showTable ? (
        <div className="max-h-72 overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted">{table.head.map((h) => <th key={h} className="px-1 py-1 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i} className="border-t border-line/60">{r.map((c, j) => <td key={j} className="px-1 py-1 tabular-nums">{c}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ height }}>{children}</div>
      )}
    </div>
  );
}

const fmt = (v: unknown, d = 2) => (typeof v === "number" ? (Math.abs(v) < 1 && v !== 0 ? v.toFixed(d) : v.toFixed(1)) : String(v ?? "—"));

export function TrendLines({ data, x, series, yLabel, height, yDomain }: {
  data: Row[]; x: string; series: { key: string; label: string }[]; yLabel?: string; height?: number; yDomain?: [number, number];
}) {
  return (
    <ChartFrame height={height} table={{ head: [x, ...series.map((s) => s.label)], rows: data.map((d) => [String(d[x]), ...series.map((s) => fmt(d[s.key]))]) }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey={x} {...AXIS} />
          <YAxis {...AXIS} domain={yDomain ?? ["auto", "auto"]} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: "var(--chart-axis)", fontSize: 11 } : undefined} />
          <Tooltip {...TT} formatter={(v) => fmt(v)} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
          {series.map((s, i) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={SERIES[i]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function Bars({ data, x, series, height, stacked = false, layout = "horizontal", yLabel }: {
  data: Row[]; x: string; series: { key: string; label: string }[]; height?: number; stacked?: boolean; layout?: "horizontal" | "vertical"; yLabel?: string;
}) {
  const vertical = layout === "vertical";
  return (
    <ChartFrame height={height} table={{ head: [x, ...series.map((s) => s.label)], rows: data.map((d) => [String(d[x]), ...series.map((s) => fmt(d[s.key]))]) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout={layout} margin={{ top: 8, right: 16, bottom: 4, left: vertical ? 40 : 0 }} barGap={2}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={vertical} horizontal={!vertical} />
          {vertical ? (
            <>
              <XAxis type="number" {...AXIS} />
              <YAxis type="category" dataKey={x} {...AXIS} width={140} />
            </>
          ) : (
            <>
              <XAxis dataKey={x} {...AXIS} />
              <YAxis {...AXIS} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: "var(--chart-axis)", fontSize: 11 } : undefined} />
            </>
          )}
          <Tooltip {...TT} cursor={{ fill: "rgb(var(--line) / 0.35)" }} formatter={(v) => fmt(v)} />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={SERIES[i]} stackId={stacked ? "a" : undefined}
              stroke="rgb(var(--surface))" strokeWidth={stacked ? 2 : 0}
              radius={stacked && i < series.length - 1 ? 0 : vertical ? [0, 4, 4, 0] : [4, 4, 0, 0]} maxBarSize={36} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/** Raw vs context-adjusted estimates; the diagonal-free design avoids implying the axes share a scale meaning. */
export function RawAdjustedScatter({ points, height = 320 }: {
  points: { employee_id: string; raw_estimate: number; adjusted_estimate: number; conclusion: string }[]; height?: number;
}) {
  const groups = [
    { key: "insufficient_evidence", label: "Insufficient evidence" },
    { key: "within_expected_range", label: "Within expected range" },
    { key: "clear", label: "Clear difference (CI excludes 0)" },
  ];
  const by = (k: string) => points.filter((p) => (k === "clear" ? ["above_context_expectation", "below_context_expectation"].includes(p.conclusion) : p.conclusion === k));
  return (
    <ChartFrame height={height} table={{ head: ["employee", "raw (pp)", "adjusted (pp)", "conclusion"], rows: points.map((p) => [p.employee_id, fmt(p.raw_estimate), fmt(p.adjusted_estimate), p.conclusion]) }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" />
          <XAxis type="number" dataKey="raw_estimate" name="Raw" {...AXIS} label={{ value: "Raw estimate (pp vs organisation mean)", position: "insideBottom", offset: -10, fill: "var(--chart-axis)", fontSize: 11 }} />
          <YAxis type="number" dataKey="adjusted_estimate" name="Adjusted" {...AXIS} label={{ value: "Context-adjusted (pp)", angle: -90, position: "insideLeft", fill: "var(--chart-axis)", fontSize: 11 }} />
          <ZAxis range={[60, 60]} />
          <ReferenceLine x={0} stroke="var(--chart-axis)" strokeDasharray="3 3" />
          <ReferenceLine y={0} stroke="var(--chart-axis)" strokeDasharray="3 3" />
          <Tooltip {...TT} formatter={(v) => fmt(v)} labelFormatter={() => ""}
            content={({ payload }) => {
              const p = payload?.[0]?.payload as (typeof points)[number] | undefined;
              if (!p) return null;
              return (
                <div style={TT.contentStyle} className="px-2 py-1">
                  <div className="font-medium">{p.employee_id}</div>
                  <div>Raw: {fmt(p.raw_estimate)} pp · Adjusted: {fmt(p.adjusted_estimate)} pp</div>
                  <div className="text-muted">{p.conclusion.replace(/_/g, " ")}</div>
                </div>
              );
            }} />
          <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12 }} />
          {groups.map((g, i) => (
            <Scatter key={g.key} name={g.label} data={by(g.key)} fill={SERIES[i]} stroke="rgb(var(--surface))" strokeWidth={2} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/** Point estimates with 95% intervals, drawn as SVG so every interval is visible. */
export function IntervalPlot({ items, unit = "pp", zeroLabel = "context expectation" }: {
  items: { label: string; estimate: number; low: number; high: number; note?: string }[]; unit?: string; zeroLabel?: string;
}) {
  const lo = Math.min(0, ...items.map((i) => i.low));
  const hi = Math.max(0, ...items.map((i) => i.high));
  const pad = (hi - lo) * 0.08 || 1;
  const min = lo - pad;
  const max = hi + pad;
  const W = 640;
  const row = 34;
  const left = 210;
  const sx = (v: number) => left + ((v - min) / (max - min)) * (W - left - 20);
  const H = items.length * row + 30;
  return (
    <ChartFrame height={H} table={{ head: ["item", "estimate", "95% low", "95% high"], rows: items.map((i) => [i.label, fmt(i.estimate), fmt(i.low), fmt(i.high)]) }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="Estimates with 95% intervals">
        <line x1={sx(0)} x2={sx(0)} y1={4} y2={H - 22} stroke="var(--chart-axis)" strokeDasharray="3 3" />
        <text x={sx(0)} y={H - 6} textAnchor="middle" fontSize={10} fill="var(--chart-axis)">0 = {zeroLabel}</text>
        {items.map((it, k) => {
          const y = 16 + k * row;
          return (
            <g key={it.label}>
              <title>{`${it.label}: ${fmt(it.estimate)} ${unit} (95% ${fmt(it.low)} to ${fmt(it.high)})${it.note ? ` — ${it.note}` : ""}`}</title>
              <rect x={0} y={y - row / 2 + 2} width={W} height={row - 4} fill="transparent" />
              <text x={left - 8} y={y + 4} textAnchor="end" fontSize={11} fill="rgb(var(--ink))">{it.label}</text>
              <line x1={sx(it.low)} x2={sx(it.high)} y1={y} y2={y} stroke="var(--series-1)" strokeWidth={2} strokeLinecap="round" />
              <circle cx={sx(it.estimate)} cy={y} r={5} fill="var(--series-1)" stroke="rgb(var(--surface))" strokeWidth={2} />
              <text x={Math.min(sx(it.high) + 6, W - 30)} y={y + 4} fontSize={10} fill="var(--chart-axis)">{fmt(it.estimate)}</text>
            </g>
          );
        })}
      </svg>
    </ChartFrame>
  );
}
