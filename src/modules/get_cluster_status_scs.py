# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the status of a cluster.
This script uses the `crm_mon` command-line tool to retrieve the status of a cluster and performs
various validations on the cluster status.

Methods:
    check_node(node, sap_sid)
    run_module()
    main()
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from ansible.module_utils.commands import (
        STONITH_ACTION,
        PACEMAKER_STATUS,
        CLUSTER_STATUS,
    )
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from src.module_utils.commands import (
        STONITH_ACTION,
        PACEMAKER_STATUS,
        CLUSTER_STATUS,
    )


class ClusterStatusChecker(SapAutomationQA):
    """
    Class to check the status of a pacemaker cluster in a SAP HANA environment.
    """

    def __init__(self, sap_sid: str, ansible_os_family: str = ""):
        super().__init__()
        self.sap_sid = sap_sid
        self.ansible_os_family = ansible_os_family
        self.result.update(
            {
                "ascs_node": "",
                "ers_node": "",
                "cluster_status": "",
                "start": datetime.now(),
                "end": None,
                "pacemaker_status": "",
                "stonith_action": "",
            }
        )

    def _get_stonith_action(self) -> None:
        """
        Retrieves the STONITH action from the crm_attribute.
        """
        try:
            stonith_action = self.execute_command_subprocess(STONITH_ACTION[self.ansible_os_family])
            stonith_action = (
                stonith_action.split("stonith-action:")[-1]
                if self.ansible_os_family == "REDHAT"
                else stonith_action
            )
            self.result["stonith_action"] = stonith_action.strip()
        except Exception:
            self.result["stonith_action"] = "reboot"

    def _process_node_attributes(self, node_attributes: ET.Element) -> Dict[str, Any]:
        """
        Processes node attributes and identifies primary/secondary nodes.

        :param node_attributes: The XML element containing node attributes.
        :type node_attributes: ET.Element
        :return: A dictionary containing the primary and secondary node information, plus cluster status.
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

    def run(self) -> Dict[str, str]:
        """
        Main function that runs the Ansible module and performs the cluster status checks.

        This function retrieves operation step from module arguments and performs following checks:
        - Checks the status of the cluster using the `crm_mon` command.
        - Validates the cluster status and checks if pacemakerd is running.
        - Checks if the minimum required number of nodes are configured in the cluster.
        - Checks if all nodes in the cluster are online.
        - Checks the attributes of each node in the cluster.

        :return: A dictionary containing the result of the cluster status checks.
        :rtype: Dict[str, str]
        """
        self.log(logging.INFO, "Starting cluster status check")

        self._get_stonith_action()

        try:
            while self.result["ascs_node"] == "":
                self.result["cluster_status"] = self.execute_command_subprocess(CLUSTER_STATUS)
                cluster_status_xml = ET.fromstring(self.result["cluster_status"])
                self.log(logging.INFO, "Cluster status retrieved")

                if self.execute_command_subprocess(PACEMAKER_STATUS).strip() == "active":
                    self.result["pacemaker_status"] = "running"
                else:
                    self.result["pacemaker_status"] = "stopped"
                self.log(logging.INFO, f"Pacemaker status: {self.result['pacemaker_status']}")

                if (
                    int(
                        cluster_status_xml.find("summary").find("nodes_configured").attrib["number"]
                    )
                    < 2
                ):
                    self.result["message"] = (
                        "Pacemaker cluster isn't stable and does not have primary or secondary node"
                    )
                    self.log(logging.WARNING, self.result["message"])

                nodes = cluster_status_xml.find("nodes")
                for node in nodes:
                    if node.attrib["online"] != "true":
                        self.result["message"] = f"Node {node.attrib['name']} is not online"
                        self.log(logging.WARNING, self.result["message"])

                self._process_node_attributes(cluster_status_xml.find("node_attributes"))

            if self.result["ascs_node"] == "" or self.result["ers_node"] == "":
                self.result["message"] = (
                    "Pacemaker cluster isn't stable and does not have primary or secondary node"
                )
                self.log(logging.WARNING, self.result["message"])
            self._get_automation_register()

        except Exception as e:
            self.handle_error(e)
        self.result["end"] = datetime.now()
        self.result["status"] = TestStatus.SUCCESS.value
        self.log(logging.INFO, "Cluster status check completed")


def run_module() -> None:
    """
    Entry point of the module.
    """
    module_args = dict(
        sap_sid=dict(type="str", required=True),
        ansible_os_family=dict(type="str", required=False),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    checker = ClusterStatusChecker(
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
