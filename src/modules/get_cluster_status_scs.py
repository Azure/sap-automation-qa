# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the status of an SCS cluster.
"""

DOCUMENTATION = r"""
---
module: get_cluster_status_scs
short_description: Checks the status of a SAP SCS cluster
description:
    - This module checks the status of a pacemaker cluster in a SAP SCS environment
    - Identifies ASCS and ERS nodes in the cluster
    - Validates if the cluster is ready and stable
options:
    sap_sid:
        description:
            - SAP System ID (SID)
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
    - Depends on crm_mon command being available
    - Validates the cluster status by checking node attributes for ASCS and ERS
requirements:
    - python >= 3.6
    - pacemaker cluster environment
"""

EXAMPLES = r"""
- name: Check SAP SCS cluster status
  get_cluster_status_scs:
    sap_sid: "S4D"
    ansible_os_family: "{{ ansible_os_family|lower }}"
  register: cluster_result

- name: Display SCS cluster status
  debug:
    msg: "ASCS node: {{ cluster_result.ascs_node }}, ERS node: {{ cluster_result.ers_node }}"

- name: Fail if SCS cluster is not stable
  fail:
    msg: "SAP SCS cluster is not properly configured"
  when: cluster_result.ascs_node == '' or cluster_result.ers_node == ''
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
ascs_node:
    description: Name of the node running the ASCS instance
    returned: always
    type: str
    sample: "sapapp1"
ers_node:
    description: Name of the node running the ERS instance
    returned: always
    type: str
    sample: "sapapp2"
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.get_cluster_status import BaseClusterStatusChecker
except ImportError:
    from src.module_utils.get_cluster_status import BaseClusterStatusChecker


class SCSClusterStatusChecker(BaseClusterStatusChecker):
    """
    Class to check the status of a pacemaker cluster in an SAP SCS environment.
    """

    def __init__(self, sap_sid: str, ansible_os_family: str = ""):
        super().__init__(ansible_os_family)
        self.sap_sid = sap_sid
        self.result.update(
            {
                "ascs_node": "",
                "ers_node": "",
            }
        )

    def _process_node_attributes(self, node_attributes: ET.Element) -> Dict[str, Any]:
        """
        Processes node attributes and identifies ASCS and ERS nodes.

        :param node_attributes: XML element containing node attributes.
        :type node_attributes: ET.Element
        :return: Dictionary with ASCS and ERS node information.
        :rtype: Dict[str, Any]
        """
        all_nodes = [node.attrib.get("name") for node in node_attributes]
        for node in node_attributes:
            node_name = node.attrib["name"]
            for attribute in node:
                if attribute.attrib["name"] == f"runs_ers_{self.sap_sid.upper()}":
                    if attribute.attrib["value"] == "1":
                        self.result["ers_node"] = node_name
                    else:
                        self.result["ascs_node"] = node_name

        if self.result["ascs_node"] == "" and self.result["ers_node"] != "":
            self.result["ascs_node"] = next(
                (n for n in all_nodes if n != self.result["ers_node"]), ""
            )
        return self.result

    def _is_cluster_ready(self) -> bool:
        """
        Check if the cluster is ready by verifying the ASCS node.

        :return: True if the cluster is ready, False otherwise.
        :rtype: bool
        """
        return self.result["ascs_node"] != ""

    def _is_cluster_stable(self) -> bool:
        """
        Check if the cluster is stable by verifying both ASCS and ERS nodes.

        :return: True if the cluster is stable, False otherwise.
        :rtype: bool
        """
        return self.result["ascs_node"] != "" and self.result["ers_node"] != ""


def run_module() -> None:
    """
    Entry point of the module.
    """
    module_args = dict(
        sap_sid=dict(type="str", required=True),
        ansible_os_family=dict(type="str", required=False),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    checker = SCSClusterStatusChecker(
        sap_sid=module.params["sap_sid"],
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
