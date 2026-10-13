"""Shared fixtures. API tests run against a temporary SQLite database with a small synthetic org."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")

_TMP = Path(os.environ.get("MV_TEST_TMP", "/tmp/meritvector-tests"))
_TMP.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MV_SECRET_KEY", "test-secret-not-for-production")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'api-test.db'}"
os.environ["MV_DATA_DIR"] = str(_TMP / "data")
os.environ["MV_ARTIFACT_DIR"] = str(_TMP / "models")
os.environ["MV_DEMO_AUTH"] = "true"

from meritvector_analytics.synthetic import SyntheticConfig, generate  # noqa: E402

SMALL = SyntheticConfig(seed=11, n_program_managers=4, n_project_managers=30, n_technical_pms=10)


@pytest.fixture(scope="session")
def small_dataset():
    return generate(SMALL)


@pytest.fixture(scope="session")
def full_dataset():
    return generate()


@pytest.fixture(scope="session")
def small_result(small_dataset):
    from meritvector_analytics.pipeline import run_pipeline

    d = small_dataset
    return run_pipeline(
        d.events,
        d.employees,
        str(d.config.as_of),
        manager_ratings=d.manager_ratings,
        promotions=d.promotions,
        protected_attributes=d.protected_attributes,
        n_boot=30,
    )


@pytest.fixture(scope="session")
def api_client():
    db_path = _TMP / "api-test.db"
    if db_path.exists():
        db_path.unlink()
    from fastapi.testclient import TestClient

    from meritvector_api import db as dbm
    from meritvector_api.main import app
    from meritvector_api.seed import bootstrap

    dbm.configure(os.environ["DATABASE_URL"])
    dbm.create_all()
    with dbm.session() as s:
        bootstrap(s, config=SMALL, n_boot=20)
    with TestClient(app) as c:
        yield c


def login(client, user_id: str) -> dict[str, str]:
    r = client.post("/auth/demo-login", json={"user_id": user_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
