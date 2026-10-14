"""Registry, download and parsing of public real-world project datasets (config/public_data/sources.yaml)."""

from __future__ import annotations

import hashlib
import io
import os
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from meritvector_analytics.measurement import config_dir


class PublicDataUnavailable(RuntimeError):
    """Raised when a dataset has not been fetched (run scripts/fetch_public_data.py)."""


def registry() -> dict[str, Any]:
    return yaml.safe_load((config_dir() / "public_data" / "sources.yaml").read_text())


def cache_dir() -> Path:
    env = os.environ.get("MV_PUBLIC_DATA_DIR")
    if env:
        return Path(env)
    return config_dir().parent / "data" / "public"


@dataclass(frozen=True)
class Source:
    id: str
    spec: dict[str, Any]
    base_url: str

    @property
    def url(self) -> str:
        return f"{self.base_url}/{self.spec['file']}"

    @property
    def path(self) -> Path:
        return cache_dir() / self.spec["file"]

    @property
    def available(self) -> bool:
        return self.path.exists() and sha256(self.path.read_bytes()) == self.spec["sha256"]


def sources() -> dict[str, Source]:
    reg = registry()
    return {k: Source(k, v, reg["mirror"]["base_url"]) for k, v in reg["sources"].items()}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(source_id: str, timeout: int = 60) -> Path:
    """Download one dataset from the pinned mirror and verify its checksum before caching it."""
    src = sources()[source_id]
    if src.available:
        return src.path
    with urllib.request.urlopen(src.url, timeout=timeout) as r:  # noqa: S310 - fixed https URL from the registry
        data = r.read()
    digest = sha256(data)
    if digest != src.spec["sha256"]:
        raise ValueError(f"{source_id}: checksum mismatch ({digest}); refusing to cache")
    src.path.parent.mkdir(parents=True, exist_ok=True)
    src.path.write_bytes(data)
    return src.path


# ------------------------------------------------------------------ parsing
def parse_arff(text: str) -> pd.DataFrame:
    """Minimal ARFF reader: numeric and nominal attributes, '%' comments, '?' as missing."""
    names: list[str] = []
    kinds: list[str] = []
    rows: list[list[str]] = []
    in_data = False
    for raw in text.splitlines():
        line = raw.split("%", 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if not in_data and low.startswith("@attribute"):
            rest = line[len("@attribute") :].strip()
            name, _, typ = rest.partition(" ") if not rest.startswith(("'", '"')) else _quoted(rest)
            names.append(name.strip("'\""))
            kinds.append("nominal" if typ.strip().startswith("{") else "numeric")
        elif low.startswith("@data"):
            in_data = True
        elif in_data:
            rows.append([c.strip().strip("'\"") for c in line.split(",")])
    df = pd.DataFrame(rows, columns=names).replace("?", np.nan)
    for n, k in zip(names, kinds, strict=True):
        if k == "numeric":
            df[n] = pd.to_numeric(df[n], errors="coerce")
    return df


def _quoted(rest: str) -> tuple[str, str, str]:
    q = rest[0]
    end = rest.index(q, 1)
    return rest[1:end], " ", rest[end + 1 :]


def load(source_id: str) -> pd.DataFrame:
    src = sources()[source_id]
    if not src.available:
        raise PublicDataUnavailable(f"{source_id} not fetched — run `python scripts/fetch_public_data.py`")
    raw = src.path.read_bytes()
    if src.spec["file"].endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            body = z.read(src.spec["member"])
        return pd.read_csv(io.BytesIO(body), sep=";", encoding="cp1252", decimal=",", thousands=".")
    return parse_arff(raw.decode("utf-8", errors="replace"))
