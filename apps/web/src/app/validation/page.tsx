"use client";

import { useState } from "react";
import { Bars, TrendLines } from "@/components/charts";
import { Badge, Button, Card, ErrorState, Loading, Markdown, Notice, PageHeader, Stat, Table } from "@/components/ui";
import { ApiError, post, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { label, num, pct } from "@/lib/format";
import type { AnyRec } from "@/lib/types";

export default function ValidationPage() {
  const { me } = useAuth();
  const { data, error, loading } = useApi<AnyRec>("/analysis/validation");
  const runs = useApi<AnyRec[]>("/analysis/runs");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState error={error} />;
  const v = data.validation;
  const oot = Object.entries(v.out_of_time.models as Record<string, AnyRec>).map(([k, m]) => ({ model: label(k), mae: Math.round(m.mae * 100) / 100, rmse: m.rmse, r2: m.r2 }));
  const rel = v.calibration.reliability.map((r: AnyRec) => ({ bin: `${Math.round(r.mean_predicted * 100)}%`, predicted: Math.round(r.mean_predicted * 1000) / 10, observed: Math.round(r.observed_rate * 1000) / 10, n: r.n }));
  const se = data.synthetic_evaluation;
  const fair = data.fairness;
  return (
    <div>
      <PageHeader title="Model Validation" subtitle={`Run ${data.run_id} · data fingerprint ${String(data.data_hash).slice(0, 12)} · ${data.counts.milestones} milestones · ${data.counts.projects} projects`}
        actions={["hr_reviewer", "admin"].includes(me?.role ?? "") && <Button onClick={async () => { try { const r = await post<AnyRec>("/analysis/train", {}); setMsg(r.note); } catch (e) { setErr(e as ApiError); } }}>Retrain models</Button>} />
      {msg && <Notice>{msg}</Notice>}
      <ErrorState error={err} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Best out-of-time model" value={<span className="text-base">{label(v.out_of_time.best_by_mae)}</span>} hint={`cutoff ${v.out_of_time.cutoff}`} />
        <Stat label="Leakage checks" value={`${v.leakage_checks.filter((c: AnyRec) => c.passed).length}/${v.leakage_checks.length}`} hint="passed" />
        <Stat label="Brier score" value={num(v.calibration.brier, 3)} hint={`climatology ${num(v.calibration.brier_climatology, 3)}`} />
        <Stat label="Abstentions" value={data.conclusion_counts.insufficient_evidence ?? 0} hint="employees with insufficient evidence" />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Baseline model comparison (out-of-time)" subtitle={`Train ≤ ${v.out_of_time.cutoff}, test on the following 6 months (${v.out_of_time.n_test} milestones). Lower MAE is better.`}>
          <Bars data={oot} x="model" series={[{ key: "mae", label: "MAE (pp)" }]} layout="vertical" height={240} />
        </Card>
        <Card title="Calibration" subtitle={`${v.calibration.event}; ECE ${num(v.calibration.expected_calibration_error, 3)}`}>
          <TrendLines data={rel} x="bin" series={[{ key: "predicted", label: "Predicted %" }, { key: "observed", label: "Observed %" }]} height={240} />
        </Card>
        <Card title="Leakage checks">
          <ul className="space-y-2 text-sm">{v.leakage_checks.map((c: AnyRec) => <li key={c.check} className="flex gap-2"><Badge tone={c.passed ? "good" : "critical"}>{c.passed ? "● pass" : "■ fail"}</Badge><span>{c.check}<span className="block text-xs text-muted">{String(c.detail)}</span></span></li>)}</ul>
        </Card>
        <Card title="Cross-validation & bootstrap">
          <Table head={["Model", "MAE (mean ± sd)", "Folds"]} rows={Object.entries(v.cross_validation as Record<string, AnyRec>).map(([k, c]) => [label(k), `${num(c.mae_mean, 2)} ± ${num(c.mae_sd, 2)}`, c.folds])} />
          <p className="mt-2 text-sm">Cluster bootstrap ({v.bootstrap.n_boot} resamples over projects): median interval width {num(v.bootstrap.median_boot_ci_width)} pp; {pct(v.bootstrap.direction_agreement_with_mixed_intervals)} agreement with mixed-model intervals on direction of evidence.</p>
        </Card>
        <Card title="Sensitivity analysis">
          <Table head={["Specification", "Spearman ρ", "Conclusions changed"]} rows={Object.entries(v.sensitivity as Record<string, AnyRec>).map(([k, s]) => [label(k), num(s.spearman_with_base, 3), s.share_conclusions_changed === null ? "—" : pct(s.share_conclusions_changed, 1)])} />
        </Card>
        <Card title="Data drift (train vs test period)">
          <Table head={["Feature", "Train mean", "Test mean", "PSI", "Status"]} rows={v.drift.map((d: AnyRec) => [label(d.feature), num(d.train_mean, 2), num(d.test_mean, 2), num(d.psi, 3), <Badge key="s" tone={d.status === "stable" ? "neutral" : "warn"}>{label(d.status)}</Badge>])} />
        </Card>
        <Card title="Missing-data diagnostics">
          <p className="text-sm">{v.missing_data.interpretation}</p>
          <Table head={["Environment", "Quality score missing"]} rows={Object.entries(v.missing_data.quality_missing_by_environment as Record<string, number>).map(([k, x]) => [label(k), pct(x, 1)])} />
          <p className="mt-2 text-xs text-muted">{v.missing_data.employees_below_min_evidence} employees below the minimum evidence threshold; {v.missing_data.projects_without_stakeholder_feedback} projects without stakeholder feedback.</p>
        </Card>
        <Card title="Prediction-error analysis" subtitle="Out-of-time absolute error of the context model, by group">
          <Bars data={v.prediction_error.technical_complexity.map((r: AnyRec) => ({ group: `Complexity ${r.group}`, mae: Math.round(r.mae * 10) / 10 }))} x="group" series={[{ key: "mae", label: "MAE (pp)" }]} height={200} />
          <Table head={["Environment", "MAE", "Mean error", "n"]} rows={v.prediction_error.environment.map((r: AnyRec) => [label(r.group), num(r.mae), num(r.mean_error), r.n])} />
        </Card>
        <Card title="Historical ratings as biased labels" subtitle="Spearman correlations (synthetic)">
          {data.label_audit && <Table head={["Relationship", "ρ"]} rows={[
            ["Manager rating ↔ raw outcomes", num(data.label_audit.rating_vs_raw_outcome_spearman, 2)],
            ["Manager rating ↔ context-adjusted evidence", num(data.label_audit.rating_vs_adjusted_estimate_spearman, 2)],
            ["Manager rating ↔ meeting volume", num(data.label_audit.rating_vs_meeting_volume_spearman, 2)],
            ["Adjusted evidence ↔ meeting volume", num(data.label_audit.adjusted_estimate_vs_meeting_volume_spearman, 2)],
          ]} />}
          <p className="mt-2 text-xs text-muted">{data.label_audit?.interpretation}</p>
        </Card>
        <Card title="Fairness audit (aggregated)" subtitle="Protected attributes never enter individual estimates">
          {typeof fair === "string" ? <Notice>{fair}</Notice> : fair ? (
            <div className="space-y-2 text-sm">
              <Table head={["Group", "n", "Mean rating", "Promotion rate", "Mean adjusted evidence"]} rows={fair.groups.map((g: AnyRec) => [g.group, g.n, num(g.mean_rating, 2), pct(g.promotion_rate), num(g.mean_adjusted_estimate, 2)])} />
              {Object.entries(fair.gaps as Record<string, AnyRec>).map(([k, g]) => <div key={k} className="text-xs">{label(k)} gap ({g.comparison}): {num(g.difference, 2)} [95% {num(g.ci_low, 2)}, {num(g.ci_high, 2)}]</div>)}
              <p className="font-medium">{fair.finding}</p>
              <p className="text-xs text-muted">{fair.governance} Minimum cell size {fair.min_cell_size}.</p>
              {fair.extended && <ExtendedFairness ext={fair.extended} />}
            </div>
          ) : <Notice>No fairness audit in this run.</Notice>}
        </Card>
        {se && (
          <Card title="Synthetic ground-truth recovery" subtitle="Evaluation only — possible because the data is synthetic; hidden parameters never enter training" className="lg:col-span-2">
            <div className="grid gap-3 md:grid-cols-4">
              <Stat label="Adjusted ↔ truth" value={num(se.spearman_truth_vs_adjusted, 2)} hint="Spearman ρ" />
              <Stat label="Raw ↔ truth" value={num(se.spearman_truth_vs_raw, 2)} />
              <Stat label="Manager rating ↔ truth" value={num(se.spearman_truth_vs_manager_rating, 2)} />
              <Stat label="Interval coverage" value={pct(se.interval_coverage_of_true_effect)} hint={`${se.n_strong_conclusions} strong conclusions, ${pct(se.directional_accuracy_of_strong_conclusions)} correct direction`} />
            </div>
          </Card>
        )}
        <Card title="Model card" className="lg:col-span-2"><Markdown text={data.model_card} /></Card>
        <Card title="Model runs (versioned)" className="lg:col-span-2">
          <Table head={["Version", "Created", "Data", "Best model", "Artifacts"]} rows={(runs.data ?? []).map((r) => [<code key="v" className="text-xs">{r.id}</code>, String(r.created_at).slice(0, 19), <code key="d" className="text-xs">{r.data_hash}</code>, label(r.best_model), <span key="a" className="text-xs text-muted">{r.artifact_path}</span>])} />
        </Card>
      </div>
    </div>
  );
}

const EXT_LABEL: Record<string, string> = {
  mean_complexity: "Mean project complexity", difficult_share: "Share of milestones on the most complex projects",
  mean_resource_constraint: "Mean resource shortfall", mean_dependencies: "Mean dependencies",
  abstained: "Share with no conclusion (insufficient evidence)", settled_milestones: "Settled milestones per person",
  quality_missing_share: "Share of quality scores missing", mean_abs_residual: "Context-model error (mean |residual|, pp)",
  interval_width: "Width of 95% interval (pp)",
};

function ExtendedFairness({ ext }: { ext: AnyRec }) {
  if (ext.suppressed) return <Notice>{ext.suppressed}</Notice>;
  const sections: [string, string][] = [["opportunity", "Unequal opportunity — assignment of conditions"], ["missing_evidence", "Missing evidence"], ["model_error", "Model error by group"]];
  const groups = Object.keys(ext.groups);
  return (
    <div className="mt-3 space-y-3 border-t border-line pt-3">
      {sections.map(([k, title]) => (
        <div key={k}>
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted">{title}</h3>
          <Table head={["Measure", ...groups, `Gap (${ext.comparison}) [95%]`]} rows={Object.entries(ext[k] as Record<string, AnyRec>).map(([m, v]) => [
            EXT_LABEL[m] ?? label(m), ...groups.map((g) => num(v.means[g], 2)),
            <span key="g">{num(v.difference, 2)} [{num(v.ci_low, 2)}, {num(v.ci_high, 2)}] {v.clear && <Badge tone="warn">▲ clear difference</Badge>}</span>,
          ])} />
        </div>
      ))}
      <p className="font-medium">{ext.finding}</p>
      <p className="text-xs text-muted">{ext.multiple_comparisons}</p>
    </div>
  );
}
