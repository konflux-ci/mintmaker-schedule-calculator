# AGENTS.md

## Project overview

Backend for MintMaker UI schedule timers. The tool reads a Cron schedule from cluster and a Renovate configuration file and returns `.txt` files with list of `n` future runs. 

Stack: Python, uv, Containerfile
Docs: root [README.md](README.md)

## Architecture

`DUC (a K8s/OpenShift resource) → pod → __main__.py → cli.main()` → `*.txt` ([output filenames](README.md#what-it-does))

- **`k8s.py`**: CronJob schedule via Kubernetes client ([Notes](README.md#notes) — in-cluster vs kubeconfig).
- **`cli.py`**: argparse ([CLI flags](README.md#basic-usage)), `merge_cron_schedules` + `cron-converter`, Renovate `enabledManagers` + `schedule[0]`, file writes.
- **Alignment**: no field overlap → empty runs, warning; exit **1** only if CronJob schedule cannot be loaded; partial manager failures exit **0** with errors logged (keep unless told otherwise).

## Commands

This project uses `uv` for development. Follow setup in [Setup (with uv)](README.md#setup-with-uv).

- **Help**: `uv run python -m mintmaker_schedule_calculator -h`
- **Run**: `uv run python -m mintmaker_schedule_calculator -n 5 -c renovate.json` - see [Basic Usage](README.md#basic-usage) for flags explained
- **Lint check**: `uv run ruff check src` (single file - `uv run ruff check src/mintmaker_schedule_calculator/cli.py`)
- **Quick type check**: `uv run --with pyright pyright src/mintmaker_schedule_calculator`
- **Build image**: `podman/docker build -f Containerfile -t mintmaker-schedule-calculator .`

## Conventions

- **Edits**: Target minimal diff. Files to edit: `k8s.py` (cluster I/O), `cli.py` (cron/Renovate/output). Use `snake_case` naming. Use `logger` (no `print`) when the output is important.
- **Tests**: Add or update tests for behavior changes.
- **Documentation**: Update the corresponding parts of documentation (root README.md) to reflect changes made when applicable.
- **Imports & deps**: Stdlib → third-party → local (`isort` via ruff `I`); fix with `uv run ruff check --fix src`. Add packages in `pyproject.toml` (`dependencies` or `[dependency-groups] dev`), then `uv lock` and `uv sync`. After pulling lockfile changes, run `uv sync`.
- **Dependencies**: [Requirements](README.md#requirements) + `pyproject.toml` / `uv lock`.
- **Outputs**: General schedule to `general_scheduled_times.txt` and one file per manager to `<manager>_scheduled_times.txt`. Output files `*.txt` gitignored. Sanitize manager names (`.` `-` → `_`).
- **Commits**: Do not commit unless asked. Do not commit secrets, `.env`, or generated txt. Use conventional commits (e.g., `feat:`, `fix:`, `chore:`). Explain what and why was changed in the commit message.
- **PRs**: Target `main` branch.
- **Avoid**: drive-by refactors, exit-code “fixes”.
