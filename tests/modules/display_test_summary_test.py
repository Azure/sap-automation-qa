# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the display_test_summary module.
"""

import json
import pytest
from typing import List, Optional
from src.modules.display_test_summary import (
    TestSummaryDisplay,
    _HA_CONFIG_TEST_NAME,
    main,
)


def _make_log_entry(
    test_name: str = "HA Parameters Validation",
    hostname: str = "node01",
    status: str = "FAILED",
    parameters: Optional[list] = None,
) -> dict:
    """
    Helper: build a single JSONL log entry.
    """
    if parameters is None:
        parameters = []
    return {
        "TestCaseName": test_name,
        "TestCaseHostname": hostname,
        "TestCaseStatus": status,
        "TestCaseDetails": {"parameters": parameters},
    }


def _param(
    name: str,
    value: str,
    expected: str,
    status: str = "PASSED",
    category: str = "crm_config",
) -> dict:
    return {
        "category": category,
        "id": f"{category}_{name}",
        "name": name,
        "value": value,
        "expected_value": expected,
        "status": status,
    }


class TestTestSummaryDisplay:
    """Test cases for TestSummaryDisplay."""

    @pytest.fixture
    def display(self, tmp_path):
        """Return a wired-up TestSummaryDisplay."""
        ws = tmp_path / "SYSTEM" / "DEV"
        (ws / "logs").mkdir(parents=True)
        return TestSummaryDisplay(
            test_group_invocation_id="test-id-001",
            workspace_directory=str(ws),
        )

    @pytest.fixture
    def _write_log(self, display):
        """Fixture that writes JSONL entries to the log file."""

        def _inner(entries: list):
            log_dir = display.workspace_directory + "/logs"
            with open(
                f"{log_dir}/{display.test_group_invocation_id}.log",
                "w",
                encoding="utf-8",
            ) as fh:
                for entry in entries:
                    fh.write(json.dumps(entry) + "\n")

        return _inner

    def test_all_passed(self, display, _write_log):
        """All parameters passed on one host."""
        _write_log(
            [
                _make_log_entry(
                    status="PASSED",
                    parameters=[
                        _param("stonith-enabled", "true", "true"),
                        _param("concurrent-fencing", "true", "true"),
                    ],
                )
            ]
        )
        display.generate_summary()
        result = display.get_result()

        assert result["overall_status"] == "PASSED"
        assert result["failed_parameters"] == []
        assert len(result["test_cases"]) == 1
        tc = result["test_cases"][0]
        assert tc["passed"] == 2
        assert tc["failed"] == 0
        assert "[PASS]" in result["summary"]

    def test_failures_shown(self, display, _write_log):
        """FAILED params surfaced for ha-config test."""
        _write_log(
            [
                _make_log_entry(
                    status="FAILED",
                    parameters=[
                        _param("stonith-enabled", "true", "true"),
                        _param(
                            "migration-threshold",
                            "50",
                            "5000",
                            status="FAILED",
                            category="rsc_defaults",
                        ),
                        _param(
                            "pcmk_action_limit",
                            "-1",
                            "3",
                            status="FAILED",
                            category="fence_agent",
                        ),
                    ],
                )
            ]
        )
        display.generate_summary()
        result = display.get_result()

        assert result["overall_status"] == "FAILED"
        assert len(result["failed_parameters"]) == 2
        names = {fp["name"] for fp in result["failed_parameters"]}
        assert names == {"migration-threshold", "pcmk_action_limit"}
        assert "[FAIL]" in result["summary"]
        assert "migration-threshold" in result["summary"]

    def test_multiple_hosts_dedup(self, display, _write_log):
        """Same test on two hosts, failed params de-duplicated."""
        params = [
            _param("stonith-enabled", "true", "true"),
            _param(
                "migration-threshold",
                "50",
                "5000",
                status="FAILED",
                category="rsc_defaults",
            ),
        ]
        _write_log(
            [
                _make_log_entry(
                    hostname="node01",
                    status="FAILED",
                    parameters=params,
                ),
                _make_log_entry(
                    hostname="node02",
                    status="FAILED",
                    parameters=params,
                ),
            ]
        )
        display.generate_summary()
        result = display.get_result()

        assert result["overall_status"] == "FAILED"
        tc = result["test_cases"][0]
        assert tc["host_count"] == 2
        assert len(result["failed_parameters"]) == 1

    def test_non_ha_config_no_failed_params(self, display, _write_log):
        """Non-ha-config test does not populate failed_parameters."""
        _write_log(
            [
                _make_log_entry(
                    test_name="Some Other Test",
                    status="FAILED",
                    parameters=[
                        _param(
                            "foo",
                            "bar",
                            "baz",
                            status="FAILED",
                        )
                    ],
                )
            ]
        )
        display.generate_summary()
        result = display.get_result()

        assert result["overall_status"] == "FAILED"
        assert result["failed_parameters"] == []

    def test_info_only_params(self, display, _write_log):
        """INFO-only parameters counted correctly."""
        _write_log(
            [
                _make_log_entry(
                    status="PASSED",
                    parameters=[
                        _param(
                            "subscriptionId",
                            "xyz",
                            "",
                            status="INFO",
                        ),
                        _param("stonith-enabled", "true", "true"),
                    ],
                )
            ]
        )
        display.generate_summary()
        result = display.get_result()
        tc = result["test_cases"][0]
        assert tc["info"] == 1
        assert tc["passed"] == 1

    def test_empty_log(self, display, _write_log):
        """Empty log file produces warning."""
        _write_log([])
        display.generate_summary()
        result = display.get_result()
        assert result["overall_status"] == "WARNING"

    def test_missing_log(self, display):
        """Missing log file handled gracefully."""
        display.generate_summary()
        result = display.get_result()
        assert result["overall_status"] == "WARNING"

    def test_multiple_test_cases(self, display, _write_log):
        """Multiple distinct test cases aggregated."""
        _write_log(
            [
                _make_log_entry(
                    test_name="HA Parameters Validation",
                    hostname="node01",
                    status="PASSED",
                    parameters=[
                        _param("stonith-enabled", "true", "true"),
                    ],
                ),
                _make_log_entry(
                    test_name="Kill HANA Primary",
                    hostname="node01",
                    status="PASSED",
                    parameters=[],
                ),
            ]
        )
        display.generate_summary()
        result = display.get_result()
        assert len(result["test_cases"]) == 2
        assert result["overall_status"] == "PASSED"


class TestModuleEntryPoint:
    """Verify run_module / main wiring."""

    def test_main_calls_run_module(self, mocker):
        """main() delegates to run_module()."""
        mock_run = mocker.patch("src.modules.display_test_summary.run_module")
        main()
        mock_run.assert_called_once()
