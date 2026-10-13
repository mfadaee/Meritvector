"use client";

import { useState } from "react";
import { Badge, Button, Card, ErrorState, HealthBadge, Loading, Notice, PageHeader, ProjectLink, Table } from "@/components/ui";
import { useApi } from "@/lib/api";
import { label, num, pct } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

export default function ProjectsPage() {
  const [f, setF] = useState({ status: "active", business_unit: "", health: "", q: "" });
  const [selected, setSelected] = useState<string[]>([]);
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]).toString();
  const { data, error, loading } = useApi<AnyRec>(`/portfolio/projects?limit=200&${qs}`);
  const cmp = useApi<AnyRec>(selected.length >= 2 ? `/portfolio/compare?ids=${selected.join(",")}` : null);
  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < 4 ? [...s, id] : s));
  return (
    <div>
      <PageHeader title="Project Portfolio" subtitle="Every synthetic project with its operating conditions and health. Select 2–4 projects to compare outcomes and conditions side by side." />
      <div className="mb-4 flex flex-wrap gap-2">
        <select aria-label="Status" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className="rounded-lg border border-line bg-raised px-2 py-1.5 text-sm">
          <option value="">All statuses</option><option value="active">Active</option><option value="completed">Completed</option>
        </select>
        <select aria-label="Business unit" value={f.business_unit} onChange={(e) => setF({ ...f, business_unit: e.target.value })} className="rounded-lg border border-line bg-raised px-2 py-1.5 text-sm">
          <option value="">All business units</option>{(data?.business_units ?? []).map((b: string) => <option key={b}>{b}</option>)}
        </select>
        <select aria-label="Health" value={f.health} onChange={(e) => setF({ ...f, health: e.target.value })} className="rounded-lg border border-line bg-raised px-2 py-1.5 text-sm">
          <option value="">Any health</option><option value="green">On track</option><option value="amber">At risk</option><option value="red">Off track</option><option value="closed">Closed</option>
        </select>
        <input aria-label="Search projects" placeholder="Search name" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} className="rounded-lg border border-line bg-raised px-2 py-1.5 text-sm" />
        {selected.length > 0 && <Button variant="secondary" onClick={() => setSelected([])}>Clear selection ({selected.length})</Button>}
      </div>
      {cmp.data && (
        <Card title="Comparison: outcomes and operating conditions" subtitle={cmp.data.note} className="mb-4">
          <Table head={["", ...cmp.data.projects.map((p: AnyRec) => <ProjectLink key={p.project_id} id={p.project_id} name={p.name} />)]} rows={[
            ["Lead", ...cmp.data.projects.map((p: AnyRec) => p.lead)],
            ["Health", ...cmp.data.projects.map((p: AnyRec) => <HealthBadge key={p.project_id} health={p.health} />)],
            ...["technical_complexity", "dependency_count", "resource_constraint", "team_size", "environment", "maturity"].map((k) => [label(k), ...cmp.data!.projects.map((p: AnyRec) => String(p.conditions[k]))]),
            ["On-time milestones", ...cmp.data.projects.map((p: AnyRec) => pct(p.outcomes.on_time_rate))],
            ["Mean slip (% of interval)", ...cmp.data.projects.map((p: AnyRec) => num(p.outcomes.mean_slip_pct))],
            ["Risks / issues", ...cmp.data.projects.map((p: AnyRec) => `${p.outcomes.risks} / ${p.outcomes.issues}`)],
          ]} />
        </Card>
      )}
      {loading ? <Loading /> : error ? <ErrorState error={error} /> : (
        <Card title={`${data?.total ?? 0} projects`}>
          <Notice>Complexity, dependencies and resource constraint come from the PMO assessment at kick-off. Health is a transparent rule — see METRICS_FRAMEWORK.md.</Notice>
          <div className="mt-2">
            <Table head={["", "Project", "Lead", "Unit", "Complexity", "Deps", "Resource constraint", "Status", "Health"]} rows={(data?.items ?? []).map((p: AnyRec) => [
              <input key="c" type="checkbox" aria-label={`Compare ${p.name}`} checked={selected.includes(p.id)} onChange={() => toggle(p.id)} />,
              <ProjectLink key="p" id={p.id} name={p.name} />, p.lead_name, p.business_unit, `${p.technical_complexity}/5`, p.dependency_count,
              p.resource_constraint.toFixed(2), <Badge key="s">{p.status}</Badge>, <HealthBadge key="h" health={p.health} />,
            ])} />
          </div>
        </Card>
      )}
    </div>
  );
}
