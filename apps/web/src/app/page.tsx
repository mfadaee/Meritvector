"use client";

import Link from "next/link";
import { Bars, TrendLines } from "@/components/charts";
import { Card, ErrorState, HealthBadge, Loading, Notice, PageHeader, Stat } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { pct } from "@/lib/format";

type Overview = {
  tenant: { name: string; as_of: string };
  kpis: { employees: number; projects_total: number; projects_active: number; business_units: number; on_time_rate_recent: number | null; open_high_risks: number; open_dependencies: number };
  health_counts: Record<string, number>;
  delivery_trend: { quarter: string; milestones: number; on_time_rate: number; mean_slip_pct: number; mean_complexity: number }[];
  complexity_distribution: { technical_complexity: number; status: string; projects: number }[];
  evidence_coverage: { employees: number; insufficient_evidence: number; share_with_sufficient_evidence: number; run_id: string } | null;
  notes: string;
};

export default function OverviewPage() {
  const { me } = useAuth();
  const { data, error, loading } = useApi<Overview>("/portfolio/overview");
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const cx = [1, 2, 3, 4, 5].map((c) => ({
    complexity: `Level ${c}`,
    completed: data.complexity_distribution.find((d) => d.technical_complexity === c && d.status === "completed")?.projects ?? 0,
    active: data.complexity_distribution.find((d) => d.technical_complexity === c && d.status === "active")?.projects ?? 0,
  }));
  const trend = data.delivery_trend.map((d) => ({ ...d, on_time_pct: Math.round(d.on_time_rate * 1000) / 10 }));
  return (
    <div>
      <PageHeader title="Overview" subtitle={`${data.tenant.name}. ${data.notes}`} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Employees" value={data.kpis.employees} hint={`${data.kpis.business_units} business units`} />
        <Stat label="Active projects" value={data.kpis.projects_active} hint={`${data.kpis.projects_total} in 24-month history`} />
        <Stat label="On-time milestones (recent)" value={pct(data.kpis.on_time_rate_recent)} hint="Planned 3–9 months ago · raw, not adjusted" />
        <Stat label="Open high-severity risks" value={data.kpis.open_high_risks} hint={`${data.kpis.open_dependencies} open dependencies`} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Project delivery trend" subtitle="Share of achieved milestones within 5% of their planned interval, by quarter" className="lg:col-span-2">
          <TrendLines data={trend} x="quarter" series={[{ key: "on_time_pct", label: "On-time %" }]} yLabel="%" />
        </Card>
        <Card title="Active project health" subtitle="Rule-based RAG from the registers">
          <div className="space-y-2">
            {(["green", "amber", "red"] as const).map((h) => (
              <div key={h} className="flex items-center justify-between rounded-lg border border-line px-3 py-2">
                <HealthBadge health={h} />
                <span className="text-lg font-semibold tabular-nums">{data.health_counts[h] ?? 0}</span>
              </div>
            ))}
            <Link href="/projects" className="block pt-1 text-xs text-accent hover:underline">Open project portfolio →</Link>
          </div>
        </Card>
        <Card title="Project complexity distribution" subtitle="PMO technical-complexity assessment at kick-off" className="lg:col-span-2">
          <Bars data={cx} x="complexity" series={[{ key: "completed", label: "Completed" }, { key: "active", label: "Active" }]} stacked yLabel="projects" />
        </Card>
        <Card title="Evidence coverage" subtitle="Performance-assessment features">
          {data.evidence_coverage ? (
            <div className="space-y-2 text-sm">
              <div className="text-2xl font-semibold">{pct(data.evidence_coverage.share_with_sufficient_evidence)}</div>
              <p className="text-muted">
                of {data.evidence_coverage.employees} employees have enough validated evidence for a context-adjusted estimate.
                {" "}{data.evidence_coverage.insufficient_evidence} are reported as “insufficient evidence”.
              </p>
              <p className="text-xs text-muted">Model run {data.evidence_coverage.run_id}</p>
            </div>
          ) : (
            <Notice>
              {me?.tenant.assessment_enabled
                ? "Evidence coverage is shown to managers, HR reviewers and administrators."
                : "Assessment features are not enabled for this organisation (governance approval required)."}
            </Notice>
          )}
        </Card>
      </div>
    </div>
  );
}
