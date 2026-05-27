# Mintmaker schedule calculator

This repo contains the backend side of MintMaker's schedule timers in the UI.

### What it does
This module fetches CronJob schedules from OpenShift clusters and parses Renovate configuration to extract manager schedules. It calculates the next `n` scheduled runs and writes results to `.txt` files:
- general schedule to `general_scheduled_times.txt`
- one file per manager to `<manager>_scheduled_times.txt`

## Requirements

- Python **3.12**
- [`uv`](https://docs.astral.sh/uv/)
- Access to a Kubernetes/OpenShift cluster - needed for the tool to fetch the CronJob schedule from the cluster

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
uv run python -m mintmaker_schedule_calculator -n 5 -c renovate.json
```

- `-n / --count`: number of upcoming runs to calculate (default: `5`)
- `-c / --config`: path to a `renovate.json` file (default: `renovate.json`)
- `--cronjob-name`: CronJob name to read from the cluster (default: `create-dependencyupdatecheck`)
- `--namespace`: Kubernetes namespace for the CronJob (default: `mintmaker`)

To show help/usage hint with options, run:

```bash
uv run python -m mintmaker_schedule_calculator -h
```

### Notes

- By default, the tool reads the CronJob schedule using the Kubernetes Python client ([`kubernetes-client/python`](https://github.com/kubernetes-client/python)).
  - In-cluster: it uses the pod’s service account credentials.
  - Locally: it falls back to your kubeconfig (same cluster/login context you’d use with `kubectl`/`oc`).

## Development

To work on this project locally:

1. Complete [Setup (with uv)](#setup-with-uv) above.
2. Edit code under `src/mintmaker_schedule_calculator/` (CLI entry point: `cli.py`, cluster access: `k8s.py`).
3. Run the tool as in [Run](#run) to verify changes. For cluster-backed behavior, use a kubeconfig pointed at a cluster where the mintmaker namespace with a CronJob exists.

Pull requests are reviewed by the owners in [`.github/CODEOWNERS`](.github/CODEOWNERS). CI builds the container image from [`Containerfile`](Containerfile) via Konflux/Tekton on each PR to `main`.
