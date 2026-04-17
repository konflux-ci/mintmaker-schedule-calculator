import logging
from typing import Literal

logger = logging.getLogger(__name__)


def load_kube_client(api_type: Literal["core", "batch"] = "core"):
    """
    Returns a configured kubernetes API client.

    Args:
        api_type: "core" for CoreV1Api, "batch" for BatchV1Api

    Prefers in-cluster config, falls back to local kubeconfig.
    """
    if api_type not in ("core", "batch"):
        raise ValueError(f"Invalid api_type: {api_type!r}. Expected 'core' or 'batch'.")

    try:
        from kubernetes import client, config  # type: ignore[import-not-found]
        from kubernetes.config.config_exception import (  # type: ignore[import-not-found]
            ConfigException,
        )
    except ImportError as e:
        logger.error("Kubernetes client library is not installed: %s.", e)
        return None

    try:
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config.")
        except ConfigException:
            config.load_kube_config()
            logger.info("Loaded kubeconfig from local environment.")

        if api_type == "batch":
            return client.BatchV1Api()
        return client.CoreV1Api()

    except Exception as e:
        logger.error("Failed to load Kubernetes config: %s.", e)
        return None


def get_cronjob_schedule_from_k8s(cronjob_name: str, namespace: str) -> str | None:
    api = load_kube_client("batch")
    if api is None:
        return None

    try:
        cronjob = api.read_namespaced_cron_job(name=cronjob_name, namespace=namespace)
        schedule = getattr(getattr(cronjob, "spec", None), "schedule", None)
        if not schedule:
            logger.error("CronJob %s/%s has no schedule.", namespace, cronjob_name)
            return None
        logger.info("Found schedule: %s.", schedule)
        return schedule
    except Exception as e:
        logger.error("Error fetching CronJob %s/%s: %s.", namespace, cronjob_name, e)
        return None


def get_configmap_from_k8s(configmap_name: str, namespace: str) -> dict | None:
    """Get a ConfigMap and return its data."""
    api = load_kube_client("core")
    if api is None:
        return None

    try:
        cm = api.read_namespaced_config_map(name=configmap_name, namespace=namespace)
        logger.info("Found ConfigMap: %s/%s.", namespace, configmap_name)
        return cm.data or {}
    except Exception as e:
        logger.error(
            "Error fetching ConfigMap %s/%s: %s.", namespace, configmap_name, e
        )
        return None


def create_results_configmap(name: str, namespace: str, data: dict[str, str]) -> bool:
    """Create or replace a ConfigMap with schedule calculation results.

    Creates the ConfigMap on first run. If it already exists (HTTP 409),
    replaces it atomically via replace_namespaced_config_map.
    """
    from kubernetes import client  # type: ignore[import-not-found]

    api = load_kube_client("core")
    if not api:
        return False

    body = client.V1ConfigMap(metadata=client.V1ObjectMeta(name=name), data=data)

    try:
        api.create_namespaced_config_map(namespace, body)
        return True
    except client.exceptions.ApiException as e:
        if e.status != 409:
            logger.error("Error creating ConfigMap %s/%s: %s.", namespace, name, e)
            return False

    try:
        api.replace_namespaced_config_map(name, namespace, body)
    except client.exceptions.ApiException as e:
        logger.error("Error replacing ConfigMap %s/%s: %s.", namespace, name, e)
        return False
    return True
