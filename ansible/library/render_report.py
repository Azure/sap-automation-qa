"""Module to render the HTML report for the test group invocation.
"""

from datetime import datetime
from ansible.module_utils.basic import AnsibleModule
import json
from datetime import datetime
import jinja2


def run_module():
    """
    This function is the entry point for the Ansible module.
    It renders a report using a provided template and test case results.

    :return: None
    """
    module_args = dict(
        test_group_invocation_id=dict(type="str", required=True),
        test_group_name=dict(type="str", required=True),
        report_template=dict(type="str", required=True),
        workspace_directory=dict(type="str", required=True),
    )
    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    result = {
        "changed": False,
        "report_path": None,
        "status": None,
        "start": datetime.now(),
        "end": datetime.now(),
    }
    workspace_directory = module.params["workspace_directory"]
    test_group_invocation_id = module.params["test_group_invocation_id"]
    test_group_name = module.params["test_group_name"]
    report_path = f"{workspace_directory}/quality_assurance/{test_group_name}_{test_group_invocation_id}.html"
    try:
        # Read the log file
        with open(
            f"{workspace_directory}/logs/{test_group_invocation_id}.log", "r"
        ) as log_file:
            test_case_results = [json.loads(line) for line in log_file.readlines()]

        # Load the template and render the report with the test case results
        template_content = jinja2.Template(module.params["report_template"])
        with open(f"{report_path}", "w") as report_file:
            report_file.write(
                template_content.render({"test_case_results": test_case_results})
            )
        result["report_path"] = report_path
        result["status"] = "Report rendered successfully"
    except Exception as e:
        result["status"] = str(e)
        module.fail_json(msg="Failed to render report", **result)
    module.exit_json(**result)


if __name__ == "__main__":
    run_module()
