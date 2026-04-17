import argparse
import json
import logging
import os
from datetime import datetime, timezone

from cron_converter import Cron

from .k8s import (
    get_configmap_from_k8s,
    get_cronjob_schedule_from_k8s,
    create_results_configmap,
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
OUTPUT_CONFIGMAP = os.environ.get(
    "OUTPUT_CONFIGMAP", "mintmaker-schedule-calculator-results"
)


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

    reference = datetime.now(timezone.utc)
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
    configmap_name: str, namespace: str, key: str = "renovate.json"
) -> dict[str, str]:
    try:
        data = get_configmap_from_k8s(configmap_name, namespace)
        if data is None:
            logger.error("Could not fetch ConfigMap %s/%s.", namespace, configmap_name)
            return {}

        if key not in data:
            logger.error(
                "Key '%s' not found in ConfigMap %s/%s.", key, namespace, configmap_name
            )
            return {}

        config = json.loads(data[key])
        managers_with_schedules = find_managers_with_schedules(config)

        if managers_with_schedules:
            logger.info(
                "Found %d manager(s) with schedules.", len(managers_with_schedules)
            )
        else:
            logger.info("No managers with schedules found.")

        return managers_with_schedules
    except Exception as e:
        logger.error("Error parsing renovate config from ConfigMap: %s.", e)
        return {}


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

        logger.info("Processing CronJob schedule...")
        general_schedule = get_cronjob_schedule_from_k8s(
            cronjob_name=args.cronjob_name,
            namespace=args.namespace,
        )
        if not general_schedule:
            return 1

        try:
            result = analyze_cron_schedule(
                general_schedule, general_schedule, args.count
            )
            output["general_scheduled_times.txt"] = format_schedule_times(result)
        except Exception as e:
            logger.error("Failed to process general schedule: %s.", e)

        logger.info("Processing Renovate managers...")
        managers = parse_renovate_config_from_configmap(
            args.configmap, args.namespace, args.configmap_key
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

        if output and not create_results_configmap(
            OUTPUT_CONFIGMAP, args.namespace, output
        ):
            return 1

        logger.info("Schedule analysis complete.")
        return 0
    except Exception as e:
        logger.error("Error while analyzing schedules: %s.", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
