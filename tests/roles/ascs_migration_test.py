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
import ansible_runner


class TestASCSMigration:
    """
    Test class for ASCS migration tasks.
    """

    def _file_operations(self, operation, file_path, content=None):
        """
        Perform file operations (read, write) on a given file.

        :param operation: The operation to perform (create, read, write, delete).
        :type operation: str
        :param file_path: The path to the file.
        :type file_path: str
        :param content: The content to write to the file (for write operation).
        :type content: str
        :return: The content of the file (for read operation).
        :rtype: str
        """

        file_operation = "w" if operation == "write" else "r"
        with open(file_path, file_operation, encoding="utf-8") as f:
            if operation == "write":
                f.write(content)
            elif operation == "read":
                return f.read()

    @pytest.fixture
    def ansible_inventory(self):
        """
        Create a temporary Ansible inventory file for testing.
        This inventory contains two hosts (scs01 and scs02) with local connections.

        :yield: Path to the temporary inventory file.
        :yield type: str
        """
        inventory_content = self._file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent / "tests/roles/mock_data/inventory.txt",
        )

        inventory_path = Path(__file__).parent / "test_inventory.ini"
        self._file_operations(
            operation="write",
            file_path=inventory_path,
            content=inventory_content,
        )

        yield str(inventory_path)

        inventory_path.unlink(missing_ok=True)

    def mock_modules(self, temp_dir):
        """
        Mock the following python module to return a predefined status.
        - get_cluster_status_scs
        - log_parser
        - send_telemetry_data
        - crm_resource
        - crm

        :param temp_dir: Path to the temporary directory.
        :type temp_dir: str
        """
        module_names = [
            "project/library/get_cluster_status_scs",
            "project/library/log_parser",
            "project/library/send_telemetry_data",
            "bin/crm_resource",
            "bin/crm",
        ]

        for module in module_names:
            content = self._file_operations(
                operation="read",
                file_path=Path(__file__).parent.parent.parent
                / f"tests/roles/mock_data/{module.split('/')[-1]}.txt",
            )
            self._file_operations(
                operation="write",
                file_path=f"{temp_dir}/{module}",
                content=content,
            )
            os.chmod(f"{temp_dir}/{module}", 0o755)

    @pytest.fixture
    def ascs_migration_tasks(self):
        """
        Load the ASCS migration tasks from the YAML file.

        :return: Parsed YAML content of the tasks file.
        :rtype: dict
        """
        return self._file_operations(
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
        :yield: Path to the temporary test environment.
        :yield type: str
        """

        temp_dir = tempfile.mkdtemp()

        os.makedirs(f"{temp_dir}/env", exist_ok=True)
        os.makedirs(f"{temp_dir}/project", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/roles/ha_scs/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/roles/misc/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/bin", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/library", exist_ok=True)

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

        self.mock_modules(temp_dir)

        extravars = {
            "item": {
                "name": "Manual ASCS Migration",
                "task_name": "ascs-migration",
                "description": "The Resource Migration test validates planned failover scenarios by "
                + "executing controlled resource movement between ASCS and ERS nodes.",
                "enabled": True,
            },
            "node_tier": "scs",
            "pre_validations_status": "PASSED",
            "cluster_status_pre": {
                "ascs_node": "scs01",
                "ers_node": "scs02",
                "status": "PASSED",
                "pacemaker_status": "running",
            },
            "ansible_hostname": "scs01",
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
            "cleanup_failed_resource_pre": {
                "rc": 0,
                "stdout": "Cleanup successful",
                "stderr": "",
            },
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
        self._file_operations(
            operation="write", file_path=f"{temp_dir}/env/extravars", content=json.dumps(extravars)
        )

        # Read the playbook content and replace placeholders with actual values
        playbook_content = self._file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent / "tests/roles/mock_data/playbook.txt",
        )

        # Write the playbook content to a temporary file
        self._file_operations(
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
        result = ansible_runner.run(
            private_data_dir=test_environment,
            playbook="test_playbook.yml",
            inventory=ansible_inventory,
            quiet=False,
            verbosity=5,
            envvars={"PATH": f"{test_environment}/bin:" + os.environ.get("PATH", "")},
            extravars={"ansible_become": False},
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

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            if task and "Migrate ASCS resource" in task:
                migrate_executed = True
            elif task and "Validate SCS cluster status" in task:
                validate_executed = True
            elif task and "Remove location constraints" in task:
                unmigrate_executed = True
            elif task and "Cleanup resources" in task:
                cleanup_executed = True

        assert migrate_executed, "ASCS migration task was not executed"
        assert validate_executed, "SCS cluster status validation task was not executed"
        assert unmigrate_executed, "Remove location constraints task was not executed"
        assert cleanup_executed, "Cleanup resources task was not executed"
