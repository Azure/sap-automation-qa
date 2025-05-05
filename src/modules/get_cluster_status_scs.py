# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the status of an SCS cluster.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.get_cluster_status import BaseClusterStatusChecker
    from ansible.module_utils.commands import CIB_ADMIN
except ImportError:
    from src.module_utils.get_cluster_status import BaseClusterStatusChecker
    from src.module_utils.commands import (
        CIB_ADMIN,
    )


DOCUMENTATION = r"""
---
module: get_cluster_status_scs
short_description: Checks the status of a SAP SCS cluster
description:
    - This module checks the status of a pacemaker cluster in a SAP SCS environment.
    - Identifies ASCS and ERS nodes in the cluster.
    - Validates if the cluster is ready and stable.
    - Retrieves detailed resource and node attributes for ASCS and ERS.
options:
    sap_sid:
        description:
            - SAP System ID (SID).
            - Used to identify the specific ASCS and ERS resources.
        type: str
        required: true
    ansible_os_family:
        description:
            - Operating system family (e.g., redhat, suse).
            - Used to determine OS-specific commands and configurations.
        type: str
        required: false
author:
    - Microsoft Corporation
notes:
    - This module requires root privileges to access pacemaker cluster information.
    - Depends on crm_mon command being available.
    - Validates the cluster status by checking node attributes for ASCS and ERS.
requirements:
    - python >= 3.6
    - pacemaker cluster environment
    - SAP SCS cluster configured
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

- name: Validate detailed cluster attributes
  debug:
    msg: "ASCS attributes: {{ cluster_result.cluster_status.ascs_node }}, ERS attributes: {{ cluster_result.cluster_status.ers_node }}"
"""

RETURN = r"""
status:
    description: Status of the cluster check.
    returned: always
    type: str
    sample: "SUCCESS"
message:
    description: Descriptive message about the cluster status.
    returned: always
    type: str
    sample: "Cluster is stable and ready."
ascs_node:
    description: Name of the node running the ASCS instance.
    returned: always
    type: str
    sample: "sapapp1"
ers_node:
    description: Name of the node running the ERS instance.
    returned: always
    type: str
    sample: "sapapp2"
cluster_status:
    description: Detailed cluster attributes for ASCS and ERS nodes.
    returned: always
    type: dict
    contains:
        ascs_node:
            description: Attributes of the ASCS node.
            type: dict
        ers_node:
            description: Attributes of the ERS node.
            type: dict
"""


class SCSClusterStatusChecker(BaseClusterStatusChecker):
    """
    Class to check the status of a pacemaker cluster in an SAP SCS environment.
    """

    def __init__(
        self,
        sap_sid: str,
        ansible_os_family: str = "",
    ):
        super().__init__(ansible_os_family)
        self.sap_sid = sap_sid
        self.ascs_resource_id = ""
        self.ers_resource_id = ""
        self._get_resource_ids()
        self.result.update(
            {
                "ascs_node": "",
                "ers_node": "",
                "ascs_resource_id": self.ascs_resource_id,
                "ers_resource_id": self.ers_resource_id,
            }
        )

    def _get_resource_ids(self) -> None:
        """
        Retrieves the resource IDs for ASCS and ERS from the cluster status XML.

        :return: None
        """
        try:
            resources_string = self.execute_command_subprocess(CIB_ADMIN("resources"))
            if resources_string is not None:
                resources = ET.fromstring(resources_string).findall(
                    ".//primitive[@type='SAPInstance']"
                )
                for resource in resources:
                    resource_id = resource.attrib.get("id")
                    instance_attributes = resource.find("instance_attributes")

                    if instance_attributes is not None:
                        is_ers = False

                        for nvpair in instance_attributes:
                            name = nvpair.attrib.get("name")
                            value = nvpair.attrib.get("value")

                            if name == "IS_ERS" and value == "true":
                                is_ers = True

                        if is_ers:
                            self.ers_resource_id = resource_id
                        else:
                            self.ascs_resource_id = resource_id

        except Exception as ex:
            self.handle_error(ex)

    def _process_node_attributes(self, cluster_status_xml: ET.Element) -> Dict[str, Any]:
        """
        Processes node attributes and identifies ASCS and ERS nodes.

        :param cluster_status_xml: XML element containing node attributes.
        :type cluster_status_xml: ET.Element
        :return: Dictionary with ASCS and ERS node information.
        :rtype: Dict[str, Any]
        """
        result = {
            "ascs_node": "",
            "ers_node": "",
            "cluster_status": {
                "ascs_node": {},
                "ers_node": {},
            },
        }
        resources = cluster_status_xml.find("resources")
        node_attributes = cluster_status_xml.find("node_attributes")

        try:
            if node_attributes is not None:
                for node in node_attributes:
                    node_name = node.attrib.get("name")
                    for attribute in node:
                        if attribute.attrib.get("name") == f"runs_ers_{self.sap_sid.upper()}":
                            attr_value = attribute.attrib.get("value")
                            if attr_value == "1":
                                result["ers_node"] = node_name
                            elif attr_value == "0":
                                result["ascs_node"] = node_name
                            break

            # If node attributes do not report correct ASCS/ERS nodes, exit
            # and return empty values
            if result["ascs_node"] == "" and result["ers_node"] == "":
                return self.result

            if resources is not None and self.ascs_resource_id and self.ers_resource_id:
                ascs_resource = resources.find(f".//resource[@id='{self.ascs_resource_id}']")
                ers_resource = resources.find(f".//resource[@id='{self.ers_resource_id}']")

                for resource in [ascs_resource, ers_resource]:
                    if resource is None:
                        continue

                    resource_id = resource.attrib.get("id")

                    node_type = "ascs_node" if resource_id == self.ascs_resource_id else "ers_node"
                    node_element = resource.find("node")
                    if node_element is None:
                        result[node_type] = ""
                        continue

                    node_name = node_element.attrib.get("name")
                    if node_name is None:
                        continue

                    failed = resource.attrib.get("failed", "false").lower() == "true"
                    active = resource.attrib.get("active", "false").lower() == "true"
                    role = resource.attrib.get("role", "unknown").lower()
                    role_status = role == "started"

                    if not failed and active and role_status:
                        result[node_type] = (
                            node_name if result[node_type] == "" else result[node_type]
                        )
                        result["cluster_status"][node_type] = {
                            "name": node_name,
                            "id": resource.attrib.get("id"),
                            "resource_agent": resource.attrib.get("resource_agent"),
                            "role": role,
                            "active": "true",
                            "orphaned": resource.attrib.get("orphaned"),
                            "blocked": resource.attrib.get("blocked"),
                            "failed": "false",
                            "nodes_running_on": resource.attrib.get("nodes_running_on"),
                            "failure_ignored": resource.attrib.get("failure_ignored"),
                        }
                    else:
                        result[node_type] = ""
            else:
                self.log(
                    logging.ERROR,
                    "Failed to find resources in the cluster status XML.",
                )
        except Exception as ex:
            self.handle_error(ex)

        self.result.update(result)
        return self.result

    def _is_cluster_ready(self) -> bool:
        """
        Check if the cluster is ready by verifying at least one of ASCS or ERS nodes.

        :return: True if either ASCS or ERS node is available, False otherwise.
        :rtype: bool
        """
        return self.result["ascs_node"] != "" or self.result["ers_node"] != ""

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
