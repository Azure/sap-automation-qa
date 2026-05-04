---
name: workspace-validator
description: >
  Validate SAP workspace configurations before running tests.
  Use when asked to validate a workspace, check config, or troubleshoot workspace setup issues.
  Triggered by "validate workspace", "check config", "workspace issues", "fix workspace",
  "sap-parameters check", "hosts.yaml check", or "SSH auth problems".
allowed-tools: shell
---

# Workspace Validator

Validates SAP workspace configurations before test execution. Checks file presence, field
completeness, valid values, SSH authentication readiness, and inventory structure.

## When to Use

| Trigger | Action |
|---------|--------|
| `validate workspace` / `check config` | Run full validation |
| `workspace issues` / `fix workspace` | Diagnose and fix problems |
| `sap-parameters check` | Validate SAP parameters file |
| `hosts.yaml check` | Validate Ansible inventory |
| `SSH auth problems` | Check authentication configuration |

## Running Validation

```bash
python3 .github/skills/workspace-validator/scripts/validate_workspace.py [WORKSPACE_PATH]
```

If no path is provided, discovers and validates all workspaces under `WORKSPACES/SYSTEM/`.

**Examples:**
```bash
# Validate specific workspace
python3 .github/skills/workspace-validator/scripts/validate_workspace.py \
  WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00

# Validate all workspaces
python3 .github/skills/workspace-validator/scripts/validate_workspace.py
```

**Exit codes:**
- `0` — All critical checks passed
- `1` — One or more critical checks failed

## What Gets Validated

### 1. File Presence

| File | Status |
|------|--------|
| `sap-parameters.yaml` | Required |
| `hosts.yaml` or `{SID}_hosts.yaml` | Required |
| SSH key file (extensions: ppk, pem, key, private, rsa, ed25519, ecdsa, dsa) | Conditional |
| `password` file | Conditional (VMPASSWORD auth only) |

### 2. sap-parameters.yaml Validation

**Always required fields:**
- `sap_sid` — SAP System ID (3 chars, uppercase alphanumeric)
- `platform` — Valid values: `HANA`, `DB2`
- `db_sid` — Database SID
- `db_instance_number` — String, 2 digits (e.g., `"00"`)
- `database_high_availability` — Boolean (`true`/`false`)
- `scs_high_availability` — Boolean
- `scs_instance_number` — String, 2 digits
- `ers_instance_number` — String, 2 digits
- `NFS_provider` — Valid values: `AFS`, `ANF`

**Conditional fields:**
- `database_cluster_type` — Required when `database_high_availability: true`. Values: `AFA`, `ISCSI`, `ANF`
- `scs_cluster_type` — Required when `scs_high_availability: true`. Values: `AFA`, `ISCSI`, `ANF`
- `database_scale_out` — Boolean, defaults to `false`
- `key_vault_id` — Azure resource ID (if Key Vault auth)
- `secret_id` — Key Vault secret URL (if Key Vault auth)
- `user_assigned_identity_client_id` — UUID (if MSI auth)
- `ANF_account_rg` — Required when `NFS_provider: ANF` or cluster_type includes ANF
- `ANF_account_name` — Required when ANF is used

**Azure Backup fields (for AzureBackupDatabase tests):**
- `backup_vault_resource_id` — Recovery Services vault resource ID
- `backup_container_name` — Format: `VMAppContainer;Compute;<rg>;<vm>`
- `backup_item_name` — Format: `saphanadatabase;<sid>;<db>`
- `backup_target_filesystem_path` — e.g., `/hana/backup/restore`
- `backup_target_container_name` — Target container (ALR)
- `backup_target_database_name` — e.g., `SYSTEMDB`
- `backup_restore_point_time` — ISO 8601 UTC (empty string for latest)

### 3. hosts.yaml Validation

**Required groups (based on test type):**
- `{SID}_DB` — 2 hosts (for DatabaseHighAvailability)
- `{SID}_SCS` — 1 host (for CentralServicesHighAvailability)
- `{SID}_ERS` — 1 host (for CentralServicesHighAvailability)
- `{SID}_PAS` — 1 host (optional)
- `{SID}_APP` — 1+ hosts (optional)

**Required per-host fields:**
- `ansible_host` — IP address or hostname
- `ansible_user` — SSH username (typically `azureadm`)
- `ansible_connection` — Must be `ssh`
- `connection_type` — Must be `key`
- `virtual_host` — Virtual hostname for cluster resources
- `become_user` — Must be `root`
- `os_type` — Must be `linux`
- `vm_name` — Azure VM name

**Required group vars:**
- `node_tier` — Values: `hana`, `scs`, `ers`, `pas`, `app`
- `supported_tiers` — List (e.g., `[hana]`)

### 4. SSH Authentication

Priority order (checked top-to-bottom, first match wins):
1. **Key Vault** — `secret_id` field in sap-parameters.yaml → MSI retrieves SSH key
2. **Local key file** — File with extension: `ppk`, `pem`, `key`, `private`, `rsa`, `ed25519`, `ecdsa`, `dsa`, or filename containing `ssh_key`
3. **Password file** — File named `password` in workspace directory (VMPASSWORD auth)

## Output Format

```
════════════════════════════════════════════════════════════════
  Workspace Validation: DEV-WEEU-SAP01-X00
════════════════════════════════════════════════════════════════

📁 File Checks
  ✅ sap-parameters.yaml found
  ✅ hosts.yaml found
  ✅ SSH key file found (ssh_key.pem)

📋 sap-parameters.yaml
  ✅ sap_sid: X00
  ✅ platform: HANA
  ✅ database_high_availability: true
  ✅ database_cluster_type: AFA
  ❌ db_instance_number: missing (required)
  ⚠️  ANF_account_rg: missing (needed when NFS_provider=ANF)

📋 hosts.yaml
  ✅ X00_DB group: 2 hosts found
  ✅ All hosts have required fields
  ❌ X00_SCS group: missing (required for SCS HA tests)

🔐 SSH Authentication
  ✅ Key Vault auth configured (secret_id present)

────────────────────────────────────────────────────────────────
  Result: ❌ FAILED (2 errors, 1 warning)
────────────────────────────────────────────────────────────────
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `sap-parameters.yaml not found` | File missing | Create from template (use `workspace-creator`) |
| `hosts.yaml not found` | Inventory missing | Create with all required host groups |
| `Invalid sap_sid` | Not 3 chars or invalid chars | Use exactly 3 uppercase alphanumeric chars |
| `Invalid platform` | Not HANA or DB2 | Set to `HANA` or `DB2` |
| `No SSH authentication found` | No key/vault/password | Add key file or configure Key Vault |
| `{SID}_DB missing` | Group not in hosts.yaml | Add group with 2 hosts for HA |
| `virtual_host missing` | Host field incomplete | Add virtual hostname for cluster resource |

## Pre-Completion Checklist

Before reporting validation complete:
- [ ] Script ran without Python errors
- [ ] All critical (❌) issues are resolved or explained
- [ ] Warnings (⚠️) are acknowledged with rationale
- [ ] SSH authentication path is confirmed working
- [ ] Host groups match the intended test type

## Related Skills

| Need to... | Use skill |
|------------|-----------|
| Create a workspace from scratch | `workspace-creator` |
| Run tests on validated workspace | `test-runner` |
| Set up the environment first | `setup-guide` |
