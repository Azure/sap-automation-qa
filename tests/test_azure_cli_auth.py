# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Validate Azure CLI version-aware managed identity authentication."""

from pathlib import Path

import pytest
import yaml
from ansible.plugins.test.core import version_compare

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
AUTH_TASK_FILE = SRC_DIR / "roles" / "misc" / "tasks" / "authenticate-azure.yml"
AUTH_TASK_INCLUDE = "./roles/misc/tasks/authenticate-azure.yml"
PLAYBOOK_FILES = [
    SRC_DIR / "playbook_00_backup_db_functional_tests.yml",
    SRC_DIR / "playbook_00_configuration_checks.yml",
    SRC_DIR / "playbook_00_ha_db_functional_tests.yml",
    SRC_DIR / "playbook_00_ha_scs_functional_tests.yml",
    SRC_DIR / "playbook_01_ha_offline_tests.yml",
]


def _load_yaml(path: Path):
    """Load YAML content from a repository file."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_playbooks_include_shared_azure_authentication_once() -> None:
    """Every entry-point playbook must include the shared authentication tasks once."""
    for playbook_file in PLAYBOOK_FILES:
        plays = _load_yaml(playbook_file)
        includes = [
            task["ansible.builtin.include_tasks"]
            for play in plays
            for task in play.get("tasks", [])
            if "ansible.builtin.include_tasks" in task
            and task["ansible.builtin.include_tasks"] == AUTH_TASK_INCLUDE
        ]

        assert includes == [AUTH_TASK_INCLUDE], playbook_file.name


def test_shared_authentication_uses_cli_version() -> None:
    """Shared tasks must select the managed identity argument using Azure CLI version."""
    tasks = _load_yaml(AUTH_TASK_FILE)
    tasks_by_name = {task["name"]: task for task in tasks}

    version_task = tasks_by_name["Init: Get Azure CLI Version"]
    client_id_task = tasks_by_name["Init: Authenticate With Client ID (az cli >= 2.61)"]
    username_task = tasks_by_name["Init: Authenticate With Username (az cli < 2.61)"]

    assert version_task["register"] == "azure_cli_version"
    assert version_task["ansible.builtin.command"]["cmd"] == (
        "az version --query '\"azure-cli\"' --output tsv"
    )
    assert client_id_task["when"] == "azure_cli_version.stdout is version('2.61', '>=')"
    assert (
        "--client-id {{ user_assigned_identity_client_id }}"
        in client_id_task["ansible.builtin.command"]["cmd"]
    )
    assert username_task["when"] == "azure_cli_version.stdout is version('2.61', '<')"
    assert (
        "--username {{ user_assigned_identity_client_id }}"
        in username_task["ansible.builtin.command"]["cmd"]
    )


@pytest.mark.parametrize(
    ("cli_version", "use_client_id"),
    [("2.60.0", False), ("2.61.0", True), ("2.90.0", True)],
)
def test_cli_version_threshold(cli_version: str, use_client_id: bool) -> None:
    """Azure CLI 2.61 is the boundary for the managed identity argument change."""
    at_or_above_threshold = version_compare(cli_version, "2.61", operator=">=")
    below_threshold = version_compare(cli_version, "2.61", operator="<")

    assert at_or_above_threshold is use_client_id
    assert below_threshold is not use_client_id
