# MeritVector — notes for contributors and AI coding sessions

Evidence-based workforce intelligence MVP. **All data is synthetic.** Decision support only.

## Layout
- `packages/shared` — vocabulary + `EvidenceEvent` schema + `FORBIDDEN_MODEL_COLUMNS`.
- `packages/analytics` — all statistics (pure Python, no DB/LLM). `synthetic.py` generator, `features.py`,
  `descriptive/contextual/longitudinal/competency/validation/experiment/pipeline.py`, `evaluation.py` (only module
  allowed to read hidden ground truth).
- `packages/coordinator` — assistance; must never import `meritvector_analytics`.
- `packages/connectors` — mock integrations; outbound delivery off by default.
- `apps/api` — FastAPI, SQLAlchemy models, RBAC (`security.py`), audit, ingestion, training, workflows, CLI.
- `apps/web` — Next.js App Router + Tailwind + Recharts. Charts only render API data.

## Commands
`pip install -e ".[dev]"` · `pytest` · `ruff check . && ruff format --check .` · `python scripts/check_secrets.py` ·
`python -m meritvector_api.cli bootstrap|train|run-job <name>|worker|serve` ·
`cd apps/web && npm run lint && npm run typecheck && npm test && npm run build` ·
`docker compose up --build` (needs `MV_SECRET_KEY` in `.env`) · `python scripts/build_notebook.py --execute`.

## Rules
- Never let hidden ground truth, protected attributes, historical ratings/promotions or activity counts reach model
  features. Extend `FORBIDDEN_MODEL_COLUMNS` and the leakage checks when adding data.
- No rankings, sorted leaderboards, promotion-readiness or dismissal outputs — anywhere (API or UI).
- Every person-level estimate needs an interval and an abstention path.
- Assessment endpoints must depend on `require_assessment_enabled`; every query must be tenant-scoped; audit
  sensitive reads and all writes.
- Assistance data (transcripts, coordinator tasks) must never become assessment evidence.
- Never present deterministic output as an LLM result; keep `generator`/`disclosure` fields.
- Never commit `.env`, generated data (`data/synthetic/*`) or `artifacts/`.
- Commit as the repository owner: `git config user.name mfadaee && git config user.email 44535855+mfadaee@users.noreply.github.com`.
