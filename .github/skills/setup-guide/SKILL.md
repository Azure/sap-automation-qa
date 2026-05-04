---
name: setup-guide
description: >
  Guide for setting up the SAP Testing Automation Framework environment.
  Use when asked about installation, setup, Docker deployment, or Copilot integration.
  Triggered by "setup environment", "install staf", "how to get started", "container start",
  "setup.sh", "configure vars.yaml", "setup help", or "docker deployment".
---

# SAP Testing Automation Framework (STAF) Setup Guide

This skill guides you through setting up the STAF environment. Choose local development or Docker.

## When to Use

| Trigger | Action |
|---------|--------|
| `setup environment` / `install staf` | Full local setup |
| `container start` / `docker deployment` | Docker compose deployment |
| `configure vars.yaml` | Framework configuration |
| `setup help` / `troubleshoot setup` | Diagnose setup issues |

## Prerequisites

- **Python 3.10+** (3.12 recommended for Docker)
- **Docker** (for container deployments only)
- **Git** (cloned repository)
- **Azure prerequisites**: See `docs/SETUP.MD` for MSI, networking, Key Vault setup

## Local Environment Setup

### Install Prerequisites and Create Virtual Environment

```bash
./scripts/setup.sh
```

**Options:**
| Flag | Short | Description |
|------|-------|-------------|
| `--python python3.12` | `-p python3.12` | Use specific Python interpreter |
| `--upgrade` | `-u` | Recreate venv from scratch |

**Examples:**
```bash
./scripts/setup.sh --python python3.12
./scripts/setup.sh --upgrade
```

**What it does:**
- Creates Python virtual environment (`.venv/`)
- Installs pip dependencies
- Installs Azure CLI tools
- Prepares local execution environment

### Activate and Verify

```bash
source .venv/bin/activate
ansible --version
pytest tests/ --cov=src --cov-fail-under=85 -v
```

### Start API Locally

```bash
PYTHONPATH=src uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
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

| Flag | Short | Description |
|------|-------|-------------|
| `--image <URL>` | `-i <URL>` | Custom container image URL |
| `--username` | `-u` | ACR username |
| `--password` | `-p` | ACR password |

### What Runs

- **FastAPI** on `http://localhost:8000` — REST API
- **React** on `http://localhost:3000` — Web UI (in development)
- **SQLite** database with persistent volume
- Uses `deploy/docker-compose.yml`, non-root user (`appuser:1000`)

### Verify

```bash
curl http://localhost:8000/healthz
# Expected: {"status": "ok"}
```

## Configuration: vars.yaml

Create `vars.yaml` at the project root:

```yaml
# --- Required fields ---

# Test type selection
TEST_TYPE:                         SAPFunctionalTests    # or ConfigurationChecks

# Functional test type (when TEST_TYPE = SAPFunctionalTests)
SAP_FUNCTIONAL_TEST_TYPE:          DatabaseHighAvailability
# Options: DatabaseHighAvailability, CentralServicesHighAvailability, AzureBackupDatabase

# System identification
SYSTEM_CONFIG_NAME:                DEV-WEEU-SAP01-X00    # dir under WORKSPACES/SYSTEM/
WORKSPACES_DIR:                    WORKSPACES            # default

# Authentication
AUTHENTICATION_TYPE:               SSHKEY                # or VMPASSWORD

# --- Telemetry fields (all optional, null by default) ---

telemetry_data_destination:        null    # azureloganalytics or azuredataexplorer
telemetry_table_name:              null

# Azure Log Analytics (when telemetry_data_destination = azureloganalytics)
laws_shared_key:                   null
laws_workspace_id:                 null
laws_subscription_id:              null
laws_resource_group:               null
laws_workspace_name:               null

# Azure Data Explorer (when telemetry_data_destination = azuredataexplorer)
adx_database_name:                 null
adx_cluster_fqdn:                  null
adx_client_id:                     null

# Managed Identity (optional)
user_assigned_identity_client_id:  null
```

## Workspace Structure

```
WORKSPACES/
└── SYSTEM/
    └── DEV-WEEU-SAP01-X00/           # SYSTEM_CONFIG_NAME
        ├── sap-parameters.yaml        # SAP system parameters
        ├── hosts.yaml                 # Ansible inventory (or {SID}_hosts.yaml)
        ├── logs/                      # Auto-created by framework
        │   ├── {invocation_id}.log    # JSON lines - test case results
        │   └── execution_{timestamp}.log  # Raw Ansible output
        └── quality_assurance/         # Auto-created by render_html_report
            └── {test_group}_{invocation_id}.html
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
- [ ] `vars.yaml` exists at project root with valid `TEST_TYPE`
- [ ] Workspace directory exists under `WORKSPACES/SYSTEM/`

## Related Skills

| After setup completes... | Use skill |
|--------------------------|-----------|
| Create a workspace for your SAP system | `workspace-creator` |
| Validate an existing workspace | `workspace-validator` |
| Run your first test | `test-runner` |
