# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for location constraints
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus


class LocationConstraintsManager(SapAutomationQA):
    """
    Class to manage the location constraints in a pacemaker cluster.
    """

    def __init__(self, ansible_os_family: str):
        super().__init__()
        self.ansible_os_family = ansible_os_family
        self.module_name = {
            "SUSE": "crm",
            "REDHAT": "pcs",
        }
        self.result.update(
            {
                "location_constraint_removed": False,
            }
        )

    def remove_location_constraints(
        self, location_constraints: List[ET.Element]
    ) -> None:
        """
        Removes the specified location constraints.

        :param location_constraints: A list of location constraints to be removed.
        :type location_constraints: list
        """
        for location_constraint in location_constraints:
            rsc = location_constraint.attrib.get("rsc")
            if rsc:
                cmd = [
                    self.module_name[self.ansible_os_family],
                    "resource",
                    "clear",
                    rsc,
                ]
                self.execute_command_subprocess(cmd)
                self.result["changed"] = True
            else:
                self.result["changed"] = False

    def location_constraints_exists(self) -> List[ET.Element]:
        """
        Checks if location constraints exist.

        :return: A list of location constraints if they exist, otherwise an empty list.
        :rtype: list
        """
        try:
            xml_output = self.execute_command_subprocess(
                ["cibadmin", "--query", "--scope", "constraints"]
            )
            return (
                ET.fromstring(xml_output).findall(".//rsc_location")
                if xml_output
                else []
            )
        except Exception as e:
            self.handle_exception(e)

    def get_result(self) -> Dict[str, Any]:
        """
        Returns the result dictionary.

        :return: The result dictionary containing the status of the operation.
        :rtype: dict
        """
        return self.result


def run_module() -> None:
    """
    Entry point of the module.
    Sets up and runs the location constraints module with the specified arguments.
    """
    module_args = dict(
        action=dict(type="str", required=True),
        ansible_os_family=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    action = module.params["action"]
    ansible_os_family = module.params["ansible_os_family"]

    manager = LocationConstraintsManager(ansible_os_family)

    if module.check_mode:
        module.exit_json(**manager.get_result())

    location_constraints = manager.location_constraints_exists()
    if location_constraints and action == "remove":
        manager.remove_location_constraints(location_constraints)
        manager.result.update(
            {
                "message": "Location constraints removed",
                "location_constraint_removed": True,
                "status": TestStatus.SUCCESS.value,
            }
        )
    else:
        manager.result.update(
            {
                "status": TestStatus.INFO.value,
                "message": "Location constraints do not exist or were already removed.",
            }
        )

    if manager.result["status"] == TestStatus.ERROR.value:
        module.fail_json(
            msg="Failed to remove the location constraints", **manager.get_result()
        )

    module.exit_json(**manager.get_result())


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
