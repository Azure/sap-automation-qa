# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Python script to get and validate the status of a cluster.
This script uses the `crm_mon` command-line tool to retrieve the status of a cluster and performs
various validations on the cluster status.

Methods:
    check_node(node, database_sid)
    run_module()
    main()
"""

import logging
import concurrent.futures
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus


class ClusterStatusChecker(SapAutomationQA):
    """
    Class to check the status of a pacemaker cluster in a SAP HANA environment.
    """

    def __init__(self, database_sid: str):
        super().__init__()
        self.database_sid = database_sid
        self.result.update(
            {
                "primary_node": "",
                "secondary_node": "",
                "cluster_status": "",
                "start": datetime.now(),
                "end": None,
                "pacemaker_status": "",
            }
        )

    def _check_node(self, node: ET.Element) -> Dict[str, str]:
        """
        Checks the attributes of node & returns corresponding action based on attribute value.

        :param node: The XML element representing a node.
        :type node: xml.etree.ElementTree.Element
        :return: A dictionary containing the action to be taken based on the attribute value.
        :rtype: dict
        """
        node_states = {}

        attribute_actions = {
            f"hana_{self.database_sid}_clone_state": lambda node, value: node_states.update(
                {"clone_state": value}
            ),
            f"hana_{self.database_sid}_sync_state": lambda node, value: node_states.update(
                {"sync_state": value}
            ),
        }

        for attribute in node:
            action = attribute_actions.get(attribute.attrib["name"])
            if action:
                action(node, attribute.attrib["value"])

        if (
            node_states.get("clone_state") == "PROMOTED"
            and node_states.get("sync_state") == "PRIM"
        ):
            return {"primary_node": node.attrib["name"]}
        elif (
            node_states.get("clone_state") == "DEMOTED"
            and node_states.get("sync_state") == "SOK"
        ):
            return {"secondary_node": node.attrib["name"]}

        return {}

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
        """
        self.log(logging.INFO, "Starting cluster status check")

        try:
            while self.result["primary_node"] == "":
                self.result["cluster_status"] = self.execute_command_subprocess(
                    ["crm_mon", "--output-as=xml"]
                )
                cluster_status_xml = ET.fromstring(self.result["cluster_status"])
                self.log(logging.INFO, "Cluster status retrieved")

                if (
                    self.execute_command_subprocess(
                        ["systemctl", "is-active", "pacemaker"]
                    )
                    == "active"
                ):
                    self.result["pacemaker_status"] = "running"
                else:
                    self.result["pacemaker_status"] = "stopped"
                self.log(
                    logging.INFO, f"Pacemaker status: {self.result['pacemaker_status']}"
                )

                if (
                    int(
                        cluster_status_xml.find("summary")
                        .find("nodes_configured")
                        .attrib["number"]
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
                        self.result["message"] = (
                            f"Node {node.attrib['name']} is not online"
                        )
                        self.log(logging.WARNING, self.result["message"])

                node_attributes = cluster_status_xml.find("node_attributes")
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(self._check_node, node)
                        for node in node_attributes
                    ]
                    for future in concurrent.futures.as_completed(futures):
                        self.result.update(future.result())

            if self.result["primary_node"] == "" or self.result["secondary_node"] == "":
                self.result["message"] = (
                    "Pacemaker cluster isn't stable and does not have primary or secondary node"
                )
                self.log(logging.WARNING, self.result["message"])
        except Exception as e:
            self.handle_error(e)
        self.result["end"] = datetime.now()
        self.result["status"] = TestStatus.SUCCESS.value
        self.log(logging.INFO, "Cluster status check completed")
        return self.result


def run_module() -> None:
    """
    Entry point of the module.
    """
    module_args = dict(
        operation_step=dict(type="str", required=True),
        database_sid=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    database_sid = module.params["database_sid"]

    checker = ClusterStatusChecker(database_sid)
    result = checker.run()

    module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
