"""Command-line entry points.

    python -m meritvector_api.cli bootstrap        # create schema, load synthetic data, train
    python -m meritvector_api.cli generate --out data/synthetic/export
    python -m meritvector_api.cli train [--tenant synthetic-pmo]
    python -m meritvector_api.cli run-job <name>
    python -m meritvector_api.cli worker [--interval 60]
    python -m meritvector_api.cli serve
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import warnings


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    warnings.filterwarnings("ignore", category=FutureWarning)
    ap = argparse.ArgumentParser(prog="meritvector")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bootstrap")
    b.add_argument("--no-train", action="store_true")
    b.add_argument("--no-sandbox", action="store_true")
    b.add_argument("--n-boot", type=int, default=None)
    g = sub.add_parser("generate")
    g.add_argument("--out", default="data/synthetic/export")
    g.add_argument("--seed", type=int, default=None)
    t = sub.add_parser("train")
    t.add_argument("--tenant", default="synthetic-pmo")
    t.add_argument("--n-boot", type=int, default=None)
    j = sub.add_parser("run-job")
    j.add_argument("name")
    w = sub.add_parser("worker")
    w.add_argument("--interval", type=int, default=60)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container entrypoint
    s.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    from meritvector_api import db as dbm

    if args.cmd == "generate":
        from meritvector_analytics.synthetic import SyntheticConfig, generate

        cfg = SyntheticConfig(seed=args.seed) if args.seed is not None else SyntheticConfig()
        ds = generate(cfg)
        out = ds.write(args.out)
        print(json.dumps({"written_to": str(out), **ds.metadata}, indent=2, default=str))
        return
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("meritvector_api.main:app", host=args.host, port=args.port)
        return

    dbm.create_all()
    with dbm.session() as db:
        if args.cmd == "bootstrap":
            from meritvector_api.seed import bootstrap

            print(json.dumps(bootstrap(db, train=not args.no_train, sandbox=not args.no_sandbox, n_boot=args.n_boot),
                             indent=2, default=str))
        elif args.cmd == "train":
            from meritvector_api.training import train_tenant

            run = train_tenant(db, args.tenant, n_boot=args.n_boot)
            print(json.dumps({"run": run.id, "artifacts": run.artifact_path}, indent=2))
        elif args.cmd == "run-job":
            from meritvector_api.workflows import register_default_jobs, run_job

            register_default_jobs(db)
            r = run_job(db, args.name)
            print(json.dumps({"job": r.job_name, "status": r.status, "detail": r.detail}, indent=2, default=str))
        elif args.cmd == "worker":
            from meritvector_api.workflows import register_default_jobs, run_due_jobs

            register_default_jobs(db)
            logging.getLogger("meritvector.worker").info("worker started; polling every %ss", args.interval)
            while True:
                for r in run_due_jobs(db):
                    logging.getLogger("meritvector.worker").info("job %s -> %s", r.job_name, r.status)
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
