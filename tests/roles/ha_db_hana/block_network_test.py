# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for HANA DB block network between primary and secondary nodes.

This test class uses pytest to run functional tests on the HANA DB block-network
tasks defined in roles/ha_db_hana/tasks/block-network.yml.
It sets up a temporary test environment, mocks necessary Python modules and commands, and verifies
the execution of the tasks.
"""

import os
import shutil
import pytest
from tests.roles.ha_db_hana.roles_testing_base_db import RolesTestingBaseDB


class TestBlockNetworkTest(RolesTestingBaseDB):
    """
    Test class for HANA DB block network between primary and secondary nodes.
    """

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the HANA DB block-network test

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :type: str
        """

        task_counter_file = "/tmp/get_cluster_status_counter_block-network"
        if os.path.exists(task_counter_file):
            os.remove(task_counter_file)

        if os.path.exists("/tmp/ping_counter_block-network"):
            os.remove("/tmp/ping_counter_block-network")

        module_names = [
            "project/library/get_cluster_status_db",
            "project/library/log_parser",
            "project/library/send_telemetry_data",
            "project/library/location_constraints",
            "project/library/check_indexserver",
            "project/library/filesystem_freeze",
            "bin/crm_resource",
            "bin/iptables",
            "bin/nc",
            "bin/echo",
            "bin/sleep",
            "bin/SAPHanaSR-manageProvider",
        ]

        temp_dir = self.setup_test_environment(
            role_type="ha_db_hana",
            ansible_inventory=ansible_inventory,
            task_name="block-network",
            task_description="The block network test validates failover scenarios",
            module_names=module_names,
            extra_vars_override={
                "node_tier": "hana",
                "NFS_provider": "ANF",
                "database_cluster_type": "ISCSI",
                "sap_port_to_ping": "1128",
            },
        )

        playbook_content = self.file_operations(
            operation="read",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/block-network.yml",
        )
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/block-network.yml",
            content=playbook_content.replace(
                "for i in $(seq 1 30); do",
                "for i in {1..30}; do",
            ),
        )

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_functional_db_primary_node_success(self, test_environment, ansible_inventory):
        """
        Test the HANA DB block network between primary and secondary nodes.
        This test verifies the successful execution of the block network task and checks

        :param test_environment: Path to the temporary test environment.
        :type test_environment: str
        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        """
        result = self.run_ansible_playbook(
            test_environment=test_environment,
            inventory_file_name="inventory_db.txt",
            task_type="block-network",
        )

        assert result.rc == 0, (
            f"Playbook failed with status: {result.rc}\n"
            f"STDOUT: {result.stdout if hasattr(result, 'stdout') else 'No output'}\n"
            f"STDERR: {result.stderr if hasattr(result, 'stderr') else 'No errors'}\n"
            f"Events: {[e.get('event') for e in result.events if 'event' in e]}"
        )

        ok_events, failed_events = [], []
        for event in result.events:
            if event.get("event") == "runner_on_ok":
                ok_events.append(event)
            elif event.get("event") == "runner_on_failed":
                failed_events.append(event)

        assert len(ok_events) > 0
        # There will be 1 failed event, connection failure to primary node
        # This is the behavior be have mocked in the nc functionality
        assert len(failed_events) == 1

        post_status = {}
        pre_status = {}

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            task_result = event.get("event_data", {}).get("res")

            if task and "Create a firewall" in task:
                assert task_result.get("rc") == 0
            elif task and "Pre Validation: Validate HANA DB" in task:
                pre_status = task_result
            elif task and "Test Execution: Validate HANA DB cluster status 2" in task:
                post_status = task_result
            elif task and "Remove any location_constraints" in task:
                assert task_result.get("changed")

        assert post_status.get("primary_node") == pre_status.get("secondary_node")
        assert post_status.get("secondary_node") == pre_status.get("primary_node")
