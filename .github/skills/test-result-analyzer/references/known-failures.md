# Known STAF Test Failure Patterns

Common failure patterns encountered when running SAP Testing Automation Framework (STAF) tests.
These are **framework-level** failures — issues with test execution, connectivity, configuration,
and infrastructure validation. SAP application-level errors are out of scope.

**Usage:** Match log patterns from Ansible output against the tables below.

---

## Cluster Pre/Post Validation Failures

These occur during `ha-config` validation or pre/post checks in HA tests.

| Pattern in Log | Root Cause | Fix | OS |
|----------------|------------|-----|-----|
| `cli-ban` location constraint with `INFINITY` score | Stale location constraint from previous test or maintenance | `crm_resource --clear <resource>` (SUSE) / `pcs resource clear <resource>` (RHEL) | Both |
| `resource-migration: FAILED` with `Resource is unmanaged` | Resource in unmanaged mode from prior maintenance | `crm resource manage <resource>` (SUSE) / `pcs resource manage <resource>` (RHEL) | Both |
| `Timeout waiting for resource` | Cluster takeover exceeded test timeout | Check cluster health: `crm status` / `pcs status`. Increase timeout via `--extra-vars` | Both |
| `Cluster is in maintenance mode` | Maintenance mode not disabled after prior operation | `crm configure property maintenance-mode=false` (SUSE) / `pcs property set maintenance-mode=false` (RHEL) | Both |
| `Node is in standby` | Node put into standby by prior test, not restored | `crm node online <node>` (SUSE) / `pcs node unstandby <node>` (RHEL) | Both |
| `Resource is already active on node` | Migration target already running the resource | Check `crm status` / `pcs status` — may indicate previous test cleanup failure | Both |

## Fencing and SBD Failures

These occur during `sbd-fencing` tests or when fencing is triggered by crash/kill tests.

| Pattern in Log | Root Cause | Fix | OS |
|----------------|------------|-----|-----|
| `sbd: command not found` | SBD package not installed | `zypper install sbd` (SUSE) / `yum install sbd` (RHEL) | Both |
| `Fencing failed` or `stonith action failed` | SBD device or Azure Fence Agent not working | SBD: `sbd -d <device> list`. Azure: verify MSI permissions on compute resources | Both |
| `Node failed to fence within timeout` | Fencing delay exceeds cluster timeout | Increase stonith timeout in cluster properties. Check SBD device latency | Both |

---

## SSH / Connection Failures

Ansible connectivity failures — the framework cannot reach target hosts.

| Pattern in Log | Root Cause | Fix |
|----------------|------------|-----|
| `UNREACHABLE!` with `Failed to connect to the host via ssh` | SSH connection failed | Verify IP in `hosts.yaml`. Test: `ssh -i <key> <user>@<host>`. Check NSG rules |
| `Permission denied (publickey,password)` | SSH key auth failed | Check `ssh_key.ppk` in workspace, or `secret_id` in `sap-parameters.yaml` for Key Vault |
| `Connection timed out` | Host unreachable (firewall, VM stopped) | Verify IP in `hosts.yaml`. Check Azure NSG allows port 22. Verify VM is running |
| `Host key verification failed` | Host SSH key changed | STAF sets `ANSIBLE_HOST_KEY_CHECKING=False` automatically. Clear `~/.ssh/known_hosts` if needed |
| `Connection refused` on port 22 | SSH service not running on target | Check: `systemctl status sshd` on target host |

---

## Workspace Configuration Errors

Missing or incorrect STAF configuration files.

| Pattern in Log | Root Cause | Fix |
|----------------|------------|-----|
| `variable 'db_sid' is undefined` | Required field missing in `sap-parameters.yaml` | Add field. Run `/workspace-validator` to check all fields |
| `No such file or directory: vars.yaml` | Framework `vars.yaml` not configured at project root | Create `vars.yaml` with `TEST_TYPE`, `SAP_FUNCTIONAL_TEST_TYPE`, `SYSTEM_CONFIG_NAME`, `AUTHENTICATION_TYPE` |
| `Could not find the specified file: hosts.yaml` | Ansible inventory missing from workspace | Create `WORKSPACES/SYSTEM/{name}/hosts.yaml` with host groups and entries |
| `Workspace '<name>' not found` | Workspace directory does not exist | Create directory under `WORKSPACES/SYSTEM/` with `sap-parameters.yaml` and `hosts.yaml` |
| `sap-parameters.yaml not found` | Missing from workspace directory | Create `sap-parameters.yaml` — use `/workspace-creator` skill |
| `configuration_check_module: validation failed` | System config does not match expected value | Review expected vs actual in output. Update system config or adjust values in `roles/configuration_checks/vars/` |

---

## Azure Infrastructure Validation Failures

These occur during STAF's `azure-lb` test and MSI-based authentication.

| Pattern in Log | Root Cause | Fix |
|----------------|------------|-----|
| `Azure LB validation failed: probe port not responding` | Health probe port not listening on cluster node | Verify azure-lb resource agent is running in cluster |
| `get_azure_lb module: Unauthorized` | MSI not assigned or missing Reader role | Assign MSI to VM. Grant Reader role on Load Balancer resource |
| `MSI authentication failed` | Managed identity not enabled on management server | Enable system-assigned MSI or set `user_assigned_identity_client_id` in `sap-parameters.yaml` |
| `Key Vault secret not found` | `secret_id` in `sap-parameters.yaml` is incorrect | Verify: `az keyvault secret show --id <secret_id>`. Check URL format |
| `Token acquisition failed for Key Vault` | MSI missing Key Vault Secrets User role | Grant role: `az role assignment create --role "Key Vault Secrets User"` |
| `ANF filesystem freeze failed` | `fs-freeze` test — permissions or ANF not configured | Verify `ANF_account_rg` and `ANF_account_name` in `sap-parameters.yaml` |

