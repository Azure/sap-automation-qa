# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_cluster_status_scs module.
"""

import pytest
import xml.etree.ElementTree as ET
from src.modules.get_cluster_status_scs import SCSClusterStatusChecker, run_module


class TestSCSClusterStatusChecker:
    """
    Test cases for the SCSClusterStatusChecker class.
    """

    @pytest.fixture
    def scs_checker(self):
        """
        Fixture for creating a SCSClusterStatusChecker instance.
        """
        return SCSClusterStatusChecker(sap_sid="TST", ansible_os_family="REDHAT")

    def test_process_node_attributes(self, scs_checker):
        """
        Test processing node attributes to identify ASCS and ERS nodes.

        :param scs_checker: Instance of SCSClusterStatusChecker.
        :type scs_checker: SCSClusterStatusChecker
        """
        xml_str = """
        <node_attributes>
            <node name="node1">
                <attribute name="runs_ers_TST" value="0"/>
            </node>
            <node name="node2">
                <attribute name="runs_ers_TST" value="1"/>
            </node>
        </node_attributes>
        """
        node_attributes = ET.fromstring(xml_str)

        scs_checker._process_node_attributes(node_attributes)

        assert scs_checker.result["ascs_node"] == "node1"
        assert scs_checker.result["ers_node"] == "node2"

    def test_process_node_attributes_incomplete(self, scs_checker):
        """
        Test processing node attributes when ASCS node is not found.

        :param scs_checker: Instance of SCSClusterStatusChecker.
        :type scs_checker: SCSClusterStatusChecker
        """
        xml_str = """
        <node_attributes>
            <node name="node1">
                <attribute name="some_other_attr" value="value"/>
            </node>
            <node name="node2">
                <attribute name="runs_ers_TST" value="1"/>
            </node>
        </node_attributes>
        """
        node_attributes = ET.fromstring(xml_str)

        scs_checker._process_node_attributes(node_attributes)

        assert scs_checker.result["ascs_node"] == "node1"
        assert scs_checker.result["ers_node"] == "node2"

    def test_is_cluster_ready(self, scs_checker):
        """
        Test the _is_cluster_ready method.

        :param scs_checker: Instance of SCSClusterStatusChecker.
        :type scs_checker: SCSClusterStatusChecker
        """
        scs_checker.result["ascs_node"] = ""
        assert not scs_checker._is_cluster_ready()

        scs_checker.result["ascs_node"] = "node1"
        assert scs_checker._is_cluster_ready()

    def test_is_cluster_stable(self, scs_checker):
        """
        Test the _is_cluster_stable method.

        :param scs_checker: Instance of SCSClusterStatusChecker.
        :type scs_checker: SCSClusterStatusChecker
        """
        scs_checker.result["ascs_node"] = ""
        scs_checker.result["ers_node"] = ""
        assert not scs_checker._is_cluster_stable()

        scs_checker.result["ascs_node"] = "node1"
        scs_checker.result["ers_node"] = ""
        assert not scs_checker._is_cluster_stable()

        scs_checker.result["ascs_node"] = "node1"
        scs_checker.result["ers_node"] = "node2"
        assert scs_checker._is_cluster_stable()


class TestRunModule:
    """
    Test cases for the run_module function.
    """

    def test_run_module(self, mocker):
        """
        Test the run_module function.

        :param mocker: Mocking library to patch methods.
        :type mocker: mocker.MockerFixture
        """
        mock_ansible_module = mocker.MagicMock()
        mock_ansible_module.params = {"sap_sid": "TST", "ansible_os_family": "REDHAT"}
        mocker.patch(
            "src.modules.get_cluster_status_scs.AnsibleModule", return_value=mock_ansible_module
        )

        mock_run = mocker.MagicMock()
        mock_checker = mocker.MagicMock()
        mock_checker.run = mock_run
        mock_checker.get_result.return_value = {"status": "PASSED"}
        mocker.patch(
            "src.modules.get_cluster_status_scs.SCSClusterStatusChecker", return_value=mock_checker
        )

        run_module()

        mock_ansible_module.exit_json.assert_called_once_with(status="PASSED")
