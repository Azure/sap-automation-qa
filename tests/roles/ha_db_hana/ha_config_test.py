# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for HANA DB HA config validation tasks

This test class uses pytest to run functional tests on the HANA DB HA config validation tasks
defined in roles/ha_db_hana/tasks/ha-config.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import os
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_db_hana.roles_testing_base_db import RolesTestingBaseDB


class TestDbHaConfigValidation(RolesTestingBaseDB):
    """
    Test class for HANA DB HA config validation tasks.
    """

    @pytest.fixture
    def hana_ha_config_tasks(self):
        """
        Load the HANA DB HA config validation tasks from the YAML file.

        :return: Parsed YAML content of the tasks file.
        :rtype: dict
        """
        return self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent
            / "src/roles/ha_db_hana/tasks/ha-config.yml",
        )

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the HANA DB HA config validation tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        temp_dir = self.setup_test_environment(
            role_type="ha_db_hana",
            ansible_inventory=ansible_inventory,
            task_name="ha-config",
            task_description="The HANA DB HA config validation test validates the DB cluster "
            + "configuration and other system configuration",
            module_names=[
                "project/library/get_pcmk_properties_db",
                "project/library/log_parser",
                "project/library/send_telemetry_data",
                "project/library/get_package_list",
                "bin/crm_resource",
                "bin/crm",
            ],
            extra_vars_override={
                "node_tier": "hana"
            }
        )

        os.makedirs(f"{temp_dir}/project/roles/ha_db_hana/tasks/files", exist_ok=True)
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/files/constants.yaml",
            content=self.file_operations(
                operation="read",
                file_path=Path(__file__).parent.parent / "mock_data/cluster_config.txt",
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
        Test the HANA DB HA config validation tasks using Ansible Runner.

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
            if "Create package dictionary" in task:
                assert task_result.get("changed") is False
                assert task_result["details"][1].get("Corosync").get("version") == "2.4.5"
            if "Virtual Machine name" in task:
                assert task_result.get("changed") is False
            if "HA Configuration check" in task:
                assert task_result.get("changed") is False
                assert (
                    task_result["details"].get("parameters", {})[1].get("name")
                    == "migration-threshold"
                )
                assert task_result["details"].get("parameters", {})[1].get("value") == "3"
