# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for ASCS migration tasks.

This test class uses pytest to run functional tests on the ASCS migration tasks
defined in roles/ha_scs/tasks/ascs-migration.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import tempfile
import os
import json
import shutil
from pathlib import Path
import pytest
from tests.roles.roles_testing_base import RolesTestingBase


class TestASCSMigration(RolesTestingBase):
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

        temp_dir = tempfile.mkdtemp()

        os.makedirs(f"{temp_dir}/env", exist_ok=True)
        os.makedirs(f"{temp_dir}/project", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/roles/ha_scs/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/roles/misc/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/bin", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/library", exist_ok=True)

        if os.path.exists("/tmp/get_cluster_status_counter"):
            os.remove("/tmp/get_cluster_status_counter")

        file_list = [
            "ha_scs/tasks/ascs-migration.yml",
            "misc/tasks/test-case-setup.yml",
            "misc/tasks/pre-validations-scs.yml",
            "misc/tasks/post-validations-scs.yml",
            "misc/tasks/rescue.yml",
            "misc/tasks/var-log-messages.yml",
            "misc/tasks/post-telemetry-data.yml",
        ]
        for file in file_list:
            src_file = Path(__file__).parent.parent.parent / f"src/roles/{file}"
            dest_file = f"{temp_dir}/project/roles/{file}"
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            shutil.copy(src_file, dest_file)

        self.mock_modules(
            temp_dir=temp_dir,
            module_names=[
                "project/library/get_cluster_status_scs",
                "project/library/log_parser",
                "project/library/send_telemetry_data",
                "bin/crm_resource",
                "bin/crm",
            ],
        )

        extravars = {
            "item": {
                "name": "Manual ASCS Migration",
                "task_name": "ascs-migration",
                "description": "The Resource Migration test validates planned failover scenarios by "
                + "executing controlled resource movement between ASCS and ERS nodes.",
                "enabled": True,
            },
            "node_tier": "scs",
            "commands": [
                {
                    "name": "ascs_resource_migration_cmd",
                    "SUSE": "crm resource migrate SAP_ASCS00_ascs00 scs02",
                },
                {
                    "name": "ascs_resource_unmigrate_cmd",
                    "SUSE": "crm resource clear SAP_ASCS00_ascs00",
                },
            ],
            "ansible_os_family": "SUSE",
            "sap_sid": "TST",
            "db_sid": "TST",
            "database_high_availability": "true",
            "scs_high_availability": "true",
            "database_cluster_type": "AFA",
            "NFS_provider": "AFS",
            "scs_cluster_type": "AFA",
            "platform": "HANA",
            "scs_instance_number": "00",
            "ers_instance_number": "01",
            "group_name": "HA_SCS",
            "group_invocation_id": "test-run-123",
            "group_start_time": "2025-03-18 11:00:00",
            "telemetry_data_destination": "mock_destination",
            "_workspace_directory": temp_dir,
            "ansible_distribution": "SUSE",
            "ansible_distribution_version": "15",
        }

        # Write the extravars to a file
        self.file_operations(
            operation="write", file_path=f"{temp_dir}/env/extravars", content=json.dumps(extravars)
        )

        # Read the playbook content and replace placeholders with actual values
        playbook_content = self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent / "tests/roles/mock_data/playbook.txt",
        )

        playbook_content = playbook_content.replace("ansible_hostname ==", "inventory_hostname ==")

        # Write the playbook content to a temporary file
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/test_playbook.yml",
            content=playbook_content
            % (
                extravars["item"]["name"],
                temp_dir,
                extravars["item"]["task_name"],
            ),
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
            test_environment=test_environment,
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
