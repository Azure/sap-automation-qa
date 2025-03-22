# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for HANA DB primary node crash and node kill tasks

This test class uses pytest to run functional tests on the HANA DB primary node crash, kill, echo-b,
and crash-index tasks defined in roles/ha_db_hana/tasks/primary-node-crash.yml.
It sets up a temporary test environment, mocks necessary Python modules and commands, and verifies
the execution of the tasks.
"""

import os
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_db_hana.roles_testing_base_db import RolesTestingBaseDB


class TestDbHDBOperations(RolesTestingBaseDB):
    """
    Test class for HANA DB primary node crash, kill, echo-b, and crash-index tasks.
    """

    @pytest.fixture(
        params=[
            "primary-node-crash",
            "primary-node-kill",
            "primary-echo-b",
            "primary-crash-index",
            "sbd-fencing",
            "fs-freeze",
        ]
    )
    def task_type(self, request):
        """
        Parameterized fixture to test both primary and secondary node operations.

        :param request: pytest request object containing the parameter
        :type request: pytest.request
        :return: Dictionary with task configuration details
        :rtype: dict
        """
        task_name = request.param

        if task_name == "primary-node-crash":
            return {
                "task_name": task_name,
                "command_task": "Stop the HANA DB",
                "command_type": "stop",
                "validate_task": "Test execution: Validate HANA DB cluster status 2",
            }
        elif task_name == "primary-node-kill":
            return {
                "task_name": task_name,
                "command_task": "Test Execution: Kill the HANA DB",
                "command_type": "kill-9",
                "validate_task": "Test execution: Validate HANA DB cluster status 2",
            }
        elif task_name == "primary-echo-b":
            return {
                "task_name": task_name,
                "command_task": "Test Execution: Echo b",
                "command_type": "echo b",
                "validate_task": "Test Execution: Validate HANA DB cluster status 2",
            }
        elif task_name == "primary-crash-index":
            return {
                "task_name": task_name,
                "command_task": "Test Execution: Crash the index server",
                "command_type": "killall",
                "validate_task": "Test Execution: Validate HANA DB cluster status",
            }
        elif task_name == "sbd-fencing":
            return {
                "task_name": task_name,
                "command_task": "Test Execution: Kill the inquisitor process",
                "command_type": "kill",
                "validate_task": "Test Execution: Validate HANA DB cluster status 2",
            }
        elif task_name == "fs-freeze":
            return {
                "task_name": task_name,
                "validate_task": "Test Execution: Validate HANA DB cluster status 2",
                "command_task": "dummy (no command)",
            }

    @pytest.fixture
    def test_environment(self, ansible_inventory, task_type):
        """
        Set up a temporary test environment for the HANA DB primary node operations tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :param task_type: Dictionary with task configuration details.
        :type task_type: dict
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        task_counter_file = f"/tmp/get_cluster_status_counter_{task_type['task_name']}"
        if os.path.exists(task_counter_file):
            os.remove(task_counter_file)

        module_names = [
            "project/library/get_cluster_status_db",
            "project/library/log_parser",
            "project/library/send_telemetry_data",
            "project/library/location_constraints",
            "project/library/check_indexserver",
            "project/library/filesystem_freeze",
            "bin/crm_resource",
            "bin/crm",
            "bin/echo",
            "bin/killall",
        ]

        if task_type["task_name"] == "sbd-fencing":
            module_names.extend(["bin/pgrep", "bin/kill", "bin/head"])

        temp_dir = self.setup_test_environment(
            role_type="ha_db_hana",
            ansible_inventory=ansible_inventory,
            task_name=task_type["task_name"],
            task_description=f"The {task_type['task_name']} test validates failover scenarios",
            module_names=module_names,
            extra_vars_override={
                "node_tier": "hana",
                "NFS_provider": "ANF",
                "database_cluster_type": "ISCSI",
            },
        )

        os.makedirs(f"{temp_dir}/bin", exist_ok=True)
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/bin/HDB",
            content=self.file_operations(
                operation="read",
                file_path=Path(__file__).parent.parent / "mock_data/HDB.txt",
            ),
        )
        os.chmod(f"{temp_dir}/bin/HDB", 0o755)

        playbook_content = self.file_operations(
            operation="read",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/{task_type['task_name']}.yml",
        )
        self.file_operations(
            operation="write",
            file_path=f"{temp_dir}/project/roles/ha_db_hana/tasks/{task_type['task_name']}.yml",
            content=playbook_content.replace("set -o pipefail\n", "").replace(
                "/usr/sap/{{ db_sid | upper }}/HDB{{ db_instance_number }}/", ""
            ),
        )

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_functional_db_primary_node_success(
        self, test_environment, ansible_inventory, task_type
    ):
        """
        Test the HANA DB primary node operations tasks using Ansible Runner.

        :param test_environment: Path to the temporary test environment.
        :type test_environment: str
        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :param task_type: Dictionary with task configuration details.
        :type task_type: dict
        """
        result = self.run_ansible_playbook(
            test_environment=test_environment,
            inventory_file_name="inventory_db.txt",
            task_type=task_type["task_name"],
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

        post_status = {}
        pre_status = {}

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            task_result = event.get("event_data", {}).get("res")

            if task and task_type.get("command_task") in task:
                if task_type["command_type"] == "echo b" or task_type["command_type"] == "kill":
                    assert task_result.get("changed") is True
                else:
                    assert task_result.get("rc") == 0
            elif (
                task
                and "Test Execution: Validate HANA DB cluster status 1" in task
                and task_type["task_name"] == "primary-node-crash"
            ):
                assert not task_result.get("secondary_node")
            elif task and task_type["validate_task"] in task:
                assert task_result.get("secondary_node")
                assert task_result.get("primary_node")
                post_status = task_result
            elif task and "Pre Validation: Validate HANA DB" in task:
                pre_status = task_result
            elif task and "Remove any location_constraints" in task:
                assert task_result.get("changed")

        assert post_status.get("primary_node") == pre_status.get("secondary_node")
        assert post_status.get("secondary_node") == pre_status.get("primary_node")
