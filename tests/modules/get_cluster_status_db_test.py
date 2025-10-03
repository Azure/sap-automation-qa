# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Unit tests for the get_cluster_status_db module.
"""

import xml.etree.ElementTree as ET
import pytest
from src.modules.get_cluster_status_db import (
    HanaClusterStatusChecker,
    run_module,
)
from src.module_utils.enums import OperatingSystemFamily, HanaSRProvider


class TestHanaClusterStatusChecker:
    """
    Test cases for the HanaClusterStatusChecker class.
    """

    @pytest.fixture
    def hana_checker_classic(self):
        """
        Fixture for creating a HanaClusterStatusChecker instance with classic SAP HANA SR provider.

        :return: Instance of HanaClusterStatusChecker.
        :rtype: HanaClusterStatusChecker
        """
        return HanaClusterStatusChecker(
            database_sid="TEST",
            ansible_os_family=OperatingSystemFamily.REDHAT,
            saphanasr_provider=HanaSRProvider.SAPHANASR,
            db_instance_number="00",
            hana_clone_resource_name="rsc_SAPHanaCon_TEST_HDB00",
            hana_primitive_resource_name="rsc_SAPHanaPrm_TEST_HDB00",
        )

    @pytest.fixture
    def hana_checker_angi(self):
        """
        Fixture for creating a HanaClusterStatusChecker instance with ANGI SAP HANA SR provider.

        :return: Instance of HanaClusterStatusChecker.
        :rtype: HanaClusterStatusChecker
        """
        return HanaClusterStatusChecker(
            database_sid="TEST",
            ansible_os_family=OperatingSystemFamily.SUSE,
            saphanasr_provider=HanaSRProvider.ANGI,
            db_instance_number="00",
            hana_clone_resource_name="rsc_SAPHanaCon_TEST_HDB00",
            hana_primitive_resource_name="rsc_SAPHanaCon_TEST_HDB00",
        )

    def test_get_cluster_pramaeters(self, mocker, hana_checker_classic):
        """
        Test the _get_cluster_parameters method.

        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        :param hana_checker_classic: Instance of HanaClusterStatusChecker.
        :type hana_checker_classic: HanaClusterStatusChecker
        """
        mocker.patch.object(
            hana_checker_classic,
            "execute_command_subprocess",
            return_value="true",
        )

        hana_checker_classic._get_cluster_parameters()

        assert hana_checker_classic.result["AUTOMATED_REGISTER"] == "true"

    def test_get_cluster_parameters_exception(self, mocker, hana_checker_classic):
        """
        Test the _get_cluster_parameters method when an exception occurs.

        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        :param hana_checker_classic: Instance of HanaClusterStatusChecker.
        :type hana_checker_classic: HanaClusterStatusChecker
        """
        mocker.patch.object(
            hana_checker_classic, "execute_command_subprocess", side_effect=Exception("Test error")
        )

        hana_checker_classic._get_cluster_parameters()

        assert hana_checker_classic.result["AUTOMATED_REGISTER"] == "unknown"

    def test_process_node_attributes_primary_only(self, hana_checker_classic):
        """
        Test processing node attributes with only the primary node.

        :param hana_checker_classic: Instance of HanaClusterStatusChecker.
        :type hana_checker_classic: HanaClusterStatusChecker
        """

        xml_str = """
        <dummy>
            <node_attributes>
                <node name="node1">
                    <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                    <attribute name="hana_TEST_sync_state" value="PRIM"/>
                    <attribute name="hana_TEST_site" value="site1"/>
                    <attribute name="hana_TEST_op_mode" value="logreplay"/>
                    <attribute name="hana_TEST_srmode" value="syncmem"/>
                </node>
            </node_attributes>
        </dummy>
        """

        result = hana_checker_classic._process_node_attributes(ET.fromstring(xml_str))

        assert result["primary_node"] == "node1"
        assert result["secondary_node"] == ""
        assert result["operation_mode"] == "logreplay"
        assert result["replication_mode"] == "syncmem"
        assert result["primary_site_name"] == "site1"

    def test_process_node_attributes_primary_only_angi(self, hana_checker_angi):
        """
        Test processing node attributes with only the primary node when using ANGI provider.

        :param hana_checker_angi: Instance of HanaClusterStatusChecker.
        :type hana_checker_angi: HanaClusterStatusChecker
        """

        xml_str = """
        <dummy>
            <node_attributes>
                <node name="node1">
                    <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                    <attribute name="hana_TEST_roles" value="master1:master:worker:master"/>
                    <attribute name="hana_TEST_site" value="SITEA"/>
                    <attribute name="hana_TEST_vhost" value="node1"/>
                    <attribute name="master-rsc_SAPHanaCon_TEST_HDB00" value="150"/>
                </node>
            </node_attributes>
        </dummy>
        """

        result = hana_checker_angi._process_node_attributes(ET.fromstring(xml_str))

        assert result["primary_node"] == "node1"
        assert result["secondary_node"] == ""
        assert result["primary_site_name"] == "SITEA"

    def test_process_node_attributes_both_nodes_angi(self, hana_checker_angi):
        """
        Test processing node attributes with both primary and secondary nodes.

        :param hana_checker_angi: Instance of HanaClusterStatusChecker.
        :type hana_checker_angi: HanaClusterStatusChecker
        """
        xml_str = """
        <dummy>
            <node_attributes>
                <node name="node1">
                    <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                    <attribute name="hana_TEST_roles" value="master1:master:worker:master"/>
                    <attribute name="hana_TEST_site" value="SITEA"/>
                    <attribute name="hana_TEST_vhost" value="node1"/>
                    <attribute name="master-rsc_SAPHanaCon_TEST_HDB00" value="150"/>
                </node>
                <node name="node2">
                    <attribute name="hana_TEST_clone_state" value="DEMOTED"/>
                    <attribute name="hana_TEST_roles" value="master1:master:worker:master"/>
                    <attribute name="hana_TEST_site" value="SITEB"/>
                    <attribute name="hana_TEST_vhost" value="node2"/>
                    <attribute name="master-rsc_SAPHanaCon_TEST_HDB00" value="100"/>
                </node>
            </node_attributes>
        </dummy>
        """
        result = hana_checker_angi._process_node_attributes(ET.fromstring(xml_str))

        assert result["primary_node"] == "node1"
        assert result["secondary_node"] == "node2"
        assert result["primary_site_name"] == "SITEA"

    def test_process_node_attributes_both_nodes(self, hana_checker_classic):
        """
        Test processing node attributes with both primary and secondary nodes.

        :param hana_checker_classic: Instance of HanaClusterStatusChecker.
        :type hana_checker_classic: HanaClusterStatusChecker
        """
        xml_str = """
        <dummy>
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
        </dummy>
        """
        result = hana_checker_classic._process_node_attributes(ET.fromstring(xml_str))

        assert result["primary_node"] == "node1"
        assert result["secondary_node"] == "node2"
        assert result["operation_mode"] == "logreplay"
        assert result["replication_mode"] == "syncmem"
        assert result["primary_site_name"] == "site1"

    def test_is_cluster_ready(self, hana_checker_classic):
        """
        Test the _is_cluster_ready method.

        :param hana_checker_classic: Instance of HanaClusterStatusChecker.
        :type hana_checker_classic: HanaClusterStatusChecker
        """
        hana_checker_classic.result["primary_node"] = ""
        assert not hana_checker_classic._is_cluster_ready()

        hana_checker_classic.result["primary_node"] = "node1"
        assert hana_checker_classic._is_cluster_ready()

    def test_is_cluster_stable(self, hana_checker_classic):
        """
        Test the _is_cluster_stable method.

        :param hana_checker_classic: Instance of HanaClusterStatusChecker.
        :type hana_checker_classic: HanaClusterStatusChecker
        """
        hana_checker_classic.result["primary_node"] = ""
        hana_checker_classic.result["secondary_node"] = ""
        assert not hana_checker_classic._is_cluster_stable()

        hana_checker_classic.result["primary_node"] = "node1"
        hana_checker_classic.result["secondary_node"] = ""
        assert not hana_checker_classic._is_cluster_stable()

        hana_checker_classic.result["primary_node"] = "node1"
        hana_checker_classic.result["secondary_node"] = "node2"
        assert hana_checker_classic._is_cluster_stable()

    def test_run(self, mocker, hana_checker_classic):
        """
        Test the run method of the HanaClusterStatusChecker class.
        :param mocker: Mocking library for Python.
        :type mocker: _mocker.MagicMock
        :param hana_checker_classic: Instance of HanaClusterStatusChecker.
        :type hana_checker_classic: HanaClusterStatusChecker
        """
        mock_super_run = mocker.patch(
            "src.module_utils.get_cluster_status.BaseClusterStatusChecker.run",
            return_value={"status": "PASSED"},
        )

        mock_get_automation = mocker.patch.object(hana_checker_classic, "_get_cluster_parameters")

        result = hana_checker_classic.run()

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
            "operation_step": "check",
            "saphanasr_provider": "SAPHanaSR",
            "db_instance_number": "00",
        }
        mocker.patch(
            "src.modules.get_cluster_status_db.ansible_facts", return_value={"os_family": "REDHAT"}
        )

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
