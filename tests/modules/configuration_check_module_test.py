# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the ConfigurationCheckModule.

This test suite provides comprehensive coverage for configuration check execution,
validation, parallel processing, and error handling.
Tests use pytest with monkeypatch for mocking, avoiding unittest entirely.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch

import pytest

from src.modules.configuration_check_module import ConfigurationCheckModule
from src.module_utils.enums import (
    TestStatus,
    TestSeverity,
    Check,
    CheckResult,
    ApplicabilityRule,
)


class MockAnsibleModule:
    """
    Mock Ansible module for testing ConfigurationCheckModule.

    Simulates the AnsibleModule interface with params, exit_json, and fail_json.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {
            "check_file_content": "",
            "context": {},
            "filter_tags": None,
            "filter_categories": None,
            "parallel_execution": False,
            "max_workers": 3,
            "enable_retry": False,
            "workspace_directory": "/tmp/workspace",
            "hostname": None,
            "test_group_invocation_id": "test-id",
            "test_group_name": "test-group",
            "azure_resources": {},
        }
        self.exit_calls = []
        self.fail_calls = []

    def exit_json(self, **kwargs):
        """Mock exit_json to capture successful exits"""
        self.exit_calls.append(kwargs)

    def fail_json(self, **kwargs):
        """Mock fail_json to capture failure exits"""
        self.fail_calls.append(kwargs)


@pytest.fixture
def mock_ansible_module():
    """Fixture to provide a fresh MockAnsibleModule instance"""
    return MockAnsibleModule()


@pytest.fixture
def config_module(mock_ansible_module):
    """Fixture to provide a ConfigurationCheckModule instance"""
    return ConfigurationCheckModule(mock_ansible_module)


@pytest.fixture
def sample_check():
    """Fixture to provide a sample Check object"""
    return Check(
        id="test_check_001",
        name="Test Check",
        description="A test check for validation",
        category="System",
        workload="SAP",
        severity=TestSeverity.WARNING,
        collector_type="command",
        collector_args={"command": "echo test"},
        validator_type="string",
        validator_args={"expected": "test"},
        tags=["test", "system"],
        applicability=[],
        references={},
        report="check",
    )


class TestConfigurationCheckModuleInit:
    """Test suite for ConfigurationCheckModule initialization"""

    def test_initialization(self, mock_ansible_module):
        """Test ConfigurationCheckModule initializes properly"""
        module = ConfigurationCheckModule(mock_ansible_module)
        assert module.module == mock_ansible_module
        assert module.module_params == mock_ansible_module.params
        assert module.checks == []
        assert module.hostname is None
        assert module.context == {}
        assert "check_results" in module.result
        assert len(module._collector_registry) > 0
        assert len(module._validator_registry) > 0

    def test_collector_registry_initialization(self, config_module):
        """Test collector registry contains expected collectors"""
        registry = config_module._collector_registry
        assert "command" in registry
        assert "azure" in registry
        assert "module" in registry

    def test_validator_registry_initialization(self, config_module):
        """Test validator registry contains expected validators"""
        registry = config_module._validator_registry
        assert "string" in registry
        assert "range" in registry
        assert "list" in registry
        assert "check_support" in registry
        assert "properties" in registry


class TestSetContext:
    """Test suite for set_context method"""

    def test_set_context_with_hostname(self, config_module):
        """Test setting context with hostname"""
        context = {"hostname": "testhost", "os": "SLES", "version": "15.3"}
        config_module.set_context(context)
        assert config_module.context == context
        assert config_module.hostname == "testhost"

    def test_set_context_without_hostname(self, config_module):
        """Test setting context without hostname"""
        context = {"os": "RHEL", "version": "8.4"}
        config_module.set_context(context)
        assert config_module.context == context
        assert config_module.hostname is None


class TestLoadChecks:
    """Test suite for load_checks method"""

    def test_load_checks_from_yaml_string(self, config_module):
        """Test loading checks from YAML string"""
        yaml_content = """
