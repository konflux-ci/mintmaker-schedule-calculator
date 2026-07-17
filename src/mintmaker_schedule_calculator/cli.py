import argparse
import json
import logging
import os
import re
from datetime import UTC, datetime

from cron_converter import Cron
from kubernetes.client import CoreV1Api  # type: ignore[import-not-found]

from .k8s import (
    create_results_configmap,
    get_configmap_from_k8s,
    get_cronjob_schedule_from_k8s,
    load_kube_client,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CRONJOB_NAME = "create-dependencyupdatecheck"
CRONJOB_NAMESPACE = "mintmaker"
CONFIGMAP_NAME = "renovate-config"
DEFAULT_OUTPUT_CONFIGMAP = "mintmaker-schedule-calculator-results"
# Allow default or mintmaker-schedule-calculator-<label>-results
OUTPUT_CONFIGMAP_PATTERN = re.compile(
    r"^mintmaker-schedule-calculator(-[a-z0-9]+)?-results$"
)


def get_output_configmap_name() -> str:
    """Return OUTPUT_CONFIGMAP after validating it matches the allowed pattern."""
    name = os.environ.get("OUTPUT_CONFIGMAP", DEFAULT_OUTPUT_CONFIGMAP)
    if not OUTPUT_CONFIGMAP_PATTERN.fullmatch(name):
        raise ValueError(
            f"Invalid OUTPUT_CONFIGMAP '{name}'; must match "
            f"{OUTPUT_CONFIGMAP_PATTERN.pattern}"
        )
    return name


def merge_cron_schedules(
    cron_expression: str, general_schedule_expression: str
) -> Cron | None:
    """Merge two cron expressions by intersecting their fields."""
    cron = Cron()
    cron.from_string(cron_expression)

    if cron_expression == general_schedule_expression:
        return cron

    general_cron = Cron()
    general_cron.from_string(general_schedule_expression)

    cron_list = cron.to_list()
    general_list = general_cron.to_list()

    field_names = ["minutes", "hours", "days of month", "months", "days of week"]
    merged: list[list[int]] = []
    for i in range(len(field_names)):
        intersection = sorted(set(cron_list[i]) & set(general_list[i]))
        if not intersection:
            logger.warning(
                "No intersection in %s field - schedules never align.", field_names[i]
            )
            return None
        merged.append(intersection)

    merged_cron = Cron()
    merged_cron.from_list(merged)
    return merged_cron


def analyze_cron_schedule(
    cron_expression: str, general_schedule_expression: str, number_of_runs: int
) -> list[str]:
    logger.info("Finding next %d aligned runs between schedules.", number_of_runs)

    merged_schedule = merge_cron_schedules(cron_expression, general_schedule_expression)
    if merged_schedule is None:
        logger.warning("Schedules have no overlap - they never align.")
        return []

    logger.info("Merged schedule: %s", merged_schedule.to_string())

    reference = datetime.now(UTC)
    schedule = merged_schedule.schedule(reference)

    next_runs: list[str] = []
    for _ in range(number_of_runs):
        next_runs.append(schedule.next().isoformat(timespec="seconds"))

    return next_runs


def format_schedule_times(next_runs: list[str]) -> str:
    return "\n".join(next_runs) + ("\n" if next_runs else "")


def find_managers_with_schedules(config: dict) -> dict[str, str]:
    managers: dict[str, str] = {}
    enabled_managers = config.get("enabledManagers", [])

    for manager in enabled_managers:
        if manager in config and isinstance(config[manager], dict):
            manager_config = config[manager]
            if "schedule" in manager_config:
                schedule = manager_config["schedule"]
                if isinstance(schedule, list) and schedule:
                    managers[manager] = schedule[0]
                    logger.info(
                        "Found manager '%s' with schedule: %s.", manager, schedule[0]
                    )

    return managers


def parse_renovate_config_from_configmap(
    configmap_name: str, namespace: str, api: CoreV1Api, key: str = "renovate.json"
) -> dict[str, str]:
    data = get_configmap_from_k8s(configmap_name, namespace, api)

    if key not in data:
        raise ValueError(
            f"Key '{key}' not found in ConfigMap {namespace}/{configmap_name}."
        )

    config = json.loads(data[key])
    managers_with_schedules = find_managers_with_schedules(config)

    if managers_with_schedules:
        logger.info("Found %d manager(s) with schedules.", len(managers_with_schedules))
    else:
        logger.info("No managers with schedules found.")

    return managers_with_schedules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mintmaker_schedule_calculator",
        description="Analyze CronJob and Renovate managers schedules.",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=5,
        help="Number of next scheduled runs to calculate (default: 5)",
    )
    parser.add_argument(
        "--configmap",
        type=str,
        default=CONFIGMAP_NAME,
        help=f"ConfigMap name containing renovate.json (default: {CONFIGMAP_NAME})",
    )
    parser.add_argument(
        "--configmap-key",
        type=str,
        default="renovate.json",
        help="Key in ConfigMap containing the config (default: renovate.json)",
    )
    parser.add_argument(
        "--cronjob-name",
        type=str,
        default=CRONJOB_NAME,
        help=f"CronJob name to read from the cluster (default: {CRONJOB_NAME})",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=CRONJOB_NAMESPACE,
        help=f"Kubernetes namespace for the CronJob (default: {CRONJOB_NAMESPACE})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        output: dict[str, str] = {}
        parser = build_parser()
        args = parser.parse_args(argv)
        output_configmap = get_output_configmap_name()

        core_api, batch_api = load_kube_client()

        logger.info("Processing CronJob schedule...")
        general_schedule = get_cronjob_schedule_from_k8s(
            cronjob_name=args.cronjob_name,
            namespace=args.namespace,
            api=batch_api,
        )

        try:
            result = analyze_cron_schedule(
                general_schedule, general_schedule, args.count
            )
            output["general_scheduled_times.txt"] = format_schedule_times(result)
        except Exception as e:
            logger.error("Failed to process general schedule: %s.", e)

        logger.info("Processing Renovate managers...")
        managers = parse_renovate_config_from_configmap(
            args.configmap, args.namespace, core_api, args.configmap_key
        )

        for manager_name, schedule in managers.items():
            logger.info("Processing manager: %s.", manager_name)

            try:
                result = analyze_cron_schedule(schedule, general_schedule, args.count)
                safe_name = manager_name.replace(".", "_").replace("-", "_")
                filename = f"{safe_name}_scheduled_times.txt"
                output[filename] = format_schedule_times(result)
            except Exception as e:
                logger.error("Failed to process manager '%s': %s.", manager_name, e)

        if not output:
            logger.warning(
                "No schedule results produced; nothing written to ConfigMap."
            )
            return 1

        create_results_configmap(output_configmap, args.namespace, output, core_api)

        logger.info("Schedule analysis complete.")
        return 0
    except Exception as e:
        logger.error("Error while analyzing schedules: %s.", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
