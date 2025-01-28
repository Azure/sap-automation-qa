#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


"""
Constants module for SAP App Later cluster configuration.
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
        "stonith:fence_azure_arm": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15",
            "monitor-interval": "3600",
            "pcmk_monitor_timeout": "120",
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
            "monitor-interval": "10",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "ocf:heartbeat:IPaddr2": {
            "monitor-interval": "10",
            "monitor-timeout": "20",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "ocf:heartbeat:SAPInstance:ASCS": {
            "AUTOMATIC_RECOVER": "false",
            "MINIMAL_PROBE": "true",
            "resource-stickiness": "5000",
            "priority": "100",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
        },
        "ocf:heartbeat:SAPInstance:ERS": {
            "AUTOMATIC_RECOVER": "false",
            "IS_ERS": "true",
            "MINIMAL_PROBE": "true",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
        },
    },
    "REDHAT": {
        "stonith:fence_azure_arm": {
            "pcmk_monitor_retries": "4",
            "pcmk_action_limit": "3",
            "power_timeout": "240",
            "pcmk_reboot_timeout": "900",
            "pcmk_delay_max": "15",
            "monitor-interval": "3600",
            "pcmk_monitor_timeout": "120",
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
            "monitor-interval": "10",
            "monitor-timeout": "20s",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "ocf:heartbeat:IPaddr2": {
            "monitor-interval": "10",
            "monitor-timeout": "20",
            "start-interval": "0s",
            "start-timeout": "20s",
            "stop-interval": "0s",
            "stop-timeout": "20s",
        },
        "ocf:heartbeat:SAPInstance:ASCS": {
            "AUTOMATIC_RECOVER": "false",
            "MINIMAL_PROBE": "true",
            "resource-stickiness": "5000",
            "priority": "100",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
        },
        "ocf:heartbeat:SAPInstance:ERS": {
            "AUTOMATIC_RECOVER": "false",
            "IS_ERS": "true",
            "MINIMAL_PROBE": "true",
            "monitor-interval": "11",
            "monitor-timeout": "60",
            "start-interval": "0s",
            "start-timeout": "180s",
            "stop-interval": "0s",
            "stop-timeout": "240s",
            "promote-interval": "0s",
            "promote-timeout": "320s",
            "demote-interval": "0s",
            "demote-timeout": "320s",
        },
    },
}

CLUSTER_PROPERTIES = {
    "crm_config": {
        "cib-bootstrap-options": {
            "have-watchdog": "false",
            "cluster-infrastructure": "corosync",
            "stonith-enabled": "true",
            "concurrent-fencing": "true",
            "stonith-timeout": "900",
            "maintenance-mode": "false",
            "azure-events_globalPullState": "IDLE",
            "priority-fencing-delay": "30",
        }
    },
    "rsc_defaults": {
        "build-resource-defaults": {
            "resource-stickiness": "1",
            "migration-threshold": "3",
            "priority": "1",
        }
    },
}

OS_PARAMETERS = {
    "REDHAT": {
        "sysctl": {
            "net.ipv4.tcp_timestamps": {"expected_value": "1"},
            "vm.swappiness": {"expected_value": "10"},
        },
        "corosync-cmapctl": {
            "runtime.config.totem.token": {"expected_value": "30000"},
            "runtime.config.totem.consensus": {"expected_value": "36000"},
        },
    },
    "SUSE": {
        "sysctl": {
            "net.ipv4.tcp_timestamps": {"expected_value": "1"},
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
        "score": "-5000",
        "rsc-role": "Started",
        "with-rsc-role": "Promoted",
    },
    "rsc_order": {
        "first-action": "start",
        "then-action": "stop",
        "symmetrical": "false",
    },
    "rsc_location": {
        "score-attribute": "#health-azure",
        "operation": "defined",
        "attribute": "#uname",
    },
}

PARAMETER_VALUE_FORMAT = "Name: %s, Value: %s, Expected Value: %s"
