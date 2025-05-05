# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for ASCS migration tasks.

This test class uses pytest to run functional tests on the ASCS migration tasks
defined in roles/ha_scs/tasks/ascs-migration.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import os
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_scs.roles_testing_base_scs import RolesTestingBaseSCS


class TestASCSMigration(RolesTestingBaseSCS):
    """
    Test class for ASCS migration tasks.
    """

    @pytest.fixture
    def ascs_migration_tasks(self):
        """
        Load the ASCS migration tasks from the YAML file.

        :return: Parsed YAML content of the tasks file.
        :rtype: dict
        """
        return self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent
            / "src/roles/ha_scs/tasks/ascs-migration.yml",
        )

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the ASCS migration tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        os.environ["TASK_NAME"] = "ascs-migration"
        task_counter_file = "/tmp/get_cluster_status_counter_ascs-migration"
        if os.path.exists(task_counter_file):
            os.remove(task_counter_file)

        commands = [
            {"name": "get_sap_instance_resource_id", "SUSE": "cibadmin --query --scope resources"},
            {
                "name": "ascs_resource_migration_cmd",
                "SUSE": "crm resource migrate SAP_ASCS00_ascs00 scs02",
            },
            {
                "name": "ascs_resource_unmigrate_cmd",
                "SUSE": "crm resource clear SAP_ASCS00_ascs00",
            },
        ]

        temp_dir = self.setup_test_environment(
            role_type="ha_scs",
            ansible_inventory=ansible_inventory,
            task_name="ascs-migration",
            task_description="The Resource Migration test validates planned failover scenarios",
            module_names=[
                "project/library/get_cluster_status_scs",
                "project/library/log_parser",
                "project/library/send_telemetry_data",
                "bin/crm_resource",
                "bin/crm",
                "bin/cibadmin",
            ],
            extra_vars_override={"commands": commands, "node_tier": "scs"},
        )

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_functional_ascs_migration_success(self, test_environment, ansible_inventory):
        """
        Test the ASCS migration tasks using Ansible Runner.

        :param test_environment: Path to the temporary test environment.
        :type test_environment: str
        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        """
        result = self.run_ansible_playbook(
            test_environment=test_environment, inventory_file_name="inventory_scs.txt"
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

        migrate_executed = False
        validate_executed = False
        unmigrate_executed = False
        cleanup_executed = False
        post_status = {}
        pre_status = {}

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            if task and "Migrate ASCS resource" in task:
                migrate_executed = True
            elif task and "Test Execution: Validate SCS" in task:
                validate_executed = True
                post_status = event.get("event_data", {}).get("res")
            elif task and "Cleanup resources" in task:
                cleanup_executed = True
            elif task and "Pre Validation: Validate SCS" in task:
                pre_status = event.get("event_data", {}).get("res")
            elif task and "Remove location constraints" in task:
                unmigrate_executed = True

        assert post_status.get("ascs_node") == pre_status.get("ers_node")
        assert post_status.get("ers_node") == pre_status.get("ascs_node")

        assert migrate_executed, "ASCS migration task was not executed"
        assert validate_executed, "SCS cluster status validation task was not executed"
        assert unmigrate_executed, "Remove location constraints task was not executed"
        assert cleanup_executed, "Cleanup resources task was not executed"
