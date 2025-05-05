# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Base class for cluster status checking implementations.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any

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


class BaseClusterStatusChecker(SapAutomationQA):
    """
    Base class to check the status of a pacemaker cluster.
    """

    def __init__(self, ansible_os_family: str = ""):
        super().__init__()
        self.ansible_os_family = ansible_os_family
        self.result.update(
            {
                "cluster_status": "",
                "start": datetime.now(),
                "end": None,
                "pacemaker_status": "",
                "stonith_action": "",
            }
        )

    def _get_stonith_action(self) -> None:
        """
        Retrieves the stonith action from the system.
        """
        self.result["stonith_action"] = "unknown"
        try:
            stonith_action = self.execute_command_subprocess(STONITH_ACTION[self.ansible_os_family])
            actions = [
                "reboot",
                "poweroff",
                "off",
            ]
            for action in actions:
                if action in stonith_action:
                    self.result["stonith_action"] = action
                    break
        except Exception as ex:
            self.log(logging.WARNING, f"Failed to get stonith action: {str(ex)}")

    def _validate_cluster_basic_status(self, cluster_status_xml: ET.Element):
        """
        Validate the basic status of the cluster.

        :param cluster_status_xml: XML element containing cluster status.
        :type cluster_status_xml: ET.Element
        """
        if self.execute_command_subprocess(PACEMAKER_STATUS).strip() == "active":
            self.result["pacemaker_status"] = "running"
        else:
            self.result["pacemaker_status"] = "stopped"
        self.log(logging.INFO, f"Pacemaker status: {self.result['pacemaker_status']}")

        if int(cluster_status_xml.find("summary").find("nodes_configured").attrib["number"]) < 2:
            self.result["message"] = "Pacemaker cluster isn't stable (insufficient nodes)"
            self.log(logging.WARNING, self.result["message"])

        nodes = cluster_status_xml.find("nodes")
        for node in nodes:
            if node.attrib["online"] != "true":
                self.result["message"] = f"Node {node.attrib['name']} is not online"
                self.log(logging.WARNING, self.result["message"])

    def _process_node_attributes(self, cluster_status_xml: ET.Element) -> Dict[str, Any]:
        """
        Abstract method to process node attributes.

        :param node_attributes: XML element containing node attributes.
        :type node_attributes: ET.Element
        :raises NotImplementedError: If the method is not implemented in a child class.
        :return: Dictionary with node attributes.
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Child classes must implement this method")

    def run(self) -> Dict[str, str]:
        """
        Run the cluster status check.

        :return: Result of the cluster status check.
        :rtype: Dict[str, str]
        """
        self.log(logging.INFO, "Starting cluster status check")
        self._get_stonith_action()

        try:
            while not self._is_cluster_ready():
                self.result["cluster_status"] = self.execute_command_subprocess(CLUSTER_STATUS)
                cluster_status_xml = ET.fromstring(self.result["cluster_status"])
                self.log(logging.INFO, "Cluster status retrieved")

                self._validate_cluster_basic_status(cluster_status_xml)
                self._process_node_attributes(cluster_status_xml=cluster_status_xml)

            if not self._is_cluster_stable():
                self.result["message"] = "Pacemaker cluster isn't stable"
                self.log(logging.WARNING, self.result["message"])

        except Exception as ex:
            self.handle_error(ex)

        self.result["end"] = datetime.now()
        self.result["status"] = TestStatus.SUCCESS.value
        self.log(logging.INFO, "Cluster status check completed")
        return self.result

    def _is_cluster_ready(self) -> bool:
        """
        Abstract method to check if the cluster is ready.
        To be implemented by child classes.

        :raises NotImplementedError: If the method is not implemented in a child class.
        :return: True if the cluster is ready, False otherwise.
        :rtype: bool
        """
        raise NotImplementedError("Child classes must implement this method")

    def _is_cluster_stable(self) -> bool:
        """
        Abstract method to check if the cluster is in a stable state.
        To be implemented by child classes.

        :raises NotImplementedError: If the method is not implemented in a child class.
        :return: True if the cluster is ready, False otherwise.
        :rtype: bool
        """
        raise NotImplementedError("Child classes must implement this method")
