# Synthetic data

Generated, never committed. Everything here is **synthetic** — no real people or projects.

* `python -m meritvector_api.cli generate --out data/synthetic/export` writes a full dataset.
* `python -m meritvector_api.cli bootstrap` writes one directory per tenant (`synthetic-pmo/`, `synthetic-sandbox/`)
  and loads it into the database.

Layout of a generated dataset:

| Path | Contents | Who may read it |
|---|---|---|
| `*.csv`, `*.jsonl` | Observable records: employees, projects, milestones, risks, dependencies, evidence events, meetings, historical ratings, promotions | Application |
| `controlled/protected_attributes.csv` | Synthetic protected-group attribute | Aggregated fairness audit only |
| `hidden/ground_truth.csv` | Latent contribution, growth, activity propensity, visibility, archetype, rater leniency | Evaluation harness and tests only — never the database, never model features |
| `metadata.json` | Seed, counts, as-of date | Anyone |

The generator is deterministic for a given seed (default `20261013`).
