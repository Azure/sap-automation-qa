# STAF Test Catalog

Complete reference of all test groups and test cases.

## Test Groups

### HA_DB_HANA — HANA Database High Availability (15 tests)

API name: `DatabaseHighAvailability`

| Test Case | Description | Task File |
|-----------|-------------|-----------|
| `ha-config` | HA configuration validation (online) | `ha-config.yml` |
| `ha-config-offline` | HA configuration validation (offline, no cluster) | `ha-config-offline.yml` |
| `azure-lb` | Azure Load Balancer validation | `azure-lb.yml` |
| `resource-migration` | Controlled resource migration between nodes | `resource-migration.yml` |
| `primary-node-crash` | Simulate primary node OS crash | `primary-node-crash.yml` |
| `primary-crash-index` | Terminate primary indexserver process | `primary-crash-index.yml` |
| `primary-node-kill` | Force terminate primary node | `primary-node-kill.yml` |
| `primary-echo-b` | Trigger primary crash via echo-b (SysRq) | `primary-echo-b.yml` |
| `secondary-node-kill` | Force terminate secondary node | `secondary-node-kill.yml` |
| `secondary-crash-index` | Terminate secondary indexserver process | `secondary-crash-index.yml` |
| `secondary-echo-b` | Trigger secondary crash via echo-b (SysRq) | `secondary-echo-b.yml` |
| `block-network` | Network isolation between cluster nodes | `block-network.yml` |
| `block-hana-shared` | Block access to HANA shared filesystem | `block-hana-shared.yml` |
| `fs-freeze` | ANF filesystem freeze/unfreeze test | `fs-freeze.yml` |
| `sbd-fencing` | SBD (STONITH Block Device) fencing test | `sbd-fencing.yml` |

**Supported topologies:** Scale-Up, Scale-Out HSR, Scale-Out Standby
**Supported SR providers:** SAPHanaSR, SAPHanaSR-angi
**Target OS:** SUSE (crm), RHEL (pcs)

---

### HA_SCS — SAP Central Services High Availability (13 tests)

API name: `CentralServicesHighAvailability`

| Test Case | Description | Task File |
|-----------|-------------|-----------|
| `ha-config` | HA configuration validation (online) | `ha-config.yml` |
| `ha-config-offline` | HA configuration validation (offline, no cluster) | `ha-config-offline.yml` |
| `azure-lb` | Azure Load Balancer validation | `azure-lb.yml` |
| `sapcontrol-config` | SAP control process validation | `sapcontrol-config.yml` |
| `ascs-migration` | ASCS instance migration | `ascs-migration.yml` |
| `ascs-node-crash` | ASCS node crash simulation | `ascs-node-crash.yml` |
| `block-network` | Network isolation between SCS/ERS nodes | `block-network.yml` |
| `kill-message-server` | Terminate SAP message server process | `kill-message-server.yml` |
| `kill-enqueue-server` | Terminate SAP enqueue server process | `kill-enqueue-server.yml` |
| `kill-enqueue-replication` | Terminate enqueue replication server | `kill-enqueue-replication.yml` |
| `kill-sapstartsrv-process` | Terminate SAPStartSrv process | `kill-sapstartsrv-process.yml` |
| `manual-restart` | Manual restart of SAP services | `manual-restart.yml` |
| `ha-failover-to-node` | Forced failover to specific node | `ha-failover-to-node.yml` |

**Supported enqueue types:** ENSA1, ENSA2
**Target OS:** SUSE (crm), RHEL (pcs)

---

### BACKUP_DB_HANA — Azure Backup for HANA Database (5 tests)

API name: `AzureBackupDatabase`

| Test Case | Description | Task File | Notes |
|-----------|-------------|-----------|-------|
| `backup-setup-verification` | Verify backup infrastructure setup | `backup-setup-verification.yml` | Pre-check |
| `restore-to-db` | Online Log Restore (OLR) to database | `restore-to-db.yml` | OLR |
| `restore-to-filesystem` | Restore backup to filesystem path | `restore-to-filesystem.yml` | |
| `recover-db-commands` | Execute database recovery commands | `recover-db-commands.yml` | Post-restore |
| `restore-cross-vm` | Alternate Location Restore across VMs | `restore-cross-vm.yml` | ALR, disabled by default |

**Required sap-parameters.yaml fields:**
- `backup_vault_resource_id`
- `backup_container_name`
- `backup_item_name`
- `backup_target_filesystem_path`
- `backup_target_container_name` (for ALR)
- `backup_target_database_name`
- `backup_restore_point_time` (ISO 8601 UTC, empty for latest)

---

## ConfigurationChecks

API name: `ConfigurationChecks` (use `--test-type=ConfigurationChecks` CLI flag or set `TEST_TYPE=ConfigurationChecks` in vars.yaml)

| Type | Description |
|------|-------------|
| `all` | Run all configuration checks |
| `Database` | HANA/DB2 database instance configuration |
| `CentralServiceInstances` | SCS and ERS instance configuration |
| `ApplicationInstances` | PAS and APP server configuration |
| `WebDispatcherInstances` | Web Dispatcher configuration |
| `ObserverInstances` | Observer instance configuration |

**Direct execution:**
```bash
./scripts/sap_automation_qa.sh --test-type=ConfigurationChecks --system-config=DEV-WEEU-SAP01-X00 --auth-type=SSHKEY
./scripts/sap_automation_qa.sh --test-type=ConfigurationChecks --system-config=DEV-WEEU-SAP01-X00 --extra-vars='{"configuration_test_type":"Database"}'
```

---

## Test Selection Examples

```bash
# Single test
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config]

# Multiple tests
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config,azure-lb,resource-migration]

# All tests in group
./scripts/sap_automation_qa.sh --test-groups=HA_SCS

# Offline-only (safe, no cluster changes)
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config-offline] --offline

# API mode
./scripts/sap_automation_qa.sh job create --workspace DEV-WEEU-SAP01-X00 --test-group DatabaseHighAvailability --test-ids ha-config,azure-lb
```