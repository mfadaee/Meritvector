"""Loaders for configuration that lives outside the code."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from meritvector_analytics.measurement.spec import JobFamilySpec, Metric, Ontology


def config_dir() -> Path:
    """Resolve the configuration root: MV_CONFIG_DIR, else the nearest ``config/`` above this file or the CWD."""
    env = os.getenv("MV_CONFIG_DIR")
    if env:
        return Path(env)
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for parent in [start, *start.parents]:
            cand = parent / "config" / "job_families"
            if cand.is_dir():
                return parent / "config"
    raise FileNotFoundError("MeritVector config directory not found; set MV_CONFIG_DIR")


def _research_dir() -> Path:
    env = os.getenv("MV_RESEARCH_DIR")
    return Path(env) if env else config_dir().parent / "research"


@lru_cache
def load_ontology() -> Ontology:
    return Ontology.model_validate(yaml.safe_load((config_dir() / "measurement" / "ontology.yaml").read_text()))


@lru_cache
def load_job_family(family_id: str = "pmo") -> JobFamilySpec:
    path = config_dir() / "job_families" / family_id / "family.yaml"
    if not path.exists():
        raise KeyError(f"unknown job family {family_id!r}")
    return JobFamilySpec.model_validate(yaml.safe_load(path.read_text()))


def list_job_families() -> list[dict[str, Any]]:
    out = []
    for p in sorted((config_dir() / "job_families").glob("*/family.yaml")):
        spec = load_job_family(p.parent.name)
        out.append(
            {
                "id": spec.id,
                "name": spec.name,
                "version": spec.version,
                "status": spec.status,
                "metrics": len(spec.metrics),
                "dimensions": len(spec.context_dimensions) + len(spec.responsibility_dimensions) + len(spec.outcome_dimensions),
            }
        )
    return out


def find_metric(metric_id: str, family_id: str = "pmo") -> Metric | None:
    return next((m for m in load_job_family(family_id).metrics if m.id == metric_id), None)


@lru_cache
def load_library() -> dict[str, Any]:
    return json.loads((_research_dir() / "references" / "library.json").read_text())
