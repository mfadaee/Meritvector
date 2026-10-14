"""Run the flagship study end to end and write its research report.

python scripts/run_flagship.py [--n-boot 200] [--no-public]

Writes artifacts/flagship/flagship_v2.json (not committed) and docs/research/FLAGSHIP_REPORT.md.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--no-public", action="store_true", help="skip the real-data replication")
    args = ap.parse_args()
    warnings.filterwarnings("ignore")

    from meritvector_analytics import __version__
    from meritvector_analytics.evaluation import flagship_truth_check
    from meritvector_analytics.flagship import render_report, run_flagship
    from meritvector_analytics.pipeline import run_pipeline
    from meritvector_analytics.synthetic import generate

    ds = generate()
    result = run_pipeline(
        ds.events,
        ds.employees,
        str(ds.config.as_of),
        manager_ratings=ds.manager_ratings,
        promotions=ds.promotions,
        protected_attributes=ds.protected_attributes,
        n_boot=args.n_boot,
    )
    f = run_flagship(result, ds.manager_ratings)
    truth = flagship_truth_check(result, f, ds.ground_truth)

    real = None
    if not args.no_public:
        from meritvector_analytics.public_data import sources
        from meritvector_analytics.public_data.studies import desharnais, ebspm

        if all(s.available for k, s in sources().items() if k in ("ebspm", "desharnais")):
            e, d = ebspm(n_boot=args.n_boot), desharnais(n_boot=args.n_boot * 5)
            real = {"EBSPM (488 real projects, 3 organisations)": e["plain_language"], "Desharnais (77 real projects)": d["plain_language"]}
        else:
            print("public datasets not fetched — skipping the real-data replication (python scripts/fetch_public_data.py)")

    meta = {"seed": ds.config.seed, "analytics": __version__, "data fingerprint": result.data_hash[:12], "bootstrap resamples": args.n_boot}
    public = {k: v for k, v in f.items() if not k.startswith("_")}
    out = ROOT / "artifacts" / "flagship"
    out.mkdir(parents=True, exist_ok=True)
    (out / "flagship_v2.json").write_text(
        json.dumps({**public, "truth_check": truth, "real_world": real, "meta": meta}, indent=2, default=str)
    )
    report = ROOT / "docs" / "research" / "FLAGSHIP_REPORT.md"
    report.write_text(render_report(f, truth, real, meta))
    print(f"wrote {report} and {out / 'flagship_v2.json'}")


if __name__ == "__main__":
    main()
