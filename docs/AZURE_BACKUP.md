# Functional Test for Azure Backup for SAP HANA

The SAP Testing Automation Framework includes an Azure Backup testing component that validates the configuration of Azure Backup infrastructure and functionality of restore operations by performing actual restore for SAP HANA databases deployed on Azure.

> **Important:** This is a **testing and validation tool only**. It is designed to verify that Azure Backup is correctly configured and that restore operations function as expected. It should **not** be used as a substitute for actual SAP HANA database restore procedures in any scenario.

## Supported Scenarios

The framework supports both **HA (two-node cluster)** and **Non-HA (single-node)** HANA deployments. Five test cases cover the end-to-end backup-restore lifecycle:

| # | Test Case | Task Name | Description |
|---|-----------|-----------|-------------|
| 1 | Azure Backup Configuration Validation | `backup-setup-verification` | Discovers all protected HANA databases in the Recovery Services vault, verifies backup configuration health, and checks that recent restore points exist. |
| 2 | Restore Backup to HANA DB | `restore-to-db` | Triggers a full or point-in-time restore to the original HANA database via Azure Backup, monitors the restore job, then validates HANA is running. |
| 3 | Restore Backup to FileSystem | `restore-to-filesystem` | Restores the HANA backup as files to a filesystem path, verifies the files are present, then recovers the HANA DB from those files and validates it is operational. |
| 4 | Recover DB using Database Commands | `recover-db-commands` | Tests native HANA recovery using `recoverSys.py` / `RECOVER DATA`. Queries the backup catalog, stops HANA, performs recovery, restarts, and validates consistency. |
| 5 | Cross-VM Restore | `restore-cross-vm` | Restores **tenant databases only** from VM-1 to VM-2 (AlternateWorkloadRestore). SYSTEMDB is not restored in cross-VM scenarios. Validates the target HANA instance starts and the databases are consistent. **Disabled by default** — requires `backup_target_vm_name` and must be explicitly enabled. |

## Prerequisites

### 1. Setup Configuration

Follow the steps (1.1 - 1.5) in [Setup Guide for SAP Testing Automation Framework](./SETUP.MD) to set up the framework on a management server.

### 2. System Configuration

Update the `TEST_TYPE` parameter in [`vars.yaml`](./../vars.yaml) file to `SAPFunctionalTests` and `SAP_FUNCTIONAL_TEST_TYPE` to `AzureBackupDatabase` to enable the Azure Backup test scenarios.

