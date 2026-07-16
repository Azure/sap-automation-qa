# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for the MCP capability classification registry."""

import pytest
from src.core.execution.test_catalog import TEST_GROUP_PLAYBOOKS
from src.core.execution.capability_classification import (
    TEST_GROUP_CAPABILITIES,
    GroupCapability,
    get_capability,
)


class TestRegistryCompleteness:
    """
    Every `TEST_GROUP_PLAYBOOKS` group is classified exactly once.
    """

    def test_every_playbook_group_is_classified(self) -> None:
        """
        Registry keys exactly match `TEST_GROUP_PLAYBOOKS` keys.
        """
        assert set(TEST_GROUP_CAPABILITIES) == set(TEST_GROUP_PLAYBOOKS)

    def test_no_duplicate_classification_keys(self) -> None:
        """
        Each group appears exactly once (dict keys are inherently unique;
        confirms the `test_group` field matches its registry key).
        """
        for key, capability in TEST_GROUP_CAPABILITIES.items():
            assert capability.test_group == key

    def test_unknown_group_raises_not_defaults(self) -> None:
        """
        Looking up an unclassified group raises, never silently defaults.
        """
        with pytest.raises(KeyError):
            get_capability("NoSuchTestGroup")


class TestOnlineClassification:
    """
    Destructive/read-only classification matches current playbook behavior.
    """

    def test_configuration_checks_is_read_only(self) -> None:
        """
        ConfigurationChecks is a read-only diagnostic group (`FR-003`).
        """
        capability = get_capability("ConfigurationChecks")
        assert capability.read_only is True
        assert capability.destructive is False
        assert capability.idempotent is True

    @pytest.mark.parametrize(
        "test_group",
        ["DatabaseHighAvailability", "CentralServicesHighAvailability"],
    )
    def test_ha_fault_injection_groups_are_destructive(self, test_group: str) -> None:
        """
        HA fault-injection groups are destructive/non-idempotent (`FR-004`).
        """
        capability = get_capability(test_group)
        assert capability.read_only is False
        assert capability.destructive is True
        assert capability.idempotent is False

    def test_azure_backup_database_is_destructive(self) -> None:
        """
        AzureBackupDatabase performs live restore operations, so it is
        classified destructive/non-idempotent, not read-only.
        """
        capability = get_capability("AzureBackupDatabase")
        assert capability.read_only is False
        assert capability.destructive is True
        assert capability.idempotent is False


class TestOfflineEligibility:
    """
    Offline eligibility matches `sap_automation_qa.sh`'s `get_playbook_name`.
    """

    @pytest.mark.parametrize(
        "test_group",
        ["DatabaseHighAvailability", "CentralServicesHighAvailability"],
    )
    def test_ha_groups_are_offline_eligible(self, test_group: str) -> None:
        """
        Both SUSE and RHEL HA groups share the same offline eligibility;
        OS-specific behavior stays inside playbook/module logic.
        """
        assert get_capability(test_group).offline_eligible is True

    @pytest.mark.parametrize(
        "test_group",
        ["ConfigurationChecks", "AzureBackupDatabase"],
    )
    def test_non_ha_groups_are_not_offline_eligible(self, test_group: str) -> None:
        """
        Only the two HA fault-injection groups support offline dispatch.
        """
        assert get_capability(test_group).offline_eligible is False

    def test_offline_dispatch_is_read_only_and_idempotent(self) -> None:
        """
        Offline dispatch (static CIB-file analysis) is always read-only,
        non-destructive and idempotent, regardless of the group's online
        (fault-injection) classification.
        """
        capability = get_capability("DatabaseHighAvailability")
        offline_capability = capability.for_dispatch(offline=True)
        assert offline_capability.read_only is True
        assert offline_capability.destructive is False
        assert offline_capability.idempotent is True

    def test_online_dispatch_is_unchanged(self) -> None:
        """
        `for_dispatch(offline=False)` returns the same instance/values.
        """
        capability = get_capability("DatabaseHighAvailability")
        assert capability.for_dispatch(offline=False) == capability

    def test_offline_dispatch_rejects_ineligible_group(self) -> None:
        """
        Requesting offline dispatch for a non-eligible group raises.
        """
        capability = get_capability("ConfigurationChecks")
        with pytest.raises(ValueError):
            capability.for_dispatch(offline=True)


class TestCapabilityDataclass:
    """
    `GroupCapability` is a plain, immutable data holder.
    """

    def test_is_frozen(self) -> None:
        """
        Instances are immutable (pure-data, no speculative behavior).
        """
        capability = get_capability("ConfigurationChecks")
        with pytest.raises(AttributeError):
            capability.read_only = False  # type: ignore[misc]

    def test_open_world_is_false_for_all_groups(self) -> None:
        """
        Every group operates against a fixed, workspace-scoped inventory
        (or a specific configured Azure Backup vault), never an open/
        unbounded set of external entities.
        """
        for capability in TEST_GROUP_CAPABILITIES.values():
            assert capability.open_world is False

    def test_capability_is_instance_of_dataclass(self) -> None:
        """
        Registry values are `GroupCapability` instances.
        """
        for capability in TEST_GROUP_CAPABILITIES.values():
            assert isinstance(capability, GroupCapability)
