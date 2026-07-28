# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Changed

- CLI reads Renovate configuration from a Kubernetes ConfigMap and writes schedule results to a ConfigMap (`OUTPUT_CONFIGMAP`, default: `mintmaker-schedule-calculator-results`).
- `OUTPUT_CONFIGMAP` must match `mintmaker-schedule-calculator(-[a-z0-9]+)?-results`.
- Exit code **1** now covers ConfigMap read/write failures, missing config key, empty results, and invalid `OUTPUT_CONFIGMAP` (not only CronJob fetch failures).

### Removed

- `-c / --config <path>` — use `--configmap` and `--configmap-key` instead.
- Local `.txt` output files — results are written to a Kubernetes ConfigMap.

**Migration:**

```bash
# Before
uv run python -m mintmaker_schedule_calculator -n 5 -c renovate.json

# After
uv run python -m mintmaker_schedule_calculator -n 5 --configmap renovate-config --configmap-key renovate.json
```
