# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Ansible Python module to check the configuration of the workload system running on Azure
"""

import logging
import time
import json
import re
import sys
from typing import Optional, Dict, Any, List, Type
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.enums import (
        TestStatus,
        TestSeverity,
        Check,
        CheckResult,
        ApplicabilityRule,
    )
    from ansible.module_utils.collector import (
        Collector,
        CommandCollector,
        AzureDataParser,
        ModuleCollector,
    )
    from ansible.module_utils.filesystem_collector import FileSystemCollector
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.enums import (
        TestStatus,
        TestSeverity,
        Check,
        CheckResult,
        ApplicabilityRule,
    )
    from src.module_utils.collector import (
        Collector,
        CommandCollector,
        AzureDataParser,
        ModuleCollector,
    )
    from src.module_utils.filesystem_collector import FileSystemCollector


class ConfigurationCheckModule(SapAutomationQA):
    """
    Class to handle configuration checks using the ConfigurationCheck class.
    """

    def __init__(self, module):
        self.module = module
        self.module_params = module.params
        super().__init__()
        self.checks: List[Check] = []
        self.result.update(
            {
                "check_results": [],
            }
        )
        self.hostname: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.context: Dict[str, Any] = {}
        self._collector_registry = self._init_collector_registry()
        self._validator_registry = self._init_validator_registry()
        self.failure_count = 0
        self.max_failures = 5
        self.last_failure_time = None

    def _init_collector_registry(self) -> Dict[str, Type[Collector]]:
        """
        Initialize collector registry with built-in collectors
        """
        return {
            "command": CommandCollector,
            "azure": AzureDataParser,
            "module": ModuleCollector,
        }

    def _init_validator_registry(self) -> Dict[str, Any]:
        """
        Initialize validator registry with built-in validators
        """
        return {
            "string": self.validate_string,
            "range": self.validate_numeric_range,
            "list": self.validate_list,
            "min_list": self.validate_min_list,
            "check_support": self.validate_vm_support,
            "properties": self.validate_properties,
        }

    def execute_check_with_retry(self, check: Check, max_retries: int = 3) -> CheckResult:
        """
        Execute check with retry logic for enhanced robustness

        :param check: Check to execute
        :type check: Check
        :param max_retries: Maximum number of retry attempts
        :type max_retries: int
        :return: Result of the check execution
        :rtype: CheckResult
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                self.log(
                    logging.DEBUG,
                    f"Executing check {check.id}, attempt {attempt + 1}/{max_retries}",
                )
                return self.execute_check(check)
            except Exception as e:
                last_error = e
                self.log(
                    logging.WARNING, f"Check {check.id} failed on attempt {attempt + 1}: {str(e)}"
                )

                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    self.log(logging.INFO, f"Retrying check {check.id} in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.log(logging.ERROR, f"Check {check.id} failed after {max_retries} attempts")

        return CheckResult(
            check=check,
            status=TestStatus.ERROR,
            hostname=self.hostname or "unknown",
            expected_value=None,
            actual_value=None,
            execution_time=0,
            timestamp=datetime.now(),
            details=f"Check failed after {max_retries} attempts. Last error: {str(last_error)}",
        )

    def build_execution_order(self, checks: List[Check]) -> List[List[Check]]:
        """
        Group checks into execution batches based on dependencies using simple topological sort

        :param checks: List of checks to order
        :type checks: List[Check]
        :return: List of batches that can run in parallel
        :rtype: List[List[Check]]
        """
        check_map = {check.id: check for check in checks}
        batches = []
        remaining_checks = set(check.id for check in checks)

        while remaining_checks:
            ready_checks = []
            for check_id in remaining_checks:
                check = check_map[check_id]
                dependencies = getattr(check, "dependencies", [])
                if not dependencies or not any(dep in remaining_checks for dep in dependencies):
                    ready_checks.append(check)

            if not ready_checks:
                self.log(
                    logging.WARNING,
                    "Potential circular dependency detected, adding remaining checks to batch",
                )
                ready_checks = [check_map[check_id] for check_id in remaining_checks]

            batches.append(ready_checks)
            remaining_checks -= {check.id for check in ready_checks}

        return batches

    def execute_checks_parallel(
        self,
        filter_tags: Optional[List[str]] = None,
        filter_categories: Optional[List[str]] = None,
        max_workers: int = 3,
        enable_retry: bool = True,
    ) -> list:
        """
        Execute checks in parallel batches respecting dependencies

        :param filter_tags: Optional list of tags to filter checks by
        :type filter_tags: Optional[List[str]]
        :param filter_categories: Optional list of categories to filter checks by
        :type filter_categories: Optional[List[str]]
        :param max_workers: Maximum number of parallel workers
        :type max_workers: int
        :param enable_retry: Whether to enable retry mechanism
        :type enable_retry: bool
        :return: List of check results
        :rtype: List[CheckResult]
        """
        checks_to_run = self.checks

        if filter_tags:
            checks_to_run = [
                check for check in checks_to_run if any(tag in check.tags for tag in filter_tags)
            ]

        if filter_categories:
            checks_to_run = [
                check for check in checks_to_run if check.category in filter_categories
            ]

        if not checks_to_run:
            self.log(logging.WARNING, "No checks to execute after applying filters")
            return []

        self.start_time = datetime.now()
        self.log(
            logging.INFO,
            f"Starting parallel execution of {len(checks_to_run)} checks with {max_workers} workers",
        )
        execution_batches = self.build_execution_order(checks_to_run)
        self.log(logging.INFO, f"Organized checks into {len(execution_batches)} execution batches")
        for i, batch in enumerate(execution_batches):
            self.log(
                logging.INFO, f"Batch {i+1}: {len(batch)} checks - {[check.id for check in batch]}"
            )

        results = []
        for batch_idx, batch in enumerate(execution_batches):
            self.log(
                logging.INFO,
                f"Executing batch {batch_idx + 1}/{len(execution_batches)} with {len(batch)} checks",
            )

            actual_workers = min(max_workers, len(batch))
            self.log(logging.INFO, f"Using {actual_workers} workers for batch {batch_idx + 1}")

            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                if enable_retry:
                    futures = [
                        executor.submit(self.execute_check_with_retry, check) for check in batch
                    ]
                else:
                    futures = [executor.submit(self.execute_check, check) for check in batch]

                batch_results = [future.result() for future in futures]
                results.extend(batch_results)
                self.result["check_results"].extend(batch_results)

        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()

        self.log(logging.INFO, f"Parallel execution completed in {duration:.2f} seconds")

        summary = self.get_results_summary()

        self.result.update(
            {
                "status": (
                    TestStatus.SUCCESS.value if summary["failed"] == 0 else TestStatus.ERROR.value
                ),
                "message": f"Parallel execution completed with {summary['failed']} failures",
                "summary": summary,
                "execution_summary": {
                    "total_checks": len(results),
                    "execution_time": duration,
                    "parallel_batches": len(execution_batches),
                    "max_workers": max_workers,
                },
            }
        )

        return results

    def is_check_applicable(self, check: Check) -> bool:
        """
        Check if a check is applicable based on its applicability rules and the current context

        :param check: The check to evaluate
        :type check: Check
        :return: True if applicable, False otherwise
        :rtype: bool
        """
        self.log(
            logging.DEBUG,
            f"Checking applicability for check {check.applicability}",
        )
        for rule in check.applicability:
            context_value = self.context.get(rule.property)
            if not rule.is_applicable(context_value):
                self.log(
                    logging.DEBUG,
                    f"Check {check.id} not applicable: Rule for '{rule.property}' with value "
                    + f"'{rule.value}' doesn't match context value '{context_value}'",
                )
                return False

        return True

    def set_context(self, context: Dict[str, Any]) -> None:
        """
        Set execution context for checks

        :param context: Dictionary containing context variables like OS, version, etc.
        :type context: Dict[str, Any]
        """
        self.context = context
        self.hostname = context.get("hostname")

    def load_checks(self, raw_file_content: str) -> None:
        """
        Load checks from a YAML file.
        Validates the structure and initializes Check objects based on applicability rules.

        :param raw_file_content: Check file content as a string or dictionary
        :type raw_file_content: str or dict
        """
        check_file_content = None

        if isinstance(raw_file_content, str):
            check_file_content = self.parse_yaml_from_content(raw_file_content)

        if not check_file_content:
            self.log(logging.ERROR, "YAML parsing failed: No content found.")
            return

        if "checks" in check_file_content:
            checks = check_file_content.get("checks", [])
        else:
            checks = check_file_content
        if not checks:
            self.log(logging.ERROR, "No checks found in the file.")
            return
        for check in checks:
            if not isinstance(check, dict):
                self.log(logging.ERROR, f"Invalid check format. {check}")
                continue

            applicability_rules = []
            if "applicability" in check and isinstance(check["applicability"], dict):
                for property_name, property_value in check["applicability"].items():
                    applicability_rules.append(
                        ApplicabilityRule(property=property_name, value=property_value)
                    )

            self.checks.append(
                Check(
                    id=check.get("id", "unknown"),
                    name=check.get("name", "Unnamed Check"),
                    description=check.get("description", ""),
                    category=check.get("category", "General"),
                    workload=check.get("workload", "SAP"),
                    severity=TestSeverity(check.get("severity", "WARNING")),
                    collector_type=check.get("collector_type", "command"),
                    collector_args=check.get("collector_args", {}),
                    validator_type=check.get("validator_type", "string"),
                    validator_args=check.get("validator_args", {}),
                    tags=check.get("tags", []),
                    applicability=applicability_rules,
                    references=check.get("references", {}),
                    report=check.get("report", "check"),
                )
            )
        self.log(
            logging.INFO,
            f"Loaded {len(self.checks)} checks from the configuration file.",
        )

    def _create_validation_result(self, severity: TestSeverity, is_success: bool) -> TestStatus:
        """
        Create a validation result based on TestSeverity and success status

        :param severity: TestSeverity of the check
        :type severity: TestSeverity
        :param is_success: Whether the check was successful
        :type is_success: bool
        """
        if is_success:
            return TestStatus.SUCCESS.value

        TestSeverity_map = {
            severity.INFO: TestStatus.INFO.value,
            severity.LOW: TestStatus.WARNING.value,
            severity.WARNING: TestStatus.WARNING.value,
            severity.CRITICAL: TestStatus.ERROR.value,
        }
        return TestSeverity_map.get(severity, TestStatus.ERROR.value)

    def validate_properties(self, check: Check, collected_data: str) -> Dict[str, Any]:
        """
        Validate collected properties against expected properties

        :param check: Check definition
        :type check: Check
        :param collected_data: Collected properties as JSON string
        :type collected_data: str
        :return: Validation result
        :rtype: Dict[str, Any]
        """
        expected_properties = check.validator_args.get("properties", [])
        if not isinstance(expected_properties, list):
            expected_properties = []

        try:
            collected_properties = json.loads(collected_data) if collected_data else {}
        except (json.JSONDecodeError, TypeError):
            return {
                "status": TestStatus.ERROR.value,
            }
        if isinstance(collected_properties, dict) and "error" in collected_properties:
            return {
                "status": TestStatus.ERROR.value,
            }
        is_valid = True
        for prop in expected_properties:
            if not isinstance(prop, dict):
                continue
            if prop.get("property", "") not in collected_properties or str(
                collected_properties[prop.get("property", "")]
            ) != str(prop.get("value", "")):
                is_valid = False
                break
        return {
            "status": self._create_validation_result(check.severity, is_valid),
        }

    def validate_string(self, check: Check, collected_data: str) -> Dict[str, Any]:
        """
        Validate string data against expected values

        :param check: The check definition
        :type check: Check
        :param collected_data: Collected string data
        :type collected_data: str
        :return: Validation result
        :rtype: Dict[str, Any]
        """
        expected = check.validator_args.get("expected") or check.validator_args.get(
            "expected_output", ""
        )
        collected = str(collected_data).strip() if collected_data is not None else ""

        if check.validator_args.get("strip_whitespace", True):
            expected = str(expected).strip()
            expected = re.sub(r"\s+", " ", expected)
            collected = re.sub(r"\s+", " ", collected)

        if check.validator_args.get("case_insensitive", False):
            expected = expected.lower()
            collected = collected.lower()

        return {
            "status": self._create_validation_result(check.severity, collected == expected),
        }

    def validate_numeric_range(self, check: Check, collected_data: str) -> Dict[str, Any]:
        """
        Validate numeric data against expected range

        :param check: The check definition
        :type check: Check
        :param collected_data: Collected numeric data as string
        :type collected_data: str
        :return: Validation result
        :rtype: Dict[str, Any]
        """
        try:
            value = float(str(collected_data).strip())
            min_val = float(check.validator_args.get("min", "-inf"))
            max_val = float(check.validator_args.get("max", "inf"))

            return {
                "status": self._create_validation_result(
                    check.severity, min_val <= value <= max_val
                ),
            }
        except ValueError:
            return {
                "status": TestStatus.ERROR.value,
            }

    def validate_list(self, check: Check, collected_data: str) -> Dict[str, Any]:
        """
        Validate collected data against expected list (contains)

        :param check: Check
        :type check: Check
        :param collected_data: Data collected from system
        :type collected_data: str
        :return: Validation result dictionary
        :rtype: Dict[str, Any]
        """
        expected_list = check.validator_args.get("valid_list", [])
        if not isinstance(expected_list, list):
            expected_list = []
        collected_list = str(collected_data).strip().split(",") if collected_data else []
        collected_list = [item.strip() for item in collected_list]
        return {
            "status": self._create_validation_result(
                check.severity, any(item in expected_list for item in collected_list)
            ),
        }

    def validate_min_list(self, check: Check, collected_data: str) -> Dict[str, Any]:
        """
        Validate that each value in a space-separated list meets or exceeds minimum values.
        Used for kernel parameters like kernel.sem where actual values must be >= minimum required.

        :param check: Check definition containing min_values and separator in validator_args
        :type check: Check
        :param collected_data: Space-separated string of values from system
        :type collected_data: str
        :return: Validation result dictionary
        :rtype: Dict[str, Any]
        """
        min_values = check.validator_args.get("min_values", [])
        separator = check.validator_args.get("separator", " ")
        try:

            if not isinstance(min_values, list):
                return {
                    "status": TestStatus.ERROR.value,
                }

            collected_values = (
                str(collected_data).strip().split(separator) if collected_data else []
            )
            collected_values = [val.strip() for val in collected_values if val.strip()]
            if len(collected_values) != len(min_values):
                return {
                    "status": self._create_validation_result(check.severity, False),
                }
            all_valid = True
            for actual, minimum in zip(collected_values, min_values):
                try:
                    actual_int = int(actual)
                    minimum_int = int(minimum)
                    if actual_int > sys.maxsize or minimum_int > sys.maxsize:
                        continue
                    if actual_int < minimum_int:
                        all_valid = False
                        break
                except (ValueError, OverflowError):
                    all_valid = False
                    break

            return {
                "status": self._create_validation_result(check.severity, all_valid),
            }
        except Exception as ex:
            self.log(logging.ERROR, f"Error while validating min list {ex}")
            return {
                "status": TestStatus.ERROR.value,
            }

    def validate_vm_support(self, check: Check, collected_data: str) -> Dict[str, Any]:
        """
        Validates if a VM SKU is supported for the given role and database type

        :param check: Check definition
        :type check: Check
        :param collected_data: VM SKU from metadata service
        :type collected_data: str
        :return: Validation result
        :rtype: Dict[str, Any]
        """
        try:
            value = collected_data.strip()
            role = self.context.get("role", "")
            database_type = self.context.get("database_type", "")
            validation_rules = check.validator_args.get("validation_rules", {})
            supported_configurations = self.context.get("supported_configurations", {}).get(
                validation_rules, {}
            )

            if not value or not supported_configurations or not role:
                return {
                    "status": TestStatus.ERROR.value,
                }

            if "VMs" in validation_rules:
                if database_type not in supported_configurations.get(value, {}).get(role, {}).get(
                    "SupportedDB", []
                ):
                    return {
                        "status": TestStatus.ERROR.value,
                    }

            elif "OSDB" in validation_rules:
                if role not in supported_configurations.get(
                    database_type, {}
                ) or value.upper() not in supported_configurations.get(database_type, {}).get(
                    role, []
                ):
                    return {
                        "status": TestStatus.ERROR.value,
                    }

            return {
                "status": TestStatus.SUCCESS.value,
            }

        except Exception:
            return {
                "status": TestStatus.ERROR.value,
            }

    def validate_result(self, check: Check, collected_data: Any) -> Dict[str, Any]:
        """
        Validate collected data based on the validator type

        :param check: Check definition
        :type check: Check
        :param collected_data: Data collected from system
        :type collected_data: Any
        :return: Validation result dictionary
        :rtype: Dict[str, Any]
        """
        validator = self._validator_registry.get(check.validator_type)
        if validator:
            return validator(check, collected_data)
        else:
            available = list(self._validator_registry.keys())
            return {
                "status": TestStatus.ERROR.value,
                "details": f"Validator '{check.validator_type}' not found. Available: {available}",
            }

    def execute_check(self, check: Check) -> CheckResult:
        """
        Execute a single check against the current context

        :param check: Check to execute
        :type check: Check
        :return: Result of the check execution
        :rtype: CheckResult
        """

        def create_result(
            status: TestStatus,
            actual_value=None,
            execution_time=0,
            details=None,
        ) -> CheckResult:
            """
            Create a CheckResult object

            :param status: Status of the check execution
            :type status: TestStatus
            :param actual_value: Actual value collected during the check, defaults to None
            :type actual_value: str, optional
            :param execution_time: Time taken to execute the check, defaults to 0
            :type execution_time: int, optional
            :param details: Additional details about the check execution, defaults to None
            :type details: str, optional
            :return: CheckResult object
            :rtype: CheckResult
            """
            expected_value = ""
            if check.validator_type == "range":
                min_val = check.validator_args.get("min", "N/A")
                max_val = check.validator_args.get("max", "N/A")
                expected_value = f"Min: {min_val}, Max: {max_val}"
            elif check.validator_type == "list":
                valid_list = check.validator_args.get("valid_list", [])
                if isinstance(valid_list, list) and valid_list:
                    expected_value = ", ".join(str(v) for v in valid_list)
            elif check.validator_type == "min_list":
                min_values = check.validator_args.get("min_values", [])
                separator = check.validator_args.get("separator", " ")
                if isinstance(min_values, list) and min_values:
                    expected_value = f"Min: {separator.join(str(v) for v in min_values)}"
            elif check.validator_type == "properties":
                props = check.validator_args.get("properties", [])
                if isinstance(props, list) and props:
                    expected_value = ", ".join(
                        [
                            f"{prop.get('name', prop.get('property', ''))}:{prop.get('value', '')}"
                            for prop in props
                            if isinstance(prop, dict)
                        ]
                    )
            else:
                expected_value = check.validator_args.get(
                    "expected", check.validator_args.get("expected_output", "")
                )

            return CheckResult(
                check=check,
                status=status,
                hostname=self.hostname or "unknown",
                expected_value=expected_value,
                actual_value=actual_value,
                execution_time=execution_time,
                timestamp=datetime.now(),
                details=details,
            )

        if not self.is_check_applicable(check):
            return create_result(TestStatus.SKIPPED.value, details="Check not applicable")

        collector_class = self._collector_registry.get(check.collector_type)
        if not collector_class:
            available = list(self._collector_registry.keys())
            return create_result(
                status=TestStatus.ERROR.value,
                details=f"Collector '{check.collector_type}' not found. Available: {available}",
            )

        collector = collector_class(parent=self)
        start_time = time.time()
        try:
            collected_data = collector.collect(check, self.context)
            execution_time = time.time() - start_time
            if check.severity == TestSeverity.INFO:
                return create_result(TestStatus.INFO.value, actual_value=collected_data)
            validation_result = self.validate_result(check, collected_data)
            return create_result(
                status=validation_result["status"],
                actual_value=collected_data,
                execution_time=int(execution_time),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            self.log(logging.ERROR, f"Error executing check {check.id}: {str(e)}")
            return create_result(
                status=TestStatus.ERROR.value,
                actual_value=None,
                execution_time=int(execution_time),
                details=f"Error: {str(e)}",
            )

    def execute_checks(
        self,
        filter_tags: Optional[List[str]] = None,
        filter_categories: Optional[List[str]] = None,
        parallel: bool = False,
        max_workers: int = 3,
        enable_retry: bool = False,
    ) -> list:
        """
        Execute all loaded checks, optionally filtered by tags or categories

        :param filter_tags: Optional list of tags to filter checks by
        :type filter_tags: Optional[List[str]]
        :param filter_categories: Optional list of categories to filter checks by
        :type filter_categories: Optional[List[str]]
        :param parallel: Whether to execute checks in parallel
        :type parallel: bool
        :param max_workers: Maximum number of parallel workers (ignored if parallel=False)
        :type max_workers: int
        :param enable_retry: Whether to enable retry mechanism for failed checks
        :type enable_retry: bool
        :return: List of check results
        :rtype: List[CheckResult]
        """
        if parallel:
            return self.execute_checks_parallel(
                filter_tags=filter_tags,
                filter_categories=filter_categories,
                max_workers=max_workers,
                enable_retry=enable_retry,
            )
        checks_to_run = self.checks

        if filter_tags:
            tag_set = set(filter_tags)
            checks_to_run = [c for c in checks_to_run if any(tag in tag_set for tag in c.tags)]

        if filter_categories:
            category_set = set(filter_categories)
            checks_to_run = [c for c in checks_to_run if c.category in category_set]

        if not checks_to_run:
            self.log(
                logging.WARNING,
                f"No checks match the specified filters: tags={filter_tags}, "
                + f"categories={filter_categories}",
            )
            return list()

        self.start_time = datetime.now()
        self.log(logging.INFO, f"Starting execution of {len(checks_to_run)} checks")

        results = list()
        for check in checks_to_run:
            if enable_retry:
                result = self.execute_check_with_retry(check)
            else:
                result = self.execute_check(check)
            results.append(result)
            self.result["check_results"].append(result)

        self.end_time = datetime.now()

        summary = self.get_results_summary()

        duration = (self.end_time - self.start_time).total_seconds()
        self.log(
            logging.INFO,
            f"Check execution complete. Duration: {duration:.2f}s. "
            f"PASSED: {summary['passed']}, FAILED: {summary['failed']}, "
            f"WARNING: {summary['warnings']},"
            f"SKIPPED: {summary['skipped']}",
        )

        self.result.update(
            {
                "status": (
                    TestStatus.SUCCESS.value if summary["failed"] == 0 else TestStatus.ERROR.value
                ),
                "message": f"Check execution completed with {summary['failed']} failures",
                "summary": summary,
                "check_results": results,
            }
        )
        return results

    def get_results_summary(self) -> Dict[str, int]:
        """
        Get summary statistics for check results

        :return: Dictionary with result summaries
        :rtype: Dict[str, int]
        """
        if not self.result["check_results"]:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "skipped": 0,
                "info": 0,
            }

        return {
            "total": len(self.result["check_results"]),
            "passed": sum(
                1 for r in self.result["check_results"] if r.status == TestStatus.SUCCESS.value
            ),
            "failed": sum(
                1 for r in self.result["check_results"] if r.status == TestStatus.ERROR.value
            ),
            "warnings": sum(
                1 for r in self.result["check_results"] if r.status == TestStatus.WARNING.value
            ),
            "skipped": sum(
                1 for r in self.result["check_results"] if r.status == TestStatus.SKIPPED.value
            ),
            "info": sum(
                1 for r in self.result["check_results"] if r.status == TestStatus.INFO.value
            ),
        }

    def format_results_for_html_report(self):
        """
        Reformat results for HTML report.
        Removes CONTEXT template placeholders to prevent Ansible template evaluation errors.
        """

        def remove_context_templates(value):
            """
            Recursively remove or neutralize CONTEXT template placeholders.
            Replaces {{ CONTEXT.* }} with a safe placeholder to prevent Ansible templating issues.

            :param value: Value to process (str, dict, list, or other)
            :type value: Any
            :return: Value with CONTEXT templates removed
            :rtype: Any
            """
            if isinstance(value, str):
                # Replace {{ CONTEXT.property }} with <CONTEXT.property> to neutralize templates
                return re.sub(
                    r"\{\{\s*CONTEXT\.[^}]+\s*\}\}",
                    lambda m: m.group(0).replace("{{", "<").replace("}}", ">"),
                    value,
                )
            if isinstance(value, dict):
                return {k: remove_context_templates(v) for k, v in value.items()}
            if isinstance(value, list):
                return [remove_context_templates(item) for item in value]
            return value

        serialized_results = []
        for check_result in self.result["check_results"]:
            result_dict = {
                "check": {
                    "id": check_result.check.id,
                    "name": check_result.check.name,
                    "description": check_result.check.description,
                    "category": check_result.check.category,
                    "workload": check_result.check.workload,
                    "severity": (
                        check_result.check.severity.value
                        if hasattr(check_result.check.severity, "value")
                        else str(check_result.check.severity)
                    ),
                    "collector_type": check_result.check.collector_type,
                    "collector_args": remove_context_templates(check_result.check.collector_args),
                    "validator_type": check_result.check.validator_type,
                    "validator_args": remove_context_templates(check_result.check.validator_args),
                    "tags": check_result.check.tags,
                    "references": check_result.check.references,
                    "report": check_result.check.report,
                },
                "status": (
                    check_result.status.value
                    if hasattr(check_result.status, "value")
                    else str(check_result.status)
                ),
                "hostname": check_result.hostname,
                "expected_value": check_result.expected_value,
                "actual_value": check_result.actual_value,
                "execution_time": check_result.execution_time,
                "timestamp": (
                    check_result.timestamp.isoformat()
                    if hasattr(check_result.timestamp, "isoformat")
                    else str(check_result.timestamp)
                ),
                "details": check_result.details,
            }
            serialized_results.append(result_dict)
        self.result["check_results"] = serialized_results

    def run(self):
        """
        Run the module with enhanced error handling and reporting
        """
        execution_start_time = datetime.now()
        try:
            context = self.module_params["context"]
            custom_hostname = self.module_params["hostname"]

            if custom_hostname:
                context["hostname"] = custom_hostname

            self.set_context(context)
            if self.context.get("check_type", {}).get("file_name") in [
                "hana",
                "db2",
                "ascs",
                "app",
            ]:
                temp_context = FileSystemCollector(parent=self).collect(
                    check=None, context=self.context
                )
                self.context.update(temp_context)

            if not self.module_params["check_file_content"]:
                self.module.fail_json(
                    msg="No check file content provided",
                    error_type="CONFIGURATION_ERROR",
                    error_details="Check file content is required but was empty or None",
                )

            self.load_checks(raw_file_content=self.module_params["check_file_content"])
            if not self.checks:
                self.log(logging.WARNING, "No applicable checks found for current context")
                self.result.update(
                    {
                        "status": "SUCCESS",
                        "message": "No applicable checks found for current context",
                        "check_results": [],
                        "summary": {
                            "passed": 0,
                            "failed": 0,
                            "warnings": 0,
                            "skipped": 0,
                            "total": 0,
                        },
                        "execution_warnings": ["No checks matched the current system context"],
                    }
                )
                self.module.exit_json(**self.result)
                return
            self.execute_checks(
                filter_tags=self.module_params["filter_tags"],
                filter_categories=self.module_params["filter_categories"],
                parallel=self.module_params.get("parallel_execution", False),
                max_workers=self.module_params.get("max_workers", 3),
                enable_retry=self.module_params.get("enable_retry", False),
            )
            self.format_results_for_html_report()
            result = dict(self.result)
            execution_end_time = datetime.now()
            execution_duration = (execution_end_time - execution_start_time).total_seconds()

            result.update(
                {
                    "formatted_filesystem_info": self.context.get("formatted_filesystem_info", {}),
                    "azure_disks_info": self.context.get("azure_disks_info", []),
                    "lvm_groups_info": self.context.get("lvm_groups_info", []),
                    "lvm_volumes_info": self.context.get("lvm_volumes_info", []),
                    "anf_volumes_info": self.context.get("anf_volumes_info", []),
                    "execution_metadata": {
                        "start_time": execution_start_time.isoformat(),
                        "end_time": execution_end_time.isoformat(),
                        "duration_seconds": execution_duration,
                        "total_checks_attempted": len(self.checks),
                        "checks_completed": len(result.get("check_results", [])),
                        "python_module_version": "1.0.0",
                        "execution_mode": (
                            "parallel"
                            if self.module_params.get("parallel_execution", False)
                            else "sequential"
                        ),
                    },
                }
            )

            if "summary" in result:
                summary = dict(result["summary"])
                result["summary"] = summary
            self.module.exit_json(**result)
        except Exception as e:
            execution_end_time = datetime.now()
            execution_duration = (execution_end_time - execution_start_time).total_seconds()

            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "execution_duration": execution_duration,
                "module_params": {
                    k: v for k, v in self.module_params.items() if k != "check_file_content"
                },
                "checks_loaded": len(self.checks) if hasattr(self, "checks") else 0,
                "timestamp": datetime.now().isoformat(),
            }
            partial_results = self.result.get("check_results", [])
            if partial_results:
                error_details["partial_results_available"] = True
                error_details["completed_checks"] = len(partial_results)

            self.module.fail_json(
                msg=f"Configuration check execution failed: {str(e)}",
                error_details=error_details,
                **self.result,
            )


def main():
    """
    Main function to run the Ansible module
    """
    module_args = dict(
        check_file_content=dict(type="str", required=True),
        context=dict(type="dict", required=True),
        filter_tags=dict(type="list", elements="str", required=False, default=None),
        filter_categories=dict(type="list", elements="str", required=False, default=None),
        parallel_execution=dict(type="bool", required=False, default=False),
        max_workers=dict(type="int", required=False, default=3),
        enable_retry=dict(type="bool", required=False, default=False),
        workspace_directory=dict(type="str", required=True),
        hostname=dict(type="str", required=False, default=None),
        test_group_invocation_id=dict(type="str", required=True),
        test_group_name=dict(type="str", required=True),
        azure_resources=dict(type="dict", required=False, default={}),
    )
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    runner = ConfigurationCheckModule(module)
    runner.run()


if __name__ == "__main__":
    main()