Follow the steps (2.1 - 2.2) in [Setup Guide for SAP Testing Automation Framework](./SETUP.MD#2-system-configuration) to configure your system details.

### 3. Required Access and Permissions

The management server's managed identity (system- or user-assigned) requires the following roles to perform backup restore operations and interact with Azure resources. For more details on configuring system assigned managed identity vs user assigned managed identity, see [Setup Guide for SAP Testing Automation Framework](./SETUP.MD#4-identity-and-authorization).

1. Depending on the type of managed identity method you want to use, configure managed identity on management server
   - [Configuring access using user-assigned managed identity](./SETUP.MD#option-1-user-assigned-managed-identity).
   - [Configuring access using system-assigned managed identity](./SETUP.MD#option-2-system-assigned-managed-identity).
2. Grant the managed identity (system- or user-assigned) the following roles:

| Role | Scope | Purpose |
|------|-------|---------|
| **Backup Operator** | Recovery Services vault | Discover protected items, list restore points, trigger restore operations, monitor restore jobs |
| **Virtual Machine Contributor** | Target VM(s) where restore is performed | Required for restore operations to interact with the target HANA VM (e.g., filesystem restores, cross-VM restores) |

### 4. Azure Backup Configuration

- A **Recovery Services vault** must exist with SAP HANA backup configured.
- At least one HANA database must be **registered and protected** with a backup policy.
- A recent backup (full or incremental) must have completed successfully so restore points are available.

For setup guidance, see [Back up SAP HANA databases in Azure VMs](https://learn.microsoft.com/azure/backup/sap-hana-database-instances-backup).

## Configuration

### 1. Update `vars.yaml`

Set the test type to `AzureBackupDatabase`:

```yaml
TEST_TYPE:                  SAPFunctionalTests
SAP_FUNCTIONAL_TEST_TYPE:   AzureBackupDatabase
```

### 2. Configure Backup Parameters

Add the following variables to your system's `sap-parameters.yaml` file (under `WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/`):

```yaml
# Recovery Services vault ARM resource ID (required)
backup_vault_resource_id:         "/subscriptions/xxxx/resourceGroups/my-rg/providers/Microsoft.RecoveryServices/vaults/my-vault"

# Whether to restore SYSTEMDB (set false to skip)
backup_restore_systemdb:          true
# Restrict tenant restore to specific DBs (empty = all tenants)
backup_restore_tenants:           []          # e.g. ["HDB", "H01"]

# Target path for file-based restore; must be writable
backup_target_filesystem_path:    "/sapinstall/hana_backup/"

# Target VM hostname for cross-VM restore (required for test case 5, disabled by default)
# Must be a hostname resolvable from the source VM (e.g., via DNS or /etc/hosts)
backup_target_vm_name:            ""
# Target VM resource group (optional; defaults to source VM's resource group if empty)
backup_target_vm_rg:              ""

# Point-in-time restore (optional, ISO 8601 UTC)
backup_restore_point_time:        ""

# HANA userstore key (created as part of pre-registration for Azure Backup)
hana_userstore_key:               "SYSTEM"
```

#### Parameter Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `backup_vault_resource_id` | `""` | Full ARM resource ID of the Recovery Services vault (required) |
| `backup_restore_systemdb` | `true` | Whether to include SYSTEMDB in restore operations |
| `backup_restore_tenants` | `[]` | List of tenant DB names to restore; empty means all tenants |
| `backup_target_filesystem_path` | `"/sapinstall/hana_backup/"` | Filesystem path for restore-as-files (test case 3) |
| `backup_target_vm_name` | `""` | Target VM hostname for cross-VM restore (test case 5) |
| `backup_target_vm_rg` | `""` | Target VM resource group; defaults to source VM's RG if empty |
| `backup_restore_point_time` | `""` | Point-in-time for restore in ISO 8601 UTC; empty uses latest recovery point |
| `hana_userstore_key` | `"SYSTEM"` | HANA hdbuserstore key for database connectivity |

### 3. User-Assigned Managed Identity (Optional)

If your management server uses a user-assigned managed identity, set the client ID in `vars.yaml`:

```yaml
user_assigned_identity_client_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

If omitted or set to `null`, the framework uses system-assigned managed identity.

## Test Execution

Run the tests using the `sap_automation_qa.sh` script:

```bash
# Run all Azure Backup test cases
./scripts/sap_automation_qa.sh --test_groups=BACKUP_DB_HANA

# Run specific test cases
./scripts/sap_automation_qa.sh --test_groups=BACKUP_DB_HANA --test_cases=[backup-setup-verification]
./scripts/sap_automation_qa.sh --test_groups=BACKUP_DB_HANA --test_cases=[restore-to-db,restore-to-filesystem]
./scripts/sap_automation_qa.sh --test_groups=BACKUP_DB_HANA --test_cases=[restore-cross-vm]

# Run with verbose output
./scripts/sap_automation_qa.sh --test_groups=BACKUP_DB_HANA -vv
```

### Via SAP QA Service API

```bash
# Create a job through the API
./scripts/sap_automation_qa.sh job create --workspace DEV-WEEU-SAP01-X00 --test-group AzureBackupDatabase
```

## Viewing Test Results

Test results are generated the same way as HA tests. Navigate to your workspace directory:

```bash
cd WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/quality_assurance/
```

The HTML report summarises each test case with PASS/FAIL/WARNING/SKIPPED status. For details on the report format, see [High Availability — Viewing Test Results](./HIGH_AVAILABILITY.md#viewing-test-results).
