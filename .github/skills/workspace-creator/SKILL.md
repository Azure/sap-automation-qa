---
name: workspace-creator
description: >
  Create new SAP workspace configurations for STAF testing.
  Use when asked to set up a new workspace, onboard a system, or create workspace configs.
allowed-tools: shell
license: MIT
---

# Workspace Creator

Creates new SAP workspace configurations for STAF testing. Generates `sap-parameters.yaml`
and `hosts.yaml` from templates based on user-provided system details.

## Locate Framework

Before creating workspaces, locate the STAF framework directory:

```bash
if [ -f "./scripts/sap_automation_qa.sh" ]; then
  STAF_DIR="$(pwd)"
elif [ -f "../sap-automation-qa/scripts/sap_automation_qa.sh" ]; then
  STAF_DIR="$(cd ../sap-automation-qa && pwd)"
else
  git clone https://github.com/Azure/sap-automation-qa.git ../sap-automation-qa
  STAF_DIR="$(cd ../sap-automation-qa && pwd)"
fi
cd "$STAF_DIR"
```

> **⚠️ This skill is guidance only. Do NOT modify any source code, scripts, or framework files. Only help the user by creating workspace configuration files (sap-parameters.yaml, hosts.yaml) under WORKSPACES/SYSTEM/.**

## When to Use

| Trigger | Action |
|---------|--------|
| `create workspace` / `new workspace` | Full workspace creation |
| `onboard system` / `setup SAP system` | Guide through system onboarding |
| `generate hosts.yaml` | Create inventory file |
| `generate sap-parameters` | Create SAP parameters file |
| `add new system` | Create workspace directory structure |

## Workspace Location

All workspaces live under:
```
WORKSPACES/SYSTEM/{SYSTEM_CONFIG_NAME}/
```

The `SYSTEM_CONFIG_NAME` follows the convention: `{ENV}-{REGION}-{SYSTEM}-{SID}`
Example: `DEV-WEEU-SAP01-X00`

## Required Information

Before creating a workspace, gather:

| Information | Example | Required |
|-------------|---------|----------|
| System config name | `DEV-WEEU-SAP01-X00` | Yes |
| SAP SID | `X00` | Yes |
| Database SID | `HDB` | Yes |
| Platform | `HANA` or `DB2` | Yes |
| DB hosts (2 for HA) | hostname, IP, VM name | Yes |
| SCS host | hostname, IP, VM name | For SCS tests |
| ERS host | hostname, IP, VM name | For SCS tests |
| Authentication type | SSHKEY or VMPASSWORD | Yes |
| SSH key or Key Vault | Key file path or secret URL | Yes |
| HA configuration | database/scs HA, cluster type | Yes |

## Templates

### sap-parameters.yaml Template

See [templates/sap-parameters.yaml.template](templates/sap-parameters.yaml.template)

**All fields:**

```yaml
# ─── Application tier ─────────────────────────────────────────
sap_sid:                       X00
scs_high_availability:         true          # boolean
scs_cluster_type:              AFA           # Fencing mechanism: AFA (Azure Fencing Agent), ISCSI, or ASD (Azure Shared Disks)
scs_instance_number:           "00"          # 2-digit string
ers_instance_number:           "01"          # 2-digit string

# ─── Database tier ────────────────────────────────────────────
db_sid:                        HDB
db_instance_number:            "00"          # 2-digit string
platform:                      HANA          # HANA, DB2
database_high_availability:    true          # boolean
database_cluster_type:         AFA           # Fencing mechanism: AFA (Azure Fencing Agent), ISCSI, or ASD (Azure Shared Disks)
database_scale_out:            false         # boolean

# ─── Storage ──────────────────────────────────────────────────
NFS_provider:                  AFS           # AFS, ANF

# ─── Key Vault (optional — for SSH credential retrieval) ──────
key_vault_id:                  /subscriptions/.../Microsoft.KeyVault/vaults/<name>
secret_id:                     https://<name>.vault.azure.net/secrets/<secret>/<id>

# ─── Managed Identity (optional) ──────────────────────────────
user_assigned_identity_client_id: "00000000-0000-0000-0000-000000000000"

# ─── ANF (optional — when NFS_provider=ANF) ───────────────────
ANF_account_rg:                "ANF-RESOURCE-GROUP"
ANF_account_name:              "ANF-ACCOUNT-NAME"

# ─── Azure Backup (optional — for AzureBackupDatabase tests) ──
backup_vault_resource_id:      "/subscriptions/.../Microsoft.RecoveryServices/vaults/<name>"
backup_container_name:         "VMAppContainer;Compute;<rg>;<vm>"
backup_item_name:              "saphanadatabase;<sid>;<db>"
backup_target_filesystem_path: "/hana/backup/restore"
backup_target_container_name:  "VMAppContainer;Compute;<rg>;<target-vm>"
backup_target_database_name:   "SYSTEMDB"
backup_restore_point_time:     ""            # ISO 8601 UTC, empty for latest
```