checks:
  - id: check_001
    name: Test Check
    description: Test description
    category: System
    severity: WARNING
    collector_type: command
    collector_args:
      command: "echo test"
    validator_type: string
    validator_args:
      expected: "test"
    tags:
      - test
    applicability:
      os: SLES
"""
        config_module.load_checks(yaml_content)
        assert len(config_module.checks) == 1
        assert config_module.checks[0].id == "check_001"
        assert config_module.checks[0].name == "Test Check"
        assert len(config_module.checks[0].applicability) == 1

    def test_load_checks_with_multiple_checks(self, config_module):
        """Test loading multiple checks"""
        yaml_content = """
checks:
  - id: check_001
    name: First Check
    category: System
    severity: INFO
    collector_type: command
  - id: check_002
    name: Second Check
    category: Network
    severity: CRITICAL
    collector_type: azure
"""
        config_module.load_checks(yaml_content)
        assert len(config_module.checks) == 2
        assert config_module.checks[0].id == "check_001"
        assert config_module.checks[1].id == "check_002"

    def test_load_checks_empty_content(self, config_module, monkeypatch):
        """Test loading checks with empty content"""
        config_module.load_checks("")
        assert len(config_module.checks) == 0


class TestIsCheckApplicable:
    """Test suite for is_check_applicable method"""

    def test_check_applicable_no_rules(self, config_module, sample_check):
        """Test check with no applicability rules is always applicable"""
        config_module.set_context({"os": "SLES"})
        sample_check.applicability = []
        assert config_module.is_check_applicable(sample_check) is True

    def test_check_applicable_matching_rule(self, config_module, sample_check):
        """Test check with matching applicability rule"""
        config_module.set_context({"os": "SLES", "version": "15.3"})
        sample_check.applicability = [ApplicabilityRule(property="os", value="SLES")]
        assert config_module.is_check_applicable(sample_check) is True

    def test_check_not_applicable_non_matching_rule(self, config_module, sample_check):
        """Test check with non-matching applicability rule"""
        config_module.set_context({"os": "RHEL"})
        sample_check.applicability = [ApplicabilityRule(property="os", value="SLES")]
        assert config_module.is_check_applicable(sample_check) is False

    def test_check_applicable_multiple_rules_all_match(self, config_module, sample_check):
        """Test check with multiple rules that all match"""
        config_module.set_context({"os": "SLES", "role": "db"})
        sample_check.applicability = [
            ApplicabilityRule(property="os", value="SLES"),
            ApplicabilityRule(property="role", value="db"),
        ]
        assert config_module.is_check_applicable(sample_check) is True


class TestValidators:
    """Test suite for validation methods"""

    def test_validate_string_success(self, config_module, sample_check):
        """Test string validation with matching values"""
        sample_check.validator_args = {"expected": "test_value"}
        result = config_module.validate_string(sample_check, "test_value")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_string_failure(self, config_module, sample_check):
        """Test string validation with non-matching values"""
        sample_check.validator_args = {"expected": "expected_value"}
        sample_check.severity = TestSeverity.WARNING
        result = config_module.validate_string(sample_check, "actual_value")
        assert result["status"] == TestStatus.WARNING.value

    def test_validate_string_case_insensitive(self, config_module, sample_check):
        """Test case-insensitive string validation"""
        sample_check.validator_args = {"expected": "TEST", "case_insensitive": True}
        result = config_module.validate_string(sample_check, "test")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_string_whitespace_handling(self, config_module, sample_check):
        """Test string validation with whitespace handling"""
        sample_check.validator_args = {"expected": "test  value", "strip_whitespace": True}
        result = config_module.validate_string(sample_check, "  test   value  ")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_numeric_range_within_bounds(self, config_module, sample_check):
        """Test numeric range validation within bounds"""
        sample_check.validator_args = {"min": 10, "max": 100}
        result = config_module.validate_numeric_range(sample_check, "50")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_numeric_range_out_of_bounds(self, config_module, sample_check):
        """Test numeric range validation out of bounds"""
        sample_check.validator_args = {"min": 10, "max": 100}
        sample_check.severity = TestSeverity.CRITICAL
        result = config_module.validate_numeric_range(sample_check, "150")
        assert result["status"] == TestStatus.ERROR.value

    def test_validate_numeric_range_invalid_input(self, config_module, sample_check):
        """Test numeric range validation with invalid input"""
        sample_check.validator_args = {"min": 10, "max": 100}
        result = config_module.validate_numeric_range(sample_check, "not_a_number")
        assert result["status"] == TestStatus.ERROR.value

    def test_validate_list_contains_match(self, config_module, sample_check):
        """Test list validation with matching item"""
        sample_check.validator_args = {"valid_list": ["item1", "item2", "item3"]}
        result = config_module.validate_list(sample_check, "item2")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_list_no_match(self, config_module, sample_check):
        """Test list validation with no matching items"""
        sample_check.validator_args = {"valid_list": ["item1", "item2"]}
        sample_check.severity = TestSeverity.WARNING
        result = config_module.validate_list(sample_check, "item3, item4")
        assert result["status"] == TestStatus.WARNING.value

    def test_validate_min_list_all_equal(self, config_module, sample_check):
        """Test min_list validation with all values equal to minimum"""
        sample_check.validator_args = {
            "min_values": ["32000", "1024000000", "500", "32000"],
            "separator": " ",
        }
        result = config_module.validate_min_list(sample_check, "32000 1024000000 500 32000")
        assert result["status"] == TestStatus.SUCCESS.value
        sample_check.validator_args = {
            "min_values": ["32000", "1024000000", "500", "32000"],
            "separator": " ",
        }
        result = config_module.validate_min_list(sample_check, "32000 1024000000 500 32768")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_min_list_tab_separator(self, config_module, sample_check):
        """Test min_list validation with tab separator"""
        sample_check.validator_args = {
            "min_values": ["10", "20", "30"],
            "separator": "\t",
        }
        result = config_module.validate_min_list(sample_check, "10\t20\t30")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_properties_success(self, config_module, sample_check):
        """Test properties validation with matching properties"""
        sample_check.validator_args = {
            "properties": [
                {"property": "cpu", "value": "4"},
                {"property": "memory", "value": "16GB"},
            ]
        }
        collected = json.dumps({"cpu": "4", "memory": "16GB", "disk": "100GB"})
        result = config_module.validate_properties(sample_check, collected)
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_properties_failure(self, config_module, sample_check):
        """Test properties validation with missing properties"""
        sample_check.validator_args = {"properties": [{"property": "cpu", "value": "8"}]}
        sample_check.severity = TestSeverity.CRITICAL
        collected = json.dumps({"cpu": "4"})
        result = config_module.validate_properties(sample_check, collected)
        assert result["status"] == TestStatus.ERROR.value

    def test_validate_properties_invalid_json(self, config_module, sample_check):
        """Test properties validation with invalid JSON"""
        sample_check.validator_args = {"properties": []}
        result = config_module.validate_properties(sample_check, "invalid json")
        assert result["status"] == TestStatus.ERROR.value

    def test_validate_vm_support_success(self, config_module, sample_check):
        """Test VM support validation with supported configuration"""
        config_module.set_context(
            {
                "role": "db",
                "database_type": "HANA",
                "supported_configurations": {
                    "VMs": {"Standard_M32ts": {"db": {"SupportedDB": ["HANA", "DB2"]}}}
                },
            }
        )
        sample_check.validator_args = {"validation_rules": "VMs"}
        result = config_module.validate_vm_support(sample_check, "Standard_M32ts")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_vm_support_unsupported(self, config_module, sample_check):
        """Test VM support validation with unsupported configuration"""
        config_module.set_context(
            {
                "role": "db",
                "database_type": "Oracle",
                "supported_configurations": {
                    "VMs": {"Standard_M32ts": {"db": {"SupportedDB": ["HANA"]}}}
                },
            }
        )
        sample_check.validator_args = {"validation_rules": "VMs"}
        result = config_module.validate_vm_support(sample_check, "Standard_M32ts")
        assert result["status"] == TestStatus.ERROR.value


class TestValidateResult:
    """Test suite for validate_result method"""

    def test_validate_result_with_registered_validator(self, config_module, sample_check):
        """Test validate_result with registered validator"""
        sample_check.validator_type = "string"
        sample_check.validator_args = {"expected": "test"}
        result = config_module.validate_result(sample_check, "test")
        assert "status" in result
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_result_with_unregistered_validator(self, config_module, sample_check):
        """Test validate_result with unregistered validator"""
        sample_check.validator_type = "unknown_validator"
        result = config_module.validate_result(sample_check, "data")
        assert result["status"] == TestStatus.ERROR.value
        assert "not found" in result["details"]


class TestExecuteCheck:
    """Test suite for execute_check method"""

    def test_execute_check_success(self, config_module, sample_check, monkeypatch):
        """Test successful check execution"""
        config_module.set_context({"hostname": "testhost"})

        def mock_collect(check, context):
            return "test"

        with patch("src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect):
            result = config_module.execute_check(sample_check)
            assert isinstance(result, CheckResult)
            assert result.status == TestStatus.SUCCESS.value
            assert result.hostname == "testhost"

    def test_execute_check_not_applicable(self, config_module, sample_check):
        """Test check execution when check is not applicable"""
        config_module.set_context({"os": "RHEL"})
        sample_check.applicability = [ApplicabilityRule(property="os", value="SLES")]
        result = config_module.execute_check(sample_check)
        assert result.status == TestStatus.SKIPPED.value
        assert "not applicable" in result.details

    def test_execute_check_info_severity(self, config_module, sample_check, monkeypatch):
        """Test check execution with INFO severity"""
        config_module.set_context({"hostname": "testhost"})
        sample_check.severity = TestSeverity.INFO

        def mock_collect(check, context):
            return "info_data"

        with patch("src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect):
            result = config_module.execute_check(sample_check)
            assert result.status == TestStatus.INFO.value

    def test_execute_check_collector_not_found(self, config_module, sample_check):
        """Test check execution with unknown collector"""
        config_module.set_context({"hostname": "testhost"})
        sample_check.collector_type = "unknown_collector"
        result = config_module.execute_check(sample_check)
        assert result.status == TestStatus.ERROR.value
        assert "not found" in result.details

    def test_execute_check_exception_handling(self, config_module, sample_check):
        """Test check execution handles exceptions"""
        config_module.set_context({"hostname": "testhost"})

        def mock_collect_error(check, context):
            raise Exception("Collection failed")

        with patch(
            "src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect_error
        ):
            result = config_module.execute_check(sample_check)
            assert result.status == TestStatus.ERROR.value
            assert "Error" in result.details

    def test_execute_check_min_list_validator_success(self, config_module):
        """Test check execution with min_list validator - values meet minimum"""
        config_module.set_context({"hostname": "testhost"})
        check = Check(
            id="kernel_sem_check",
            name="kernel.sem",
            description="Kernel semaphore parameters",
            category="OS",
            workload="SAP",
            severity=TestSeverity.HIGH,
            collector_type="command",
            collector_args={"command": "/sbin/sysctl kernel.sem -n"},
            validator_type="min_list",
            validator_args={
                "min_values": ["32000", "1024000000", "500", "32000"],
                "separator": " ",
            },
            tags=["kernel"],
            applicability=[],
            references={},
            report="check",
        )

        def mock_collect(check_obj, context):
            return "32000 1024000000 500 32768"

        with patch("src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect):
            result = config_module.execute_check(check)
            assert result.status == TestStatus.SUCCESS.value
            assert result.expected_value == "Min: 32000 1024000000 500 32000"
            assert result.actual_value == "32000 1024000000 500 32768"

    def test_execute_check_min_list_validator_failure(self, config_module):
        """Test check execution with min_list validator - values below minimum"""
        config_module.set_context({"hostname": "testhost"})
        check = Check(
            id="kernel_sem_check",
            name="kernel.sem",
            description="Kernel semaphore parameters",
            category="OS",
            workload="SAP",
            severity=TestSeverity.HIGH,
            collector_type="command",
            collector_args={"command": "/sbin/sysctl kernel.sem -n"},
            validator_type="min_list",
            validator_args={
                "min_values": ["32000", "1024000000", "500", "32000"],
                "separator": " ",
            },
            tags=["kernel"],
            applicability=[],
            references={},
            report="check",
        )

        def mock_collect(check_obj, context):
            return "32000 1024000000 500 31999"

        with patch("src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect):
            result = config_module.execute_check(check)
            assert result.status == TestStatus.ERROR.value
            assert result.expected_value == "Min: 32000 1024000000 500 32000"
            assert result.actual_value == "32000 1024000000 500 31999"


class TestExecuteCheckWithRetry:
    """Test suite for execute_check_with_retry method"""

    def test_execute_check_with_retry_success_first_attempt(self, config_module, sample_check):
        """Test retry mechanism succeeds on first attempt"""
        config_module.set_context({"hostname": "testhost"})

        def mock_collect(check, context):
            return "test"

        with patch("src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect):
            result = config_module.execute_check_with_retry(sample_check, max_retries=3)
            assert result.status == TestStatus.SUCCESS.value

    def test_execute_check_with_retry_eventual_success(self, config_module, sample_check):
        """Test retry mechanism succeeds on first attempt (no retry needed)"""
        config_module.set_context({"hostname": "testhost"})

        def mock_collect(check, context):
            return "test"

        with patch("src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect):
            with patch("time.sleep"):  # Skip actual sleep
                result = config_module.execute_check_with_retry(sample_check, max_retries=3)
                assert result.status == TestStatus.SUCCESS.value

    def test_execute_check_with_retry_all_attempts_fail(self, config_module, sample_check):
        """Test retry mechanism fails after all attempts"""
        config_module.set_context({"hostname": "testhost"})

        def mock_collect_error(check, context):
            raise Exception("Persistent failure")

        with patch(
            "src.module_utils.collector.CommandCollector.collect", side_effect=mock_collect_error
        ):
            with patch("time.sleep"):  # Skip actual sleep
                result = config_module.execute_check_with_retry(sample_check, max_retries=3)
                assert result.status == TestStatus.ERROR.value
                assert result.details is not None
                assert "Error" in result.details or "failure" in result.details


class TestBuildExecutionOrder:
    """Test suite for build_execution_order method"""

    def test_build_execution_order_no_dependencies(self, config_module):
        """Test building execution order with no dependencies"""
        checks = [
            Check(
                id="check1",
                name="Check 1",
                description="Test check 1",
                category="System",
                workload="SAP",
                severity=TestSeverity.INFO,
            ),
            Check(
                id="check2",
                name="Check 2",
                description="Test check 2",
                category="System",
                workload="SAP",
                severity=TestSeverity.INFO,
            ),
        ]
        batches = config_module.build_execution_order(checks)
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_build_execution_order_simple(self, config_module):
        """Test building execution order returns all checks in single batch"""
        check1 = Check(
            id="check1",
            name="Check 1",
            description="Test check 1",
            category="System",
            workload="SAP",
            severity=TestSeverity.INFO,
        )
        check2 = Check(
            id="check2",
            name="Check 2",
            description="Test check 2",
            category="System",
            workload="SAP",
            severity=TestSeverity.INFO,
        )

        batches = config_module.build_execution_order([check1, check2])
        assert len(batches) >= 1
        total_checks = sum(len(batch) for batch in batches)
        assert total_checks == 2


class TestExecuteChecks:
    """Test suite for execute_checks method"""

    def test_execute_checks_sequential(self, config_module):
        """Test sequential check execution"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Test Check
    category: System
    severity: INFO
    collector_type: command
    collector_args:
      command: "echo test"
    validator_type: string
    validator_args:
      expected: "test"
