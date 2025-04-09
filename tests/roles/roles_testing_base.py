# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Base class for testing roles in Ansible playbooks.
This class provides a framework for setting up and tearing down test environments,
mocking necessary modules, and executing Ansible tasks.
"""

import tempfile
import shutil
import json
import os
from pathlib import Path
import ansible_runner


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
                file_path=Path(__file__).parent / f"mock_data/{module.split('/')[-1]}.txt",
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

    def run_ansible_playbook(self, test_environment, inventory_file_name, task_type=None):
        """
        Run an Ansible playbook using the specified inventory.

        :param test_environment: Path to the test environment.
        :type test_environment: str
        :param inventory_file_name: Name of the inventory file.
        :type inventory_file_name: str
        :param task_type: Type of task to run (optional).
        :type task_type: str
        :return: Result of the Ansible playbook execution.
        :rtype: ansible_runner.Runner
        """

        self.file_operations(
            operation="write",
            file_path=f"{test_environment}/test_inventory.ini",
            content=self.file_operations(
                operation="read",
                file_path=Path(__file__).parent / f"mock_data/{inventory_file_name}",
            ),
        )
        return ansible_runner.run(
            private_data_dir=test_environment,
            playbook="test_playbook.yml",
            inventory=f"{test_environment}/test_inventory.ini",
            quiet=False,
            verbosity=2,
            envvars={
                "PATH": f"{test_environment}/bin:" + os.environ.get("PATH", ""),
                "TEST_TASK_TYPE": task_type,
            },
            extravars={"ansible_become": False},
        )

    def setup_test_environment(
        self,
        ansible_inventory,
        role_type,
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
        :param role_type: Type of role (e.g., "db", "ers", "scs")
        :type role_type: str
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
        os.makedirs(f"{temp_dir}/project/roles/{role_type}/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/roles/misc/tasks", exist_ok=True)
        os.makedirs(f"{temp_dir}/bin", exist_ok=True)
        os.makedirs(f"{temp_dir}/project/library", exist_ok=True)
        os.makedirs(f"{temp_dir}/host_vars", exist_ok=True)

        if os.path.exists("/tmp/get_cluster_status_counter"):
            os.remove("/tmp/get_cluster_status_counter")

        standard_files = [
            "misc/tasks/test-case-setup.yml",
            f"misc/tasks/pre-validations-{role_type.split('_')[1]}.yml",
            "misc/tasks/post-validations.yml",
            "misc/tasks/rescue.yml",
            "misc/tasks/var-log-messages.yml",
            "misc/tasks/post-telemetry-data.yml",
        ]

        task_file = f"{role_type}/tasks/{task_name}.yml"
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
            "db_instance_number": "02",
            "group_name": role_type.upper(),
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
            file_path=Path(__file__).parent / "mock_data/playbook.txt",
        )
        playbook_content = playbook_content.replace("ansible_hostname ==", "inventory_hostname ==")

        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/test_playbook.yml",
            content=playbook_content
            % (
                base_extra_vars["item"]["name"],
                temp_dir,
                role_type,
                base_extra_vars["item"]["task_name"],
            ),
        )

        return temp_dir
