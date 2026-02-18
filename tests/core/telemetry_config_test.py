# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for TelemetryConfig loader."""

from pathlib import Path
from textwrap import dedent
import pytest
from src.core.models.telemetry import TelemetryConfig
from src.core.observability.telemetry_handlers import (
    load_telemetry_config,
    _coalesce,
)


class TestTelemetryConfig:
    """Unit tests for TelemetryConfig dataclass."""

    def test_has_log_analytics_with_shared_key(self) -> None:
        """
        Workspace ID + shared key enables Log Analytics.
        """
        cfg = TelemetryConfig(
            laws_workspace_id="ws-123",
            laws_shared_key="key-abc",
        )
        assert cfg.has_log_analytics is True

    def test_has_log_analytics_with_azure_lookup(self) -> None:
        """
        Workspace ID + subscription/RG/name enables Log Analytics.
        """
        cfg = TelemetryConfig(
            laws_workspace_id="ws-123",
            laws_subscription_id="sub",
            laws_resource_group="rg",
            laws_workspace_name="wn",
        )
        assert cfg.has_log_analytics is True

    def test_has_log_analytics_false_when_empty(self) -> None:
        """
        Empty config reports Log Analytics as unavailable.
        """
        cfg = TelemetryConfig()
        assert cfg.has_log_analytics is False

    def test_has_adx(self) -> None:
        """
        Full ADX credentials enable ADX.
        """
        cfg = TelemetryConfig(
            adx_database_name="db",
            adx_cluster_fqdn="https://c.kusto.windows.net",
            adx_client_id="client",
        )
        assert cfg.has_adx is True

    def test_has_adx_false_when_partial(self) -> None:
        """
        Partial ADX credentials report ADX as unavailable.
        """
        cfg = TelemetryConfig(adx_database_name="db")
        assert cfg.has_adx is False

    def test_is_enabled(self) -> None:
        """
        Config is enabled when any destination is configured.
        """
        cfg = TelemetryConfig(
            laws_workspace_id="ws",
            laws_shared_key="key",
        )
        assert cfg.is_enabled is True

    def test_is_not_enabled_empty(self) -> None:
        """
        Empty config is not enabled.
        """
        assert TelemetryConfig().is_enabled is False

    def test_service_table_default(self) -> None:
        """
        Default service table uses SAP_AUTOMATION_QA prefix.
        """
        cfg = TelemetryConfig()
        assert cfg.service_table() == "SAP_AUTOMATION_QA_ServiceLogs"

    def test_service_table_custom(self) -> None:
        """
        Custom base table name is used as service table prefix.
        """
        cfg = TelemetryConfig(
            telemetry_table_name="MyTable",
        )
        assert cfg.service_table() == "MyTable_ServiceLogs"

    def test_service_table_explicit(self) -> None:
        """
        Explicit service_log_table_name takes precedence.
        """
        cfg = TelemetryConfig(
            service_log_table_name="ExplicitServiceLogs",
        )
        assert cfg.service_table() == "ExplicitServiceLogs"

    def test_frozen(self) -> None:
        """
        Frozen dataclass rejects attribute assignment.
        """
        cfg = TelemetryConfig()
        with pytest.raises(AttributeError):
            cfg.laws_workspace_id = "x"  # type: ignore[misc]


class TestCoalesce:
    """Tests for _coalesce helper."""

    def test_returns_first_non_empty(self) -> None:
        """
        Returns the first non-empty, non-null value.
        """
        assert _coalesce(None, "", "value") == "value"

    def test_returns_none_when_all_empty(self) -> None:
        """
        Returns None when all values are empty or whitespace.
        """
        assert _coalesce(None, "", "   ") is None

    def test_skips_null_string(self) -> None:
        """
        Literal 'null' strings are treated as empty.
        """
        assert _coalesce("null", "Null", "real") == "real"

    def test_strips_whitespace(self) -> None:
        """
        Returned value has leading/trailing whitespace stripped.
        """
        assert _coalesce("  val  ") == "val"


class TestLoadTelemetryConfig:
    """Tests for load_telemetry_config."""

    def test_loads_from_yaml(self, tmp_path: Path) -> None:
        """
        Loads all fields from a valid vars.yaml file.
        """
        yaml_file = tmp_path / "vars.yaml"
        yaml_file.write_text(dedent("""\
            telemetry_data_destination: azureloganalytics
            laws_workspace_id: ws-from-yaml
            laws_shared_key: key-from-yaml
            telemetry_table_name: TestTable
            """))
        cfg = load_telemetry_config(vars_path=yaml_file)
        assert cfg.telemetry_data_destination == "azureloganalytics"
        assert cfg.laws_workspace_id == "ws-from-yaml"
        assert cfg.laws_shared_key == "key-from-yaml"
        assert cfg.telemetry_table_name == "TestTable"
        assert cfg.has_log_analytics is True

    def test_env_overrides_yaml(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Environment variables override values from vars.yaml.
        """
        yaml_file = tmp_path / "vars.yaml"
        yaml_file.write_text("laws_workspace_id: yaml-ws\n")
        monkeypatch.setenv("LAWS_WORKSPACE_ID", "env-ws")

        cfg = load_telemetry_config(vars_path=yaml_file)
        assert cfg.laws_workspace_id == "env-ws"

    def test_null_in_yaml_treated_as_none(self, tmp_path: Path) -> None:
        """
        YAML null values are treated as None.
        """
        yaml_file = tmp_path / "vars.yaml"
        yaml_file.write_text(dedent("""\
            telemetry_data_destination: null
            laws_workspace_id: null
            """))
        cfg = load_telemetry_config(vars_path=yaml_file)
        assert cfg.telemetry_data_destination is None
        assert cfg.laws_workspace_id is None
        assert cfg.is_enabled is False

    def test_missing_file_returns_empty_config(self) -> None:
        """
        Missing vars.yaml returns an empty disabled config.
        """
        cfg = load_telemetry_config(vars_path=Path("/nonexistent/vars.yaml"))
        assert cfg.is_enabled is False

    def test_adx_config_from_yaml(self, tmp_path: Path) -> None:
        """
        ADX credentials are loaded from vars.yaml.
        """
        yaml_file = tmp_path / "vars.yaml"
        yaml_file.write_text(dedent("""\
            telemetry_data_destination: azuredataexplorer
            adx_database_name: TestDB
            adx_cluster_fqdn: https://cluster.kusto.windows.net
            adx_client_id: client-123
            """))
        cfg = load_telemetry_config(vars_path=yaml_file)
        assert cfg.has_adx is True
        assert cfg.adx_database_name == "TestDB"

    def test_batch_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Batch size and flush interval are read from env vars.
        """
        monkeypatch.setenv("TELEMETRY_BATCH_SIZE", "200")
        monkeypatch.setenv("TELEMETRY_FLUSH_INTERVAL", "30.0")
        cfg = load_telemetry_config(vars_path=Path("/nonexistent"))
        assert cfg.batch_size == 200
        assert cfg.flush_interval_seconds == 30.0
