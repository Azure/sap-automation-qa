# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Base class for testing roles in Ansible playbooks.
This class provides a framework for setting up and tearing down test environments,
mocking necessary modules, and executing Ansible tasks.
"""

from typing import Iterator
from pathlib import Path
import pytest
from tests.roles.roles_testing_base import RolesTestingBase


class RolesTestingBaseSCS(RolesTestingBase):
    """
    Base class for testing roles in Ansible playbooks.
    """

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
            file_path=Path(__file__).parent.parent / "mock_data/inventory_scs.txt",
        )

        inventory_path = Path(__file__).parent / "test_inventory.ini"
        self.file_operations(
            operation="write",
            file_path=inventory_path,
            content=inventory_content,
        )

        yield str(inventory_path)

        inventory_path.unlink(missing_ok=True)
