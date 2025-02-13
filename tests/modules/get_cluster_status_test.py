"""
Unit tests for the get_cluster_status module.
"""

import pytest
from src.modules.get_cluster_status import ClusterStatusChecker


@pytest.fixture
def cluster_status_checker():
    """
    Fixture for creating a ClusterStatusChecker instance.

    :return: ClusterStatusChecker instance
    :rtype: ClusterStatusChecker
    """
    return ClusterStatusChecker(database_sid="TEST", ansible_os_family="REDHAT")


class TestClusterStatusChecker:
    def test_run_primary_node(self, mocker, cluster_status_checker):
        """
        Test the run method for a primary node.
        """
        mock_check_output = mocker.patch(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess"
        )
        mock_check_output.side_effect = [
            "reboot",
            """
        <cluster_status>
            <summary>
                <nodes_configured number="2"/>
            </summary>
            <nodes>
                <node name="node2" online="true"/>
            </nodes>
            <node_attributes>
                <node name="node1">
                    <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                    <attribute name="hana_TEST_sync_state" value="PRIM"/>
                </node>
            </node_attributes>
        </cluster_status>
        """,
            "active",
            "True",
        ]

        mock_ansible_module = mocker.patch("src.modules.get_cluster_status.AnsibleModule")
        mock_ansible_module.return_value.params = {
            "operation_step": "check",
            "database_sid": "TEST",
        }

        cluster_status_checker.run()
        assert cluster_status_checker.result["primary_node"] == "node1"
        assert cluster_status_checker.result["secondary_node"] == ""
        assert cluster_status_checker.result["status"] == "PASSED"

    def test_run_secondary_node(self, mocker, cluster_status_checker):
        """
        Test the run method for a secondary node.
        """
        mock_check_output = mocker.patch(
            "src.module_utils.sap_automation_qa.SapAutomationQA.execute_command_subprocess"
        )
        mock_check_output.side_effect = [
            "reboot",
            """
        <cluster_status>
            <summary>
                <nodes_configured number="2"/>
            </summary>
            <nodes>
                <node name="node2" online="true"/>
            </nodes>
            <node_attributes>
                <node name="node1">
                    <attribute name="hana_TEST_clone_state" value="PROMOTED"/>
                    <attribute name="hana_TEST_sync_state" value="PRIM"/>
                </node>
                <node name="node2">
                    <attribute name="hana_TEST_clone_state" value="DEMOTED"/>
                    <attribute name="hana_TEST_sync_state" value="SOK"/>
                </node>
            </node_attributes>
        </cluster_status>
        """,
            "active",
            "True",
        ]
        mock_ansible_module = mocker.patch("src.modules.get_cluster_status.AnsibleModule")
        mock_ansible_module.return_value.params = {
            "operation_step": "check",
            "database_sid": "TEST",
        }

        cluster_status_checker.run()
        assert cluster_status_checker.result["primary_node"] == "node1"
        assert cluster_status_checker.result["secondary_node"] == "node2"
        assert cluster_status_checker.result["status"] == "PASSED"
