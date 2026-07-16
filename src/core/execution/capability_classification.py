# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
MCP capability classification registry for `test_group` values.

This module is server-enforced source data (`FR-005`): classification is
looked up here, never inferred or defaulted, before any MCP Tool is bound
to a `test_group`.
"""

from src.core.execution.test_catalog import TEST_GROUP_PLAYBOOKS
from src.core.models.capability import GroupCapability

TEST_GROUP_CAPABILITIES: dict[str, GroupCapability] = {
    "ConfigurationChecks": GroupCapability(
        test_group="ConfigurationChecks",
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=False,
        offline_eligible=False,
    ),
    "DatabaseHighAvailability": GroupCapability(
        test_group="DatabaseHighAvailability",
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=False,
        offline_eligible=True,
    ),
    "CentralServicesHighAvailability": GroupCapability(
        test_group="CentralServicesHighAvailability",
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=False,
        offline_eligible=True,
    ),
    "AzureBackupDatabase": GroupCapability(
        test_group="AzureBackupDatabase",
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=False,
        offline_eligible=False,
    ),
}


def _validate_registry_completeness() -> None:
    """Fail fast if the registry drifts from `TEST_GROUP_PLAYBOOKS`.

    :raises RuntimeError: If any `TEST_GROUP_PLAYBOOKS` entry is
        unclassified, or the registry contains an entry that no longer
        maps to a playbook.
    """
    known_groups = set(TEST_GROUP_PLAYBOOKS)
    classified_groups = set(TEST_GROUP_CAPABILITIES)
    if known_groups != classified_groups:
        missing = known_groups - classified_groups
        extra = classified_groups - known_groups
        raise RuntimeError(
            "capability_classification registry is out of sync with "
            f"TEST_GROUP_PLAYBOOKS (missing={sorted(missing)}, "
            f"extra={sorted(extra)})"
        )


_validate_registry_completeness()


def get_capability(test_group: str) -> GroupCapability:
    """Look up the MCP safety classification for a `test_group`.

    :param test_group: `test_group` key to classify.
    :returns: The registered `GroupCapability`.
    :raises KeyError: If `test_group` is not a known, classified group —
        never silently defaulted (`FR-005`).
    """
    try:
        return TEST_GROUP_CAPABILITIES[test_group]
    except KeyError as exc:
        raise KeyError(f"Unclassified test group: {test_group}") from exc
