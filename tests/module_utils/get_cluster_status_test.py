# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_cluster_status module.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any
import pytest
from src.module_utils.get_cluster_status import BaseClusterStatusChecker


class TestableBaseClusterChecker(BaseClusterStatusChecker):
    """
    Testable implementation of BaseClusterStatusChecker to test abstract methods.
    """

    def __init__(self, ansible_os_family=""):
        super().__init__(ansible_os_family)
        self.test_ready = False
        self.test_stable = False

    def _process_node_attributes(self, node_attributes: ET.Element) -> Dict[str, Any]:
        """
        Process node attributes and return a dictionary with node information.

        :param node_attributes: XML element containing node attributes.
        :type node_attributes: ET.Element
        :return: Dictionary with node information.
        :rtype: Dict[str, Any]
        """
        return {"processed": True}

    def _is_cluster_ready(self) -> bool:
        """
        Check if the cluster is ready.

        :return: True if the cluster is ready, False otherwise.
        :rtype: bool
        """
        return self.test_ready

    def _is_cluster_stable(self) -> bool:
        """
        Implement abstract method for testing.

        :return: True if the cluster is stable, False otherwise.
        :rtype: bool
        """
        return self.test_stable


class TestBaseClusterStatusChecker:
    """
    Test cases for the BaseClusterStatusChecker class.
    """

    @pytest.fixture
    def base_checker(self):
        """
        Fixture for creating a testable BaseClusterStatusChecker instance.

        :return: Instance of TestableBaseClusterChecker.
        :rtype: TestableBaseClusterChecker
        """
        return TestableBaseClusterChecker(ansible_os_family="REDHAT")

    def test_get_stonith_action_rhel94(self, mocker, base_checker):
        """
        Test the _get_stonith_action method when the command executes successfully.

        :param mocker: Mocking library to patch methods.
        :type mocker: mocker.MockerFixture
        :param base_checker: Instance of TestableBaseClusterChecker.
        :type base_checker: TestableBaseClusterChecker
        """
        return_values = ["reboot", "poweroff", "off"]
        for return_value in return_values:
            mock_execute = mocker.patch.object(
                base_checker,
                "execute_command_subprocess",
                return_value="Cluster Properties: cib-bootstrap-options\n"
                + f" stonith-action={return_value}",
            )

            base_checker._get_stonith_action()
            mock_execute.assert_called_once()
            assert base_checker.result["stonith_action"] == return_value

    def test_get_stonith_action(self, mocker, base_checker):
        """
        Test the _get_stonith_action method when the command executes successfully.

        :param mocker: Mocking library to patch methods.
        :type mocker: mocker.MockerFixture
        :param base_checker: Instance of TestableBaseClusterChecker.
        :type base_checker: TestableBaseClusterChecker
        """
        return_values = ["reboot", "poweroff", "off"]
        for return_value in return_values:
            mock_execute = mocker.patch.object(
                base_checker,
                "execute_command_subprocess",
                return_value="Cluster Properties: cib-bootstrap-options\n"
                + f" stonith-action: {return_value}",
            )

            base_checker._get_stonith_action()
            mock_execute.assert_called_once()
            assert base_checker.result["stonith_action"] == return_value

    def test_get_stonith_action_exception(self, mocker, base_checker):
        """
        Test the _get_stonith_action method when the command raises an exception.

        :param mocker: Mocking library to patch methods.
        :type mocker: mocker.MockerFixture
        :param base_checker: Instance of TestableBaseClusterChecker.
        :type base_checker: TestableBaseClusterChecker
        """
        mock_execute = mocker.patch.object(
            base_checker, "execute_command_subprocess", side_effect=Exception("Test error")
        )

        base_checker._get_stonith_action()

        mock_execute.assert_called_once()
        assert base_checker.result["stonith_action"] == "unknown"

    def test_validate_cluster_basic_status_success(self, mocker, base_checker):
        """
        Test _validate_cluster_basic_status method with a successful cluster status.

        :param mocker: Mocking library to patch methods.
        :type mocker: mocker.MockerFixture
        :param base_checker: Instance of TestableBaseClusterChecker.
        :type base_checker: TestableBaseClusterChecker
        """
        mocker.patch.object(base_checker, "execute_command_subprocess", return_value="active")

        xml_str = """
        <cluster_status>
            <summary>
                <nodes_configured number="2"/>
            </summary>
            <nodes>
                <node name="node1" online="true"/>
                <node name="node2" online="true"/>
            </nodes>
        </cluster_status>
        """
        cluster_xml = ET.fromstring(xml_str)

        base_checker._validate_cluster_basic_status(cluster_xml)

        assert base_checker.result["pacemaker_status"] == "running"

    def test_validate_cluster_basic_status_insufficient_nodes(self, mocker, base_checker):
        """
        Test _validate_cluster_basic_status method with insufficient nodes.

        :param mocker: Mocking library to patch methods.
        :type mocker: mocker.MockerFixture
        :param base_checker: Instance of TestableBaseClusterChecker.
        :type base_checker: TestableBaseClusterChecker
        """
        mocker.patch.object(base_checker, "execute_command_subprocess", return_value="active")

        xml_str = """
        <cluster_status>
            <summary>
                <nodes_configured number="1"/>
            </summary>
            <nodes>
                <node name="node1" online="true"/>
            </nodes>
        </cluster_status>
        """
        cluster_xml = ET.fromstring(xml_str)

        base_checker._validate_cluster_basic_status(cluster_xml)

        assert "insufficient nodes" in base_checker.result["message"]

    def test_validate_cluster_basic_status_offline_node(self, base_checker):
        """
        Test _validate_cluster_basic_status method with an offline node.

        :param base_checker: Instance of TestableBaseClusterChecker.
        :type base_checker: TestableBaseClusterChecker
        """

        xml_str = """
        <cluster_status>
            <summary>
                <nodes_configured number="2"/>
            </summary>
            <nodes>
                <node name="node1" online="true"/>
                <node name="node2" online="false"/>
            </nodes>
        </cluster_status>
        """
        cluster_xml = ET.fromstring(xml_str)

        base_checker._validate_cluster_basic_status(cluster_xml)

        assert "node2 is not online" in base_checker.result["message"]

    def test_run_cluster_ready(self, mocker, base_checker):
        """
        Test the run method when the cluster is ready.

        :param mocker: Mocking library to patch methods.
        :type mocker: mocker.MockerFixture
        :param base_checker: Instance of TestableBaseClusterChecker.
        :type base_checker: TestableBaseClusterChecker
        """
        mock_execute = mocker.patch.object(base_checker, "execute_command_subprocess")
        mock_execute.side_effect = [
            "reboot",
            """
            <cluster_status>
                <summary>
                    <nodes_configured number="2"/>
                </summary>
                <nodes>
                    <node name="node1" online="true"/>
                    <node name="node2" online="true"/>
                </nodes>
                <node_attributes>
                    <node name="node1"/>
                </node_attributes>
            </cluster_status>
            """,
            "active",
        ]

        # Set the test ready flag to True
        base_checker.test_ready = True
        base_checker.test_stable = True

        result = base_checker.run()

        assert result["status"] == "PASSED"
        assert "end" in result
