#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


"""
Constants module for SAP HANA cluster configuration.
This module contains all the constant values used for cluster validation
and configuration.
"""
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module_utils:
    cluster_constants:
        description: Constants for SAP HANA cluster configuration
        version_added: "1.0.0"
        author: 
            - "SDAF Core Team (@sdafcoreteam)"
"""

CLUSTER_RESOURCES = {
    "SUSE": {
        "cln_SAPHanaTopology": {
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
        },
        "ocf:suse:SAPHanaTopology": {
            "monitor-interval": "10",
            "monitor-timeout": "600",
            "start-interval": "0",
            "start-timeout": "600",
            "stop-interval": "0",
            "stop-timeout": "300",
        },
        "msl_SAPHana": {
            "notify": "true",
            "clone-max": "2",
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
        },
        "ocf:suse:SAPHana": {
            "PREFER_SITE_TAKEOVER": "true",
            "DUPLICATE_PRIMARY_TIMEOUT": "7200",
            "AUTOMATED_REGISTER": "true",
            "start-interval": "0",
            "start-timeout": "3600",
            "stop-interval": "0",
            "stop-timeout": "3600",
            "promote-interval": "0",
            "promote-timeout": "3600",
            "monitor-Master-interval": "60",
            "monitor-Master-timeout": "700",
            "monitor-Slave-interval": "61",
            "monitor-Slave-timeout": "700",
            "demote-interval": "0s",
            "demote-timeout": "320",
        },
        "stonith:fence_azure_arm": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15",
            "monitor-interval": "3600",
            "monitor-timeout": "120",
        },
        "ocf:heartbeat:azure-events-az": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "ocf:heartbeat:azure-lb": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
            "resource-stickiness": "0",
        },
        "ocf:heartbeat:IPaddr2": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
        },
    },
    "REDHAT": {
        "ocf:heartbeat:SAPHanaTopology": {
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
            "monitor-interval": "10",
            "monitor-timeout": "600",
            "start-interval": "0s",
            "start-timeout": "600",
            "stop-interval": "0s",
            "stop-timeout": "300",
        },
        "ocf:heartbeat:SAPHana": {
            "notify": "true",
            "clone-max": "2",
            "clone-node-max": "1",
            "target-role": "Started",
            "interleave": "true",
            "PREFER_SITE_TAKEOVER": "true",
            "DUPLICATE_PRIMARY_TIMEOUT": "7200",
            "AUTOMATED_REGISTER": "true",
            "start-interval": "0s",
            "start-timeout": "3600",
            "stop-interval": "0s",
            "stop-timeout": "3600",
            "promote-interval": "0s",
            "promote-timeout": "3600",
            "monitor-Master-interval": "59",
            "monitor-Master-timeout": "700",
            "monitor-Slave-interval": "61",
            "monitor-Slave-timeout": "700",
            "demote-interval": "0s",
            "demote-timeout": "3600",
        },
        "stonith:fence_azure_arm": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15s",
            "monitor-interval": "3600",
            "pcmk_monitor_timeout": "120",
        },
        "ocf:heartbeat:azure-events-az": {
            "interleave": "true",
            "allow-unhealthy-nodes": "true",
            "failure-timeout": "120s",
            "start-start-delay": "60s",
            "monitor-interval": "10s",
        },
        "ocf:heartbeat:azure-lb": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
        },
        "ocf:heartbeat:IPaddr2": {
            "monitor-interval": "10s",
            "monitor-timeout": "20s",
        },
    },
}

CLUSTER_PROPERTIES = {
    "DEFAULTS": {
        "crm_config": {
            "cib-bootstrap-options": {
                "cluster-infrastructure": "corosync",
                "stonith-enabled": "true",
                "concurrent-fencing": "true",
                "maintenance-mode": "false",
                "azure-events_globalPullState": "IDLE",
                "priority-fencing-delay": "30",
            }
        },
        "rsc_defaults": {
            "build-resource-defaults": {
                "resource-stickiness": "1000",
                "migration-threshold": "5000",
                "priority": "1",
            }
        },
        "op_defaults": {
            "op-options": {
                "timeout": "600",
                "record-pending": "true",
            }
        },
    },
    "ISCSI": {
        "crm_config": {
            "cib-bootstrap-options": {
                "have-watchdog": "true",
                "stonith-timeout": "144s",
            }
        },
    },
    "AFA": {
        "crm_config": {
            "cib-bootstrap-options": {
                "have-watchdog": "false",
                "stonith-timeout": "900s",
            }
        }
    },
}

OS_PARAMETERS = {
    "REDHAT": {
        "sysctl": {
            "net.ipv4.tcp_timestamps": {"expected_value": "0"},
            "vm.swappiness": {"expected_value": "10"},
        },
        "corosync-cmapctl": {
            "runtime.config.totem.token": {"expected_value": "30000"},
            "runtime.config.totem.consensus": {"expected_value": "36000"},
        },
    },
    "SUSE": {
        "sysctl": {
            "net.ipv4.tcp_timestamps": {"expected_value": "0"},
            "vm.swappiness": {"expected_value": "10"},
        },
        "corosync-cmapctl": {
            "runtime.config.totem.token": {"expected_value": "30000"},
            "runtime.config.totem.consensus": {"expected_value": "36000"},
            "quorum.expected_votes": {"expected_value": "2"},
        },
    },
}

CUSTOM_OS_PARAMETERS = {
    "REDHAT": {
        "quorum.expected_votes": {
            "expected_value": "2",
            "parameter_name": "Expected votes",
            "command": ["pcs", "quorum", "status"],
        },
    },
    "SUSE": {},
}

REQUIRED_PARAMETERS = {
    "priority-fencing-delay",
}

CONSTRAINTS = {
    "rsc_colocation": {
        "score": "4000",
        "rsc-role": "Started",
        "with-rsc-role": "Promoted",
    },
    "rsc_order": {
        "first-action": "start",
        "then-action": "start",
        "symmetrical": "false",
    },
    "rsc_location": {
        "score-attribute": "#health-azure",
        "operation": "defined",
        "attribute": "#uname",
    },
}

PROBES = {
    "probe_threshold": 2,
    "interval_in_seconds": 5,
    "number_of_probes": 2,
}

RULES = {
    "idle_timeout_in_minutes": 30,
    "enable_floating_ip": True,
    "enable_tcp_reset": False,
}

PACKAGE_LIST = [
    {"name": "Corosync Lib", "key": "corosynclib"},
    {"name": "Corosync", "key": "corosync"},
    {"name": "Fence Agents Common", "key": "fence-agents-common"},
    {"name": "Fencing Agent", "key": "fence-agents-azure-arm"},
    {"name": "Pacemaker CLI", "key": "pacemaker-cli"},
    {"name": "Pacemaker Libs", "key": "pacemaker-libs"},
    {"name": "Pacemaker Schemas", "key": "pacemaker-schemas"},
    {"name": "Pacemaker", "key": "pacemaker"},
    {"name": "Resource Agent", "key": "resource-agents"},
    {"name": "SAP Cluster Connector", "key": "sap-cluster-connector"},
    {"name": "SAPHanaSR", "key": "SAPHanaSR"},
    {"name": "Socat", "key": "socat"},
]

PCMK_KEYWORDS = {
    "LogAction",
    "LogNodeActions",
    "pacemaker-fenced",
    "check_migration_threshold",
    "corosync",
    "Result of",
    "reboot",
    "cannot run anywhere",
    "attrd_peer_update",
    "High CPU load detected",
    "cli-ban",
    "cli-prefer",
    "cib-bootstrap-options-maintenance-mode",
    "-is-managed",
    "-maintenance",
    "-standby",
}
SYS_KEYWORDS = {
    "SAPHana",
    "SAPHanaController",
    "SAPHanaTopology",
    "SAPInstance",
    "fence_azure_arm",
    "rsc_st_azure",
    "rsc_ip_",
    "rsc_nc_",
    "rsc_Db2_",
    "rsc_HANA_",
    "corosync",
    "Result of",
    "reboot",
}

LAWS_RESOURCE = "/api/logs"
LAWS_METHOD = "POST"
LAWS_CONTENT_TYPE = "application/json"
