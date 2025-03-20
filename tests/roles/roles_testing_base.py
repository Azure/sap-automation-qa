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

        :yield: Path to the temporary inventory file.
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