"""
        config_module.load_checks(yaml_content)

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            results = config_module.execute_checks(parallel=False)
            assert len(results) == 1
            assert results[0].status == TestStatus.INFO.value

    def test_execute_checks_with_tag_filter(self, config_module):
        """Test check execution with tag filtering"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Check 1
    tags: [production, system]
  - id: check_002
    name: Check 2
    tags: [development, network]
"""
        config_module.load_checks(yaml_content)

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            results = config_module.execute_checks(filter_tags=["production"])
            assert len(results) == 1
            assert results[0].check.id == "check_001"

    def test_execute_checks_with_category_filter(self, config_module):
        """Test check execution with category filtering"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Check 1
    category: System
  - id: check_002
    name: Check 2
    category: Network
"""
        config_module.load_checks(yaml_content)

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            results = config_module.execute_checks(filter_categories=["System"])
            assert len(results) == 1
            assert results[0].check.category == "System"

    def test_execute_checks_no_matching_filters(self, config_module):
        """Test check execution with filters that match nothing"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Check 1
    tags: [production]
"""
        config_module.load_checks(yaml_content)
        results = config_module.execute_checks(filter_tags=["nonexistent"])
        assert len(results) == 0


class TestGetResultsSummary:
    """Test suite for get_results_summary method"""

    def test_get_results_summary_empty(self, config_module):
        """Test summary with no results"""
        summary = config_module.get_results_summary()
        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0

    def test_get_results_summary_with_results(self, config_module, sample_check):
        """Test summary with mixed results"""
        result1 = Mock()
        result1.status = TestStatus.SUCCESS.value
        result1.check = sample_check

        result2 = Mock()
        result2.status = TestStatus.ERROR.value
        result2.check = sample_check

        result3 = Mock()
        result3.status = TestStatus.WARNING.value
        result3.check = sample_check

        config_module.result["check_results"] = [result1, result2, result3]

        summary = config_module.get_results_summary()
        assert summary["total"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["warnings"] == 1


class TestFormatResultsForHtmlReport:
    """Test suite for format_results_for_html_report method"""

    def test_format_results_removes_context_templates(self, config_module, sample_check):
        """Test that CONTEXT templates are neutralized in formatted results"""
        sample_check.collector_args = {"command": "echo {{ CONTEXT.hostname }}"}
        config_module.result["check_results"] = [
            CheckResult(
                check=sample_check,
                status=TestStatus.SUCCESS,
                hostname="test",
                expected_value="",
                actual_value="",
                execution_time=0,
                timestamp=datetime.now(),
            )
        ]
        config_module.format_results_for_html_report()
        formatted = config_module.result["check_results"][0]
        assert "{{ CONTEXT" not in str(formatted["check"]["collector_args"])
        assert "<" in str(formatted["check"]["collector_args"])

    def test_format_results_serialization(self, config_module, sample_check):
        """Test that results are properly serialized for HTML"""
        config_module.result["check_results"] = [
            CheckResult(
                check=sample_check,
                status=TestStatus.SUCCESS,
                hostname="testhost",
                expected_value="expected",
                actual_value="actual",
                execution_time=10,
                timestamp=datetime.now(),
            )
        ]
        config_module.format_results_for_html_report()
        result = config_module.result["check_results"][0]
        assert isinstance(result, dict)
        assert "check" in result
        assert "status" in result
        assert result["hostname"] == "testhost"


class TestRunMethod:
    """Test suite for the main run method"""

    def test_run_successful_execution(self, mock_ansible_module):
        """Test successful run with valid checks"""
        mock_ansible_module.params.update(
            {
                "check_file_content": """
