# Mintmaker schedule calculator

This repo contains the backend side of MintMaker's schedule timers in the UI.

### What it does
This module fetches CronJob schedules from OpenShift clusters and reads
Renovate configuration from a Kubernetes ConfigMap. It calculates the
next `n` scheduled runs and writes results to a Kubernetes ConfigMap
(default: `mintmaker-schedule-calculator-results`):
- general schedule to key `general_scheduled_times.txt`
- one key per manager: `<manager>_scheduled_times.txt`

Set the output ConfigMap name with the `OUTPUT_CONFIGMAP` environment variable
(default: `mintmaker-schedule-calculator-results`). The name must match
`mintmaker-schedule-calculator(-[a-z0-9]+)?-results`.

## Requirements

- Python **3.12**
- [`uv`](https://docs.astral.sh/uv/)
- Access to a Kubernetes/OpenShift cluster — needed to read the CronJob schedule, Renovate config, and write results

## Setup (with uv)

From the repo root:

```bash
uv python install 3.12
uv venv --python 3.12
uv sync
```

Verify:

```bash
uv run python -V
```

## Run

The recommended way to run is as a module.

### Basic usage

```bash
uv run python -m mintmaker_schedule_calculator -n 5
```

- `-n / --count`: number of upcoming runs to calculate (default: `5`)
- `--configmap`: ConfigMap containing Renovate config (default: `renovate-config`)
- `--configmap-key`: key in the ConfigMap with the Renovate JSON (default: `renovate.json`)
- `--cronjob-name`: CronJob name to read from the cluster (default: `create-dependencyupdatecheck`)
- `--namespace`: Kubernetes namespace (default: `mintmaker`)

To show help/usage hint with options, run:

```bash
uv run python -m mintmaker_schedule_calculator -h
```

### Notes

- By default, the tool reads the CronJob schedule using the Kubernetes Python client ([`kubernetes-client/python`](https://github.com/kubernetes-client/python)).
  - In-cluster: it uses the pod’s service account credentials.
  - Locally: it falls back to your kubeconfig (same cluster/login context you’d use with `kubectl`/`oc`).
- If the output ConfigMap already exists, it is replaced with fresh data.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (including partial manager failures when at least one result was written) |
| `1` | CronJob/ConfigMap fetch failure, missing config key, ConfigMap write failure, empty results, invalid `OUTPUT_CONFIGMAP`, or other uncaught errors |

## Development

To work on this project locally:

1. Complete [Setup (with uv)](#setup-with-uv) above.
2. Edit code under `src/mintmaker_schedule_calculator/` (CLI entry point: `cli.py`, cluster access: `k8s.py`).
3. Run the tool as in [Run](#run) to verify changes. For cluster-backed behavior, use a kubeconfig pointed at a cluster where the mintmaker namespace with a CronJob exists.

### Lint

Ruff rules and settings are in [`pyproject.toml`](pyproject.toml) (`[tool.ruff]` / `[tool.ruff.lint]`).

**Commands** (report-only, same as CI):

```bash
uv run ruff format --check src tests
uv run ruff check src tests
```

Auto-fix: `uv run ruff format src tests` and `uv run ruff check --fix src tests`.  
Single file: `uv run ruff check src/mintmaker_schedule_calculator/cli.py`.

**CI**: [`.github/workflows/ruff.yaml`](.github/workflows/ruff.yaml) runs format `--check` and `ruff check` on PRs and pushes to `main` (check name: `Ruff lint check`). [`.github/workflows/fullsend.yaml`](.github/workflows/fullsend.yaml) waits for that check before dispatching.

**Suppression baseline**: no `# noqa` comments and no global `ignore`. Tests allow `S101` via `[tool.ruff.lint.per-file-ignores]` (pytest assertions). Prefer fixing findings; if a new suppression is required, keep it narrow and update this baseline.

Pull requests are reviewed by the owners in [`.github/CODEOWNERS`](.github/CODEOWNERS). CI builds the container image from [`Containerfile`](Containerfile) via Konflux/Tekton on each PR to `main`. See [CHANGELOG.md](CHANGELOG.md) for release notes.
