# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Module to render the HTML report for the test group invocation.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List
import jinja2
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.enums import TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.enums import TestStatus

DOCUMENTATION = r"""
---
module: render_html_report
short_description: Renders HTML reports for SAP automation test results
description:
    - This module generates HTML reports from test results log files
    - Uses Jinja2 templates to format test results into readable HTML
    - Creates report files in the specified workspace directory
options:
    test_group_invocation_id:
        description:
            - Unique identifier for the test group invocation
            - Used to locate the corresponding log file
        type: str
        required: true
    test_group_name:
        description:
            - Name of the test group
            - Used as part of the generated report filename
        type: str
        required: true
    report_template:
        description:
            - Jinja2 HTML template content for rendering the report
            - Should support test_case_results and report_generation_time variables
        type: str
        required: true
    workspace_directory:
        description:
            - Base directory where logs are stored and reports will be generated
            - Reports will be created in {workspace_directory}/quality_assurance/
        type: str
        required: true
    framework_version:
        description:
            - Version of the SAP Automation QA framework
        type: str
        required: false
author:
    - Microsoft Corporation
notes:
    - Log files should be in JSON format, one JSON object per line
    - Requires jinja2 module for template rendering
    - Creates directory structure if it doesn't exist
requirements:
    - python >= 3.6
    - jinja2
"""

EXAMPLES = r"""
- name: Generate HTML report for SAP HANA test group
  render_html_report:
    test_group_invocation_id: "20230101-120000"
    test_group_name: "hana_cluster_validation"
    report_template: "{{ lookup('file', 'templates/report_template.html') }}"
    workspace_directory: "/var/log/sap-automation-qa"
    framework_version: "1.0.0"
  register: report_result

- name: Show path to generated report
  debug:
    msg: "HTML report generated at {{ report_result.report_path }}"

- name: Fail if report generation failed
  fail:
    msg: "Failed to generate test report"
  when: report_result.status != 'SUCCESS'
"""

RETURN = r"""
status:
    description: Status of the report generation
    returned: always
    type: str
    sample: "SUCCESS"
report_path:
    description: Path to the generated HTML report
    returned: on success
    type: str
    sample: "/var/log/sap-automation-qa/quality_assurance/hana_cluster_validation_20230101-120000.html"
message:
    description: Error message if report generation failed
    returned: on failure
    type: str
    sample: "Log file not found"
"""


class HTMLReportRenderer(SapAutomationQA):
    """
    Class to render the HTML report for the test group invocation.
    """

    def __init__(
        self,
        test_group_invocation_id: str,
        test_group_name: str,
        report_template: str,
        workspace_directory: str,
        test_case_results: List[Dict[str, Any]] = [],
        system_info: Dict[str, Any] = {},
        framework_version: str = "unknown",
    ):
        super().__init__()
        self.test_group_invocation_id = test_group_invocation_id
        self.test_group_name = test_group_name
        self.report_template = report_template
        self.workspace_directory = workspace_directory
        self.result.update(
            {
                "status": None,
            }
        )
        self.test_case_results = test_case_results or []
        self.system_info = system_info or {}
        self.framework_version = framework_version

    def read_log_file(self) -> List[Dict[str, Any]]:
        """
        Reads the log file and returns the test case results.

        :return: A list of test case results.
        :rtype: List[Dict[str, Any]]
        """
        log_file_path = os.path.join(
            self.workspace_directory, "logs", f"{self.test_group_invocation_id}.log"
        )
        try:
            with open(log_file_path, "r", encoding="utf-8") as log_file:
                results = []
                for line_num, line in enumerate(log_file.readlines(), 1):
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError as json_ex:
                        self.log(
                            logging.WARNING,
                            f"Invalid JSON on line {line_num} in {log_file_path}: {json_ex}",
                        )
                        continue
                return results
        except FileNotFoundError as ex:
            self.log(
                logging.ERROR,
                f"Log file {log_file_path} not found.",
            )
            self.handle_error(ex)
            return []

    def render_report(self, test_case_results: List[Dict[str, Any]]) -> None:
        """
        Renders the HTML report using the provided template and test case results.

        :param test_case_results: A list of test case results.
        :type test_case_results: List[Dict[str, Any]]
        """
        try:
            report_path = os.path.join(
                self.workspace_directory,
                "quality_assurance",
                f"{self.test_group_name}_{self.test_group_invocation_id}.html",
            )
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            template = jinja2.Template(self.report_template)
            with open(report_path, "w", encoding="utf-8") as report_file:
                report_file.write(
                    template.render(
                        {
                            "test_case_results": test_case_results,
                            "report_generation_time": datetime.now().strftime(
                                "%m/%d/%Y, %I:%M:%S %p"
                            ),
                            "system_info": self.system_info,
                            "framework_version": self.framework_version,
                        }
                    )
                )
            self.result["report_path"] = report_path
            self.result["status"] = TestStatus.SUCCESS.value
        except Exception as ex:
            self.handle_error(ex)


def run_module() -> None:
    """
    Entry point of the module.
    Sets up and runs the HTML report rendering module with the specified arguments.
    """
    module_args = dict(
        test_group_invocation_id=dict(type="str", required=True),
        test_group_name=dict(type="str", required=True),
        report_template=dict(type="str", required=True),
        workspace_directory=dict(type="str", required=True),
        test_case_results=dict(type="list", required=False),
        system_info=dict(type="dict", required=False),
        framework_version=dict(type="str", required=False),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    renderer = HTMLReportRenderer(
        test_group_invocation_id=module.params["test_group_invocation_id"],
        test_group_name=module.params["test_group_name"],
        report_template=module.params["report_template"],
        workspace_directory=module.params["workspace_directory"],
        test_case_results=module.params.get("test_case_results", []),
        system_info=module.params.get("system_info", {}),
        framework_version=module.params.get("framework_version", "unknown"),
    )

    test_case_results = (
        renderer.read_log_file() if not renderer.test_case_results else renderer.test_case_results
    )
    renderer.render_report(test_case_results)

    module.exit_json(**renderer.get_result())


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
