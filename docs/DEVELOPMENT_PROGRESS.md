# Development progress

Checkpoint log for Phase 2 (research-driven talent intelligence). Phase 1 history: [PROGRESS.md](PROGRESS.md).
Each work package is implemented, tested, committed, pushed, merged by pull request and verified on `main`.

| Work package | Content | Branch / PR | Status |
|---|---|---|---|
| Phase 1 | v0.1 MVP | `feature/meritvector-mvp` → [#1](https://github.com/mfadaee/Meritvector/pull/1) | Merged `75e286a` |
| WP-A | Research foundation: evidence library (38 checked sources), ontology (9 constructs), PMO spec (16 context / 10 responsibility / 10 outcome dimensions), illustrative engineering family, versioned schema, registered questions and hypotheses, validity framework, gap analysis, prioritisation | `feature/phase2-research-foundation` → [#2](https://github.com/mfadaee/Meritvector/pull/2) | Merged `20717a9` |
| WP-B | Research engine: 15 workstreams (EDA, hypotheses, regression/generalisation, 30-day risk classifier, clustering, growth, causal DAGs, experiment design), scenarios A–F, within-person (Mundlak) context model, model registry, dataset versions, research API with reproduction | `feature/phase2-research-engine` | In review |
| WP-C | Research Laboratory UI, explanations, evidence chains, retrieval | — | Pending |
| WP-D | Flagship v2, product and commercial docs | — | Pending |

## How to resume
1. `git fetch origin && git checkout main && git pull`.
2. Read this file and [GAP_ANALYSIS](architecture/GAP_ANALYSIS.md) for the next open work package.
3. Run `pytest` and the web checks before changing anything.