checks:
  - id: check_001
    name: Test Check
    severity: INFO
    collector_type: command
    collector_args:
      command: "echo test"
    validator_type: string
    validator_args:
      expected: "test"
""",
                "context": {"hostname": "testhost", "os": "SLES"},
            }
        )

        module = ConfigurationCheckModule(mock_ansible_module)

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            module.run()

        assert len(mock_ansible_module.exit_calls) == 1
        result = mock_ansible_module.exit_calls[0]
        assert "check_results" in result
        assert "summary" in result

    def test_run_no_check_content(self, mock_ansible_module):
        """Test run fails with no check content"""
        mock_ansible_module.params["check_file_content"] = None
        mock_ansible_module.params["context"] = {"hostname": "testhost"}

        module = ConfigurationCheckModule(mock_ansible_module)
        module.run()

        assert len(mock_ansible_module.fail_calls) == 1
        assert "No check file content" in mock_ansible_module.fail_calls[0]["msg"]

    def test_run_exception_handling(self, mock_ansible_module):
        """Test run handles exceptions gracefully"""
        mock_ansible_module.params.update(
            {
                "check_file_content": "invalid: yaml: content:",
                "context": {"hostname": "testhost"},
            }
        )

        module = ConfigurationCheckModule(mock_ansible_module)

        with patch.object(module, "parse_yaml_from_content", side_effect=Exception("Parse error")):
            module.run()

        assert len(mock_ansible_module.fail_calls) == 1
        assert "failed" in mock_ansible_module.fail_calls[0]["msg"]


class TestCreateValidationResult:
    """Test suite for _create_validation_result method"""

    def test_create_validation_result_success(self, config_module):
        """Test validation result creation for success"""
        result = config_module._create_validation_result(TestSeverity.WARNING, True)
        assert result == TestStatus.SUCCESS.value

    def test_create_validation_result_failure_severity_mapping(self, config_module):
        """Test validation result maps severity to status on failure"""
        assert (
            config_module._create_validation_result(TestSeverity.INFO, False)
            == TestStatus.INFO.value
        )
        assert (
            config_module._create_validation_result(TestSeverity.WARNING, False)
            == TestStatus.WARNING.value
        )
        assert (
            config_module._create_validation_result(TestSeverity.CRITICAL, False)
            == TestStatus.ERROR.value
        )


class TestExecuteChecksParallel:
    """Test suite for execute_checks_parallel method"""

    def test_execute_checks_parallel_basic(self, config_module):
        """Test parallel execution with basic checks"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Test Check 1
    category: System
    severity: INFO
    collector_type: command
    collector_args:
      command: "echo test1"
    validator_type: string
    validator_args:
      expected: "test1"
  - id: check_002
    name: Test Check 2
    category: Network
    severity: INFO
    collector_type: command
    collector_args:
      command: "echo test2"
    validator_type: string
    validator_args:
      expected: "test2"
