# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_cluster_status_db module.
"""

import xml.etree.ElementTree as ET
import pytest
from src.modules.get_cluster_status_db import HanaClusterStatusChecker, run_module


class TestHanaClusterStatusChecker:
    """
    Test cases for the HanaClusterStatusChecker class.
    """

    @pytest.fixture
    def hana_checker(self):
        """
        Fixture for creating a HanaClusterStatusChecker instance.

        :return: Instance of HanaClusterStatusChecker.
        :rtype: HanaClusterStatusChecker
        """
        return HanaClusterStatusChecker(database_sid="TEST", ansible_os_family="REDHAT")

    def test_get_automation_register(self, mocker, hana_checker):
        """
        Test the _get_automation_register method.

        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        :param hana_checker: Instance of HanaClusterStatusChecker.
        :type hana_checker: HanaClusterStatusChecker
        """
        mocker.patch.object(
            hana_checker,
            "execute_command_subprocess",
            return_value='<nvpair id="cib-bootstrap-options-AUTOMATED_REGISTER" '
            + 'name="AUTOMATED_REGISTER" value="true"/>',
        )

        hana_checker._get_automation_register()

        assert hana_checker.result["AUTOMATED_REGISTER"] == "true"

    def test_get_automation_register_exception(self, mocker, hana_checker):
        """
        Test the _get_automation_register method when an exception occurs.

        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        :param hana_checker: Instance of HanaClusterStatusChecker.
        :type hana_checker: HanaClusterStatusChecker
        """
        mocker.patch.object(
            hana_checker, "execute_command_subprocess", side_effect=Exception("Test error")
        )

        hana_checker._get_automation_register()

        assert hana_checker.result["AUTOMATED_REGISTER"] == "unknown"

    def test_process_node_attributes_primary_only(self, hana_checker):
        """
        Test processing node attributes with only the primary node.

        :param hana_checker: Instance of HanaClusterStatusChecker.
        :type hana_checker: HanaClusterStatusChecker
        """
        xml_str = """
        <node_attributes>
            <node name="node1">
                <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                <attribute name="hana_TEST_sync_state" value="PRIM"/>
                <attribute name="hana_TEST_site" value="site1"/>
                <attribute name="hana_TEST_op_mode" value="logreplay"/>
                <attribute name="hana_TEST_srmode" value="syncmem"/>
            </node>
        </node_attributes>
        """
        node_attributes = ET.fromstring(xml_str)

        result = hana_checker._process_node_attributes(node_attributes)

        assert result["primary_node"] == "node1"
        assert result["secondary_node"] == ""
        assert result["operation_mode"] == "logreplay"
        assert result["replication_mode"] == "syncmem"
        assert result["primary_site_name"] == "site1"

    def test_process_node_attributes_both_nodes(self, hana_checker):
        """
        Test processing node attributes with both primary and secondary nodes.

        :param hana_checker: Instance of HanaClusterStatusChecker.
        :type hana_checker: HanaClusterStatusChecker
        """
        xml_str = """
        <node_attributes>
            <node name="node1">
                <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                <attribute name="hana_TEST_sync_state" value="PRIM"/>
                <attribute name="hana_TEST_site" value="site1"/>
                <attribute name="hana_TEST_op_mode" value="logreplay"/>
                <attribute name="hana_TEST_srmode" value="syncmem"/>
            </node>
            <node name="node2">
                <attribute name="hana_TEST_clone_state" value="DEMOTED"/>
                <attribute name="hana_TEST_sync_state" value="SOK"/>
                <attribute name="hana_TEST_site" value="site2"/>
            </node>
        </node_attributes>
        """
        node_attributes = ET.fromstring(xml_str)

        result = hana_checker._process_node_attributes(node_attributes)

        assert result["primary_node"] == "node1"
        assert result["secondary_node"] == "node2"
        assert result["operation_mode"] == "logreplay"
        assert result["replication_mode"] == "syncmem"
        assert result["primary_site_name"] == "site1"

    def test_is_cluster_ready(self, hana_checker):
        """
        Test the _is_cluster_ready method.

        :param hana_checker: Instance of HanaClusterStatusChecker.
        :type hana_checker: HanaClusterStatusChecker
        """
        hana_checker.result["primary_node"] = ""
        assert not hana_checker._is_cluster_ready()

        hana_checker.result["primary_node"] = "node1"
        assert hana_checker._is_cluster_ready()

    def test_is_cluster_stable(self, hana_checker):
        """
        Test the _is_cluster_stable method.

        :param hana_checker: Instance of HanaClusterStatusChecker.
        :type hana_checker: HanaClusterStatusChecker
        """
        hana_checker.result["primary_node"] = ""
        hana_checker.result["secondary_node"] = ""
        assert not hana_checker._is_cluster_stable()

        hana_checker.result["primary_node"] = "node1"
        hana_checker.result["secondary_node"] = ""
        assert not hana_checker._is_cluster_stable()

        hana_checker.result["primary_node"] = "node1"
        hana_checker.result["secondary_node"] = "node2"
        assert hana_checker._is_cluster_stable()

    def test_run(self, mocker, hana_checker):
        """
        Test the run method of the HanaClusterStatusChecker class.
        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        :param hana_checker: Instance of HanaClusterStatusChecker.
        :type hana_checker: HanaClusterStatusChecker
        """
        mock_super_run = mocker.patch(
            "src.module_utils.get_cluster_status.BaseClusterStatusChecker.run",
            return_value={"status": "PASSED"},
        )

        mock_get_automation = mocker.patch.object(hana_checker, "_get_automation_register")

        result = hana_checker.run()

        mock_super_run.assert_called_once()
        mock_get_automation.assert_called_once()
        assert result["status"] == "PASSED"


class TestRunModule:
    """
    Test cases for the run_module function.
    """

    def test_run_module(self, mocker):
        """
        Test the run_module function.

        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        """
        mock_ansible_module = mocker.MagicMock()
        mock_ansible_module.params = {
            "database_sid": "TEST",
            "ansible_os_family": "REDHAT",
            "operation_step": "check",
        }
        mocker.patch(
            "src.modules.get_cluster_status_db.AnsibleModule", return_value=mock_ansible_module
        )
        mock_run = mocker.MagicMock(return_value={"status": "PASSED"})
        mock_checker = mocker.MagicMock()
        mock_checker.run = mock_run
        mock_checker.get_result.return_value = {"status": "PASSED"}
        mocker.patch(
            "src.modules.get_cluster_status_db.HanaClusterStatusChecker", return_value=mock_checker
        )
        run_module()

        mock_ansible_module.exit_json.assert_called_once_with(status="PASSED")
