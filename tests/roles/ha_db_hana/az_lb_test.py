# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for Azure LB configuration validation tasks.

This test class uses pytest to run functional tests on the Azure LB configuration validation tasks
defined in roles/ha_db_hana/tasks/azure-lb.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import os
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_db_hana.roles_testing_base_db import RolesTestingBaseDB


class TestAzLBConfigValidation(RolesTestingBaseDB):
    """
    Test class for Azure LB configuration validation tasks.
    """

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the Azure LB configuration validation tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        temp_dir = self.setup_test_environment(
            role_type="ha_db_hana",
            ansible_inventory=ansible_inventory,
            task_name="azure-lb",
            task_description="The test validates the Azure load balancer configuration.",
            module_names=[
                "project/library/get_azure_lb",
                "project/library/log_parser",
                "project/library/send_telemetry_data",
                "project/library/get_package_list",
                "bin/crm_resource",
            ],
            extra_vars_override={"node_tier": "hana"},
        )

        os.makedirs(f"{temp_dir}/project/roles/ha_db_hana/tasks/files", exist_ok=True)
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/files/constants.yaml",
            content=self.file_operations(
                operation="read",
                file_path=Path(__file__).parent.parent / "mock_data/mock_azure_lb.txt",
            ),
        )

        os.makedirs(f"{temp_dir}/project/library", exist_ok=True)
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/library/uri",
            content=self.file_operations(
                operation="read",
                file_path=Path(__file__).parent.parent / "mock_data/azure_metadata.txt",
            ),
        )
        os.chmod(f"{temp_dir}/project/library/uri", 0o755)

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_ha_config_validation_success(self, test_environment, ansible_inventory):
        """
        Test the Azure LB configuration validation tasks using Ansible Runner.

        :param test_environment: Path to the temporary test environment.
        :type test_environment: str
        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        """
        result = self.run_ansible_playbook(
            test_environment=test_environment, inventory_file_name="inventory_db.txt"
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

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            task_result = event.get("event_data", {}).get("res")
            if "Retrieve Subscription ID" in task:
                assert task_result.get("changed") is False
            if "Azure Load Balancer check" in task:
                assert task_result.get("changed") is False
                assert task_result["details"]["parameters"][1].get("name") == "probe_threshold"
                assert task_result["details"]["parameters"][1].get("value") == "2"
