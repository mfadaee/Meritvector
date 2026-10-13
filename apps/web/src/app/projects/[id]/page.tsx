"use client";

import { useParams } from "next/navigation";
import { Bars } from "@/components/charts";
import { Badge, Card, EmployeeLink, ErrorState, HealthBadge, Loading, PageHeader, SeverityBadge, Stat, Table } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { date, label } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const { data, error, loading } = useApi<AnyRec>(`/portfolio/projects/${id}`);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const slip = data.milestones.filter((m: AnyRec) => m.slip_pct !== null).map((m: AnyRec) => ({ milestone: m.name.replace(" of ", "/").replace("Milestone ", "M"), slip_pct: m.slip_pct }));
  const canSeeLead = me?.permissions.all_contribution || (me?.permissions.team_contribution) || me?.employee_id === data.lead?.employee_id;
  return (
    <div>
      <PageHeader title={data.name} subtitle={<>{data.business_unit} · {label(data.kind)} · {date(data.start_date)} → {date(data.planned_end)} · Lead: {data.lead ? (canSeeLead ? <EmployeeLink id={data.lead.employee_id} name={data.lead.display_name} /> : data.lead.display_name) : "—"}</>}
        actions={<span className="flex gap-2"><Badge>{data.status}</Badge><HealthBadge health={data.health?.health} /></span>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label="Complexity" value={`${data.technical_complexity}/5`} />
        <Stat label="Dependencies" value={data.dependency_count} />
        <Stat label="Resource constraint" value={data.resource_constraint.toFixed(2)} hint="0 = fully staffed" />
        <Stat label="Team size" value={data.team_size} />
        <Stat label="Environment" value={<span className="text-base">{label(data.environment)}</span>} />
        <Stat label="Maturity" value={<span className="text-base">{label(data.maturity)}</span>} />
      </div>
      <p className="mt-2 text-xs text-muted">{data.context_note}</p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Milestone schedule variance" subtitle="Slip as % of the planned interval (negative = early)">
          {slip.length ? <Bars data={slip} x="milestone" series={[{ key: "slip_pct", label: "Slip %" }]} yLabel="% of interval" height={220} /> : <p className="text-sm text-muted">No milestones achieved yet.</p>}
        </Card>
        <Card title="Milestones">
          <Table head={["Milestone", "Planned", "Actual", "Slip (days)", "Status"]} rows={data.milestones.map((m: AnyRec) => [m.name, date(m.planned_date), date(m.actual_date), m.slip_days ?? "—", label(m.status)])} />
        </Card>
        <Card title="Risks and issues (RAID)">
          <Table head={["Risk", "Severity", "Identified", "Status"]} rows={data.risks.map((r: AnyRec) => [r.title, <SeverityBadge key="s" severity={r.severity} />, date(r.identified_on), label(r.status)])} empty="No risks recorded." />
        </Card>
        <Card title="Dependencies">
          <Table head={["Depends on", "Raised", "Resolved", "Status"]} rows={data.dependencies.map((d: AnyRec) => [d.depends_on, date(d.raised_on), date(d.resolved_on), label(d.status)])} empty="No dependencies." />
        </Card>
      </div>
    </div>
  );
}
