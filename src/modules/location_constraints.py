# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for location constraints
"""

import xml.etree.ElementTree as ET
from typing import List
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.facts.compat import ansible_facts

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA
    from ansible.module_utils.commands import RSC_CLEAR, CONSTRAINTS
    from ansible.module_utils.enums import OperatingSystemFamily, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA
    from src.module_utils.commands import RSC_CLEAR, CONSTRAINTS
    from src.module_utils.enums import OperatingSystemFamily, TestStatus


DOCUMENTATION = r"""
---
module: location_constraints
short_description: Manages pacemaker location constraints
description:
    - This module manages location constraints in a pacemaker cluster
    - Can check for existing location constraints
    - Can remove location constraints to enable proper cluster resource movement
options:
    action:
        description:
            - The action to perform on location constraints
            - Currently supported action is 'remove'
        type: str
        required: true
        choices: ['remove']
author:
    - Microsoft Corporation
notes:
    - This module requires root privileges to execute cluster management commands
    - Uses the crm_resource command to clear location constraints
    - XML processing is used to parse cluster configuration
requirements:
    - python >= 3.6
    - pacemaker cluster environment
"""

EXAMPLES = r"""
- name: Remove all location constraints
  location_constraints:
    action: "remove"
  register: constraints_result

- name: Display constraint removal results
  debug:
    msg: "Constraints removed: {{ constraints_result.location_constraint_removed }}"
"""

RETURN = r"""
status:
    description: Status of the operation
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Descriptive message about the operation
    returned: always
    type: str
    sample: "Location constraints removed"
location_constraint_removed:
    description: Whether any location constraints were removed
    returned: always
    type: bool
    sample: true
details:
    description: Output from the command execution
    returned: always
    type: str
    sample: "<constraints>...</constraints>"
changed:
    description: Whether the module made any changes
    returned: always
    type: bool
    sample: true
"""


class LocationConstraintsManager(SapAutomationQA):
    """
    Class to manage the location constraints in a pacemaker cluster.
    """

    def __init__(self, ansible_os_family: OperatingSystemFamily):
        super().__init__()
        self.ansible_os_family = ansible_os_family
        self.result.update(
            {
                "location_constraint_removed": False,
            }
        )

    def remove_location_constraints(self, location_constraints: List[ET.Element]) -> None:
        """
        Removes the specified location constraints.

        :param location_constraints: A list of location constraints to be removed.
        :type location_constraints: List[ET.Element]
        """
        for location_constraint in location_constraints:
            rsc = location_constraint.attrib.get("rsc")
            if rsc:
                command_output = self.execute_command_subprocess(
                    RSC_CLEAR[self.ansible_os_family](rsc)
                )
                self.result.update(
                    {
                        "details": command_output,
                        "changed": True,
                    }
                )
            else:
                self.result["changed"] = False

    def location_constraints_exists(self) -> List[ET.Element]:
        """
        Checks if location constraints exist.

        :return: A list of location constraints if they exist, otherwise an empty list.
        :rtype: List[ET.Element]
        """
        try:
            xml_output = self.execute_command_subprocess(CONSTRAINTS)
            self.result["details"] = xml_output
            return ET.fromstring(xml_output).findall(".//rsc_location") if xml_output else []
        except Exception as ex:
            self.handle_error(ex)
        return []


def run_module() -> None:
    """
    Entry point of the module.
    Sets up and runs the location constraints module with the specified arguments.
    """
    module_args = dict(
        action=dict(type="str", required=True),
        filter=dict(type="str", required=False, default="os_family"),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    action = module.params["action"]

    manager = LocationConstraintsManager(
        ansible_os_family=OperatingSystemFamily(
            str(ansible_facts(module).get("os_family", "UNKNOWN")).upper()
        )
    )

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

    module.exit_json(**manager.get_result())


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
