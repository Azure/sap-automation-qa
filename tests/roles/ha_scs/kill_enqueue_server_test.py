# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for Kill Enqueue Server Process tasks.

This test class uses pytest to run functional tests on the kill-enqueue-server tasks
defined in roles/ha_scs/tasks/kill-enqueue-server.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import os
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_scs.roles_testing_base_scs import RolesTestingBaseSCS


class TestKillEnqueueServer(RolesTestingBaseSCS):
    """
    Test class for Kill Enqueue Server Process tasks.
    """

    @pytest.fixture
    def kill_enqueue_server_tasks(self):
        """
        Load the Kill Enqueue Server tasks from the YAML file.

        :return: Parsed YAML content of the tasks file.
        :rtype: dict
        """
        return self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent
            / "src/roles/ha_scs/tasks/kill-enqueue-server.yml",
        )

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the Kill Enqueue Server tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        os.environ["TASK_NAME"] = "kill-enqueue-server"
        task_counter_file = "/tmp/get_cluster_status_counter_kill-enqueue-server"
        if os.path.exists(task_counter_file):
            os.remove(task_counter_file)

        temp_dir = self.setup_test_environment(
            role_type="ha_scs",
            ansible_inventory=ansible_inventory,
            task_name="kill-enqueue-server",
            task_description="The Enqueue Server Process Kill test simulates failure of the enqueue server process",
            module_names=[
                "project/library/get_cluster_status_scs",
                "project/library/log_parser",
                "project/library/send_telemetry_data",
                "bin/crm_resource",
                "bin/pgrep",
                "bin/kill",
            ],
            extra_vars_override={"node_tier": "scs"},
        )

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_functional_kill_enqueue_server_success(self, test_environment, ansible_inventory):
        """
        Test the Kill Enqueue Server tasks using Ansible Runner.

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

        kill_executed = False
        validate_executed = False
        cleanup_executed = False
        post_status = {}
        pre_status = {}

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            if task and "Kill Enqueue Server Process" in task:
                kill_executed = True
            elif task and "Test Execution: Validate SCS cluster status" in task:
                validate_executed = True
                post_status = event.get("event_data", {}).get("res")
            elif task and "Cleanup resources" in task:
                cleanup_executed = True
            elif task and "Pre Validation: Validate SCS" in task:
                pre_status = event.get("event_data", {}).get("res")

        assert post_status.get("ascs_node") == pre_status.get("ers_node")
        assert post_status.get("ers_node") == pre_status.get("ascs_node")

        assert kill_executed, "Kill enqueue server process task was not executed"
        assert validate_executed, "SCS cluster status validation task was not executed"
        assert cleanup_executed, "Cleanup resources task was not executed"