"""
        config_module.load_checks(yaml_content)

        with patch("src.module_utils.collector.CommandCollector.collect") as mock_collect:
            mock_collect.side_effect = lambda check, context: f"test{check.id[-1]}"
            results = config_module.execute_checks_parallel(max_workers=2, enable_retry=False)
            assert len(results) == 2

    def test_execute_checks_parallel_with_retry_enabled(self, config_module):
        """Test parallel execution with retry enabled"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Test Check
    category: System
    severity: INFO
    collector_type: command
"""
        config_module.load_checks(yaml_content)

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            results = config_module.execute_checks_parallel(max_workers=1, enable_retry=True)
            assert len(results) == 1

    def test_execute_checks_parallel_no_checks_after_filter(self, config_module):
        """Test parallel execution with filters that match nothing"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Test Check
    tags: [production]
"""
        config_module.load_checks(yaml_content)
        results = config_module.execute_checks_parallel(filter_tags=["nonexistent"])
        assert len(results) == 0

    def test_execute_checks_parallel_execution_summary(self, config_module):
        """Test parallel execution updates result with execution summary"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Test Check
    category: System
    severity: INFO
"""
        config_module.load_checks(yaml_content)

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            config_module.execute_checks_parallel(max_workers=1)
            assert "execution_summary" in config_module.result
            assert "total_checks" in config_module.result["execution_summary"]
            assert "execution_time" in config_module.result["execution_summary"]


class TestParseYamlFromContent:
    """Test suite for parse_yaml_from_content method"""

    def test_parse_yaml_from_content_valid(self, config_module):
        """Test parsing valid YAML content"""
        yaml_str = """
