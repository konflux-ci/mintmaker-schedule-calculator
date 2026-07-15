import logging

from kubernetes import client, config  # type: ignore[import-not-found]
from kubernetes.client import BatchV1Api, CoreV1Api  # type: ignore[import-not-found]
from kubernetes.config.config_exception import (  # type: ignore[import-not-found]
    ConfigException,
)

logger = logging.getLogger(__name__)


def load_kube_client() -> tuple[CoreV1Api, BatchV1Api]:
    """
    Load kube config and return configured CoreV1Api and BatchV1Api clients.

    Prefers in-cluster config, falls back to local kubeconfig.
    """
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config.")
    except ConfigException:
        config.load_kube_config()
        logger.info("Loaded kubeconfig from local environment.")

    return client.CoreV1Api(), client.BatchV1Api()


def get_cronjob_schedule_from_k8s(
    cronjob_name: str, namespace: str, api: BatchV1Api
) -> str:
    cronjob = api.read_namespaced_cron_job(name=cronjob_name, namespace=namespace)
    schedule = getattr(getattr(cronjob, "spec", None), "schedule", None)
    if not schedule:
        raise ValueError(f"CronJob {namespace}/{cronjob_name} has no schedule.")
    logger.info("Found schedule: %s.", schedule)
    return schedule


def get_configmap_from_k8s(
    configmap_name: str, namespace: str, api: CoreV1Api
) -> dict[str, str]:
    """Get a ConfigMap and return its data."""
    config_map = api.read_namespaced_config_map(
        name=configmap_name, namespace=namespace
    )
    logger.info("Found ConfigMap: %s/%s.", namespace, configmap_name)
    return config_map.data or {}


def create_results_configmap(
    name: str, namespace: str, data: dict[str, str], api: CoreV1Api
) -> None:
    """Create or replace a ConfigMap with schedule calculation results.

    Creates the ConfigMap on first run. If it already exists (HTTP 409),
    replaces it via replace_namespaced_config_map.
    """
    body = client.V1ConfigMap(metadata=client.V1ObjectMeta(name=name), data=data)

    try:
        api.create_namespaced_config_map(namespace, body)
    except client.exceptions.ApiException as e:
        if e.status != 409:
            raise
        api.replace_namespaced_config_map(name, namespace, body)
