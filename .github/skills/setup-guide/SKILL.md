---
name: setup-guide
description: >
  Guide for setting up the SAP Testing Automation Framework environment.
  Use when asked about installation, setup, Docker deployment, or Copilot integration.
  Triggered by "setup environment", "install staf", "how to get started", "container start",
  "setup.sh", "configure vars.yaml", "setup help", or "docker deployment".
allowed-tools: shell
license: MIT
---

# SAP Testing Automation Framework (STAF) Setup Guide

This skill guides you through setting up the STAF environment on a management server.
For full details, see `docs/SETUP.MD`.

## Locate Framework

Before running any commands, locate the STAF framework directory:

```bash
# Check current directory first
if [ -f "./scripts/sap_automation_qa.sh" ]; then
  STAF_DIR="$(pwd)"
# Check sibling directory
elif [ -f "../sap-automation-qa/scripts/sap_automation_qa.sh" ]; then
  STAF_DIR="$(cd ../sap-automation-qa && pwd)"
# Not found — clone it
else
  git clone https://github.com/Azure/sap-automation-qa.git ../sap-automation-qa
  STAF_DIR="$(cd ../sap-automation-qa && pwd)"
fi
cd "$STAF_DIR"
```

All commands below assume you are in the STAF framework directory.

## Local vs Container: When to Use Which

| Use Case | Recommended Setup | Why |
|----------|-------------------|-----|
| Run test playbooks from CLI | **Local** (`./scripts/setup.sh`) | Direct Ansible execution, no server needed |
| One-off HA or config tests | **Local** | Simpler, no Docker dependency |
| Scheduled/recurring tests | **Container** (`./scripts/setup.sh container start`) | REST API + cron scheduling + job management |

The container builds its own isolated environment — local setup is **not** required when using Docker.
Both setups read the same workspace configs from `WORKSPACES/SYSTEM/`.

> **⚠️ This skill is guidance only. Do NOT modify any source code, scripts, or framework files. Only help the user by providing instructions, running commands, and answering questions.**

## When to Use

| Trigger | Action |
|---------|--------|
| `setup environment` / `install staf` | Full local setup |
| `container start` / `docker deployment` | Docker compose deployment |
| `configure vars.yaml` | Framework configuration |
| `setup help` / `troubleshoot setup` | Diagnose setup issues |

## Prerequisites

### Infrastructure

