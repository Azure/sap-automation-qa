# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the status of a HANA cluster.
"""

DOCUMENTATION = r"""
---
module: get_cluster_status_db
short_description: Checks the status of a SAP HANA database cluster
description:
    - This module checks the status of a pacemaker cluster in a SAP HANA environment
    - Identifies primary and secondary nodes in the cluster
    - Retrieves operation mode, replication mode, and other cluster attributes
    - Validates if the cluster is ready and stable
options:
    operation_step:
        description:
            - The current operation step being executed
        type: str
        required: true
    database_sid:
        description:
            - SAP HANA database SID
        type: str
        required: true
    ansible_os_family:
        description:
            - Operating system family (redhat, suse, etc.)
        type: str
        required: false
author:
    - Microsoft Corporation
notes:
    - This module requires root privileges to access pacemaker cluster information
    - Depends on crm_mon and crm_attribute commands being available
    - Validates the cluster status by checking node attributes
requirements:
    - python >= 3.6
    - pacemaker cluster environment
"""

EXAMPLES = r"""
- name: Check SAP HANA cluster status
  get_cluster_status_db:
    operation_step: "check_cluster"
    database_sid: "HDB"
    ansible_os_family: "{{ ansible_os_family|lower }}"
  register: cluster_result

- name: Display cluster status
  debug:
    msg: "Primary node: {{ cluster_result.primary_node }}, Secondary node: {{ cluster_result.secondary_node }}"

- name: Fail if cluster is not stable
  fail:
    msg: "HANA cluster is not properly configured"
  when: cluster_result.primary_node == '' or cluster_result.secondary_node == ''
"""

RETURN = r"""
status:
    description: Status of the cluster check
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Descriptive message about the cluster status
    returned: always
    type: str
    sample: "Cluster is stable and ready"
primary_node:
    description: Name of the primary node in the HANA cluster
    returned: always
    type: str
    sample: "hanadb1"
secondary_node:
    description: Name of the secondary node in the HANA cluster
    returned: always
    type: str
    sample: "hanadb2"
operation_mode:
    description: HANA system replication operation mode
    returned: always
    type: str
    sample: "logreplay"
replication_mode:
    description: HANA system replication mode
    returned: always
    type: str
    sample: "sync"
primary_site_name:
    description: Name of the primary site in HANA system replication
    returned: always
    type: str
    sample: "Site1"
AUTOMATED_REGISTER:
    description: Status of automated registration
    returned: always
    type: str
    sample: "true"
cluster_status:
    description: Detailed cluster attributes for each node
    returned: always
    type: dict
    contains:
        primary:
            description: Attributes of the primary node
            type: dict
        secondary:
            description: Attributes of the secondary node
            type: dict
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.get_cluster_status import BaseClusterStatusChecker
    from ansible.module_utils.commands import AUTOMATED_REGISTER
except ImportError:
    from src.module_utils.get_cluster_status import BaseClusterStatusChecker
    from src.module_utils.commands import AUTOMATED_REGISTER


class HanaClusterStatusChecker(BaseClusterStatusChecker):
    """
    Class to check the status of a pacemaker cluster in a SAP HANA environment.
    """

    def __init__(self, database_sid: str, ansible_os_family: str = ""):
        super().__init__(ansible_os_family)
        self.database_sid = database_sid
        self.result.update(
            {
                "primary_node": "",
                "secondary_node": "",
                "operation_mode": "",
                "replication_mode": "",
                "primary_site_name": "",
                "AUTOMATED_REGISTER": "false",
            }
        )

    def _get_automation_register(self) -> None:
        """
        Retrieves the value of the AUTOMATED_REGISTER attribute.
        """
        try:
            cmd_output = self.execute_command_subprocess(AUTOMATED_REGISTER).strip()
            self.result["AUTOMATED_REGISTER"] = ET.fromstring(cmd_output).get("value")
        except Exception:
            self.result["AUTOMATED_REGISTER"] = "unknown"

    def _process_node_attributes(self, node_attributes: ET.Element) -> Dict[str, Any]:
        """
        Processes node attributes and identifies primary and secondary nodes.

        :param node_attributes: XML element containing node attributes.
        :type node_attributes: ET.Element
        :return: Dictionary with primary and secondary node information.
        :rtype: Dict[str, Any]
        """
        result = {
            "primary_node": "",
            "secondary_node": "",
            "cluster_status": {"primary": {}, "secondary": {}},
            "operation_mode": "",
            "replication_mode": "",
            "primary_site_name": "",
        }

        attribute_map = {
            f"hana_{self.database_sid}_op_mode": "operation_mode",
            f"hana_{self.database_sid}_srmode": "replication_mode",
        }

        for node in node_attributes:
            node_name = node.attrib["name"]
            node_states = {}
            node_attributes_dict = {}

            for attribute in node:
                attr_name = attribute.attrib["name"]
                attr_value = attribute.attrib["value"]
                node_attributes_dict[attr_name] = attr_value

                if attr_name in attribute_map:
                    result[attribute_map[attr_name]] = attr_value

                if attr_name == f"hana_{self.database_sid}_clone_state":
                    node_states["clone_state"] = attr_value
                elif attr_name == f"hana_{self.database_sid}_sync_state":
                    node_states["sync_state"] = attr_value

            if (
                node_states.get("clone_state") == "PROMOTED"
                and node_states.get("sync_state") == "PRIM"
            ):
                result["primary_node"] = node_name
                result["cluster_status"]["primary"] = node_attributes_dict
                result["primary_site_name"] = node_attributes_dict.get(
                    f"hana_{self.database_sid}_site", ""
                )
            elif (
                node_states.get("clone_state") == "DEMOTED"
                and node_states.get("sync_state") == "SOK"
            ):
                result["secondary_node"] = node_name
                result["cluster_status"]["secondary"] = node_attributes_dict

        # Update instance attributes
        self.result.update(result)
        return result

    def _is_cluster_ready(self) -> bool:
        """
        Check if the primary node has been identified.

        :return: True if the primary node is identified, False otherwise.
        :rtype: bool
        """
        return self.result["primary_node"] != ""

    def _is_cluster_stable(self) -> bool:
        """
        Check if both primary and secondary nodes are identified.

        :return: True if both nodes are identified, False otherwise.
        :rtype: bool
        """
        return self.result["primary_node"] != "" and self.result["secondary_node"] != ""

    def run(self) -> Dict[str, str]:
        """
        Main function that runs the cluster status checks.

        :return: Dictionary with the result of the checks.
        :rtype: Dict[str, str]
        """
        result = super().run()
        self._get_automation_register()
        return result


def run_module() -> None:
    """
    Entry point of the module.
    """
    module_args = dict(
        operation_step=dict(type="str", required=True),
        database_sid=dict(type="str", required=True),
        ansible_os_family=dict(type="str", required=False),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    checker = HanaClusterStatusChecker(
        database_sid=module.params["database_sid"],
        ansible_os_family=module.params["ansible_os_family"],
    )
    checker.run()

    module.exit_json(**checker.get_result())


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
