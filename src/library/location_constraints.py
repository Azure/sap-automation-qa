# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Custom ansible module for location constraints
"""

import subprocess
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from ansible.module_utils.basic import AnsibleModule


class LocationConstraintsManager:
    """
    Class to manage the location constraints in a pacemaker cluster.
    """

    def __init__(self, ansible_os_family: str):
        self.ansible_os_family = ansible_os_family
        self.module_name = {
            "SUSE": "crm",
            "REDHAT": "pcs",
        }
        self.result = {
            "changed": False,
            "location_constraint_removed": False,
            "stdout": "",
            "msg": "",
        }

    def _run_command(self, cmd: List[str]) -> str:
        """
        Executes a command and returns the output.

        :param cmd: The command to be executed.
        :type cmd: list
        :return: The output of the command.
        :rtype: str
        """
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        ) as proc:
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    proc.returncode, cmd, output=stdout, stderr=stderr
                )
            return stdout

    def remove_location_constraints(
        self, location_constraints: List[ET.Element]
    ) -> None:
        """
        Removes the specified location constraints.

        :param location_constraints: A list of location constraints to be removed.
        :type location_constraints: list
        """
        for location_constraint in location_constraints:
            if location_constraint.attrib.get("rsc") is not None:
                cmd = [
                    self.module_name[self.ansible_os_family],
                    "resource",
                    "clear",
                    location_constraint.attrib["rsc"],
                ]
                self._run_command(cmd)
                self.result["location_constraint_removed"] = True

    def location_constraints_exists(self) -> List[ET.Element]:
        """
        Checks if location constraints exist.

        :return: A list of location constraints if they exist, otherwise an empty list.
        :rtype: list
        """
        xml_output = self._run_command(
            ["cibadmin", "--query", "--scope", "constraints"]
        )
        constraints = (
            ET.fromstring(xml_output).findall(".//rsc_location") if xml_output else None
        )
        return constraints if constraints is not None else []

    def get_result(self) -> Dict[str, Any]:
        """
        Returns the result dictionary.

        :return: The result dictionary containing the status of the operation.
        :rtype: dict
        """
        return self.result


def main() -> None:
    """
    Entry point of the script.
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

    try:
        location_constraints = manager.location_constraints_exists()
        if location_constraints and action == "remove":
            manager.remove_location_constraints(location_constraints)
            manager.result["changed"] = True
            manager.result["msg"] = "Location constraints removed"
        else:
            manager.result["msg"] = (
                "Location constraints do not exist or were already removed."
            )
    except Exception as e:
        module.fail_json(msg=str(e))

    module.exit_json(**manager.get_result())


if __name__ == "__main__":
    main()