- **SAP System on Azure IaaS** — must follow [SAP on Azure best practices](https://learn.microsoft.com/azure/sap/workloads/sap-high-availability-guide-start)
- **Management (Jump) server** — must run a [supported OS version](https://learn.microsoft.com/en-us/azure/sap/automation/testing-framework-supportability#supported-distributions-for-management-server)
- **Network connectivity** — management server must reach the SAP system VNet; if separate, [peer the VNets](https://learn.microsoft.com/azure/virtual-network/virtual-network-manage-peering?tabs=peering-portal)

### Identity & Authorization

The framework needs a managed identity to access Azure resources. Choose **one** option:

**Option 1: User-Assigned Managed Identity**
1. [Create a user-assigned managed identity](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-manage-user-assigned-managed-identities) — copy the **Client ID**
2. [Assign identity to management VM](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-to-manage-ua-identity-vm) → Settings → Identity → User assigned → +Add
3. Grant roles (recommend resource-group scope): assign from identity's Azure role assignments, or from each target resource's IAM blade → Add role assignment → Managed identity
4. Set `user_assigned_identity_client_id` in `sap-parameters.yaml` to the Client ID

**Option 2: System-Assigned Managed Identity**
1. On management VM → Settings → Identity → System assigned → Status **On** → Save
2. Grant roles using same methods as Option 1
3. Leave `user_assigned_identity_client_id` blank or `""` in `sap-parameters.yaml`

### Software

- **Python 3.10+** (3.12 recommended for Docker)
- **Docker** (for container deployments only)
- **Git** (see install commands below)

### Analytics (Optional)

See `docs/TELEMETRY_SETUP.md` for Azure Log Analytics and Azure Data Explorer integration.

## Getting Started

### Option A: Install via AI Assistant Plugin (Recommended)

Install the STAF skills plugin for your AI assistant:

| Platform | Command |
|----------|---------|
| **GitHub Copilot CLI** | `copilot plugin install Azure/sap-automation-qa` |
| **Claude Code** | `/plugin marketplace add Azure/sap-automation-qa` then `/plugin install staf@sap-automation-qa` |
| **Gemini CLI** | `gemini skills install https://github.com/Azure/sap-automation-qa` |

Once installed, bring your `WORKSPACES/` directory and interact through natural language. The skills handle locating or cloning the framework automatically.

### Option B: Manual Setup

### 1. Login to Management Server

Ensure you are logged into the management server connected to the SAP system's virtual network.

### 2. Install Git

```bash
# Debian/Ubuntu                # RHEL/CentOS               # SUSE
sudo su -                      sudo su -                    sudo su -
apt-get install git            yum install git              zypper install git
```

### 3. Fork and Clone

```bash
# First: fork https://github.com/Azure/sap-automation-qa in your browser
# Then clone YOUR fork (not the Azure repo directly):
sudo su -
git clone https://github.com/GITHUB-USERNAME/sap-automation-qa.git
cd sap-automation-qa
```

### 4. Local Setup

```bash
./scripts/setup.sh
```

**Options:**
| Flag | Short | Description |
|------|-------|-------------|
| `--python python3.12` | `-p python3.12` | Use specific Python interpreter |
| `--upgrade` | `-u` | Recreate venv from scratch |

> **Python 3.6 warning**: Some management servers ship with Python 3.6 as default (not supported).
> Check available versions and point setup to a supported one:
> ```bash
> ls /usr/bin/python3*
> ./scripts/setup.sh --python /usr/bin/python3.11
> ```

**What it does:**
- Creates Python virtual environment (`.venv/`)
- Installs pip dependencies and system packages (`python3-pip`, `sshpass`, `python3-venv`)
- Installs Azure CLI tools
- Prepares local execution environment

### 5. Activate Virtual Environment

```bash
source .venv/bin/activate
```

## Container Deployment

### Commands

| Command | Description |
|---------|-------------|
| `./scripts/setup.sh container start` | Build and start full Docker stack |
| `./scripts/setup.sh container update` | Rebuild and restart |
| `./scripts/setup.sh container stop` | Stop the service |
| `./scripts/setup.sh container remove` | Remove container, network, and volumes |

### Container Options (for ACR images)

```bash
./scripts/setup.sh container start --image <acr>.azurecr.io/sap-automation-qa:latest
```

Using `--image` requires ACR access. The script attempts `az acr login` first; if that fails, set `ACR_USERNAME` and `ACR_PASSWORD` environment variables.

### What Runs

- **FastAPI** on `http://localhost:8000` — REST API (docs at `/docs`)
- **React** on `http://localhost:3000` — Web UI (in development)
- **SQLite** database with persistent volume
- Uses `deploy/docker-compose.yml`, non-root user (`appuser:1000`)

### Verify

```bash
curl http://localhost:8000/healthz
# Expected: {"status": "ok"}
```

## Configuration: vars.yaml

Create `vars.yaml` at the project root. All values can be overridden at runtime using CLI flags (e.g., `--test-type`, `--system-config`, `--auth-type`).

```yaml
# --- Required fields ---
TEST_TYPE:                         SAPFunctionalTests    # or ConfigurationChecks
SAP_FUNCTIONAL_TEST_TYPE:          DatabaseHighAvailability
# Options: DatabaseHighAvailability, CentralServicesHighAvailability, AzureBackupDatabase

SYSTEM_CONFIG_NAME:                DEV-WEEU-SAP01-X00    # dir under WORKSPACES/SYSTEM/
AUTHENTICATION_TYPE:               SSHKEY                # or VMPASSWORD

# --- Telemetry fields (all optional) ---
telemetry_data_destination:        null    # azureloganalytics or azuredataexplorer
telemetry_table_name:              null
service_log_table_name:            null    # default: <telemetry_table_name>_ServiceLogs

# Azure Log Analytics
laws_shared_key:                   null    # if omitted, auto-fetched via params below
laws_workspace_id:                 null
laws_subscription_id:              null
laws_resource_group:               null
laws_workspace_name:               null

# Azure Data Explorer
adx_database_name:                 null
adx_cluster_fqdn:                  null
adx_client_id:                     null

# Managed Identity (optional)
user_assigned_identity_client_id:  null
```

## Configuration: sap-parameters.yaml

Place in `WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/sap-parameters.yaml`:

```yaml
sap_sid:                           "X00"
db_sid:                            "X00"

scs_high_availability:             true
database_high_availability:        true
database_scale_out:                false

# Cluster type: AFA (Azure Fencing Agent), ISCSI, or ASD (Azure Shared Disks)
scs_cluster_type:                  "AFA"
database_cluster_type:             "AFA"

scs_instance_number:               "00"
ers_instance_number:               "01"
db_instance_number:                "00"
platform:                          "HANA"
NFS_provider:                      "AFS"     # or "ANF" (Azure NetApp Files)

user_assigned_identity_client_id:  ""        # blank for system-assigned MSI

# Key Vault credentials (remove if using local credential files)
key_vault_id:                      /subscriptions/.../Microsoft.KeyVault/vaults/<name>
secret_id:                         https://<vault>.vault.azure.net/secrets/<secret>/<id>

# ANF-specific (when NFS_provider = ANF)
ANF_account_rg:                    "ANF-RESOURCE-GROUP"
ANF_account_name:                  "ANF-ACCOUNT-NAME"
```

## Credential Files

### Option A: Local Files

**SSH Key**: Place private key as `ssh_key.ppk` in workspace directory:
```
WORKSPACES/SYSTEM/<DIR>/ssh_key.ppk
```

**Password**: Create a password file (username comes from `hosts.yaml`):
```bash
echo "password" > WORKSPACES/SYSTEM/<DIR>/password
chmod 600 WORKSPACES/SYSTEM/<DIR>/password
```

> When using local credential files, remove `key_vault_id` and `secret_id` from `sap-parameters.yaml`.

### Option B: Azure Key Vault

Store SSH key or password as a Key Vault secret. Configure `key_vault_id` and `secret_id` in `sap-parameters.yaml`. Requirements:
- Managed identity must have **"Key Vault Secrets User"** role on the vault
- Do **NOT** create local credential files when using Key Vault

## Workspace Structure

```
WORKSPACES/
└── SYSTEM/
    └── DEV-WEEU-SAP01-X00/           # SYSTEM_CONFIG_NAME
        ├── sap-parameters.yaml        # SAP system parameters
        ├── hosts.yaml                 # Ansible inventory (or {SID}_hosts.yaml)
        ├── ssh_key.ppk / password     # Credential file (if not using Key Vault)
        ├── logs/                      # Auto-created by framework
        │   ├── {invocation_id}.log    # JSON lines - test case results
        │   └── execution_{timestamp}.log  # Raw Ansible output
        └── quality_assurance/         # Auto-created by render_html_report
            └── {test_group}_{invocation_id}.html
```

## Log Locations

### API Mode (FastAPI/uvicorn)

| Log | Location | Format |
|-----|----------|--------|
| API server logs | stdout/stderr (console) | Structured JSON (production) or color-coded (dev) |
| Persistent API logs | `logs/api.log` | Rotating file (10 MB, 5 backups) |
| Job execution logs | `WORKSPACES/SYSTEM/{name}/logs/execution_{timestamp}.log` | Plain text (Ansible output) |
| Test result logs | `WORKSPACES/SYSTEM/{name}/logs/{invocation_id}.log` | JSON lines (one entry per test case) |
| HTML reports | `WORKSPACES/SYSTEM/{name}/quality_assurance/{group}_{invocation}.html` | HTML |

### Direct Execution Mode

| Log | Location | Format |
|-----|----------|--------|
| Ansible output | stdout (console) | Plain text |
| Test result logs | `WORKSPACES/SYSTEM/{name}/logs/{invocation_id}.log` | JSON lines |
| Execution log | `WORKSPACES/SYSTEM/{name}/logs/execution_{timestamp}.log` | Plain text |
| HTML reports | `WORKSPACES/SYSTEM/{name}/quality_assurance/{group}_{invocation}.html` | HTML |

### Docker Deployment

| Log | Location | Access |
|-----|----------|--------|
| Container logs | Docker stdout | `docker logs sap-automation-qa` |
| Persistent logs | `/app/logs/` (inside container) | Volume mount or `docker cp` |
| SQLite database | `/app/data/staf.db` (inside container) | Persistent volume |

### Accessing Logs

```bash
# API mode — view recent job log
./scripts/sap_automation_qa.sh job log --id <JOB_ID> --tail 50

# Docker — follow container logs
docker logs -f sap-automation-qa

# Direct mode — capture output to file
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA 2>&1 | tee run.log
```

## Output Format

### Setup Status Report
```
- Mode: Local / Docker
- Python: ✅ 3.12.x / ❌ Not found
- Virtual env: ✅ Active / ❌ Missing
- Azure CLI: ✅ Installed / ⚠️ Not found
- Docker: ✅ Running / ❌ Not available
- API Health: ✅ Responding / ❌ Not reachable
- Next step: [specific action]
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `python3: command not found` | Python not installed | Install Python 3.10+ for your distro |
| `venv creation failed` | Missing venv module | `apt install python3.x-venv` or use `-p` flag |
| `docker: command not found` | Docker not installed | Install Docker |
| `Cannot connect to Docker daemon` | Daemon not running | `sudo systemctl start docker` |
| `Port 8000 already in use` | Port conflict | Stop conflicting process or change port |
| `pip install failed` | Network or pip issue | Check internet, `pip install --upgrade pip` |

## Pre-Completion Checklist

Before reporting setup complete, verify:
- [ ] Setup mode completed without errors
- [ ] For local: `.venv/bin/activate` works and `ansible --version` succeeds
- [ ] For Docker: `curl http://localhost:8000/healthz` returns `{"status": "ok"}`
- [ ] `vars.yaml` exists at project root with valid `TEST_TYPE` and `AUTHENTICATION_TYPE`
- [ ] Workspace directory exists under `WORKSPACES/SYSTEM/` with `sap-parameters.yaml` and `hosts.yaml`
- [ ] Credential file present (local) or Key Vault configured (remote)
- [ ] Managed identity configured and roles assigned

## Copilot CLI Skills

| Skill | What It Does |
|-------|-------------|
| `/setup-guide` | Guides through environment setup (local, Docker) |
| `/workspace-validator` | Validates workspace `sap-parameters.yaml` and `hosts.yaml` |
| `/workspace-creator` | Creates new workspace configurations from templates |
| `/test-runner` | Executes tests via `sap_automation_qa.sh` (direct and API modes) |
| `/test-result-analyzer` | Analyzes test results, matches known failure patterns |


## Related Skills

| After setup completes... | Use skill |
|--------------------------|-----------|
| Create a workspace for your SAP system | `workspace-creator` |
| Validate an existing workspace | `workspace-validator` |
| Run your first test | `test-runner` |
