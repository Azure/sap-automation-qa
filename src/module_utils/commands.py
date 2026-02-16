# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


"""
Commands module for SAP HANA cluster configuration.
This module contains all the commands used for cluster validation
and configuration.
"""

from __future__ import absolute_import, division, print_function

try:
    from ansible.module_utils.enums import OperatingSystemFamily
except ImportError:
    from src.module_utils.enums import OperatingSystemFamily

__metaclass__ = type

DOCUMENTATION = r"""
module_utils:
    cluster_constants:
        description: Commands for SAP HANA used for cluster validation and configuration.
        version_added: "1.0.0"
        author:
            - "SDAF Core Team (@sdafcoreteam)"
"""

STONITH_ACTION = {
    OperatingSystemFamily.REDHAT: ["pcs", "property", "config", "stonith-action"],
    OperatingSystemFamily.SUSE: ["crm", "configure", "get_property", "stonith-action"],
}

AUTOMATED_REGISTER = lambda rsc: [
    "crm_resource",
    "--resource",
    rsc,
    "--get-parameter=AUTOMATED_REGISTER",
]

PRIORITY_FENCING_DELAY = [
    "crm_attribute",
    "--type",
    "crm_config",
    "--name",
    "priority-fencing-delay",
    "--quiet",
]

FREEZE_FILESYSTEM = lambda file_system, mount_point: [
    "mount",
    "-o",
    "ro",
    file_system,
    mount_point,
]

PACEMAKER_STATUS = ["systemctl", "is-active", "pacemaker"]

CLUSTER_STATUS = ["crm_mon", "--output-as=xml"]

CONSTRAINTS = ["cibadmin", "--query", "--scope", "constraints"]

RSC_CLEAR = {
    OperatingSystemFamily.SUSE: lambda rsc: ["crm", "resource", "clear", rsc],
    OperatingSystemFamily.REDHAT: lambda rsc: ["pcs", "resource", "clear", rsc],
}

CIB_ADMIN = lambda scope: ["cibadmin", "--query", "--scope", scope]

DANGEROUS_COMMANDS = [
    r"sudo\s+rm",
    r"rm\s+-rf",
]

RECOMMENDATION_MESSAGES = {
    "priority-fencing-delay": (
        "The 'priority-fencing-delay' setting is not configured. "
        "In a two-node cluster, configure priority-fencing-delay to enhance the "
        "highest-priority node's survival odds during a fence race condition. "
        "For more details on the setup, check official cluster pacemaker configuration "
        "documentation in learn.microsoft.com"
    ),
    "azureevents": (
        "The Azure scheduled events resource is not configured. "
        "It is advised to setup this agent in your cluster to monitor the Instance Metadata "
        "Service (IMDS) for platform maintenance events, allowing it to proactively drain "
        "resources or initiate a clean failover before Azure maintenance impacts the node. "
        "For more details on the setup, check official cluster pacemaker configuration "
        "documentation in learn.microsoft.com"
    ),
}
