# AGENTS.md

## Project overview

Backend for MintMaker UI schedule timers. The tool reads a CronJob schedule and Renovate config from Kubernetes, computes the next `n` aligned run times, and writes results to a ConfigMap.

Stack: Python, uv, Containerfile
Docs: root [README.md](README.md)

## Architecture

Runtime flow (in order):

```
1. DUC (K8s/OpenShift resource) starts the pod
2. pod runs: python -m mintmaker_schedule_calculator  →  __main__.py  →  cli.main()
3. read CronJob schedule from cluster
4. compute next n general runs  →  output["general_scheduled_times.txt"]
5. read ConfigMap renovate-config (--configmap-key)  →  manager schedules
6. for each manager: compute aligned runs  →  output["<manager>_scheduled_times.txt"]
7. write output dict to ConfigMap (OUTPUT_CONFIGMAP, default: mintmaker-schedule-calculator-results)
```

- **`k8s.py`**: Kubernetes client — CronJob read, ConfigMap read/write ([Notes](README.md#notes) — in-cluster vs kubeconfig).
- **`cli.py`**: argparse ([CLI flags](README.md#basic-usage)), `merge_cron_schedules` + `cron-converter`, Renovate `enabledManagers` + `schedule[0]`, builds output dict and calls `create_results_configmap`.
- **Alignment**: no field overlap → empty runs, warning; partial manager failures exit **0** with errors logged (keep unless told otherwise).

## Commands

This project uses `uv` for development. Follow setup in [Setup (with uv)](README.md#setup-with-uv).

- **Help**: `uv run python -m mintmaker_schedule_calculator -h`
- **Run**: `uv run python -m mintmaker_schedule_calculator -n 5` — see [Basic Usage](README.md#basic-usage) for flags
- **Tests**: `uv sync --extra dev && uv run pytest tests/`
- **Lint**: `uv run ruff format src tests && uv run ruff check --fix src tests` (single file: `uv run ruff check --fix path/to/file.py`). CI is report-only (`format --check` / `check`); rules and suppression baseline: [Lint](README.md#lint)
- **Quick type check**: `uv run --with pyright pyright src/mintmaker_schedule_calculator`
- **Build image**: `podman/docker build -f Containerfile -t mintmaker-schedule-calculator .`

## Conventions

- **Edits**: Target minimal diff. Files to edit: `k8s.py` (cluster I/O), `cli.py` (cron/Renovate/output). Use `snake_case` naming. Use `logger` (no `print`) when the output is important.
- **Tests**: Add or update tests for behavior changes.
- **Documentation**: Follow `.cursor/rules/docs-sync.mdc` (always on): after `src/` changes, update docstrings and mapped docs in the same response; user accepts file diffs in Cursor.
- **Imports & deps**: Stdlib → third-party → local (`isort` via ruff `I`); fix with `uv run ruff check --fix src`. Add packages in `pyproject.toml` (`dependencies` or `[dependency-groups] dev`), then `uv lock` and `uv sync`. After pulling lockfile changes, run `uv sync`.
- **Dependencies**: [Requirements](README.md#requirements) + `pyproject.toml` / `uv lock`.
- **Input**: Renovate config from ConfigMap `--configmap` / `--configmap-key` (defaults: `renovate-config`, `renovate.json`).
- **Output**: Results ConfigMap keys `general_scheduled_times.txt` and `<manager>_scheduled_times.txt` (UTC ISO timestamps, newline-separated). Default ConfigMap name: `mintmaker-schedule-calculator-results`; override with `OUTPUT_CONFIGMAP` (must match `mintmaker-schedule-calculator(-[a-z0-9]+)?-results`). Sanitize manager names (`.` `-` → `_`). Existing results ConfigMap is replaced on conflict (409).
- **Exit codes**: **0** on success (including partial manager failures when at least one result was written); **1** on CronJob/ConfigMap fetch failure, missing config key, ConfigMap write failure, empty results (nothing to write), invalid `OUTPUT_CONFIGMAP`, or other uncaught errors in `main()`.
- **Commits**: Do not commit unless asked. Do not commit secrets, `.env`, or local scratch files. Use conventional commits (e.g., `feat:`, `fix:`, `chore:`). Explain what and why was changed in the commit message.
- **PRs**: Target `main` branch.
- **Avoid**: drive-by refactors, exit-code “fixes”.
