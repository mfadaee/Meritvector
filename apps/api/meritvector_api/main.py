"""FastAPI application."""

from __future__ import annotations

import logging
import os
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from meritvector_api import __version__
from meritvector_api import db as dbm
from meritvector_api.routers import admin, analysis, auth, coordinator, employees, evidence, portfolio, research, workspace
from meritvector_api.settings import get_settings

warnings.filterwarnings("ignore", category=FutureWarning)
log = logging.getLogger("meritvector")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="MeritVector API",
        version=__version__,
        description="Workforce intelligence MVP. All bundled data is synthetic. Decision support only — "
        "no automated employment decisions, no rankings.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(s.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for r in (auth, workspace, coordinator, portfolio, evidence, employees, analysis, admin, research):
        app.include_router(r.router)

    @app.on_event("startup")
    def _startup() -> None:
        dbm.configure()
        dbm.create_all()
        if os.getenv("MV_AUTO_BOOTSTRAP", "false").lower() == "true":
            from meritvector_api.seed import bootstrap

            with dbm.session() as db:
                log.info("auto-bootstrap: %s", bootstrap(db))

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "synthetic_data_only": True,
            "llm_provider": os.getenv("MV_LLM_PROVIDER", "deterministic"),
        }

    return app


app = create_app()
