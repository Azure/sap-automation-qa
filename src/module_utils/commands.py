# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


"""
Commands module for SAP HANA cluster configuration.
This module contains all the commands used for cluster validation
and configuration.
"""
from __future__ import absolute_import, division, print_function

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
    "REDHAT": ["pcs", "property", "config", "stonith-action"],
    "SUSE": ["crm", "configure", "get_property", "stonith-action"],
}

AUTOMATED_REGISTER = [
    "cibadmin",
    "--query",
    "--xpath",
    "//nvpair[@name='AUTOMATED_REGISTER']",
]


FREEZE_FILESYSTEM = lambda file_system: [
    "mount",
    "-o",
    "ro",
    file_system,
    "/hana/shared",
]

PACEMAKER_STATUS = ["systemctl", "is-active", "pacemaker"]

CLUSTER_STATUS = ["crm_mon", "--output-as=xml"]

CONSTRAINTS = ["cibadmin", "--query", "--scope", "constraints"]

RSC_CLEAR = {
    "SUSE": lambda rsc: ["crm", "resource", "clear", rsc],
    "REDHAT": lambda rsc: ["pcs", "resource", "clear", rsc],
}