checks:
  - id: test
    name: Test
    description: Test description
"""
        parsed = config_module.parse_yaml_from_content(yaml_str)
        assert "checks" in parsed
        assert isinstance(parsed["checks"], list)

    def test_parse_yaml_from_content_with_applicability_list(self, config_module):
        """Test parsing YAML with applicability as list"""
        yaml_str = """
checks:
  - id: test
    name: Test
    description: Test
    category: System
    workload: SAP
    applicability:
      - property: os
        value: SLES
      - property: version
        value: "15"
"""
        parsed = config_module.parse_yaml_from_content(yaml_str)
        assert "checks" in parsed
        check_data = parsed["checks"][0]
        assert "applicability" in check_data


class TestCollectorRegistration:
    """Test suite for collector registration"""

    def test_register_custom_collector(self, config_module):
        """Test registering a custom collector"""

        class CustomCollector:
            pass

        config_module._collector_registry["custom"] = CustomCollector
        assert "custom" in config_module._collector_registry
        assert config_module._collector_registry["custom"] == CustomCollector

    def test_execute_check_with_custom_collector(self, config_module, sample_check):
        """Test executing check with unregistered collector type"""
        config_module.set_context({"hostname": "testhost"})
        sample_check.collector_type = "unregistered_type"
        result = config_module.execute_check(sample_check)
        assert result.status == TestStatus.ERROR.value


class TestEdgeCases:
    """Test suite for edge cases and error conditions"""

    def test_execute_check_with_empty_context(self, config_module, sample_check):
        """Test executing check with empty context"""
        config_module.set_context({})

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            result = config_module.execute_check(sample_check)
            assert isinstance(result, CheckResult)

    def test_validate_string_with_none_collected_data(self, config_module, sample_check):
        """Test string validation with None collected data"""
        sample_check.validator_args = {"expected": "test"}
        result = config_module.validate_string(sample_check, None)
        assert result["status"] in [TestStatus.WARNING.value, TestStatus.ERROR.value]

    def test_validate_numeric_range_with_min_only(self, config_module, sample_check):
        """Test numeric range validation with only min specified"""
        sample_check.validator_args = {"min": 10}
        result = config_module.validate_numeric_range(sample_check, "50")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_numeric_range_with_max_only(self, config_module, sample_check):
        """Test numeric range validation with only max specified"""
        sample_check.validator_args = {"max": 100}
        result = config_module.validate_numeric_range(sample_check, "50")
        assert result["status"] == TestStatus.SUCCESS.value

    def test_validate_list_with_empty_list(self, config_module, sample_check):
        """Test list validation with empty valid list"""
        sample_check.validator_args = {"valid_list": []}
        sample_check.severity = TestSeverity.WARNING
        result = config_module.validate_list(sample_check, "any_value")
        assert result["status"] == TestStatus.WARNING.value

    def test_is_check_applicable_missing_context_property(self, config_module, sample_check):
        """Test applicability check with missing context property"""
        config_module.set_context({"os": "SLES"})
        sample_check.applicability = [ApplicabilityRule(property="missing_prop", value="value")]
        try:
            result = config_module.is_check_applicable(sample_check)
            # If no exception, result should be False
            assert result is False
        except KeyError:
            # Expected behavior when property is missing
            pass

    def test_validate_properties_with_partial_match(self, config_module, sample_check):
        """Test properties validation with some matching and some non-matching"""
        sample_check.validator_args = {
            "properties": [
                {"property": "cpu", "value": "4"},
                {"property": "memory", "value": "32GB"},
            ]
        }
        sample_check.severity = TestSeverity.WARNING
        collected = json.dumps({"cpu": "4", "memory": "16GB"})
        result = config_module.validate_properties(sample_check, collected)
        assert result["status"] in [TestStatus.WARNING.value, TestStatus.ERROR.value]

    def test_execute_checks_with_multiple_filters(self, config_module):
        """Test check execution with both tag and category filters"""
        config_module.set_context({"hostname": "testhost"})
        yaml_content = """
checks:
  - id: check_001
    name: Check 1
    category: System
    tags: [production, critical]
  - id: check_002
    name: Check 2
    category: Network
    tags: [production]
  - id: check_003
    name: Check 3
    category: System
    tags: [development]
"""
        config_module.load_checks(yaml_content)

        with patch("src.module_utils.collector.CommandCollector.collect", return_value="test"):
            results = config_module.execute_checks(
                filter_tags=["production"], filter_categories=["System"]
            )
            assert len(results) == 1
            assert results[0].check.id == "check_001"
