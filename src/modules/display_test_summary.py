# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Module to display a summary of test results at the end of playbook execution.
Shows aggregated pass/fail/info counts per test case, and for ha-config tests
displays specific FAILED parameters.
"""

import json
import logging
import os
from collections import defaultdict
from typing import Dict, Any, List, Optional
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.enums import TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.enums import TestStatus

DOCUMENTATION = r"""
---
module: display_test_summary
short_description: Display test result summary at end of playbook
description:
    - Reads test results from the log file for a given invocation
    - Displays aggregated PASSED/FAILED/INFO counts per test case
    - For ha-config (HA Parameters Validation) test cases, lists
      specific FAILED parameters with category, name, actual and
      expected values
options:
    test_group_invocation_id:
        description:
            - Unique identifier for the test group invocation
            - Used to locate the corresponding log file
        type: str
        required: true
    workspace_directory:
        description:
            - Base directory where logs are stored
            - Expects logs in {workspace_directory}/logs/
        type: str
        required: true
author:
    - Microsoft Corporation
notes:
    - Log files should be in JSON format, one JSON object per line
    - Each line represents a test case result with TestCaseDetails
requirements:
    - python >= 3.10
"""

EXAMPLES = r"""
- name: Display test summary after all tests complete
  display_test_summary:
    test_group_invocation_id: "{{ test_group_invocation_id }}"
    workspace_directory: "{{ _workspace_directory }}"
  register: test_summary

- name: Show summary output
  debug:
    msg: "{{ test_summary.summary }}"
"""

RETURN = r"""
status:
    description: Status of the summary generation
    returned: always
    type: str
    sample: "PASSED"
summary:
    description: Formatted summary string for display
    returned: always
    type: str
overall_status:
    description: Overall test group status (PASSED, WARNING, or FAILED)
    returned: always
    type: str
test_cases:
    description: List of per-test-case summary dicts
    returned: always
    type: list
    elements: dict
failed_parameters:
    description: >
        List of dicts for FAILED parameters across all
        ha-config test cases
    returned: always
    type: list
    elements: dict
message:
    description: Error message if summary generation failed
    returned: on failure
    type: str
