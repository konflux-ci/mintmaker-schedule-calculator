from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

from mintmaker_schedule_calculator import k8s


class TestLoadKubeClient:
    @patch.object(k8s.client, "BatchV1Api")
    @patch.object(k8s.client, "CoreV1Api")
    @patch.object(k8s.config, "load_kube_config")
    @patch.object(
        k8s.config, "load_incluster_config", side_effect=ConfigException("no cluster")
    )
    def test_loads_config_and_returns_clients(
        self, mock_incluster, mock_kubeconfig, mock_core, mock_batch
    ):
        core = MagicMock()
        batch = MagicMock()
        mock_core.return_value = core
        mock_batch.return_value = batch

        core_api, batch_api = k8s.load_kube_client()

        mock_incluster.assert_called_once()
        mock_kubeconfig.assert_called_once()
        assert core_api is core
        assert batch_api is batch

    @patch.object(k8s.client, "BatchV1Api")
    @patch.object(k8s.client, "CoreV1Api")
    @patch.object(k8s.config, "load_kube_config")
    @patch.object(k8s.config, "load_incluster_config")
    def test_uses_incluster_when_available(
        self, mock_incluster, mock_kubeconfig, _mock_core, _mock_batch
    ):
        k8s.load_kube_client()

        mock_incluster.assert_called_once()
        mock_kubeconfig.assert_not_called()


class TestGetCronjobScheduleFromK8s:
    def test_returns_schedule(self):
        api = MagicMock()
        cronjob = MagicMock()
        cronjob.spec.schedule = "0 * * * *"
        api.read_namespaced_cron_job.return_value = cronjob

        result = k8s.get_cronjob_schedule_from_k8s(
            "create-dependencyupdatecheck", "mintmaker", api
        )

        assert result == "0 * * * *"
        api.read_namespaced_cron_job.assert_called_once_with(
            name="create-dependencyupdatecheck", namespace="mintmaker"
        )

    def test_missing_schedule_raises(self):
        api = MagicMock()
        cronjob = MagicMock()
        cronjob.spec.schedule = None
        api.read_namespaced_cron_job.return_value = cronjob

        with pytest.raises(
            ValueError, match="CronJob mintmaker/create-dependencyupdatecheck"
        ):
            k8s.get_cronjob_schedule_from_k8s(
                "create-dependencyupdatecheck", "mintmaker", api
            )

    def test_missing_spec_raises(self):
        api = MagicMock()
        cronjob = MagicMock()
        cronjob.spec = None
        api.read_namespaced_cron_job.return_value = cronjob

        with pytest.raises(ValueError, match="has no schedule"):
            k8s.get_cronjob_schedule_from_k8s(
                "create-dependencyupdatecheck", "mintmaker", api
            )

    def test_api_error_propagates(self):
        api = MagicMock()
        api.read_namespaced_cron_job.side_effect = ApiException(status=404)

        with pytest.raises(ApiException):
            k8s.get_cronjob_schedule_from_k8s("missing", "mintmaker", api)


class TestGetConfigmapFromK8s:
    def test_returns_configmap_data(self):
        api = MagicMock()
        api.read_namespaced_config_map.return_value = MagicMock(
            data={"renovate.json": "{}"}
        )

        result = k8s.get_configmap_from_k8s("renovate-config", "mintmaker", api)

        assert result == {"renovate.json": "{}"}

    def test_empty_configmap_returns_empty_dict(self):
        api = MagicMock()
        api.read_namespaced_config_map.return_value = MagicMock(data=None)

        result = k8s.get_configmap_from_k8s("renovate-config", "mintmaker", api)

        assert result == {}

    def test_api_error_propagates(self):
        api = MagicMock()
        api.read_namespaced_config_map.side_effect = ApiException(status=404)

        with pytest.raises(ApiException):
            k8s.get_configmap_from_k8s("missing", "mintmaker", api)


class TestCreateResultsConfigmap:
    def test_creates_configmap(self):
        api = MagicMock()

        k8s.create_results_configmap(
            "results", "mintmaker", {"general_scheduled_times.txt": "2026-01-01\n"}, api
        )

        api.create_namespaced_config_map.assert_called_once()
        api.replace_namespaced_config_map.assert_not_called()

    def test_replaces_configmap_on_conflict(self):
        api = MagicMock()
        api.create_namespaced_config_map.side_effect = ApiException(status=409)
        data = {"general_scheduled_times.txt": "2026-01-01\n"}

        k8s.create_results_configmap("results", "mintmaker", data, api)

        api.replace_namespaced_config_map.assert_called_once()
        name, namespace, body = api.replace_namespaced_config_map.call_args.args
        assert name == "results"
        assert namespace == "mintmaker"
        assert body.metadata.name == "results"
        assert body.data == data

    def test_create_error_propagates(self):
        api = MagicMock()
        api.create_namespaced_config_map.side_effect = ApiException(status=403)

        with pytest.raises(ApiException):
            k8s.create_results_configmap("results", "mintmaker", {}, api)

    def test_replace_error_propagates(self):
        api = MagicMock()
        api.create_namespaced_config_map.side_effect = ApiException(status=409)
        api.replace_namespaced_config_map.side_effect = ApiException(status=500)

        with pytest.raises(ApiException):
            k8s.create_results_configmap("results", "mintmaker", {}, api)
