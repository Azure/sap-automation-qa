# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for Kill SAPStartsrv tasks.

This test class uses pytest to run functional tests on the kill-sapstartsrv tasks
defined in roles/ha_scs/tasks/kill-sapstartsrv-process.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import os
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_scs.roles_testing_base_scs import RolesTestingBaseSCS


class TestKillSapStartSrv(RolesTestingBaseSCS):
    """
    Test class for Kill SAPStartsrv tasks.
    """

    @pytest.fixture
    def kill_sapstartsrv_tasks(self):
        """
        Load the Kill SAPStartsrv tasks from the YAML file.

        :return: Parsed YAML content of the tasks file.
        :rtype: dict
        """
        return self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent
            / "src/roles/ha_scs/tasks/kill-sapstartsrv-process.yml",
        )

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the Kill SAPStartsrv tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        os.environ["TASK_NAME"] = "kill-sapstartsrv-process"
        task_counter_file = "/tmp/get_cluster_status_counter_kill-sapstartsrv-process"
        if os.path.exists(task_counter_file):
            os.remove(task_counter_file)

        temp_dir = self.setup_test_environment(
            role_type="ha_scs",
            ansible_inventory=ansible_inventory,
            task_name="kill-sapstartsrv-process",
            task_description="The SAP startsrv Process Kill test simulates "
            + "failure of the sapstartsrv process",
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

        playbook_content = self.file_operations(
            operation="read",
            file_path=f"{temp_dir}/project/roles/ha_scs/tasks/kill-sapstartsrv-process.yml",
        )
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/roles/ha_scs/tasks/kill-sapstartsrv-process.yml",
            content=playbook_content.replace("set -o pipefail &&", ""),
        )

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_functional_kill_sapstartsrv_success(self, test_environment, ansible_inventory):
        """
        Test the Kill SAPStartsrv tasks using ansible Runner.

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

        sapstartsrv_executed = False
        sapstartsrv_executed_post = False
        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            print(task)
            if "Test Execution: Kill sapstartsrv Process" in task:
                sapstartsrv_executed = True
            elif "Find sapstartsrv PID after killing the process" in task:
                sapstartsrv_executed_post = True

        assert sapstartsrv_executed, "SAPStartsrv process was not killed"
        assert sapstartsrv_executed_post, "SAPStartsrv process was not found after killing it"
