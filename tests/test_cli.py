import json
from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from mintmaker_schedule_calculator import cli

RENOVATE_CONFIG = {
    "enabledManagers": ["npm"],
    "npm": {"schedule": ["0 2 * * 1"]},
}


class TestParseRenovateConfigFromConfigmap:
    @patch.object(cli, "get_configmap_from_k8s")
    def test_parses_manager_schedules(self, mock_get):
        mock_get.return_value = {"renovate.json": json.dumps(RENOVATE_CONFIG)}
        api = MagicMock()

        result = cli.parse_renovate_config_from_configmap(
            "renovate-config", "mintmaker", api
        )

        assert result == {"npm": "0 2 * * 1"}
        mock_get.assert_called_once_with("renovate-config", "mintmaker", api)

    @patch.object(cli, "get_configmap_from_k8s", return_value={})
    def test_missing_key_raises(self, _mock_get):
        with pytest.raises(ValueError, match=r"Key 'renovate\.json' not found"):
            cli.parse_renovate_config_from_configmap(
                "renovate-config", "mintmaker", MagicMock()
            )

    @patch.object(cli, "get_configmap_from_k8s")
    def test_no_manager_schedules_returns_empty_dict(self, mock_get):
        mock_get.return_value = {
            "renovate.json": json.dumps({"enabledManagers": ["npm"], "npm": {}})
        }

        result = cli.parse_renovate_config_from_configmap(
            "renovate-config", "mintmaker", MagicMock()
        )

        assert result == {}


class TestGetOutputConfigmapName:
    def test_default_name(self, monkeypatch):
        monkeypatch.delenv("OUTPUT_CONFIGMAP", raising=False)
        assert cli.get_output_configmap_name() == cli.DEFAULT_OUTPUT_CONFIGMAP

    def test_allows_labeled_name(self, monkeypatch):
        monkeypatch.setenv(
            "OUTPUT_CONFIGMAP", "mintmaker-schedule-calculator-dev-results"
        )
        assert (
            cli.get_output_configmap_name()
            == "mintmaker-schedule-calculator-dev-results"
        )

    def test_rejects_unrelated_name(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_CONFIGMAP", "renovate-config")
        with pytest.raises(ValueError, match="Invalid OUTPUT_CONFIGMAP"):
            cli.get_output_configmap_name()


class TestMain:
    @patch.object(cli, "load_kube_client", return_value=(MagicMock(), MagicMock()))
    @patch.object(cli, "create_results_configmap", side_effect=ApiException(status=403))
    @patch.object(cli, "parse_renovate_config_from_configmap", return_value={})
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_1_on_configmap_write_failure(
        self,
        _mock_cronjob,
        _mock_parse,
        _mock_create,
        mock_load_client,
    ):
        assert cli.main([]) == 1
        mock_load_client.assert_called_once()

    @patch.object(cli, "load_kube_client", return_value=(MagicMock(), MagicMock()))
    @patch.object(cli, "get_configmap_from_k8s", side_effect=ApiException(status=404))
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_1_on_configmap_fetch_failure(
        self, _mock_cronjob, _mock_get, mock_load_client
    ):
        assert cli.main([]) == 1
        mock_load_client.assert_called_once()

    @patch.object(cli, "load_kube_client", return_value=(MagicMock(), MagicMock()))
    @patch.object(cli, "get_configmap_from_k8s", return_value={})
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_1_on_missing_configmap_key(
        self, _mock_cronjob, _mock_get, mock_load_client
    ):
        assert cli.main([]) == 1
        mock_load_client.assert_called_once()

    @patch.object(cli, "load_kube_client", return_value=(MagicMock(), MagicMock()))
    @patch.object(cli, "create_results_configmap")
    @patch.object(cli, "parse_renovate_config_from_configmap", return_value={})
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_0_on_success(
        self,
        _mock_cronjob,
        _mock_parse,
        mock_create,
        mock_load_client,
    ):
        assert cli.main([]) == 0
        mock_load_client.assert_called_once()
        mock_create.assert_called_once()

    @patch.object(cli, "load_kube_client", return_value=(MagicMock(), MagicMock()))
    @patch.object(cli, "create_results_configmap")
    @patch.object(
        cli,
        "parse_renovate_config_from_configmap",
        return_value={
            "npm": "0 * * * *",
            "github-actions": "0 * * * *",
        },
    )
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_0_with_managers(
        self,
        _mock_cronjob,
        _mock_parse,
        mock_create,
        mock_load_client,
    ):
        assert cli.main([]) == 0
        mock_load_client.assert_called_once()
        mock_create.assert_called_once()

        _name, _namespace, data, _api = mock_create.call_args.args
        assert "general_scheduled_times.txt" in data
        assert "npm_scheduled_times.txt" in data
        assert "github_actions_scheduled_times.txt" in data
        assert data["npm_scheduled_times.txt"]
        assert data["github_actions_scheduled_times.txt"]

    @patch.object(cli, "load_kube_client", return_value=(MagicMock(), MagicMock()))
    @patch.object(cli, "create_results_configmap")
    @patch.object(cli, "parse_renovate_config_from_configmap", return_value={})
    @patch.object(cli, "analyze_cron_schedule", side_effect=Exception("boom"))
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_1_when_output_empty(
        self,
        _mock_cronjob,
        _mock_analyze,
        _mock_parse,
        mock_create,
        mock_load_client,
    ):
        assert cli.main([]) == 1
        mock_load_client.assert_called_once()
        mock_create.assert_not_called()

    @patch.object(cli, "load_kube_client", return_value=(MagicMock(), MagicMock()))
    @patch.object(cli, "create_results_configmap")
    def test_returns_1_on_invalid_output_configmap(
        self, mock_create, mock_load_client, monkeypatch
    ):
        monkeypatch.setenv("OUTPUT_CONFIGMAP", "renovate-config")
        assert cli.main([]) == 1
        mock_load_client.assert_not_called()
        mock_create.assert_not_called()
