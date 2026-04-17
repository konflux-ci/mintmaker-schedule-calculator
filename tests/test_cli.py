import json
from unittest.mock import patch

from mintmaker_schedule_calculator import cli

RENOVATE_CONFIG = {
    "enabledManagers": ["npm"],
    "npm": {"schedule": ["0 2 * * 1"]},
}


class TestParseRenovateConfigFromConfigmap:
    @patch.object(cli, "get_configmap_from_k8s")
    def test_parses_manager_schedules(self, mock_get):
        mock_get.return_value = {"renovate.json": json.dumps(RENOVATE_CONFIG)}

        result = cli.parse_renovate_config_from_configmap(
            "renovate-config", "mintmaker"
        )

        assert result == {"npm": "0 2 * * 1"}

    @patch.object(cli, "get_configmap_from_k8s", return_value=None)
    def test_fetch_failure_returns_empty_dict(self, _mock_get):
        result = cli.parse_renovate_config_from_configmap(
            "renovate-config", "mintmaker"
        )

        assert result == {}

    @patch.object(cli, "get_configmap_from_k8s", return_value={})
    def test_missing_key_returns_empty_dict(self, _mock_get):
        result = cli.parse_renovate_config_from_configmap(
            "renovate-config", "mintmaker"
        )

        assert result == {}


class TestMain:
    @patch.object(cli, "create_results_configmap", return_value=False)
    @patch.object(cli, "parse_renovate_config_from_configmap", return_value={})
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_1_on_configmap_write_failure(
        self,
        _mock_cronjob,
        _mock_parse,
        _mock_create,
    ):
        assert cli.main([]) == 1

    @patch.object(cli, "create_results_configmap", return_value=True)
    @patch.object(cli, "parse_renovate_config_from_configmap", return_value={})
    @patch.object(cli, "get_cronjob_schedule_from_k8s", return_value="0 * * * *")
    def test_returns_0_on_success(
        self,
        _mock_cronjob,
        _mock_parse,
        _mock_create,
    ):
        assert cli.main([]) == 0
