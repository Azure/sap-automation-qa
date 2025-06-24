# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the filter_tests module.
"""

import json
import tempfile
import os
import pytest
import yaml
from src.module_utils.filter_tests import TestFilter


class TestTestFilter:
    """
    Test class for the TestFilter class.
    """

    @pytest.fixture
    def sample_config(self):
        """
        Fixture providing sample test configuration data.

        :return: Sample configuration dictionary
        :rtype: dict
        """
        return {
            "sap_functional_test_type_map": [
                {"name": "DatabaseHighAvailability", "value": "HA_DB"},
                {"name": "CentralServicesHighAvailability", "value": "HA_SCS"},
            ],
            "test_groups": [
                {
                    "name": "HA_DB_HANA",
                    "test_cases": [
                        {
                            "name": "HA Parameters Validation",
                            "task_name": "ha-config",
                            "description": "Validates HA configuration",
                            "enabled": True,
                        },
                        {
                            "name": "Azure Load Balancer Validation",
                            "task_name": "azure-lb",
                            "description": "Validates Azure LB setup",
                            "enabled": True,
                        },
                        {
                            "name": "Primary Node Crash",
                            "task_name": "primary-node-crash",
                            "description": "Simulates primary node crash",
                            "enabled": True,
                        },
                    ],
                },
                {
                    "name": "HA_SCS",
                    "test_cases": [
                        {
                            "name": "SAPControl Config Validation",
                            "task_name": "sapcontrol-config",
                            "description": "Validates SAPControl config",
                            "enabled": True,
                        },
                        {
                            "name": "ASCS Node Crash",
                            "task_name": "ascs-node-crash",
                            "description": "Simulates ASCS node crash",
                            "enabled": True,
                        },
                    ],
                },
            ],
            "sap_sid": "HDB",
            "db_sid": "HDB",
            "default_retries": 50,
        }

    @pytest.fixture
    def temp_yaml_file(self, sample_config):
        """
        Fixture providing a temporary YAML file with sample configuration.

        :param sample_config: Sample configuration data
        :type sample_config: dict
        :return: Path to temporary YAML file
        :rtype: str
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(sample_config, f)
            return f.name

    def test_init_with_valid_file(self, temp_yaml_file, sample_config):
        """
        Test initialization with a valid YAML file.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param sample_config: Expected configuration data
        :type sample_config: dict
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            assert filter_obj.input_file == temp_yaml_file
            assert filter_obj.config == sample_config
        finally:
            os.unlink(temp_yaml_file)

    def test_init_with_nonexistent_file(self, capsys):
        """
        Test initialization with a non-existent file.

        :param capsys: Pytest fixture to capture stdout/stderr
        :type capsys: pytest.CaptureFixture
        """
        with pytest.raises(SystemExit) as exc_info:
            TestFilter("nonexistent_file.yaml")
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error: Configuration file nonexistent_file.yaml not found" in captured.err

    def test_init_with_invalid_yaml(self, capsys):
        """
        Test initialization with an invalid YAML file.

        :param capsys: Pytest fixture to capture stdout/stderr
        :type capsys: pytest.CaptureFixture
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            temp_file = f.name
        try:
            with pytest.raises(SystemExit) as exc_info:
                TestFilter(temp_file)
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert f"Error parsing YAML file {temp_file}" in captured.err
        finally:
            os.unlink(temp_file)

    def test_filter_tests_no_filters(self, temp_yaml_file, sample_config):
        """
        Test filter_tests with no filters applied.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param sample_config: Expected configuration data
        :type sample_config: dict
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.filter_tests()
            result_dict = json.loads(result)
            assert result_dict == sample_config
        finally:
            os.unlink(temp_yaml_file)

    def test_filter_tests_by_group(self, temp_yaml_file):
        """
        Test filter_tests with a specific test group.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.filter_tests(test_group="HA_DB_HANA")
            result_dict = json.loads(result)
            ha_db_group = next(g for g in result_dict["test_groups"] if g["name"] == "HA_DB_HANA")
            for test_case in ha_db_group["test_cases"]:
                assert test_case["enabled"] is True
            ha_scs_group = next(g for g in result_dict["test_groups"] if g["name"] == "HA_SCS")
            for test_case in ha_scs_group["test_cases"]:
                assert test_case["enabled"] is False
        finally:
            os.unlink(temp_yaml_file)

    def test_filter_tests_by_cases(self, temp_yaml_file):
        """
        Test filter_tests with specific test cases.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.filter_tests(test_cases=["ha-config", "ascs-node-crash"])
            result_dict = json.loads(result)
            for group in result_dict["test_groups"]:
                for test_case in group["test_cases"]:
                    if test_case["task_name"] in ["ha-config", "ascs-node-crash"]:
                        assert test_case["enabled"] is True
                    else:
                        assert test_case["enabled"] is False
        finally:
            os.unlink(temp_yaml_file)

    def test_filter_tests_by_group_and_cases(self, temp_yaml_file):
        """
        Test filter_tests with both test group and specific test cases.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.filter_tests(
                test_group="HA_DB_HANA", test_cases=["ha-config", "azure-lb"]
            )
            result_dict = json.loads(result)
            ha_db_group = next(g for g in result_dict["test_groups"] if g["name"] == "HA_DB_HANA")
            assert len(ha_db_group["test_cases"]) == 2
            expected_tasks = {"ha-config", "azure-lb"}
            actual_tasks = {tc["task_name"] for tc in ha_db_group["test_cases"]}
            assert actual_tasks == expected_tasks
            for test_case in ha_db_group["test_cases"]:
                assert test_case["enabled"] is True
        finally:
            os.unlink(temp_yaml_file)

    def test_get_ansible_vars_no_filters(self, temp_yaml_file, sample_config):
        """
        Test get_ansible_vars with no filters applied.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param sample_config: Expected configuration data
        :type sample_config: dict
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.get_ansible_vars()
            result_dict = json.loads(result)
            assert "test_groups" in result_dict
            assert result_dict["test_groups"] == sample_config["test_groups"]
        finally:
            os.unlink(temp_yaml_file)

    def test_get_ansible_vars_with_filters(self, temp_yaml_file):
        """
        Test get_ansible_vars with filters applied.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.get_ansible_vars(test_group="HA_SCS")
            result_dict = json.loads(result)
            assert "test_groups" in result_dict
            ha_scs_group = next(g for g in result_dict["test_groups"] if g["name"] == "HA_SCS")
            for test_case in ha_scs_group["test_cases"]:
                assert test_case["enabled"] is True
            ha_db_group = next(g for g in result_dict["test_groups"] if g["name"] == "HA_DB_HANA")
            for test_case in ha_db_group["test_cases"]:
                assert test_case["enabled"] is False
        finally:
            os.unlink(temp_yaml_file)

    def test_main_function_insufficient_args(self, monkeypatch, capsys):
        """
        Test main function with insufficient arguments.

        :param monkeypatch: Pytest monkeypatch fixture
        :type monkeypatch: pytest.MonkeyPatch
        :param capsys: Pytest fixture to capture stdout/stderr
        :type capsys: pytest.CaptureFixture
        """
        with monkeypatch.context() as m:
            m.setattr("sys.argv", ["filter_tests.py"])
            with pytest.raises(SystemExit) as exc_info:
                from src.module_utils.filter_tests import main

                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Usage: python filter_tests.py" in captured.err

    def test_main_function_with_input_file_only(self, monkeypatch, temp_yaml_file, capsys):
        """
        Test main function with only input file argument.

        :param monkeypatch: Pytest monkeypatch fixture
        :type monkeypatch: pytest.MonkeyPatch
        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param capsys: Pytest fixture to capture stdout/stderr
        :type capsys: pytest.CaptureFixture
        """
        try:
            with monkeypatch.context() as m:
                m.setattr("sys.argv", ["filter_tests.py", temp_yaml_file])
                from src.module_utils.filter_tests import main

                main()
                captured = capsys.readouterr()
                result = json.loads(captured.out)
                assert "test_groups" in result
        finally:
            os.unlink(temp_yaml_file)

    def test_main_function_with_test_group(self, monkeypatch, temp_yaml_file, capsys):
        """
        Test main function with test group specified.

        :param monkeypatch: Pytest monkeypatch fixture
        :type monkeypatch: pytest.MonkeyPatch
        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param capsys: Pytest fixture to capture stdout/stderr
        :type capsys: pytest.CaptureFixture
        """
        try:
            with monkeypatch.context() as m:
                m.setattr("sys.argv", ["filter_tests.py", temp_yaml_file, "HA_DB_HANA"])
                from src.module_utils.filter_tests import main

                main()
                captured = capsys.readouterr()
                result = json.loads(captured.out)
                assert "test_groups" in result
        finally:
            os.unlink(temp_yaml_file)

    def test_main_function_with_test_cases(self, monkeypatch, temp_yaml_file, capsys):
        """
        Test main function with test cases specified.

        :param monkeypatch: Pytest monkeypatch fixture
        :type monkeypatch: pytest.MonkeyPatch
        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param capsys: Pytest fixture to capture stdout/stderr
        :type capsys: pytest.CaptureFixture
        """
        try:
            with monkeypatch.context() as m:
                m.setattr(
                    "sys.argv", ["filter_tests.py", temp_yaml_file, "null", "ha-config,azure-lb"]
                )
                from src.module_utils.filter_tests import main

                main()
                captured = capsys.readouterr()
                result = json.loads(captured.out)
                assert "test_groups" in result
        finally:
            os.unlink(temp_yaml_file)

    def test_main_function_with_null_values(self, monkeypatch, temp_yaml_file, capsys):
        """
        Test main function with null values.

        :param monkeypatch: Pytest monkeypatch fixture
        :type monkeypatch: pytest.MonkeyPatch
        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param capsys: Pytest fixture to capture stdout/stderr
        :type capsys: pytest.CaptureFixture
        """
        try:
            with monkeypatch.context() as m:
                m.setattr("sys.argv", ["filter_tests.py", temp_yaml_file, "null", "null"])
                from src.module_utils.filter_tests import main

                main()
                captured = capsys.readouterr()
                result = json.loads(captured.out)
                assert "test_groups" in result
        finally:
            os.unlink(temp_yaml_file)

    def test_filter_tests_nonexistent_group(self, temp_yaml_file, sample_config):
        """
        Test filter_tests with a non-existent test group.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        :param sample_config: Sample configuration data
        :type sample_config: dict
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.filter_tests(test_group="NONEXISTENT_GROUP")
            result_dict = json.loads(result)
            for group in result_dict["test_groups"]:
                for test_case in group["test_cases"]:
                    assert test_case["enabled"] is False
        finally:
            os.unlink(temp_yaml_file)

    def test_filter_tests_nonexistent_cases(self, temp_yaml_file):
        """
        Test filter_tests with non-existent test cases.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            result = filter_obj.filter_tests(test_cases=["nonexistent-case"])
            result_dict = json.loads(result)
            for group in result_dict["test_groups"]:
                for test_case in group["test_cases"]:
                    assert test_case["enabled"] is False
        finally:
            os.unlink(temp_yaml_file)

    def test_config_copy_independence(self, temp_yaml_file):
        """
        Test that filtered configuration doesn't modify the original.

        :param temp_yaml_file: Path to temporary YAML file
        :type temp_yaml_file: str
        """
        try:
            filter_obj = TestFilter(temp_yaml_file)
            original_config = filter_obj.config.copy()
            filter_obj.filter_tests(test_group="HA_DB_HANA")
            assert filter_obj.config == original_config
        finally:
            os.unlink(temp_yaml_file)
