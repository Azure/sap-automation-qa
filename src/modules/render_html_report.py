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
from ansible.module_utils.basic import AnsibleModule
import jinja2

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus


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

    def read_log_file(self) -> List[Dict[str, Any]]:
        """
        Reads the log file and returns the test case results.

        :return: A list of test case results.
        :rtype: list
        """
        log_file_path = os.path.join(
            self.workspace_directory, "logs", f"{self.test_group_invocation_id}.log"
        )
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            return [json.loads(line) for line in log_file.readlines()]

    def render_report(self, test_case_results: List[Dict[str, Any]]) -> None:
        """
        Renders the HTML report using the provided template and test case results.

        :param test_case_results: A list of test case results.
        :type test_case_results: list
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
                        }
                    )
                )
            self.result["report_path"] = report_path
            self.result["status"] = TestStatus.SUCCESS.value
        except Exception as e:
            self.handle_error(e)


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
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    renderer = HTMLReportRenderer(
        test_group_invocation_id=module.params["test_group_invocation_id"],
        test_group_name=module.params["test_group_name"],
        report_template=module.params["report_template"],
        workspace_directory=module.params["workspace_directory"],
    )

    test_case_results = renderer.read_log_file()
    renderer.render_report(test_case_results)

    if renderer.result["status"] != TestStatus.SUCCESS.value:
        module.fail_json(msg="Failed to render report", **renderer.get_result())

    module.exit_json(**renderer.get_result())


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
