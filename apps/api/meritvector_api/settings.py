"""Runtime configuration from environment variables (see .env.example)."""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    secret_is_ephemeral: bool
    demo_auth_enabled: bool
    artifact_dir: Path
    data_dir: Path
    cors_origins: tuple[str, ...]
    token_ttl_minutes: int
    bootstrap_n_boot: int


@lru_cache
def get_settings() -> Settings:
    secret = os.getenv("MV_SECRET_KEY", "")
    ephemeral = not secret
    if ephemeral:
        # Never ship a hard-coded key. Without configuration, tokens are valid only for this process.
        secret = secrets.token_urlsafe(48)
        log.warning("MV_SECRET_KEY not set — using an ephemeral key; sessions will not survive a restart.")
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{REPO_ROOT / 'artifacts' / 'meritvector.db'}"),
        secret_key=secret,
        secret_is_ephemeral=ephemeral,
        demo_auth_enabled=os.getenv("MV_DEMO_AUTH", "true").lower() == "true",
        artifact_dir=Path(os.getenv("MV_ARTIFACT_DIR", str(REPO_ROOT / "artifacts" / "models"))),
        data_dir=Path(os.getenv("MV_DATA_DIR", str(REPO_ROOT / "data" / "synthetic"))),
        cors_origins=tuple(o.strip() for o in os.getenv("MV_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()),
        token_ttl_minutes=int(os.getenv("MV_TOKEN_TTL_MINUTES", "480")),
        bootstrap_n_boot=int(os.getenv("MV_BOOTSTRAP_N", "200")),
    )
