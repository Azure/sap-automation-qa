# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for formatting the packages list
"""

from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule


PACKAGE_LIST = [
    {"name": "Corosync Lib", "key": "corosynclib"},
    {"name": "Corosync", "key": "corosync"},
    {"name": "Fence Agents Common", "key": "fence-agents-common"},
    {"name": "Fencing Agent", "key": "fence-agents-azure-arm"},
    {"name": "Pacemaker CLI", "key": "pacemaker-cli"},
    {"name": "Pacemaker Libs", "key": "pacemaker-libs"},
    {"name": "Pacemaker Schemas", "key": "pacemaker-schemas"},
    {"name": "Pacemaker", "key": "pacemaker"},
    {"name": "Resource Agent", "key": "resource-agents"},
    {"name": "SAP Cluster Connector", "key": "sap-cluster-connector"},
    {"name": "SAPHanaSR", "key": "SAPHanaSR"},
    {"name": "Socat", "key": "socat"},
]


class PackageListFormatter:
    """
    Class to format the package list based on the provided package facts list.
    """

    def __init__(self, package_facts_list: Dict[str, Any]):
        self.package_facts_list = package_facts_list
        self.result = {
            "changed": False,
            "packages_list": [],
            "msg": "",
        }

    def format_packages(self) -> Dict[str, Any]:
        """
        Formats the package list based on the provided package facts list.

        :return: A dictionary containing the formatted package list.
        """
        self.result["packages_list"] = [
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

        return self.result


def main() -> None:
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


if __name__ == "__main__":
    main()
