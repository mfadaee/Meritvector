# Safe scheduled and unattended development

A prompt alone does not create a recurring job. This page describes what runs on a schedule today, and how future
unattended development (an AI coding agent or another bot) can be added without weakening review, security or branch
protection.

## What runs today

| Workflow | Trigger | Token permissions | What it does | What it cannot do |
|---|---|---|---|---|
| `ci.yml` | push to `main` / `feature/**`, pull requests | `contents: read` | lint, secret scan, public-data fetch, tests, notebook execution, web checks, Docker smoke test | push, merge, comment, deploy |
| `research-weekly.yml` | Mondays 03:17 UTC, manual dispatch | `contents: read` | full tests, flagship study, public-data studies; uploads results; flags drift of the committed report in the job summary | push, open PRs, comment, use secrets, deploy, touch real data |

## Rules for any future unattended agent

1. **Branches and PRs only.**
   - The agent works on its own branch (`bot/<topic>`) and opens a pull request.
   - It never pushes to `main`, never force-pushes, and never rewrites history.
2. **Branch protection on `main`** (repository settings; recommended):
   - require pull requests
   - require the `CI` status checks (*Backend, analytics & model validation*, *Frontend checks*, *Docker Compose startup*)
   - require at least one human approving review for any PR opened by a bot
   - dismiss stale approvals on new commits
   - disallow force pushes and deletions
3. **Least-privilege tokens.**
   - Scheduled jobs use `contents: read`.
   - A job that opens PRs gets only `contents: write` and `pull-requests: write`, uses a dedicated GitHub App
     identity, and can be revoked independently.
4. **No secrets in code.**
   - `scripts/check_secrets.py` runs in CI.
   - Credentials live only in repository or environment secrets, and never in workflows triggered by forks.
5. **Data boundaries.**
   - Unattended jobs use synthetic data and the pinned public datasets only.
   - Real tenant or employee data must never be available to CI or agents.
6. **No deployments, purchases, external messaging or surveillance** from scheduled jobs. Each requires separate,
   explicit human authorisation.
7. **History is immutable.** Agents add new dated outputs; they never edit published reports or registered
   hypotheses in place. Report changes go through a PR showing the diff.
8. **Checkpoints.**
   - Every agent run updates [DEVELOPMENT_PROGRESS](../DEVELOPMENT_PROGRESS.md) in its PR, recording what changed,
     test evidence and open issues, so the next run (or a human) can resume.

## Enabling an unattended development agent (when wanted)

1. Install the agent as a GitHub App, with access limited to this repository.
2. Add a workflow with `workflow_dispatch` (and optionally a schedule) that:
   - runs the agent with a written brief that includes these rules
   - lets the agent open a PR from a `bot/` branch, with `contents: write` and `pull-requests: write` only
3. Keep auto-merge **off**. A human reviews and merges once CI is green.
4. Review the run history monthly. Revoke the App if it acts outside these rules.
