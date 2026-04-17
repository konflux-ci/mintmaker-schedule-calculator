from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from mintmaker_schedule_calculator import k8s


class TestLoadKubeClient:
    def test_rejects_invalid_api_type(self):
        with pytest.raises(ValueError, match="Invalid api_type"):
            k8s.load_kube_client("invalid")  # type: ignore[arg-type]


class TestGetConfigmapFromK8s:
    @patch.object(k8s, "load_kube_client")
    def test_returns_configmap_data(self, mock_load):
        api = MagicMock()
        mock_load.return_value = api
        api.read_namespaced_config_map.return_value = MagicMock(
            data={"renovate.json": "{}"}
        )

        result = k8s.get_configmap_from_k8s("renovate-config", "mintmaker")

        assert result == {"renovate.json": "{}"}

    @patch.object(k8s, "load_kube_client")
    def test_empty_configmap_returns_empty_dict(self, mock_load):
        api = MagicMock()
        mock_load.return_value = api
        api.read_namespaced_config_map.return_value = MagicMock(data=None)

        result = k8s.get_configmap_from_k8s("renovate-config", "mintmaker")

        assert result == {}

    @patch.object(k8s, "load_kube_client")
    def test_api_error_returns_none(self, mock_load):
        api = MagicMock()
        mock_load.return_value = api
        api.read_namespaced_config_map.side_effect = ApiException(status=404)

        result = k8s.get_configmap_from_k8s("missing", "mintmaker")

        assert result is None

    @patch.object(k8s, "load_kube_client", return_value=None)
    def test_missing_client_returns_none(self, _mock_load):
        assert k8s.get_configmap_from_k8s("renovate-config", "mintmaker") is None


class TestCreateResultsConfigmap:
    @patch.object(k8s, "load_kube_client")
    def test_creates_configmap(self, mock_load):
        api = MagicMock()
        mock_load.return_value = api

        result = k8s.create_results_configmap(
            "results", "mintmaker", {"general_scheduled_times.txt": "2026-01-01\n"}
        )

        assert result is True
        api.create_namespaced_config_map.assert_called_once()
        api.replace_namespaced_config_map.assert_not_called()

    @patch.object(k8s, "load_kube_client")
    def test_replaces_configmap_on_conflict(self, mock_load):
        api = MagicMock()
        mock_load.return_value = api
        api.create_namespaced_config_map.side_effect = ApiException(status=409)

        result = k8s.create_results_configmap(
            "results", "mintmaker", {"general_scheduled_times.txt": "2026-01-01\n"}
        )

        assert result is True
        api.replace_namespaced_config_map.assert_called_once()

    @patch.object(k8s, "load_kube_client")
    def test_create_error_returns_false(self, mock_load):
        api = MagicMock()
        mock_load.return_value = api
        api.create_namespaced_config_map.side_effect = ApiException(status=403)

        result = k8s.create_results_configmap("results", "mintmaker", {})

        assert result is False

    @patch.object(k8s, "load_kube_client")
    def test_replace_error_returns_false(self, mock_load):
        api = MagicMock()
        mock_load.return_value = api
        api.create_namespaced_config_map.side_effect = ApiException(status=409)
        api.replace_namespaced_config_map.side_effect = ApiException(status=500)

        result = k8s.create_results_configmap("results", "mintmaker", {})

        assert result is False

    @patch.object(k8s, "load_kube_client", return_value=None)
    def test_missing_client_returns_false(self, _mock_load):
        assert k8s.create_results_configmap("results", "mintmaker", {}) is False