"""

_HA_CONFIG_TEST_NAME = "HA Parameters Validation"
_SEPARATOR = "-" * 72
_HEADER = "=" * 72


class TestSummaryDisplay(SapAutomationQA):
    """
    Reads test-group log files and produces a human-readable
    summary of results, highlighting failures for ha-config tests.
    """

    def __init__(
        self,
        test_group_invocation_id: str,
        workspace_directory: str,
    ):
        super().__init__()
        self.test_group_invocation_id = test_group_invocation_id
        self.workspace_directory = workspace_directory
        self.result.update(
            {
                "status": None,
                "summary": "",
                "overall_status": "",
                "test_cases": [],
                "failed_parameters": [],
            }
        )

    def _read_log_file(self) -> List[Dict[str, Any]]:
        """
        Read and parse the JSONL log file.

        :return: Parsed test-case result dicts.
        :rtype: list[dict]
        """
        log_path = os.path.join(
            self.workspace_directory,
            "logs",
            f"{self.test_group_invocation_id}.log",
        )
        try:
            with open(log_path, "r", encoding="utf-8") as fh:
                results: List[Dict[str, Any]] = []
                for line_num, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        self.log(
                            logging.WARNING,
                            f"Invalid JSON on line {line_num}: {exc}",
                        )
                return results
        except FileNotFoundError as exc:
            self.log(logging.ERROR, f"Log file not found: {log_path}")
            self.handle_error(exc)
            return []

    @staticmethod
    def _deduplicate_results(
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        De-duplicate test case results by (TestCaseName, TestCaseHostname).
        Keeps the last occurrence (latest write wins).

        :param results: Raw parsed log entries.
        :return: De-duplicated entries.
        """
        seen: Dict[tuple, Dict[str, Any]] = {}
        for entry in results:
            key = (
                entry.get("TestCaseName", ""),
                entry.get("TestCaseHostname", ""),
            )
            seen[key] = entry
        return list(seen.values())

    @staticmethod
    def _extract_failed_parameters(
        entry: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """
        Pull FAILED parameters from a ha-config test entry.

        :param entry: A single test-case log entry.
        :return: List of dicts with category / name / value / expected.
        """
        details = entry.get("TestCaseDetails", {})
        if not isinstance(details, dict):
            return []
        params = details.get("parameters", [])
        failures: List[Dict[str, str]] = []
        for param in params:
            if param.get("status") == TestStatus.ERROR.value:
                failures.append(
                    {
                        "category": param.get("category", ""),
                        "name": param.get("name", ""),
                        "value": param.get("value", ""),
                        "expected_value": param.get("expected_value", ""),
                        "id": param.get("id", ""),
                    }
                )
        return failures

    @staticmethod
    def _status_icon(status: str) -> str:
        """Map a test status string to a display icon.

        :param status: One of PASSED, WARNING, FAILED.
        :return: Bracketed icon string.
        """
        if status == TestStatus.SUCCESS.value:
            return "[PASS]"
        if status == TestStatus.WARNING.value:
            return "[WARN]"
        return "[FAIL]"

    @classmethod
    def _format_summary(
        cls,
        test_case_summaries: List[Dict[str, Any]],
        failed_params: List[Dict[str, str]],
        overall_status: str,
    ) -> str:
        """Build a multi-line human-readable summary string.

        :param test_case_summaries: Per-test-case aggregated stats.
        :param failed_params: Global list of FAILED ha-config params.
        :param overall_status: PASSED, WARNING, or FAILED.
        :return: Formatted string.
        """
        lines: List[str] = [
            "",
            _HEADER,
            "  TEST EXECUTION SUMMARY",
            _HEADER,
        ]

        for tc in test_case_summaries:
            icon = cls._status_icon(tc["status"])
            lines.append(f"  {icon}  {tc['test_name']}")
            lines.append(
                f"          Hosts: {tc['host_count']}  |  "
                f"Passed: {tc['passed']}  |  "
                f"Warned: {tc.get('warned', 0)}  |  "
                f"Failed: {tc['failed']}  |  "
                f"Info: {tc['info']}"
            )
            lines.append(_SEPARATOR)

        if failed_params:
            lines.append("")
            lines.append("  FAILED PARAMETERS  (HA Parameters Validation)")
            lines.append(_SEPARATOR)
            for fp in failed_params:
                lines.append(f"    - {fp['name']}")
                lines.append(f"      Category : {fp['category']}")
                lines.append(f"      Actual   : {fp['value']}")
                lines.append(f"      Expected : {fp['expected_value']}")
            lines.append(_SEPARATOR)

        lines.append("")
        overall_icon = cls._status_icon(overall_status)
        lines.append(f"  OVERALL: {overall_icon}  {overall_status}")
        lines.append(_HEADER)
        lines.append("")

        return "\n".join(lines)

    def generate_summary(self) -> None:
        """
        Read log file, aggregate results, and populate self.result
        with summary data.
        """
        raw_results = self._read_log_file()
        if not raw_results:
            self.result["status"] = TestStatus.WARNING.value
            self.result["summary"] = "No test results found."
            self.result["overall_status"] = TestStatus.WARNING.value
            return

        entries = self._deduplicate_results(raw_results)

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            tc_name = entry.get("TestCaseName", "Unknown")
            grouped[tc_name].append(entry)

        test_case_summaries: List[Dict[str, Any]] = []
        all_failed_params: List[Dict[str, str]] = []
        has_failure = False
        has_warning = False

        for tc_name, tc_entries in grouped.items():
            passed = failed = info = warned = 0
            tc_status = TestStatus.SUCCESS.value

            has_parameters = False

            for entry in tc_entries:
                entry_status = entry.get("TestCaseStatus", TestStatus.SUCCESS.value)
                if entry_status == TestStatus.ERROR.value:
                    tc_status = TestStatus.ERROR.value
                    has_failure = True
                elif entry_status == TestStatus.WARNING.value:
                    if tc_status != TestStatus.ERROR.value:
                        tc_status = TestStatus.WARNING.value
                    has_warning = True

                details = entry.get("TestCaseDetails", {})
                if not isinstance(details, dict):
                    details = {}
                params = details.get("parameters", [])
                if params:
                    has_parameters = True
                for param in params:
                    pstatus = param.get("status", "")
                    if pstatus == TestStatus.SUCCESS.value:
                        passed += 1
                    elif pstatus == TestStatus.ERROR.value:
                        failed += 1
                    elif pstatus == TestStatus.WARNING.value:
                        warned += 1
                    elif pstatus == TestStatus.INFO.value:
                        info += 1

                if tc_name == _HA_CONFIG_TEST_NAME:
                    all_failed_params.extend(self._extract_failed_parameters(entry))

            if not has_parameters:
                for entry in tc_entries:
                    host_status = entry.get("TestCaseStatus", TestStatus.SUCCESS.value)
                    if host_status == TestStatus.SUCCESS.value:
                        passed += 1
                    elif host_status == TestStatus.ERROR.value:
                        failed += 1
                    elif host_status == TestStatus.WARNING.value:
                        warned += 1
                    elif host_status == TestStatus.INFO.value:
                        info += 1

            test_case_summaries.append(
                {
                    "test_name": tc_name,
                    "status": tc_status,
                    "host_count": len(tc_entries),
                    "passed": passed,
                    "failed": failed,
                    "warned": warned,
                    "info": info,
                }
            )

        seen_failures: set = set()
        unique_failures: List[Dict[str, str]] = []
        for fp in all_failed_params:
            key = (fp["category"], fp["name"])
            if key not in seen_failures:
                seen_failures.add(key)
                unique_failures.append(fp)

        if has_failure:
            overall = TestStatus.ERROR.value
        elif has_warning:
            overall = TestStatus.WARNING.value
        else:
            overall = TestStatus.SUCCESS.value

        summary_text = self._format_summary(test_case_summaries, unique_failures, overall)

        self.result["status"] = overall
        self.result["summary"] = summary_text
        self.result["overall_status"] = overall
        self.result["test_cases"] = test_case_summaries
        self.result["failed_parameters"] = unique_failures


def run_module() -> None:
    """
    Entry point for the Ansible module.
    """
    module_args = dict(
        test_group_invocation_id=dict(type="str", required=True),
        workspace_directory=dict(type="str", required=True),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    display = TestSummaryDisplay(
        test_group_invocation_id=module.params["test_group_invocation_id"],
        workspace_directory=module.params["workspace_directory"],
    )
    display.generate_summary()
    module.exit_json(**display.get_result())


def main() -> None:
    """Entry point."""
    run_module()


if __name__ == "__main__":
    main()
