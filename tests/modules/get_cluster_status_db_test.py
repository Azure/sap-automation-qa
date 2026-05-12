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
from src.module_utils.enums import (
    OperatingSystemFamily,
    HanaSRProvider,
    HanaTopology,
)


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
        assert result["secondary_site_name"] == ""

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
        assert result["secondary_site_name"] == ""

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
        assert result["secondary_site_name"] == "SITEB"

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
        assert result["secondary_site_name"] == "site2"

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
            "hana_topology": "scale_up",
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


class TestHanaClusterStatusCheckerScaleOutHSR:
    """
    Test cases for HanaClusterStatusChecker with scale-out HSR topology.
    """

    def test_get_cluster_parameters_skips_priority_fencing_delay(
        self, mocker, scaleout_checker_classic
    ):
        """
        Verify PRIORITY_FENCING_DELAY is not queried for scale-out.
        """
        mocker.patch.object(
            scaleout_checker_classic,
            "execute_command_subprocess",
            return_value="true",
        )
        scaleout_checker_classic._get_cluster_parameters()
        assert scaleout_checker_classic.result["AUTOMATED_REGISTER"] == "true"
        assert scaleout_checker_classic.result["PRIORITY_FENCING_DELAY"] == ""
        scaleout_checker_classic.execute_command_subprocess.assert_called_once()

    @pytest.fixture
    def scaleout_checker_classic(self):
        """
        Fixture for a scale-out HSR checker using classic SAPHanaSR provider.

        :return: Instance of HanaClusterStatusChecker for scale-out HSR.
        :rtype: HanaClusterStatusChecker
        """
        return HanaClusterStatusChecker(
            database_sid="TEST",
            ansible_os_family=OperatingSystemFamily.SUSE,
            saphanasr_provider=HanaSRProvider.SAPHANASR,
            db_instance_number="00",
            hana_topology=HanaTopology.SCALE_OUT_HSR,
            hana_clone_resource_name="rsc_SAPHanaCon_TEST_HDB00",
            hana_primitive_resource_name="rsc_SAPHanaPrm_TEST_HDB00",
        )

    SCALEOUT_HSR_XML_CLASSIC = """
    <dummy>
        <node_attributes>
            <node name="node1">
                <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                <attribute name="hana_TEST_sync_state" value="PRIM"/>
                <attribute name="hana_TEST_site" value="SITEA"/>
                <attribute name="hana_TEST_op_mode" value="logreplay"/>
                <attribute name="hana_TEST_srmode" value="syncmem"/>
                <attribute name="hana_TEST_roles"
                    value="master1:master:worker:master"/>
                <attribute name="master-rsc_SAPHanaPrm_TEST_HDB00"
                    value="150"/>
            </node>
            <node name="node2">
                <attribute name="hana_TEST_clone_state" value="DEMOTED"/>
                <attribute name="hana_TEST_sync_state" value="SOK"/>
                <attribute name="hana_TEST_site" value="SITEA"/>
                <attribute name="hana_TEST_roles"
                    value="master1:slave:worker:slave"/>
                <attribute name="master-rsc_SAPHanaPrm_TEST_HDB00"
                    value="-10000"/>
            </node>
            <node name="node3">
                <attribute name="hana_TEST_clone_state" value="DEMOTED"/>
                <attribute name="hana_TEST_sync_state" value="SOK"/>
                <attribute name="hana_TEST_site" value="SITEB"/>
                <attribute name="hana_TEST_roles"
                    value="master1:master:worker:master"/>
                <attribute name="master-rsc_SAPHanaPrm_TEST_HDB00"
                    value="100"/>
            </node>
            <node name="node4">
                <attribute name="hana_TEST_clone_state" value="DEMOTED"/>
                <attribute name="hana_TEST_sync_state" value="SOK"/>
                <attribute name="hana_TEST_site" value="SITEB"/>
                <attribute name="hana_TEST_roles"
                    value="master1:slave:worker:slave"/>
                <attribute name="master-rsc_SAPHanaPrm_TEST_HDB00"
                    value="-12200"/>
            </node>
            <node name="node5">
            </node>
        </node_attributes>
    </dummy>
    """

    REAL_SCALEOUT_HSR_STABLE = """
    <pacemaker-result api-version="2.38"
        request="crm_mon --output-as=xml">
        <node_attributes>
            <node name="t02dhdb00l064">
                <attribute name="NFS_HDB_SITE" value="S1"/>
                <attribute name="azName"
                    value="ANF-EUS2-SAP01-T02_t02dhdb00l0649"/>
                <attribute name="hana_hdb_clone_state"
                    value="PROMOTED"/>
                <attribute name="hana_hdb_gra" value="2.0"/>
                <attribute name="hana_hdb_roles"
                    value="master1:master:worker:master"/>
                <attribute name="hana_hdb_site" value="SITEA"/>
                <attribute name="hana_hdb_op_mode"
                    value="logreplay"/>
                <attribute name="hana_hdb_srmode"
                    value="syncmem"/>
                <attribute name="hana_nfs_s1_active" value="true"/>
                <attribute name="master-SAPHana_HDB_HDB00"
                    value="150"/>
            </node>
            <node name="t02dhdb00l164">
                <attribute name="NFS_HDB_SITE" value="S1"/>
                <attribute name="hana_hdb_clone_state"
                    value="DEMOTED"/>
                <attribute name="hana_hdb_gra" value="2.0"/>
                <attribute name="hana_hdb_roles"
                    value="master1:slave:worker:slave"/>
                <attribute name="hana_hdb_site" value="SITEA"/>
                <attribute name="hana_nfs_s1_active" value="true"/>
                <attribute name="master-SAPHana_HDB_HDB00"
                    value="101"/>
            </node>
            <node name="t02dhdb01l064">
                <attribute name="NFS_HDB_SITE" value="S1"/>
                <attribute name="hana_hdb_clone_state"
                    value="DEMOTED"/>
                <attribute name="hana_hdb_gra" value="2.0"/>
                <attribute name="hana_hdb_roles"
                    value="master1:slave:worker:slave"/>
                <attribute name="hana_hdb_site" value="SITEA"/>
                <attribute name="hana_nfs_s1_active" value="true"/>
                <attribute name="master-SAPHana_HDB_HDB00"
                    value="101"/>
            </node>
            <node name="t02dhdb01l164">
                <attribute name="NFS_HDB_SITE" value="S2"/>
                <attribute name="hana_hdb_clone_state"
                    value="DEMOTED"/>
                <attribute name="hana_hdb_gra" value="2.0"/>
                <attribute name="hana_hdb_roles"
                    value="master1:master:worker:master"/>
                <attribute name="hana_hdb_site" value="SITEB"/>
                <attribute name="hana_nfs_s2_active" value="true"/>
                <attribute name="master-SAPHana_HDB_HDB00"
                    value="100"/>
            </node>
            <node name="t02dhdb02l064">
                <attribute name="NFS_HDB_SITE" value="S2"/>
                <attribute name="hana_hdb_clone_state"
                    value="DEMOTED"/>
                <attribute name="hana_hdb_gra" value="2.0"/>
                <attribute name="hana_hdb_roles"
                    value="master1:slave:worker:slave"/>
                <attribute name="hana_hdb_site" value="SITEB"/>
                <attribute name="hana_nfs_s2_active" value="true"/>
                <attribute name="master-SAPHana_HDB_HDB00"
                    value="-12200"/>
            </node>
            <node name="t02dhdb02l164">
                <attribute name="NFS_HDB_SITE" value="S2"/>
                <attribute name="hana_hdb_clone_state"
                    value="DEMOTED"/>
                <attribute name="hana_hdb_gra" value="2.0"/>
                <attribute name="hana_hdb_roles"
                    value="master1:slave:worker:slave"/>
                <attribute name="hana_hdb_site" value="SITEB"/>
                <attribute name="hana_nfs_s2_active" value="true"/>
                <attribute name="master-SAPHana_HDB_HDB00"
                    value="-12200"/>
            </node>
            <node name="t02observer00l649">
                <attribute name="azName"
                    value="ANF-EUS2-SAP01-T02_t02observer00l649"/>
            </node>
        </node_attributes>
    </pacemaker-result>
    """

    REAL_SCALEOUT_HSR_DEGRADED = """
    <pacemaker-result api-version="2.38"
        request="crm_mon --output-as=xml">
        <node_attributes>
            <node name="t02dhdb00l064">
                <attribute name="NFS_HDB_SITE" value="S1"/>
                <attribute name="azName"
                    value="ANF-EUS2-SAP01-T02_t02dhdb00l0649"/>
                <attribute name="hana_hdb_clone_state"
                    value="UNDEFINED"/>
                <attribute name="hana_hdb_gra" value="2.0"/>
                <attribute name="hana_hdb_roles"
                    value="master1::worker:"/>
                <attribute name="hana_hdb_site" value="SITEA"/>
                <attribute name="hana_nfs_s1_active" value="true"/>
                <attribute name="master-SAPHana_HDB_HDB00"
                    value="-INFINITY"/>
            </node>
            <node name="t02observer00l649">
                <attribute name="azName"
                    value="ANF-EUS2-SAP01-T02_t02observer00l649"/>
            </node>
        </node_attributes>
    </pacemaker-result>
    """

    @pytest.fixture
    def scaleout_checker_hdb_controller(self):
        """
        Fixture modeled on a real 7-node HANA scale-out HSR cluster.

        SID=hdb (lowercase, matching crm_mon attribute naming convention
        hana_hdb_*), instance 00, RHEL with SAPHanaController resource
        agent.  The ANGI provider is used because RHEL scale-out
        clusters use the SAPHanaController RA which produces
        ANGI-style node attributes (master-based sync, numeric
        values).

        :return: Instance of HanaClusterStatusChecker.
        :rtype: HanaClusterStatusChecker
        """
        return HanaClusterStatusChecker(
            database_sid="hdb",
            ansible_os_family=OperatingSystemFamily.REDHAT,
            saphanasr_provider=HanaSRProvider.ANGI,
            db_instance_number="00",
            hana_topology=HanaTopology.SCALE_OUT_HSR,
            hana_clone_resource_name="SAPHana_HDB_HDB00-clone",
            hana_primitive_resource_name="SAPHana_HDB_HDB00",
        )

    def test_process_scale_out_hsr_full_cluster_classic(self, scaleout_checker_classic):
        """
        Test processing a 5-node scale-out HSR cluster with classic
        SAPHanaSR provider: 2 primary-site workers, 2 secondary-site
        workers, 1 majority maker.
        """
        result = scaleout_checker_classic._process_node_attributes(
            ET.fromstring(self.SCALEOUT_HSR_XML_CLASSIC)
        )

        assert result["primary_node"] == "node1"
        assert result["primary_site_name"] == "SITEA"
        assert sorted(result["primary_site_nodes"]) == [
            "node1",
            "node2",
        ]
        assert result["secondary_site_name"] == "SITEB"
        assert sorted(result["secondary_site_nodes"]) == [
            "node3",
            "node4",
        ]
        assert result["secondary_node"] == "node3"
        assert result["majority_maker_node"] == "node5"
        assert result["operation_mode"] == "logreplay"
        assert result["replication_mode"] == "syncmem"

    def test_process_scale_out_hsr_no_node_attributes(self, scaleout_checker_classic):
        """
        Test with XML missing the node_attributes element entirely.
        """
        xml_str = "<dummy></dummy>"
        result = scaleout_checker_classic._process_node_attributes(ET.fromstring(xml_str))

        assert result["primary_node"] == ""
        assert result["primary_site_nodes"] == []
        assert result["secondary_site_nodes"] == []
        assert result["majority_maker_node"] == ""

    def test_process_scale_out_hsr_primary_only(self, scaleout_checker_classic):
        """
        Test with only primary-site nodes present (secondary site
        not yet registered).
        """
        xml_str = """
        <dummy>
            <node_attributes>
                <node name="node1">
                    <attribute name="hana_TEST_clone_state"
                        value="PROMOTED"/>
                    <attribute name="hana_TEST_sync_state"
                        value="PRIM"/>
                    <attribute name="hana_TEST_site" value="SITEA"/>
                    <attribute name="hana_TEST_op_mode"
                        value="logreplay"/>
                    <attribute name="hana_TEST_srmode"
                        value="syncmem"/>
                </node>
                <node name="node5">
                </node>
            </node_attributes>
        </dummy>
        """
        result = scaleout_checker_classic._process_node_attributes(ET.fromstring(xml_str))

        assert result["primary_node"] == "node1"
        assert result["primary_site_nodes"] == ["node1"]
        assert result["secondary_site_nodes"] == []
        assert result["majority_maker_node"] == "node5"

    def test_process_scale_out_hsr_no_majority_maker(self, scaleout_checker_classic):
        """
        Test with no majority maker node present.
        """
        xml_str = """
        <dummy>
            <node_attributes>
                <node name="node1">
                    <attribute name="hana_TEST_clone_state"
                        value="PROMOTED"/>
                    <attribute name="hana_TEST_sync_state"
                        value="PRIM"/>
                    <attribute name="hana_TEST_site" value="SITEA"/>
                </node>
                <node name="node3">
                    <attribute name="hana_TEST_clone_state"
                        value="DEMOTED"/>
                    <attribute name="hana_TEST_sync_state"
                        value="SOK"/>
                    <attribute name="hana_TEST_site" value="SITEB"/>
                </node>
            </node_attributes>
        </dummy>
        """
        result = scaleout_checker_classic._process_node_attributes(ET.fromstring(xml_str))

        assert result["primary_node"] == "node1"
        assert result["majority_maker_node"] == ""

    def test_is_cluster_stable_scale_out_hsr_full(self, scaleout_checker_classic):
        """
        Test _is_cluster_stable returns True when all scale-out HSR
        components are present.
        """
        scaleout_checker_classic.result["primary_node"] = "node1"
        scaleout_checker_classic.result["secondary_node"] = "node3"
        scaleout_checker_classic.result["secondary_site_nodes"] = [
            "node3",
            "node4",
        ]
        scaleout_checker_classic.result["majority_maker_node"] = "node5"
        assert scaleout_checker_classic._is_cluster_stable()

    def test_is_cluster_stable_scale_out_hsr_no_secondary(self, scaleout_checker_classic):
        """
        Test _is_cluster_stable returns False when secondary site has
        no nodes.
        """
        scaleout_checker_classic.result["primary_node"] = "node1"
        scaleout_checker_classic.result["secondary_site_nodes"] = []
        scaleout_checker_classic.result["majority_maker_node"] = "node5"
        assert not scaleout_checker_classic._is_cluster_stable()

    def test_is_cluster_stable_scale_out_hsr_no_majority_maker(self, scaleout_checker_classic):
        """
        Test _is_cluster_stable returns False when majority maker is
        missing.
        """
        scaleout_checker_classic.result["primary_node"] = "node1"
        scaleout_checker_classic.result["secondary_site_nodes"] = [
            "node3",
        ]
        scaleout_checker_classic.result["majority_maker_node"] = ""
        assert not scaleout_checker_classic._is_cluster_stable()

    def test_is_cluster_stable_scale_out_hsr_no_primary(self, scaleout_checker_classic):
        """
        Test _is_cluster_stable returns False when no PROMOTED master
        exists.
        """
        scaleout_checker_classic.result["primary_node"] = ""
        scaleout_checker_classic.result["secondary_site_nodes"] = [
            "node3",
        ]
        scaleout_checker_classic.result["majority_maker_node"] = "node5"
        assert not scaleout_checker_classic._is_cluster_stable()

    def test_run_module_scale_out(self, mocker):
        """
        Test run_module with scale_out_hsr topology on RHEL.
        The detected provider is SAPHanaSR; SAPHanaController
        patterns are selected by topology, not by provider.
        """
        mock_ansible_module = mocker.MagicMock()
        mock_ansible_module.params = {
            "database_sid": "hdb",
            "operation_step": "check",
            "saphanasr_provider": "SAPHanaSR",
            "db_instance_number": "00",
            "hana_topology": "scale_out_hsr",
        }
        mocker.patch(
            "src.modules.get_cluster_status_db.ansible_facts",
            return_value={"os_family": "REDHAT"},
        )
        mocker.patch(
            "src.modules.get_cluster_status_db.AnsibleModule",
            return_value=mock_ansible_module,
        )
        mock_checker = mocker.MagicMock()
        mock_checker.run.return_value = {"status": "PASSED"}
        mock_checker.get_result.return_value = {
            "status": "PASSED",
        }
        mocker.patch(
            "src.modules.get_cluster_status_db" ".HanaClusterStatusChecker",
            return_value=mock_checker,
        )
        run_module()

        mock_ansible_module.exit_json.assert_called_once_with(status="PASSED")

    def test_real_stable_cluster_sites_partitioned(self, scaleout_checker_hdb_controller):
        """
        Verify primary identification, site partitioning, op/repl
        modes, and secondary_node from real 7-node crm_mon output.
        """
        result = scaleout_checker_hdb_controller._process_node_attributes(
            ET.fromstring(self.REAL_SCALEOUT_HSR_STABLE)
        )
        assert result["primary_node"] == "t02dhdb00l064"
        assert result["primary_site_name"] == "SITEA"
        assert sorted(result["primary_site_nodes"]) == [
            "t02dhdb00l064",
            "t02dhdb00l164",
            "t02dhdb01l064",
        ]
        assert result["secondary_site_name"] == "SITEB"
        assert sorted(result["secondary_site_nodes"]) == [
            "t02dhdb01l164",
            "t02dhdb02l064",
            "t02dhdb02l164",
        ]
        assert result["secondary_node"] == "t02dhdb01l164"
        assert result["majority_maker_node"] == "t02observer00l649"
        assert result["operation_mode"] == "logreplay"
        assert result["replication_mode"] == "syncmem"

    def test_real_stable_cluster_status_dict(self, scaleout_checker_hdb_controller):
        """
        Verify cluster_status carries per-node attribute dicts with
        real-world attributes (NFS_HDB_SITE, azName, gra, etc.).
        """
        result = scaleout_checker_hdb_controller._process_node_attributes(
            ET.fromstring(self.REAL_SCALEOUT_HSR_STABLE)
        )
        primary_cs = result["cluster_status"]["primary"]
        assert "t02dhdb00l064" in primary_cs
        assert primary_cs["t02dhdb00l064"]["hana_hdb_clone_state"] == "PROMOTED"
        assert primary_cs["t02dhdb00l064"]["master-SAPHana_HDB_HDB00"] == "150"
        assert primary_cs["t02dhdb00l064"]["hana_hdb_gra"] == "2.0"
        assert primary_cs["t02dhdb00l064"]["NFS_HDB_SITE"] == "S1"

    def test_real_stable_cluster_is_stable(self, scaleout_checker_hdb_controller):
        """
        Verify the 7-node healthy cluster is reported as stable.
        """
        scaleout_checker_hdb_controller._process_node_attributes(
            ET.fromstring(self.REAL_SCALEOUT_HSR_STABLE)
        )
        assert scaleout_checker_hdb_controller._is_cluster_stable()
        assert scaleout_checker_hdb_controller._is_cluster_ready()

    def test_real_degraded_cluster_site_nodes(self, scaleout_checker_hdb_controller):
        """
        In the degraded state, t02dhdb00l064 has clone_state=UNDEFINED
        so no primary is found; single node groups into secondary;
        observer still detected as majority maker.
        """
        result = scaleout_checker_hdb_controller._process_node_attributes(
            ET.fromstring(self.REAL_SCALEOUT_HSR_DEGRADED)
        )
        assert result["primary_node"] == ""
        assert result["primary_site_name"] == ""
        assert result["primary_site_nodes"] == []
        assert result["secondary_site_nodes"] == ["t02dhdb00l064"]

    def test_real_degraded_cluster_not_stable(self, scaleout_checker_hdb_controller):
        """
        A degraded cluster with UNDEFINED clone_state and -INFINITY
        master score should NOT be reported as stable.

        Verify the UNDEFINED/-INFINITY attributes are preserved in
        cluster_status for diagnostic purposes.
        """
        scaleout_checker_hdb_controller._process_node_attributes(
            ET.fromstring(self.REAL_SCALEOUT_HSR_DEGRADED)
        )
        assert not scaleout_checker_hdb_controller._is_cluster_stable()
        assert not scaleout_checker_hdb_controller._is_cluster_ready()

        result = scaleout_checker_hdb_controller._process_node_attributes(
            ET.fromstring(self.REAL_SCALEOUT_HSR_DEGRADED)
        )
        sec_cs = result["cluster_status"]["secondary"]
        assert "t02dhdb00l064" in sec_cs
        assert sec_cs["t02dhdb00l064"]["hana_hdb_clone_state"] == "UNDEFINED"
        assert sec_cs["t02dhdb00l064"]["master-SAPHana_HDB_HDB00"] == "-INFINITY"
        assert sec_cs["t02dhdb00l064"]["hana_hdb_roles"] == "master1::worker:"

    def test_real_provider_config_hdb_controller(self, scaleout_checker_hdb_controller):
        """
        Verify provider config for real RHEL HDB scale-out cluster uses
        the SAPHanaController RA pattern (derived from topology) with
        master-SAPHana_HDB_HDB00 sync attribute.
        """
        config = scaleout_checker_hdb_controller._get_provider_config()
        assert config["clone_attr"] == "hana_hdb_clone_state"
        assert config["sync_attr"] == "master-SAPHana_HDB_HDB00"
        assert config["primary"] == {
            "clone": "PROMOTED",
            "sync": "150",
        }
        assert config["secondary"] == {
            "clone": "DEMOTED",
            "sync": "100",
        }
