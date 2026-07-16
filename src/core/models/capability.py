# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Group Capability Model
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class GroupCapability:
    """
    MCP safety classification for one `test_group` (online semantics).

    :param test_group: `test_group` key, matching `TEST_GROUP_PLAYBOOKS`.
    :param read_only: Whether the group never mutates target state (`FR-003`).
    :param destructive: Whether the group performs destructive/fault-injection
        actions (`FR-004`).
    :param idempotent: Whether repeated calls with the same arguments have no
        additional effect (`NFR-002`).
    :param open_world: Whether the group interacts with an open/unbounded set
        of external entities, rather than the workspace's fixed inventory.
    :param offline_eligible: Whether `offline=True` dispatch is supported for
        this group (`P1-RD-001`).
    """

    test_group: str
    read_only: bool
    destructive: bool
    idempotent: bool
    open_world: bool
    offline_eligible: bool

    def for_dispatch(self, offline: bool) -> "GroupCapability":
        """Return the effective classification for a dispatch mode.

        Offline dispatch runs ``playbook_01_ha_offline_tests.yml``, a
        bounded, static CIB-file analysis with no fault injection; it is
        always read-only/non-destructive/idempotent regardless of the
        group's online classification.

        :param offline: Whether the group is being dispatched with
            `offline=True`.
        :returns: The capability applicable to the requested dispatch mode.
        :raises ValueError: If `offline=True` but the group has no offline
            mode.
        """
        if not offline:
            return self
        if not self.offline_eligible:
            raise ValueError(f"'{self.test_group}' has no offline mode")
        return replace(self, read_only=True, destructive=False, idempotent=True)