### hosts.yaml Template

See [templates/hosts.yaml.template](templates/hosts.yaml.template)

**Structure (6 groups):**

```yaml
{SID}_DB:                              # 2 hosts for HA
  hosts:
    {hostname}:
      ansible_host        : {IP}
      ansible_user        : azureadm
      ansible_connection  : ssh
      connection_type     : key
      virtual_host        : {virtual_hostname}
      become_user         : root
      os_type             : linux
      vm_name             : {AZURE_VM_NAME}
  vars:
    node_tier             : hana
    supported_tiers       : [hana]

{SID}_SCS:                             # 1 host
  hosts: ...
  vars:
    node_tier             : scs
    supported_tiers       : [scs]

{SID}_ERS:                             # 1 host
  vars:
    node_tier             : ers
    supported_tiers       : [ers]

{SID}_PAS:                             # 1 host
  vars:
    node_tier             : pas
    supported_tiers       : [pas]

{SID}_APP:                             # 1+ hosts
  vars:
    node_tier             : app
    supported_tiers       : [app]
```

## Creation Steps

1. Create the directory structure:
   ```bash
   mkdir -p WORKSPACES/SYSTEM/{SYSTEM_CONFIG_NAME}/{logs,quality_assurance}
   ```

2. Generate `sap-parameters.yaml` from template with user values

3. Generate `hosts.yaml` from template with user values

4. Place SSH key file in workspace (if not using Key Vault)

5. Validate with `workspace-validator`

## Output Format

After workspace creation:
```
✅ Workspace created: WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00/

Files created:
  ✅ sap-parameters.yaml (platform: HANA, HA: true)
  ✅ hosts.yaml (groups: X00_DB[2], X00_SCS[1], X00_ERS[1], X00_PAS[1], X00_APP[1])
  ✅ SSH key: ssh_key.pem
  ✅ logs/ directory created
  ✅ quality_assurance/ directory created

Next steps:
  1. Validate: python3 .github/skills/workspace-validator/scripts/validate_workspace.py WORKSPACES/SYSTEM/DEV-WEEU-SAP01-X00
  2. Run tests: ./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config]
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| Directory already exists | Re-creation attempt | Use existing or remove first |
| Invalid SID | Not 3 uppercase alphanumeric | Fix to 3 chars (e.g., `X00`) |
| Missing DB host info | Incomplete user input | Need hostname, IP, VM name for both DB nodes |
| No SSH key provided | Auth not configured | Provide key file or Key Vault details |

## Pre-Completion Checklist

Before reporting workspace creation complete:
- [ ] Directory exists under `WORKSPACES/SYSTEM/`
- [ ] `sap-parameters.yaml` has all required fields
- [ ] `hosts.yaml` has correct groups for intended test type
- [ ] All hosts have ALL fields (ansible_host, ansible_user, ansible_connection, connection_type, virtual_host, become_user, os_type, vm_name)
- [ ] SSH authentication is configured (key file, Key Vault, or password)
- [ ] `logs/` and `quality_assurance/` directories exist
- [ ] Validated with workspace-validator

## Related Skills

| After creation... | Use skill |
|-------------------|-----------|
| Validate the workspace | `workspace-validator` |
| Run tests | `test-runner` |
| Environment not set up yet | `setup-guide` |
