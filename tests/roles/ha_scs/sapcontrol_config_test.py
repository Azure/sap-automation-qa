# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test class for SAPControl Config Validation tasks.

This test class uses pytest to run functional tests on the sapcontrol-config tasks
defined in roles/ha_scs/tasks/sapcontrol-config.yml. It sets up a temporary test environment,
mocks necessary Python modules and commands, and verifies the execution of the tasks.
"""

import os
import sys
import shutil
from pathlib import Path
import pytest
from tests.roles.ha_scs.roles_testing_base_scs import RolesTestingBaseSCS


class TestSAPControlConfig(RolesTestingBaseSCS):
    """
    Test class for SAPControl Config Validation tasks.
    """

    @pytest.fixture
    def sapcontrol_config_tasks(self):
        """
        Load the SAPControl Config Validation tasks from the YAML file.

        :return: Parsed YAML content of the tasks file.
        :rtype: dict
        """
        return self.file_operations(
            operation="read",
            file_path=Path(__file__).parent.parent.parent
            / "src/roles/ha_scs/tasks/sapcontrol-config.yml",
        )

    @pytest.fixture
    def test_environment(self, ansible_inventory):
        """
        Set up a temporary test environment for the SAPControl Config Validation tasks.

        :param ansible_inventory: Path to the Ansible inventory file.
        :type ansible_inventory: str
        :yield temp_dir: Path to the temporary test environment.
        :ytype: str
        """

        class Expression:
            def __init__(self, expression):
                self.expression = expression

            def search(self, data):
                return []

        class Functions:
            pass

        class JMESPath:
            def search(self, expression, data):
                return []

            def compile(self, expression):
                return Expression(expression)

        sys.modules["jmespath"] = JMESPath()
        sys.modules["jmespath.functions"] = Functions()

        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "jmespath"])
        sys.modules["jmespath"] = JMESPath()
        os.environ["TASK_NAME"] = "sapcontrol-config"
        task_counter_file = "/tmp/get_cluster_status_counter_sapcontrol-config"
        if os.path.exists(task_counter_file):
            os.remove(task_counter_file)

        temp_dir = self.setup_test_environment(
            role_type="ha_scs",
            ansible_inventory=ansible_inventory,
            task_name="sapcontrol-config",
            task_description="The SAPControl Config Validation test runs multiple sapcontrol commands",
            module_names=[
                "project/library/get_cluster_status_scs",
                "project/library/log_parser",
                "project/library/send_telemetry_data",
                "bin/crm_resource",
                "bin/sapcontrol",
                "bin/jmespath",
            ],
            extra_vars_override={"node_tier": "scs"},
        )

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_functional_sapcontrol_config_success(self, test_environment, ansible_inventory):
        """
        Test the SAPControl Config Validation tasks using Ansible Runner.

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

        sapcontrol_executed = False
        test_fact_set = False
        pre_validate_executed = False

        for event in ok_events:
            task = event.get("event_data", {}).get("task")
            print(task)
            if task and "Run sapcontrol commands" in task:
                sapcontrol_executed = True
            elif task and "Test Execution: Validate sapcontrol commands" in task:
                test_fact_set = True
            elif task and "Pre Validation: Validate SCS" in task:
                pre_validate_executed = True

        assert sapcontrol_executed, "SAPControl commands were not executed"
        assert test_fact_set, "Test execution facts were not set"
        assert pre_validate_executed, "Pre-validation task was not executed"
