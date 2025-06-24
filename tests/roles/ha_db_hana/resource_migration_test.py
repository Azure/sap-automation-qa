# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for HANA DB resource migration tasks.

This test class uses pytest to run functional tests on the HANA DB resource migration tasks
defined in roles/ha_db_hana/tasks/resource-migration.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import os
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_db_hana.roles_testing_base_db import RolesTestingBaseDB


class TestDbResourceMigration(RolesTestingBaseDB):
    """
    Test class for HANA DB resource migration tasks.
    """

    @pytest.fixture
    def hana_migration_tasks(self):
        """
        Load the RolesTestingBaseDB migration tasks from the YAML file.

        :return: Parsed YAML content of the tasks file.
        :rtype: dict
        """
        return self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent
            / "src/roles/ha_db_hana/tasks/resource-migration.yml",
        )

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the HANA DB resource migration tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        task_counter_file = "/tmp/get_cluster_status_counter_resource-migration"
        if os.path.exists(task_counter_file):
            os.remove(task_counter_file)

        commands = [
            {
                "name": "resource_migration_cmd",
                "SUSE": "crm resource move {{ hana_resource_name | default('msl_SAPHana_' ~ "
                "(db_sid | upper) ~ '_HDB' ~ db_instance_number) }} db02 force",
            },
            {
                "name": "get_hana_resource_id",
                "SUSE": "cibadmin --query --scope resources",
            },
            {
                "name": "get_hana_resource_id_saphanasr_angi",
                "SUSE": "cibadmin --query --scope resources",
            },
        ]

        temp_dir = self.setup_test_environment(
            role_type="ha_db_hana",
            ansible_inventory=ansible_inventory,
            task_name="resource-migration",
            task_description="The Resource Migration test validates planned failover scenarios",
            module_names=[
                "project/library/get_cluster_status_db",
                "project/library/log_parser",
                "project/library/send_telemetry_data",
                "project/library/location_constraints",
                "bin/cibadmin",
                "bin/crm_resource",
                "bin/crm",
                "bin/SAPHanaSR-manageProvider",
            ],
            extra_vars_override={"commands": commands, "node_tier": "hana"},
        )

        playbook_content = self.file_operations(
            operation="read",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/resource-migration.yml",
        )
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/resource-migration.yml",
            content=playbook_content.replace("100", "1"),
        )

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_functional_db_migration_success(self, test_environment, ansible_inventory):
        """
        Test the HANA DB resource migration tasks using Ansible Runner.

        :param test_environment: Path to the temporary test environment.
        :type test_environment: str
        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        """
        result = self.run_ansible_playbook(
            test_environment=test_environment,
            inventory_file_name="inventory_db.txt",
            task_type="resource-migration",
        )

        assert result.rc == 0, (
            f"Playbook failed with status: {result.rc}\n"
            f"STDOUT: {result.stdout.read() if result.stdout else 'No output'}\n"
            f"STDERR: {result.stderr.read() if result.stderr else 'No errors'}\n"
            f"Events: {[e.get('event') for e in result.events if 'event' in e]}"
        )

        ok_events, failed_events = [], []
        for event in result.events:
            if event.get("event") == "runner_on_ok":
                ok_events.append(event)
            elif event.get("event") == "runner_on_failed":
                failed_events.append(event)

        assert len(ok_events) > 0
        assert len(failed_events) == 0

        post_status = {}
        pre_status = {}

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            task_result = event.get("event_data", {}).get("res")
            if task and "Move the resource to the targeted node" in task:
                assert task_result.get("rc") == 0
                assert task_result.get("cmd")[3] == "msl_SAPHana_HDB"
            elif task and "Test Execution: Validate HANA DB cluster status 1" in task:
                assert task_result.get("secondary_node") == ""
            elif task and "Test Execution: Validate HANA DB cluster status 2" in task:
                assert task_result.get("secondary_node") != ""
                assert task_result.get("primary_node") != ""
                post_status = task_result
            elif task and "Pre Validation: Validate HANA DB" in task:
                pre_status = task_result
            elif task and "Remove any location_constraints" in task:
                assert task_result.get("changed")
            elif task and "Test Execution: Get HANA resource id" in task:
                assert task_result.get("rc") == 0
                assert task_result.get("stdout")

        assert post_status.get("primary_node") == pre_status.get("secondary_node")
        assert post_status.get("secondary_node") == pre_status.get("primary_node")
