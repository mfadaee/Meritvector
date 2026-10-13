"""Model registry specification (VALIDITY_FRAMEWORK): no model is registered without answering every question."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    research_question: str = Field(min_length=10)
    target_variable: str = Field(min_length=5)
    target_definition: str = Field(min_length=10)
    data_sources: list[str] = Field(min_length=1)
    analysis_type: Literal["descriptive", "predictive", "causal"]
    assumptions: list[str] = Field(min_length=1)
    baseline: str = Field(min_length=5)
    evaluation_metrics: list[str] = Field(min_length=1)
    leakage_controls: list[str] = Field(min_length=1)
    stability_evidence: str = Field(min_length=5)
    remaining_uncertainty: str = Field(min_length=5)
    limitations: list[str] = Field(min_length=1)
    prohibited_uses: list[str] = Field(min_length=1)

    @field_validator("prohibited_uses")
    @classmethod
    def _no_employment_decisions(cls, v: list[str]) -> list[str]:
        text = " ".join(v).lower()
        if not any(w in text for w in ("employment", "promotion", "dismissal", "ranking", "evaluat")):
            raise ValueError("prohibited_uses must explicitly exclude employment decisions about individuals")
        return v


MILESTONE_RISK_SPEC = dict(
    name="milestone_risk_30d",
    research_question="Which milestones due in the next 30 days are at elevated risk of slipping more than 10%?",
    target_variable="label",
    target_definition="Milestone slips more than 10% of its planned interval, or remains unachieved; snapshot 30 days before due.",
    data_sources=["PMO register (projects, milestones, RAID log, dependencies)", "change log"],
    analysis_type="predictive",
    assumptions=["Registers are updated promptly", "Future resembles the recent past (checked by out-of-time test)"],
    baseline="Base rate and the heuristic 'last milestone slipped'",
    evaluation_metrics=["PR-AUC", "precision", "recall", "F1", "Brier", "calibration", "expected cost"],
    leakage_controls=[
        "Point-in-time snapshots",
        "Automated check that every feature timestamp precedes the snapshot",
        "Chronological train/validation/test split",
        "Recent milestones excluded (right-censoring)",
    ],
    stability_evidence="Four model families compared; threshold chosen on a later validation window",
    remaining_uncertainty="Single synthetic organisation; calibration may shift with real data",
    limitations=["Synthetic data", "Project-level only", "Does not explain why a milestone is at risk"],
    prohibited_uses=["Evaluating, ranking or making employment decisions about project managers"],
)

CONTEXT_MODEL_SPEC = dict(
    name="context_adjusted_delivery",
    research_question="How do a person's milestone outcomes compare with what their projects' measured conditions predict?",
    target_variable="schedule_variance_pct",
    target_definition="Milestone slip as % of planned interval, settled milestones only",
    data_sources=["Validated assessment evidence (milestones, kick-off complexity assessments, change log)"],
    analysis_type="descriptive",
    assumptions=["Measured context captures the main confounders", "Linear additive effects", "Approximate normality"],
    baseline="Global mean and context-only OLS (out of time)",
    evaluation_metrics=["Out-of-time MAE/R²", "interval coverage (synthetic)", "sensitivity across specifications"],
    leakage_controls=["Forbidden-column assertion", "Scope changes counted only before the planned date", "Permutation check"],
    stability_evidence="Cluster bootstrap over projects; seven alternative specifications",
    remaining_uncertainty="Unmeasured context and non-random assignment",
    limitations=["Association, not causation", "One facet of contribution"],
    prohibited_uses=["Ranking employees", "Promotion, pay or dismissal decisions without qualified human review"],
)
