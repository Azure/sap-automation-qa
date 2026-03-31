#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

show_sap_automation_qa_usage() {
    local script_name="${1:-$0}"

    cat << EOF
Usage: $script_name <command> [OPTIONS]

Commands (SAP QA Service API):
  health                    Check service health
  workspace [--id <ID>]     List or get workspaces
  job <action> [OPTIONS]    Manage jobs  (create, list, get, log, events, cancel)
  schedule <action> [OPTS]  Manage schedules (create, list, get, update, delete, trigger, jobs)

  Run "$script_name job --help" or "$script_name schedule --help" for detailed usage.

Direct Playbook Execution:
  -v, -vv, -vvv, etc.       Set Ansible verbosity level
  --test_groups=GROUP       Specify test group to run (e.g., HA_DB_HANA, HA_SCS)
  --test_cases=[case1,case2] Specify specific test cases to run (comma-separated, in brackets)
  --extra-vars=VAR          Specify additional Ansible extra variables (e.g., --extra-vars='{"key":"value"}')
  --offline                 Run offline test cases using previously collected CIB data.
				While running offline tests, the script will look for CIB data in
				WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/offline_validation directory.
				Extra vars "ansible_os_family" required for offline mode
				(e.g., --extra-vars='{"ansible_os_family":"SUSE"}')
  -h, --help                Show this help message

Examples:
  # SAP QA Service
  $script_name health
  $script_name workspace
  $script_name job create --workspace DEV-WEEU-SAP01-X00 --test-group DatabaseHighAvailability
  $script_name schedule create --name "Nightly HA" --cron "0 2 * * *" --workspaces DEV-WEEU-SAP01-X00

  # High Availability Tests (direct)
  $script_name --test_groups=HA_DB_HANA --test_cases=[ha-config,primary-node-crash]
  $script_name --test_groups=HA_SCS
  $script_name --test_groups=HA_DB_HANA --test_cases=[ha-config,primary-node-crash] -vv
  $script_name --test_groups=HA_DB_HANA --test_cases=[ha-config,primary-node-crash] --extra-vars='{"key":"value"}'
  $script_name --test_groups=HA_DB_HANA --test_cases=[ha-config] --offline

  # Azure Backup Tests (set SAP_FUNCTIONAL_TEST_TYPE: AzureBackupDatabase in vars.yaml)
  $script_name --test_groups=BACKUP_DB_HANA --test_cases=[backup-setup-verification]
  $script_name --test_groups=BACKUP_DB_HANA --test_cases=[restore-to-db,restore-to-filesystem]
  $script_name --test_groups=BACKUP_DB_HANA -vv

  # Configuration Checks (requires TEST_TYPE: ConfigurationChecks in vars.yaml)
  $script_name --extra-vars='{"configuration_test_type":"all"}'
  $script_name --extra-vars='{"configuration_test_type":"high_availability"}'
  $script_name --extra-vars='{"configuration_test_type":"Database"}' -v

Available Test Cases for groups:
	$script_name --test_groups=HA_DB_HANA
				ha-config => High Availability configuration
				azure-lb => Azure Load Balancer
				resource-migration => Resource Migration
				primary-node-crash => Primary Node Crash
				block-network => Block Network Communication from Primary Master Node
				secondary-block-network => Block Network Communication from Secondary Master Node
				primary-crash-index => Kill hdbindexserver on Primary Master Node
				primary-worker-crash-index => Kill hdbindexserver on Primary Worker Node
				primary-node-kill => Kill SAP HANA Instance on Primary Master Node
				primary-worker-node-kill => Kill SAP HANA Instance on Primary Worker Node
				primary-echo-b => Crash Primary Master Node using echo b
				primary-worker-echo-b => Crash Primary Worker Node using echo b
				secondary-node-kill => Kill SAP HANA Instance on Secondary Master Node
				secondary-worker-node-kill => Kill SAP HANA Instance on Secondary Worker Node
				secondary-echo-b => Crash Secondary Master Node using echo b
				secondary-worker-echo-b => Crash Secondary Worker Node using echo b
				fs-freeze => FS Freeze
				sbd-fencing => SBD Fencing
				secondary-crash-index => Kill hdbindexserver on Secondary Master Node
				secondary-worker-crash-index => Kill hdbindexserver on Secondary Worker Node
				block-hana-shared => Block NFS IP on Primary Master Node
	$script_name --test_groups=HA_SCS
				ha-config => High Availability configuration
				azure-lb => Azure Load Balancer
				sapcontrol-config => SAP Control Configuration
				ascs-migration => ASCS Migration
				block-network => Block Network
				kill-message-server => Kill Message Server
				kill-enqueue-server => Kill Enqueue Server
				kill-enqueue-replication => Kill Enqueue Replication
				kill-sapstartsrv-process => Kill SAP Start Service Process
				manual-restart => Manual Restart
				ha-failover-to-node => HA Failover to Secondary Node
	$script_name --test_groups=BACKUP_DB_HANA
				backup-setup-verification => Azure Backup Setup Verification
				restore-to-db => Restore Backup to HANA DB
				restore-to-filesystem => Restore Backup to FileSystem
				recover-db-commands => Recover DB using Database Commands
				restore-cross-vm => Cross-VM Restore

Configuration Checks (set TEST_TYPE: ConfigurationChecks in vars.yaml):
	configuration_test_type options (use with --extra-vars):
				all => Run all configuration checks
				Database => Database (HANA) configuration checks only
				CentralServiceInstances => ASCS/ERS configuration checks only
				ApplicationInstances => Application server configuration checks only

Configuration is read from vars.yaml file.
EOF
}