---

## Telemetry Failures

Non-blocking — tests still pass/fail, but results are not sent to Azure.

| Pattern in Log | Root Cause | Fix |
|----------------|------------|-----|
| `send_telemetry_data module failed: workspace_id not provided` | Log Analytics workspace ID missing from `vars.yaml` | Set `laws_workspace_id` and `laws_shared_key` in `vars.yaml` |
| `Kusto ingest failed` | ADX cluster URL incorrect or permissions missing | Verify `adx_cluster_fqdn` and `adx_database_name` in `vars.yaml` |
| `Telemetry: 403 Forbidden` | Auth failed for telemetry destination | For Log Analytics: check `laws_shared_key`. For ADX: check MSI permissions |

---

## Job / Worker Failures (API Mode)

These occur when running tests via `./scripts/sap_automation_qa.sh job create`.

| Pattern in Log | Root Cause | Fix |
|----------------|------------|-----|
| `Job submission failed: workspace locked` | Another job running in same workspace | Wait for current job or cancel: `job cancel --id <ID>` |
| `Job status: orphaned (recovered)` | Worker crashed during execution | Job auto-marked failed on restart. Re-run job |
| `Credential provisioning failed` | No SSH key and no Key Vault configured | Add `ssh_key.ppk` to workspace, or set `secret_id` in `sap-parameters.yaml` |
| `ansible-runner failed to start` | Workspace directory structure corrupted | Verify workspace has valid `sap-parameters.yaml` and `hosts.yaml` |

---

## Test Sequencing Failures

Issues between consecutive test case runs.

| Pattern in Log | Root Cause | Fix |
|----------------|------------|-----|
| `cleanup: cluster not healthy for next test` | Previous test left cluster in bad state | `crm_resource --cleanup` (SUSE) / `pcs resource cleanup` (RHEL). Clear constraints |
| `Pre-validation failed: prerequisite not met` | System not in expected state before test | Review pre-validation output. Restore system to baseline |
| `Primary node crash: cluster did not failover` | Cluster configured for manual failover only | Verify cluster auto-failover config. May be intentional per SAP Note |

---

## Azure Backup and Restore Failures

These occur during `BACKUP_DB_HANA` tests (backup-setup-verification, restore-to-db, restore-to-filesystem, recover-db-commands, restore-cross-vm).

| Pattern in Log | Root Cause | Fix |
|----------------|------------|-----|
| `backup_vault_resource_id not found` | Missing or invalid Recovery Services vault resource ID in `sap-parameters.yaml` | Verify `backup_vault_resource_id` — format: `/subscriptions/.../Microsoft.RecoveryServices/vaults/<name>` |
| `Backup container not found` | `backup_container_name` does not match Azure Backup registration | Verify format: `VMAppContainer;Compute;<rg>;<vm>`. Check: `az backup container list --vault-name <vault> --resource-group <rg> --backup-management-type AzureWorkload` |
| `Backup item not found` or `backup_item_name invalid` | HANA database not registered with Azure Backup | Verify format: `saphanadatabase;<sid>;<db>`. Check: `az backup item list --vault-name <vault> --resource-group <rg> --workload-type SAPHANA` |
| `Restore failed: no recovery point` | No valid recovery point exists or `backup_restore_point_time` is invalid | Set `backup_restore_point_time` to valid ISO 8601 UTC timestamp, or leave empty for latest. Check: `az backup recoverypoint list` |
| `Restore timed out` or `Restore operation exceeded timeout` | Restore takes longer than expected (large database, network throttling) | Increase timeout. Check Azure Backup job status in portal. Verify storage throughput |
| `Target filesystem path not accessible` | `backup_target_filesystem_path` does not exist or has wrong permissions | Verify path exists on target VM. Check mount status: `df -h {path}`. Ensure `{sid}adm` has write access |
| `Cross-VM restore failed: target container not found` | `backup_target_container_name` invalid or target VM not registered | Verify target VM is registered with the vault. Format: `VMAppContainer;Compute;<rg>;<target-vm>` |
| `HANA database recovery failed` | Post-restore recovery commands failed (SYSTEMDB or tenant recovery) | Check HANA trace files. Verify `backup_target_database_name` (e.g., SYSTEMDB). Run `HDB info` on target |
| `MSI auth failed for Recovery Services vault` | Managed identity missing Backup Operator role on vault | Grant role: `az role assignment create --role "Backup Operator" --assignee <identity> --scope <vault-id>` |
| `pre-registration script not run` | HANA backup pre-registration script not executed on target VM | Run: `msawb-plugin-config-com-sap-hana.sh` on target. See Azure Backup for SAP HANA docs |

---

## Interpreting PLAY RECAP

The Ansible PLAY RECAP summarizes execution per host:

| Field | Meaning |
|-------|---------|
| `ok` | Tasks ran successfully (no change) |
| `changed` | Tasks that modified system state |
| `unreachable` | Host not reachable (SSH failure) — may be expected for crash/kill tests |
| `failed` | Tasks that failed — `failed > 0` on ANY host means test FAILED |
| `skipped` | Conditions not met (different OS, topology) — high count is normal |
| `rescued` | Failures caught by `rescue:` block — handled gracefully by framework |
