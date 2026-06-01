---
name: local-run-debug
description: >-
  Run and debug mintmaker-schedule-calculator locally or in-cluster: uv setup, CLI flags, kubeconfig/CronJob, checks, log patterns, exit codes, and output files. Use when running the tool locally, debugging schedule output, or investigating a failing pod.
---

# Local run & debug

## Setup

From repo root (see [README.md](../../README.md#setup-with-uv)):

```bash
uv python install 3.12
uv venv --python 3.12
uv sync
```

## Run locally

```bash
uv run python -m mintmaker_schedule_calculator -n 5 -c skills/local-run-debug/assets/renovate.json
```

| Flag | Default | Purpose |
|------|---------|---------|
| `-n` / `--count` | `5` | Number of upcoming runs per schedule |
| `-c` / `--config` | `renovate.json` | Renovate config path |
| `--cronjob-name` | `create-dependencyupdatecheck` | CronJob to read |
| `--namespace` | `mintmaker` | CronJob namespace |

Help: `uv run python -m mintmaker_schedule_calculator -h`

**Cluster auth:** uses in-cluster SA in a pod; locally uses kubeconfig (`oc`/`kubectl` context). No extra env vars. When no `kubectl` context is available, ask user to provide one (either local `minikube`/`kind` cluster or log in to a remote cluster). Do not attempt to solve this without user input.

**Config file**: `skills/local-run-debug/assets/renovate.json` — cron expressions in `schedule[0]` for each manager. Use this for testing unless instructed otherwise.

## Preflight (cluster)

Confirm context before running:

```bash
kubectl config current-context
```

Wrong context, missing CronJob, or RBAC errors → tool exits **1** and logs from `k8s.py`.

## Outputs

Writes UTC ISO timestamps (gitignored `*.txt`):

- `general_scheduled_times.txt` — cluster CronJob schedule only
- `<manager>_scheduled_times.txt` — per Renovate manager (`.` and `-` in names → `_`)

Empty file + `No intersection` / `no overlap` warnings → Renovate manager schedule does not align with the CronJob; not a crash.

Check the run times. Compare them to the Cron schedules they were discovered from. Report on correctness of the results.

## Exit codes

| Code | Meaning |
|------|---------|
| `1` | CronJob schedule could not be loaded |
| `0` | Finished (including partial manager failures logged as errors) |

Do not “fix” exit codes unless explicitly requested.

## Debug checklist

1. **CronJob fetch** — search logs for `Loaded kubeconfig` / `Loaded in-cluster`, `Found schedule:`, or `Error fetching CronJob`.
2. **Renovate config** — `enabledManagers` entries need a matching top-level block with `schedule: ["<cron>", …]`. The tool uses **`schedule[0]` only** — it must be a cron expression, not Renovate natural language (e.g. `"before 6am every weekday"`).
3. **Cron format** — `Invalid cron string format` on a manager → `schedule[0]` is not valid cron; empty `<manager>_scheduled_times.txt`. Not a crash (exit **0**).
4. **Merged schedule** — look for `Merged schedule:`; missing → schedules never align.
5. **Writes** — `Results written to` or `Could not write to file`.

Successful manager run (after general schedule): `Found manager '…' with schedule:`, then `Merged schedule:`, then `Results written to <manager>_scheduled_times.txt`.

Logging is fixed at **INFO** (`cli.py`); there is no log-level flag.

## Container smoke test

```bash
podman build -f Containerfile -t mintmaker-schedule-calculator .
podman run --rm -v "$HOME/.kube:/.kube:ro" -e KUBECONFIG=/.kube/config \
  -v "$(pwd)/skills/local-run-debug/assets/renovate.json:/opt/app-root/src/renovate.json:ro" \
  mintmaker-schedule-calculator -n 3 -c renovate.json
```

Adjust kubeconfig mount and `renovate.json` path for your environment.
