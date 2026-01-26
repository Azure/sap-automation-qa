# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Test executor interface and implementations.
"""

import json
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Protocol

from src.core.observability import get_logger

logger = get_logger(__name__)


TEST_GROUP_PLAYBOOKS = {
    "CONFIG_CHECKS": "playbook_00_configuration_checks.yml",
    "HA_DB_HANA": "playbook_00_ha_db_functional_tests.yml",
    "HA_SCS": "playbook_00_ha_scs_functional_tests.yml",
    "HA_OFFLINE": "playbook_01_ha_offline_tests.yml",
}


class TestExecutor(Protocol):
    """
    Protocol for test execution.
    """

    def run_test(
        self,
        workspace_id: str,
        test_id: str,
        test_group: str,
        inventory_path: str,
        extra_vars: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Run a test.

        :param workspace_id: Workspace identifier
        :param test_id: Test ID to run (or empty for full playbook)
        :param test_group: Test group (CONFIG_CHECKS, HA_DB_HANA, etc.)
        :param inventory_path: Path to Ansible inventory
        :param extra_vars: Additional variables to pass
        :returns: Execution result
        """
        ...


class AnsibleExecutor:
    """Executes tests using Ansible playbooks directly."""

    def __init__(
        self,
        playbook_dir: Path | str = "src",
        ansible_cfg: Optional[Path | str] = None,
    ) -> None:
        """Initialize the executor.

        :param playbook_dir: Directory containing playbooks
        :param ansible_cfg: Path to ansible.cfg
        """
        self.playbook_dir = Path(playbook_dir)
        self.ansible_cfg = Path(ansible_cfg) if ansible_cfg else self.playbook_dir / "ansible.cfg"

    def run_test(
        self,
        workspace_id: str,
        test_id: str,
        test_group: str,
        inventory_path: str,
        extra_vars: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Run a test using ansible-playbook.

        :param workspace_id: Workspace identifier
        :param test_id: Test ID to run (or empty for full playbook)
        :param test_group: Test group
        :param inventory_path: Path to Ansible inventory
        :param extra_vars: Additional variables
        :returns: Execution result dict
        """
        playbook_name = TEST_GROUP_PLAYBOOKS.get(test_group)
        if not playbook_name:
            return {
                "status": "failed",
                "error": f"Unknown test group: {test_group}",
            }

        playbook_path = self.playbook_dir / playbook_name
        if not playbook_path.exists():
            return {
                "status": "failed",
                "error": f"Playbook not found: {playbook_path}",
            }

        cmd = [
            "ansible-playbook",
            str(playbook_path),
            "-i",
            inventory_path,
        ]

        all_vars = extra_vars or {}
        all_vars["workspace_id"] = workspace_id

        if test_id:
            cmd.extend(["--tags", test_id])
            all_vars["test_id"] = test_id

        if all_vars:
            cmd.extend(["-e", json.dumps(all_vars)])

        env = {"ANSIBLE_CONFIG": str(self.ansible_cfg)}

        logger.info(
            f"Running test: workspace={workspace_id}, "
            f"test_id={test_id or 'all'}, group={test_group}"
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                env={**os.environ, **env},
            )

            if result.returncode == 0:
                return {
                    "status": "success",
                    "test_id": test_id,
                    "test_group": test_group,
                    "workspace_id": workspace_id,
                    "stdout": result.stdout[-5000:] if result.stdout else "",
                }
            else:
                return {
                    "status": "failed",
                    "test_id": test_id,
                    "test_group": test_group,
                    "workspace_id": workspace_id,
                    "error": result.stderr[-2000:] if result.stderr else "Unknown error",
                    "return_code": result.returncode,
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "error": "Test execution timed out after 1 hour",
                "test_id": test_id,
                "test_group": test_group,
            }
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "test_id": test_id,
                "test_group": test_group,
            }
