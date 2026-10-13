"""Versioned schema for the measurement ontology and job-family specifications."""

from __future__ import annotations

import warnings
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# "construct" is a domain term; it harmlessly shadows pydantic's deprecated BaseModel.construct().
warnings.filterwarnings("ignore", message='Field name "construct"')

SCHEMA_VERSION = "1.0"
CONSTRUCTS = (
    "activity",
    "responsibility",
    "complexity",
    "quality",
    "outcomes",
    "contribution",
    "development",
    "leadership",
    "career_capability_evidence",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Construct(_Strict):
    label: str
    definition: str
    indicators: list[str]
    data_sources: list[str]
    assumptions: list[str]
    reliability: str
    confounders: list[str]
    limitations: list[str]
    intended_use: str
    prohibited_interpretations: list[str]
    may_increase_merit: bool
    evidence_status: Literal["established", "reasonable_hypothesis", "product_assumption"]
    references: list[str] = Field(default_factory=list)


class ConceptualModel(_Strict):
    statement: str
    caveat: str
    references: list[str] = Field(default_factory=list)


class Ontology(_Strict):
    version: str
    conceptual_model: ConceptualModel
    constructs: dict[str, Construct]

    @model_validator(mode="after")
    def _all_constructs(self) -> Ontology:
        missing = set(CONSTRUCTS) - set(self.constructs)
        if missing:
            raise ValueError(f"ontology is missing constructs: {sorted(missing)}")
        if self.constructs["activity"].may_increase_merit:
            raise ValueError("activity must never increase merit")
        return self


class Scale(_Strict):
    type: Literal["ordinal", "continuous", "count", "categorical", "boolean"]
    min: float | None = None
    max: float | None = None
    levels: list[str] | None = None


class Dimension(_Strict):
    id: str
    label: str
    construct: str
    field: str | None
    status: Literal["modelled", "recorded", "planned"]
    source: str | None
    description: str
    scale: Scale | None = None
    direction: Literal["higher_is_better", "lower_is_better", "neutral"] | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Dimension:
        if self.construct not in CONSTRUCTS:
            raise ValueError(f"{self.id}: unknown construct {self.construct}")
        if self.status != "planned" and not self.field:
            raise ValueError(f"{self.id}: a {self.status} dimension needs a data field")
        return self


class Level(_Strict):
    id: str
    label: str


class Role(_Strict):
    id: str
    label: str
    levels: list[Level]


class EvidenceSource(_Strict):
    id: str
    system: str
    data_category: Literal["assessment_evidence", "diagnostic_activity", "org_reporting", "assistance"]
    categories: list[str]


class Metric(_Strict):
    id: str
    label: str
    construct: str
    definition: str
    computation: str
    unit: str
    direction: Literal["higher_is_better", "lower_is_better", "neutral"]
    data_sources: list[str]
    assumptions: list[str]
    limitations: list[str]
    prohibited_interpretations: list[str]
    plain_language: str

    @model_validator(mode="after")
    def _activity_neutral(self) -> Metric:
        if self.construct == "activity" and self.direction != "neutral":
            raise ValueError(f"{self.id}: activity metrics must be direction 'neutral'")
        return self


class Competency(_Strict):
    label: str
    rules: list[str]
    description: str
    opportunity_rule: str | None = None
    perception_based: bool = False


class Competencies(_Strict):
    window_months: int = 12
    note: str = ""
    items: dict[str, Competency]
    levels: dict[str, dict[str, int]]


class ValidationRequirement(_Strict):
    id: str
    description: str
    check: str


class Dashboard(_Strict):
    id: str
    roles: list[str]


class ContextModel(_Strict):
    include_role: bool = True
    time_trend: bool = True


class JobFamilySpec(_Strict):
    schema_version: Literal["1.0"]
    id: str
    name: str
    version: str
    status: Literal["active", "illustrative"]
    description: str
    context_model: ContextModel = Field(default_factory=ContextModel)
    role_taxonomy: list[Role]
    context_dimensions: list[Dimension]
    responsibility_dimensions: list[Dimension]
    outcome_dimensions: list[Dimension]
    evidence_sources: list[EvidenceSource]
    metrics: list[Metric]
    competencies: Competencies
    validation_requirements: list[ValidationRequirement]
    dashboards: list[Dashboard]

    @model_validator(mode="after")
    def _references(self) -> JobFamilySpec:
        levels = {lv.id for r in self.role_taxonomy for lv in r.levels}
        unknown = set(self.competencies.levels) - levels
        if unknown:
            raise ValueError(f"competency levels not in role taxonomy: {sorted(unknown)}")
        for lvl, req in self.competencies.levels.items():
            bad = set(req) - set(self.competencies.items)
            if bad:
                raise ValueError(f"level {lvl} references unknown competencies {sorted(bad)}")
        ids = [d.id for d in self.context_dimensions + self.responsibility_dimensions + self.outcome_dimensions]
        if len(ids) != len(set(ids)):
            raise ValueError("dimension ids must be unique")
        return self

    def modelled_fields(self) -> list[str]:
        return [d.field for d in self.context_dimensions if d.status == "modelled" and d.field]

    def context_covariates(self) -> tuple[list[str], list[str]]:
        """(numeric, categorical) covariates of the context model, in specification order."""
        modelled = [d for d in self.context_dimensions if d.status == "modelled" and d.field]
        numeric = [d.field for d in modelled if d.scale and d.scale.type in ("ordinal", "continuous", "count")]
        categorical = [d.field for d in modelled if d.scale and d.scale.type in ("categorical", "boolean")]
        if self.context_model.include_role:
            categorical.append("job_family")
        return numeric, categorical

    def competency_framework(self) -> dict:
        """The dict format used by meritvector_analytics.competency."""
        c = self.competencies
        return {
            "name": f"{self.name} competency framework",
            "version": self.version,
            "note": c.note,
            "window_months": c.window_months,
            "competencies": {k: v.model_dump(exclude_none=True) for k, v in c.items.items()},
            "levels": c.levels,
        }
