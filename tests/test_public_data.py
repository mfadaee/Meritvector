"""Public real-world data: registry integrity, verified download, parsing, decomposition maths and the studies.

The real-data tests need the datasets (python scripts/fetch_public_data.py). Locally they skip when the files are
absent; CI sets MV_REQUIRE_PUBLIC_DATA=1 so a missing dataset fails instead of silently skipping.
"""

from __future__ import annotations

import os
import re
import warnings

import numpy as np
import pandas as pd
import pytest

from meritvector_analytics.public_data import PublicDataUnavailable, parse_arff, registry, sources
from meritvector_analytics.public_data import catalog as src_mod
from meritvector_analytics.public_data.studies import STUDIES, compare_units, shapley_r2, summary

warnings.filterwarnings("ignore")

ARFF = """% comment
@relation demo
@attribute size numeric
@attribute 'kind' {a, b c,d}   % trailing comment
@attribute effort real
@data
10,a,100
?,d,50
3,a,?
"""


def test_arff_parser_handles_nominals_comments_and_missing():
    d = parse_arff(ARFF)
    assert list(d.columns) == ["size", "kind", "effort"]
    assert d["size"].isna().sum() == 1 and d["effort"].isna().sum() == 1
    assert d["kind"].tolist() == ["a", "d", "a"] and d["size"].dtype.kind == "f"


def test_registry_is_pinned_and_documented():
    reg = registry()
    assert re.fullmatch(r"[0-9a-f]{40}", reg["mirror"]["commit"])
    assert reg["mirror"]["commit"] in reg["mirror"]["base_url"]
    for sid, s in reg["sources"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"]), sid
        assert s["origin"] and s["terms"] and s["limitations"], sid
        assert "roles" in s and s["roles"]["outcomes"], sid
    assert set(STUDIES) == set(reg["sources"])


def test_fetch_refuses_a_file_with_the_wrong_checksum(tmp_path, monkeypatch):
    monkeypatch.setenv("MV_PUBLIC_DATA_DIR", str(tmp_path))

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"tampered"

    monkeypatch.setattr(src_mod.urllib.request, "urlopen", lambda *a, **k: Resp())
    with pytest.raises(ValueError, match="checksum mismatch"):
        src_mod.fetch("desharnais")
    assert not any(tmp_path.iterdir())
    with pytest.raises(PublicDataUnavailable):
        src_mod.load("desharnais")


def test_shapley_shares_sum_to_total_r2():
    rng = np.random.default_rng(0)
    d = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300), "c": rng.normal(size=300)})
    d["y"] = 2 * d["a"] + d["b"] + 0.5 * d["a"] * 0 + rng.normal(size=300)
    s = shapley_r2(d, "y", {"A": ["a"], "B": ["b"], "C": ["c"]})
    assert s["A"] + s["B"] + s["C"] == pytest.approx(s["total"])
    assert s["A"] > s["B"] > s["C"] >= -0.01


def test_unit_comparison_removes_a_gap_that_is_pure_context():
    rng = np.random.default_rng(1)
    n = 300
    unit = rng.choice(["U1", "U2", "U3"], n)
    difficulty = rng.normal(size=n) + (unit == "U1") * 1.5  # U1 gets the hard projects
    d = pd.DataFrame({"unit": unit, "difficulty": difficulty})
    d["y"] = 0.6 * d["difficulty"] + rng.normal(scale=0.3, size=n)
    out = compare_units(d, "y", "unit", ["difficulty"], n_boot=50, seed=0)
    rows = {r["unit"]: r for r in out["units"]}
    assert rows["U1"]["raw_difference_pct"] > 40
    lo, hi = rows["U1"]["adjusted_ci95"]
    assert lo < 0 < hi and abs(rows["U1"]["adjusted_difference_pct"]) < 10


def _require_data():
    missing = [k for k, s in sources().items() if not s.available]
    if missing:
        msg = f"public datasets not fetched: {missing} (python scripts/fetch_public_data.py)"
        if os.environ.get("MV_REQUIRE_PUBLIC_DATA") == "1":
            pytest.fail(msg)
        pytest.skip(msg)


@pytest.fixture(scope="module")
def results():
    _require_data()
    return {k: (fn() if k == "china" else fn(n_boot=40)) for k, (_, fn) in STUDIES.items()}


def test_real_datasets_load_with_expected_sizes(results):
    assert results["desharnais"]["n_projects"] == 77
    assert results["nasa93"]["n_projects"] == 93
    assert results["china"]["n_projects"] == 499
    assert 450 <= results["ebspm"]["results"]["log_cost_per_fp"]["n_projects"] <= 492


def test_studies_report_intervals_provenance_and_plain_language(results):
    for k, r in results.items():
        assert r["provenance"]["origin"] and r["provenance"]["terms"], k
        assert isinstance(r["plain_language"], str) and len(r["plain_language"]) > 40, k
        assert r["status"] == "exploratory", k
    dec = results["nasa93"]["variance_decomposition"]
    total = sum(b["share_of_variance"] for b in dec["blocks"].values())
    assert total == pytest.approx(dec["total_r2"], abs=1e-6)
    assert all(b["ci95"] and b["ci95"][0] <= b["ci95"][1] for b in dec["blocks"].values())


def test_context_explains_more_than_team_indicators_on_real_data(results):
    rows = summary(results)["variance_shares"]
    assert len(rows) == 4
    for r in rows:
        assert r["size_and_context_share"] > r["team_or_capability_share"], r["dataset"]


def test_raw_team_effect_shrinks_after_adjustment_in_ebspm(results):
    t = results["ebspm"]["results"]["log_cost_per_fp"]["team_indicators"]["Fixed_experienced_team"]
    assert abs(t["adjusted_pct"]) < abs(t["raw_pct"])
    assert results["ebspm"]["recording_practice"]["never_recorded_by_unit"]


def test_leakage_demonstration_shows_an_illegitimate_gain(results):
    c = results["china"]
    leaky = c["leakage_demonstration"]["models"]["linear_with_duration"]["validation_mae_log"]
    assert leaky < c["models_10_fold"]["linear_context"]["validation_mae_log"]


def test_no_unit_comparison_is_presented_as_a_ranking(results):
    units = results["ebspm"]["results"]["log_cost_per_fp"]["unit_comparison"]
    assert [u["unit"] for u in units["units"]] == sorted(u["unit"] for u in units["units"])
    assert "not a ranking" in units["note"]


def test_public_data_workstream_runs_through_the_lab_api(api_client):
    import time

    from conftest import login

    _require_data()
    h = login(api_client, "u-SYN-RES")
    run = api_client.post("/research/runs", json={"workstream": "public_data", "params": {"study": "desharnais"}}, headers=h).json()
    for _ in range(240):
        r = api_client.get(f"/research/runs/{run['id']}", headers=h).json()
        if r["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)
    assert r["status"] == "completed", r.get("error")
    assert r["result"]["data_source"].startswith("public real-world data")
    assert r["result"]["dataset_checksums"]["desharnais"] == registry()["sources"]["desharnais"]["sha256"]
