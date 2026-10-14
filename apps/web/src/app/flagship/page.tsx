"use client";

import Link from "next/link";
import { Bars } from "@/components/charts";
import { Badge, Card, ErrorState, Loading, Notice, PageHeader, Stat, Table } from "@/components/ui";
import { useApi } from "@/lib/api";
import { label, num, pct } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

function Step({ n, title, children, wide = false }: { n: number; title: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <Card title={<span><span className="mr-2 rounded-full bg-accent/10 px-2 py-0.5 text-xs text-accent">Step {n}</span>{title}</span>} className={wide ? "lg:col-span-2" : ""}>
      {children}
    </Card>
  );
}

function Plain({ text }: { text?: string }) {
  return text ? <p className="mb-3 text-sm">{text}</p> : null;
}

export default function FlagshipPage() {
  const { data, error, loading } = useApi<AnyRec>("/analysis/flagship");
  if (loading) return <Loading what="Loading flagship study" />;
  if (error || !data) return <ErrorState error={error} />;
  const s = data.steps;
  const s1 = s["1_raw_outcomes"], s2 = s["2_assignment"], s3 = s["3_models"], s4 = s["4_uncertainty"], s5 = s["5_interpretations"], s6 = s["6_sensitivity"], s7 = s["7_proxies"];
  const truth: AnyRec | undefined = data.truth_check;
  const truthBy = new Map<string, number>((truth?.signals ?? []).map((r: AnyRec) => [r.signal, r.spearman_with_truth]));
  const proxyChart = (s7.proxies as AnyRec[]).map((p) => ({
    signal: p.proxy.replace(" (lower is better)", ""),
    adjusted: Math.round(p.spearman_with_adjusted_evidence * 100) / 100,
    ...(truth ? { truth: Math.round((truthBy.get(p.proxy) ?? 0) * 100) / 100 } : {}),
  }));
  const survival = Object.entries(s6.share_of_strong_conclusions_surviving as Record<string, number>).map(([k, v]) => ({ confounder: label(k), survive: Math.round(v * 100) }));
  return (
    <div>
      <PageHeader title="Flagship study: do raw metrics misrepresent project-manager contribution?"
        subtitle={`${s1.n_project_managers} project managers · model run ${data.run_id} · ${data.data}. Seven steps, each with its evidence and its limits.`} />
      <Notice tone="warn">
        {data.ground_rules.join(" ")} People appear under pseudonyms. This study explains the method — it is not an assessment of anyone.
      </Notice>

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Raw spread explained by conditions" value={pct(s1.share_of_raw_spread_predicted_by_conditions)} hint="before anything about the person" />
        <Stat label="Complexity clustering (ICC)" value={num(s2.icc_complexity_within_pm, 2)} hint="assignment is not random" />
        <Stat label="Raw 'top' verdicts supported" value={pct(s4.raw_top_quintile.share_supported_by_adjusted_evidence)} hint={`of ${s4.raw_top_quintile.n} people in the raw top fifth`} />
        <Stat label="No conclusion" value={s4.conclusion_counts.insufficient_evidence ?? 0} hint="too little evidence — the system abstains" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Step n={1} title="Raw delivery outcomes">
          <Plain text={s1.plain_language} />
          <Table head={["Percentile", "Raw on-time rate"]} rows={Object.entries(s1.on_time_rate_quantiles as Record<string, number>).map(([k, v]) => [k.toUpperCase(), pct(v)])} />
        </Step>
        <Step n={2} title="Who gets which conditions">
          <Plain text={s2.plain_language} />
          <Table head={["Job family", "Mean complexity", "Mean staffing shortfall", "Mean dependencies"]}
            rows={s2.conditions_by_job_family.map((r: AnyRec) => [label(r.job_family), num(r.mean_complexity, 2), num(r.mean_resource_constraint, 2), num(r.mean_dependencies, 2)])} />
        </Step>
        <Step n={3} title="Transparent baseline and primary model">
          <Plain text={s3.plain_language} />
          <Table head={["Condition", "Baseline OLS (pp per unit) [95%]", "Within-person model"]} rows={s3.transparent_baseline.coefficients.map((c: AnyRec) => [
            label(c.term), `${num(c.estimate, 2)} [${num(c.ci95[0], 2)}, ${num(c.ci95[1], 2)}]`, num(s3.primary_model.within_person_coefficients?.[c.term], 2),
          ])} />
          <p className="mt-2 text-xs text-muted">Baseline R² {num(s3.transparent_baseline.r_squared, 2)}. {s3.primary_model.model}.</p>
        </Step>
        <Step n={4} title="Uncertainty and unsupported conclusions">
          <Plain text={s4.plain_language} />
          <Table head={["Conclusion", "People"]} rows={Object.entries(s4.conclusion_counts as Record<string, number>).map(([k, v]) => [label(k), v])} />
        </Step>
        <Step n={5} title="Before and after: how the same record reads" wide>
          <p className="mb-3 text-xs text-muted">Selection rule: {s5.selection_rule}</p>
          <div className="grid gap-3 md:grid-cols-2">
            {s5.examples.map((e: AnyRec) => (
              <div key={e.person} className="rounded-lg border border-line p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2"><strong>{e.person}</strong><span className="text-xs text-muted">{e.conditions}</span>
                  {truth?.example_true_effects_pp?.[e.person] !== undefined && <Badge>synthetic truth: {num(truth.example_true_effects_pp[e.person], 1)} pp</Badge>}</div>
                <p className="mt-2"><span className="text-xs font-semibold uppercase text-muted">Raw dashboard</span><br />{e.raw_dashboard_reading}</p>
                <p className="mt-2"><span className="text-xs font-semibold uppercase text-accent">MeritVector</span><br />{e.meritvector_reading}</p>
              </div>
            ))}
          </div>
        </Step>
        <Step n={6} title="Sensitivity and omitted confounders">
          <Plain text={s6.plain_language} />
          <Bars data={survival} x="confounder" series={[{ key: "survive", label: "Strong conclusions surviving (%)" }]} height={200} />
          <Table head={["Alternative specification", "Agreement (Spearman)", "Conclusions changed"]} rows={Object.entries(s6.alternative_specifications as Record<string, AnyRec>).map(([k, v]) => [label(k), num(v.spearman_with_base, 2), v.share_conclusions_changed === null ? "—" : pct(v.share_conclusions_changed)])} />
        </Step>
        <Step n={7} title="How misleading proxies distort assessment">
          <Plain text={s7.plain_language} />
          <Bars data={proxyChart} x="signal" layout="vertical" height={280}
            series={[{ key: "adjusted", label: "Correlation with adjusted evidence" }, ...(truth ? [{ key: "truth", label: "Correlation with synthetic truth" }] : [])]} />
        </Step>
        {truth && (
          <Card title="Check against the hidden synthetic truth" subtitle={truth.note} className="lg:col-span-2">
            <div className="grid gap-3 md:grid-cols-3">
              <Stat label="Raw top fifth truly above average" value={pct(truth.raw_top_quintile_truly_above_average)} hint={Math.abs(truth.raw_top_quintile_truly_above_average - 0.5) < 0.1 ? "close to a coin flip" : "share of raw top performers"} />
              <Stat label="'Above expectation' truly above" value={pct(truth.adjusted_above_truly_above_average)} />
              <Stat label="'Below expectation' truly below" value={pct(truth.adjusted_below_truly_below_average)} />
            </div>
            <div className="mt-3">
              <Table head={["Signal", "Correlation with truth", "Truly strong people placed in the bottom half"]} rows={truth.signals.map((r: AnyRec) => [r.signal, num(r.spearman_with_truth, 2), pct(r.true_top_quartile_placed_in_bottom_half)])} />
            </div>
          </Card>
        )}
        <Card title="Does this hold on real data?" className="lg:col-span-2">
          <p className="text-sm">The same pattern can be tested on public records of real projects: raw team and organisation comparisons against context-adjusted ones, with intervals. Run the studies in the <Link className="text-accent hover:underline" href="/research">Research Laboratory → Real-world data</Link> tab; findings are written up in <code>docs/research/PUBLIC_DATA_VALIDATION.md</code>.</p>
        </Card>
      </div>
    </div>
  );
}
