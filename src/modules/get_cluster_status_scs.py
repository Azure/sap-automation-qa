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
        attribute_name = f"runs_ers_{self.sap_sid.upper()}"
        for node in node_attributes:
            for attribute in node:
                if attribute.attrib["name"] == attribute_name:
                    if attribute.attrib["value"] == "1":
                        self.result["ers_node"] = node.attrib["name"]
                    else:
                        self.result["ascs_node"] = node.attrib["name"]
                else:
                    continue

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
