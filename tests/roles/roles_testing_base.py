# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Base class for testing roles in Ansible playbooks.
This class provides a framework for setting up and tearing down test environments,
mocking necessary modules, and executing Ansible tasks.
"""

import tempfile
import os
import json
import shutil
from typing import Iterator
from pathlib import Path
import ansible_runner
import pytest


class RolesTestingBase:
    """
    Base class for testing roles in Ansible playbooks.
    """

    def file_operations(self, operation, file_path, content=None):
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
    def ansible_inventory(self) -> Iterator[str]:
        """
        Create a temporary Ansible inventory file for testing.
        This inventory contains two hosts (scs01 and scs02) with local connections.

        :yield inventory_path: Path to the temporary inventory file.
        :ytype: Iterator[str]
        """
        inventory_content = self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent / "tests/roles/mock_data/inventory.txt",
        )

        inventory_path = Path(__file__).parent / "test_inventory.ini"
        self.file_operations(
            operation="write",
            file_path=inventory_path,
            content=inventory_content,
        )

        yield str(inventory_path)

        inventory_path.unlink(missing_ok=True)

    def mock_modules(self, temp_dir, module_names):
        """
        Mock the following python or commands module to return a predefined status.

        :param module_names: List of module names to mock.
        :type module_names: list
        :param temp_dir: Path to the temporary directory.
        :type temp_dir: str
        """

        for module in module_names:
            content = self.file_operations(
                operation="read",
                file_path=Path(__file__).parent.parent.parent
                / f"tests/roles/mock_data/{module.split('/')[-1]}.txt",
            )
            self.file_operations(
                operation="write",
                file_path=f"{temp_dir}/{module}",
                content=content,
            )
            os.chmod(f"{temp_dir}/{module}", 0o755)

    def _recursive_update(self, dict1, dict2):
        """
        Recursively update dict1 with values from dict2.

        :param dict1: Base dictionary to update
        :param dict2: Dictionary with values to update
        """
        for key, val in dict2.items():
            if isinstance(val, dict) and key in dict1 and isinstance(dict1[key], dict):
                self._recursive_update(dict1[key], val)
            else:
                dict1[key] = val

    def setup_test_environment(
        self,
        ansible_inventory,
        task_name,
        task_description,
        module_names,
        additional_files=None,
        extra_vars_override=None,
    ):
        """
        Set up a standard test environment for Ansible role testing.

        :param ansible_inventory: Path to the Ansible inventory file
        :type ansible_inventory: str
        :param task_name: Name of the task file to test (e.g., "ascs-migration")
        :type task_name: str
        :param task_description: Human-readable description of the test
        :type task_description: str
        :param module_names: List of modules to mock
        :type module_names: list
        :param additional_files: Additional files to copy beyond standard ones
        :type additional_files: list
        :param extra_vars_override: Dictionary of extra vars to override defaults
        :type extra_vars_override: dict
        :return: Path to the temporary test environment
        :rtype: str
        """
        temp_dir = tempfile.mkdtemp()

        os.makedirs(f"{temp_dir}/env", exist_ok=True)
        os.makedirs(f"{temp_dir}/project", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/roles/ha_scs/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/roles/misc/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/bin", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/library", exist_ok=True)
        os.makedirs(f"{temp_dir}/host_vars", exist_ok=True)

        if os.path.exists("/tmp/get_cluster_status_counter"):
            os.remove("/tmp/get_cluster_status_counter")

        standard_files = [
            "misc/tasks/test-case-setup.yml",
            "misc/tasks/pre-validations-scs.yml",
            "misc/tasks/post-validations-scs.yml",
            "misc/tasks/rescue.yml",
            "misc/tasks/var-log-messages.yml",
            "misc/tasks/post-telemetry-data.yml",
        ]

        task_file = f"ha_scs/tasks/{task_name}.yml"
        file_list = standard_files + [task_file]

        if additional_files:
            file_list.extend(additional_files)

        for file in file_list:
            src_file = Path(__file__).parent.parent.parent / f"src/roles/{file}"
            dest_file = f"{temp_dir}/project/roles/{file}"
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            shutil.copy(src_file, dest_file)

        self.mock_modules(temp_dir=temp_dir, module_names=module_names)

        base_extra_vars = {
            "item": {
                "name": f"Test {task_description}",
                "task_name": task_name,
                "description": task_description,
                "enabled": True,
            },
            "node_tier": "scs",
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

        if extra_vars_override:
            self._recursive_update(base_extra_vars, extra_vars_override)

        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/env/extravars",
            content=json.dumps(base_extra_vars),
        )

        playbook_content = self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent / "tests/roles/mock_data/playbook.txt",
        )
        playbook_content = playbook_content.replace("ansible_hostname ==", "inventory_hostname ==")

        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/test_playbook.yml",
            content=playbook_content
            % (
                base_extra_vars["item"]["name"],
                temp_dir,
                base_extra_vars["item"]["task_name"],
            ),
        )

        return temp_dir

    def run_ansible_playbook(self, test_environment):
        """
        Run an Ansible playbook using the specified inventory.

        :param test_environment: Path to the test environment.
        :type test_environment: str
        :return: Result of the Ansible playbook execution.
        :rtype: ansible_runner.Runner
        """

        inventory_content = self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent / "tests/roles/mock_data/inventory.txt",
        )
        inventory_file = f"{test_environment}/test_inventory.ini"
        self.file_operations(operation="write", file_path=inventory_file, content=inventory_content)
        return ansible_runner.run(
            private_data_dir=test_environment,
            playbook="test_playbook.yml",
            inventory=inventory_file,
            quiet=False,
            verbosity=2,
            envvars={"PATH": f"{test_environment}/bin:" + os.environ.get("PATH", "")},
            extravars={"ansible_become": False},
        )
