# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_cluster_status_scs module.
"""

import xml.etree.ElementTree as ET
import pytest
from src.modules.get_cluster_status_scs import SCSClusterStatusChecker, run_module


class TestSCSClusterStatusChecker:
    """
    Test cases for the SCSClusterStatusChecker class.
    """

    @pytest.fixture
    def scs_checker(self):
        """
        Fixture for creating a SCSClusterStatusChecker instance.

        :return: Instance of SCSClusterStatusChecker.
        :rtype: SCSClusterStatusChecker
        """
        return SCSClusterStatusChecker(sap_sid="TST", ansible_os_family="REDHAT")

    def test_get_resource_ids(self, mocker, scs_checker):
        """
        Test the _get_resource_ids method to ensure ASCS and ERS resource IDs are
        correctly identified.

        :param mocker: Mocking library to patch methods.
        :type mocker: pytest_mock.MockerFixture
        :param scs_checker: Instance of SCSClusterStatusChecker.
        :type scs_checker: SCSClusterStatusChecker
        """
        mock_resources_xml = """
        <resources>
            <primitive id="rsc_sap_TST_ASCS00" type="SAPInstance">
                <instance_attributes>
                    <nvpair name="IS_ERS" value="false"/>
                </instance_attributes>
            </primitive>
            <primitive id="rsc_sap_TST_ERS01" type="SAPInstance">
                <instance_attributes>
                    <nvpair name="IS_ERS" value="true"/>
                </instance_attributes>
            </primitive>
        </resources>
        """

        mocker.patch.object(
            scs_checker,
            "execute_command_subprocess",
            return_value=mock_resources_xml,
        )

        scs_checker._get_resource_ids()
        assert scs_checker.ascs_resource_id == "rsc_sap_TST_ASCS00"
        assert scs_checker.ers_resource_id == "rsc_sap_TST_ERS01"

    def test_process_node_attributes(self, mocker, scs_checker):
        """
        Test processing node attributes to identify ASCS and ERS nodes.

        :param mocker: Mocker fixture for mocking functions.
        :type mocker: pytest_mock.MockerFixture
        :param scs_checker: Instance of SCSClusterStatusChecker.
        :type scs_checker: SCSClusterStatusChecker
        """
        xml_str = """
        <dummy>
            <resources>
                <resource id="rsc_sap_TST_ASCS00" failed="false" active="true" role="started">
                    <node name="node1"/>
                </resource>
                <resource id="rsc_sap_TST_ERS01" failed="false" active="true" role="started">
                    <node name="node2"/>
                </resource>
            </resources>
            <node_attributes>
                <node name="node1">
                    <attribute name="runs_ers_TST" value="0"/>
                </node>
                <node name="node2">
                    <attribute name="runs_ers_TST" value="1"/>
                </node>
            </node_attributes>
        </dummy>
        """
        scs_checker.ascs_resource_id = "rsc_sap_TST_ASCS00"
        scs_checker.ers_resource_id = "rsc_sap_TST_ERS01"
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
        <dummy>
            <resources>
                <resource id="rsc_sap_TST_ERS01" failed="false" active="true" role="started">
                    <node name="node1"/>
                </resource>
            </resources>
            <node_attributes>
                <node name="node1">
                    <attribute name="some_other_attr" value="value"/>
                </node>
                <node name="node2">
                    <attribute name="runs_ers_TST" value="1"/>
                </node>
            </node_attributes>
        </dummy>
        """
        scs_checker.ascs_resource_id = "rsc_sap_TST_ASCS00"
        scs_checker.ers_resource_id = "rsc_sap_TST_ERS01"
        node_attributes = ET.fromstring(xml_str)

        scs_checker._process_node_attributes(node_attributes)

        assert scs_checker.result["ascs_node"] == ""
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
        mock_ansible_module.params = {
            "sap_sid": "TST",
            "ansible_os_family": "REDHAT",
            "scs_instance_number": "00",
            "ers_instance_number": "01",
        }
        mocker.patch(
            "src.modules.get_cluster_status_scs.AnsibleModule", return_value=mock_ansible_module
        )
        mocker.patch(
            "src.modules.get_cluster_status_scs.ansible_facts", return_value={"os_family": "REDHAT"}
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
