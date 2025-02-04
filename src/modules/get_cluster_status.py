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
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any
from ansible.module_utils.basic import AnsibleModule

try:
    from ansible.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from ansible.module_utils.commands import (
        STONITH_ACTION,
        AUTOMATED_REGISTER,
        PACEMAKER_STATUS,
        CLUSTER_STATUS,
    )
except ImportError:
    from src.module_utils.sap_automation_qa import SapAutomationQA, TestStatus
    from src.module_utils.commands import (
        STONITH_ACTION,
        AUTOMATED_REGISTER,
        PACEMAKER_STATUS,
        CLUSTER_STATUS,
    )


class ClusterStatusChecker(SapAutomationQA):
    """
    Class to check the status of a pacemaker cluster in a SAP HANA environment.
    """

    def __init__(self, database_sid: str, ansible_os_family: str = ""):
        super().__init__()
        self.database_sid = database_sid
        self.ansible_os_family = ansible_os_family
        self.result.update(
            {
                "primary_node": "",
                "secondary_node": "",
                "cluster_status": "",
                "start": datetime.now(),
                "end": None,
                "pacemaker_status": "",
                "stonith_action": "",
                "operation_mode": "",
                "replication_mode": "",
                "primary_site_name": "",
                "AUTOMATED_REGISTER": "false",
            }
        )

    def _get_stonith_action(self) -> None:
        """
        Retrieves the STONITH action from the crm_attribute.
        """
        try:
            stonith_action = self.execute_command_subprocess(
                STONITH_ACTION[self.ansible_os_family]
            )
            stonith_action = (
                stonith_action.split("\n")[-1].split(":")[-1]
                if self.ansible_os_family == "REDHAT"
                else stonith_action
            )
            self.result["stonith_action"] = stonith_action.strip()
        except Exception:
            self.result["stonith_action"] = "reboot"

    def _get_automation_register(self) -> None:
        """
        Retrieves the AUTOMATED_REGISTER attribute from the crm_attribute.
        """
        try:
            cmd_output = self.execute_command_subprocess(AUTOMATED_REGISTER).strip()
            self.result["AUTOMATED_REGISTER"] = ET.fromstring(cmd_output).get("value")
        except Exception:
            self.result["AUTOMATED_REGISTER"] = "unknown"

    def _process_node_attributes(self, node_attributes: ET.Element) -> Dict[str, Any]:
        """
        Processes node attributes and identifies primary/secondary nodes.

        :param node_attributes: The XML element containing node attributes.
        :type node_attributes: xml.etree.ElementTree.Element
        :return: A dictionary containing the primary and secondary node information, plus cluster status.
        :rtype: dict
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

        return result

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

        self._get_stonith_action()

        try:
            while self.result["primary_node"] == "":
                self.result["cluster_status"] = self.execute_command_subprocess(
                    CLUSTER_STATUS
                )
                cluster_status_xml = ET.fromstring(self.result["cluster_status"])
                self.log(logging.INFO, "Cluster status retrieved")

                if (
                    self.execute_command_subprocess(PACEMAKER_STATUS).strip()
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

                # Process node attributes, get primary and secondary nodes, and update the result
                self.result.update(
                    self._process_node_attributes(
                        cluster_status_xml.find("node_attributes")
                    )
                )

            if self.result["primary_node"] == "" or self.result["secondary_node"] == "":
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
        return self.result


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

    checker = ClusterStatusChecker(
        database_sid=module.params["database_sid"],
        ansible_os_family=module.params["ansible_os_family"],
    )
    result = checker.run()

    module.exit_json(**result)


def main() -> None:
    """
    Entry point of the script.
    """
    run_module()


if __name__ == "__main__":
    main()
