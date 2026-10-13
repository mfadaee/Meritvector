"use client";

import { Bars, TrendLines } from "@/components/charts";
import { Card, ErrorState, Loading, PageHeader, ProjectLink, SeverityBadge, Stat, Table } from "@/components/ui";
import { useApi } from "@/lib/api";
import { label, num, pct } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

export default function RisksPage() {
  const { data, error, loading } = useApi<AnyRec>("/portfolio/risks");
  const b = useApi<AnyRec>("/portfolio/bottlenecks");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const total = Object.values(data.status_counts as Record<string, number>).reduce((a, c) => a + c, 0);
  return (
    <div>
      <PageHeader title="Risk Intelligence" subtitle="Organisational risk patterns, dependency bottlenecks and resource constraints across the synthetic portfolio." />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Risks recorded" value={total} />
        <Stat label="Became issues" value={pct((data.status_counts.issue ?? 0) / total)} hint="Materialisation rate" />
        <Stat label="Mitigated" value={pct((data.status_counts.mitigated ?? 0) / total)} />
        <Stat label="Stale dependencies" value={b.data?.stale_dependencies ?? "—"} hint="Open > 21 days" />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Risk trend" subtitle="Risks identified per month and how many became issues" className="lg:col-span-2">
          <TrendLines data={data.monthly} x="month" series={[{ key: "identified", label: "Identified" }, { key: "became_issue", label: "Became issue" }, { key: "mitigated", label: "Mitigated" }]} />
        </Card>
        <Card title="Risks per project by complexity" subtitle="More complex projects carry more risk — context for any delivery comparison">
          <Bars data={data.by_complexity.map((r: AnyRec) => ({ ...r, complexity: `Level ${r.technical_complexity}`, rpp: Math.round(r.risks_per_project * 10) / 10 }))} x="complexity" series={[{ key: "rpp", label: "Risks per project" }]} height={220} />
        </Card>
        <Card title="By business unit">
          <Table head={["Unit", "Risks", "Issues", "Materialisation", "Open high"]} rows={data.by_business_unit.map((r: AnyRec) => [r.business_unit, r.risks, r.issues, pct(r.materialisation_rate), r.open_high])} />
        </Card>
        <Card title="Organisational bottlenecks" subtitle="Dependencies on other teams">
          {b.data ? <Bars data={b.data.dependencies_by_team.map((r: AnyRec) => ({ ...r, median: r.median_days_to_resolve }))} x="depends_on" series={[{ key: "median", label: "Median days to resolve" }]} layout="vertical" height={300} /> : <Loading />}
        </Card>
        <Card title="Resource constraint vs delivery" subtitle="On-time rate by PMO-assessed staffing shortfall and complexity">
          {b.data ? <Table head={["Resourcing gap", "Complexity", "Milestones", "On-time", "Mean slip %"]} rows={b.data.resource_constraint_analysis.map((r: AnyRec) => [label(r.resource_band), r.technical_complexity, r.milestones, pct(r.on_time_rate), num(r.mean_slip_pct)])} /> : <Loading />}
        </Card>
        <Card title="Recurring risk themes">
          <Table head={["Theme", "Count", "Became issue"]} rows={data.themes.map((t: AnyRec) => [t.title, t.count, t.issues])} />
        </Card>
        <Card title="Open high-severity register" className="lg:col-span-2">
          <Table head={["Risk", "Project", "Unit", "Identified", "Status", ""]} rows={data.open_high_register.slice(0, 25).map((r: AnyRec) => [r.title, <ProjectLink key="p" id={r.project_id} name={r.name} />, r.business_unit, String(r.identified_on).slice(0, 10), label(r.status), <SeverityBadge key="s" severity={r.severity} />])} />
        </Card>
      </div>
    </div>
  );
}
