export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(digits);

export const signed = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;

export const date = (v: string | null | undefined) => (v ? String(v).slice(0, 10) : "—");

export const label = (s: string | null | undefined) =>
  s ? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "—";

export const CONCLUSION_TEXT: Record<string, string> = {
  above_context_expectation: "Above context expectation",
  within_expected_range: "Within expected range",
  below_context_expectation: "Below context expectation — review context first",
  insufficient_evidence: "Insufficient evidence — no conclusion",
};

export const TREND_TEXT: Record<string, string> = {
  sustained_improvement: "Sustained improvement",
  requires_investigation: "Area requiring investigation",
  no_detectable_change: "No detectable change",
  insufficient_history: "Insufficient historical data",
};
