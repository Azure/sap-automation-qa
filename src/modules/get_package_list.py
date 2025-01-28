# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for formatting the packages list
"""

from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from ansible.module_utils.db_cluster_constants import PACKAGE_LIST
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from src.module_utils.db_cluster_constants import PACKAGE_LIST


class PackageListFormatter(SapAutomationQA):
    """
    Class to format the package list based on the provided package facts list.
    """

    def __init__(self, package_facts_list: Dict[str, Any]):
        super().__init__()
        self.package_facts_list = package_facts_list

    def format_packages(self) -> Dict[str, Any]:
        """
        Formats the package list based on the provided package facts list.

        :return: A dictionary containing the formatted package list.
        """
        try:
            self.result["details"] = [
                {
                    package["name"]: {
                        "version": self.package_facts_list[package["key"]][0].get(
                            "version"
                        ),
                        "release": self.package_facts_list[package["key"]][0].get(
                            "release"
                        ),
                        "architecture": self.package_facts_list[package["key"]][0].get(
                            "arch"
                        ),
                    }
                }
                for package in PACKAGE_LIST
                if package["key"] in self.package_facts_list
            ]
        except Exception as e:
            self.handle_error(e)
        self.result["status"] = TestStatus.SUCCESS.value
        return self.result


def run_module() -> None:
    """
    Entry point of the module.
    """
    module_args = dict(
        package_facts_list=dict(type="dict", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    package_facts_list = module.params["package_facts_list"]

    formatter = PackageListFormatter(package_facts_list)
    result = formatter.format_packages()

    module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
