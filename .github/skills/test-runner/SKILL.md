---
name: test-runner
description: >
  Execute STAF tests using sap_automation_qa.sh. Supports direct Ansible execution
  and API mode. Use when asked to run tests, execute configuration checks, or start
  HA tests on SAP systems. Triggered by "run test", "execute ha test", "start test",
  "run configuration check", "test my system", or "trigger test job".
allowed-tools: shell
license: MIT
---

# Test Runner

Executes STAF tests via `./scripts/sap_automation_qa.sh`. Supports two modes: direct
Ansible execution and API-driven job management.

## Locate Framework

Before running any commands, locate the STAF framework directory:

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

> **⚠️ This skill is guidance only. Do NOT modify any source code, scripts, or framework files. Only help the user by running test commands and interpreting output.**

## When to Use

| Trigger | Action |
|---------|--------|
| `run test` / `execute ha test` | Run specific HA test cases |
| `run configuration check` | Run config validation |
| `start test` / `test my system` | Determine and run appropriate tests |
| `trigger test job` | Create API job |
| `list running tests` | Check job status via API |
| `schedule test` | Create cron schedule |

## Direct Execution Mode

Run tests directly via Ansible (no API server required).

### Syntax

```bash
./scripts/sap_automation_qa.sh --test-groups=<GROUP> [--test-cases=[case1,case2]] [FLAGS]
```

### Test Groups

| Group | Description |
|-------|-------------|
| `HA_DB_HANA` | HANA Database HA tests (15 cases) |
| `HA_SCS` | SAP Central Services HA tests (13 cases) |
| `BACKUP_DB_HANA` | Azure Backup for HANA (5 cases) |

### Flags

| Flag | Description |
|------|-------------|
| `-v` / `-vv` / `-vvv` | Verbosity level |
| `--offline` | Run offline validation (no live cluster) |
| `--extra-vars='{...}'` | Pass extra variables as JSON |

### Parameter Overrides (override vars.yaml at runtime)

| Flag | Description |
|------|-------------|
| `--test-type=TYPE` | `SAPFunctionalTests` or `ConfigurationChecks` |
| `--system-config=NAME` | System configuration name |
| `--functional-test-type=TYPE` | e.g., `DatabaseHighAvailability` |
| `--auth-type=TYPE` | `SSHKEY` or `VMPASSWORD` |
| `--workspaces-dir=DIR` | Workspaces directory (default: `WORKSPACES`) |
| `--telemetry-destination=DEST` | `azureloganalytics` or `azuredataexplorer` |
| `--identity-client-id=ID` | User-assigned managed identity client ID |

### Examples

```bash
# Run all HANA HA tests
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA

# Run specific test cases
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config,primary-node-crash]

# Run SCS tests
./scripts/sap_automation_qa.sh --test-groups=HA_SCS

# Run Azure Backup tests
./scripts/sap_automation_qa.sh --test-groups=BACKUP_DB_HANA

# Run configuration checks (via CLI flag, no vars.yaml change needed)
./scripts/sap_automation_qa.sh --test-type=ConfigurationChecks --system-config=DEV-WEEU-SAP01-X00 --auth-type=SSHKEY

# Run specific config check type
./scripts/sap_automation_qa.sh --test-type=ConfigurationChecks --system-config=DEV-WEEU-SAP01-X00 --extra-vars='{"configuration_test_type":"Database"}'

# Offline HA validation (no cluster interaction)
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config-offline] --offline

# Verbose output
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config] -vv
```

## Capturing Execution Logs

### CLI Output Capture

Create a directory for ad-hoc log captures:

```bash
mkdir -p logs/
```

Capture stdout and stderr to a timestamped file while still printing to the terminal:

```bash
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA --test-cases=[ha-config] 2>&1 | tee logs/run_$(date +%Y%m%d_%H%M%S).log
```

Redirect all output silently to a file:

```bash
./scripts/sap_automation_qa.sh --test-groups=HA_DB_HANA 2>&1 > logs/run_$(date +%Y%m%d_%H%M%S).log
```

### Automatic Framework Logs

The framework writes logs automatically during every execution:

| Log Type | Path |
|----------|------|
| Structured results (JSON lines) | `WORKSPACES/SYSTEM/{name}/logs/{invocation_id}.log` |
| Raw Ansible output | `WORKSPACES/SYSTEM/{name}/logs/execution_{timestamp}.log` |

### API Mode Logs

For API-driven runs, stream logs and events in real time:

```bash
# Tail the job log
./scripts/sap_automation_qa.sh job log --id <JOB_ID>

# Stream SSE events
./scripts/sap_automation_qa.sh job events --id <JOB_ID>
```

### Configuration Check Types

When running configuration checks, use `--test-type=ConfigurationChecks` CLI flag or set `TEST_TYPE=ConfigurationChecks` in vars.yaml. Use `--extra-vars` to select a specific check type:

| Type | Description |
|------|-------------|
| `all` | Run all configuration checks |
| `Database` | Database instance checks |
| `CentralServiceInstances` | SCS/ERS checks |
| `ApplicationInstances` | PAS/APP checks |
| `WebDispatcherInstances` | Web Dispatcher checks |
| `ObserverInstances` | Observer checks |

## API Mode

Requires the FastAPI server running (Docker or local uvicorn).

### Health Check

```bash
./scripts/sap_automation_qa.sh health
```

### Workspace Management

```bash
# List all workspaces
./scripts/sap_automation_qa.sh workspace

# Get specific workspace
./scripts/sap_automation_qa.sh workspace --id <WORKSPACE_ID>
```

### Job Management

```bash
# Create a job
./scripts/sap_automation_qa.sh job create --workspace <WS> --test-group <GROUP> [--test-ids id1,id2]

# List jobs
./scripts/sap_automation_qa.sh job list [--workspace <WS>] [--status running] [--active]

# Get job details
./scripts/sap_automation_qa.sh job get --id <JOB_ID>

# Get job log
./scripts/sap_automation_qa.sh job log --id <JOB_ID> [--tail N]

# Stream job events (SSE)
./scripts/sap_automation_qa.sh job events --id <JOB_ID>

# Cancel a job
./scripts/sap_automation_qa.sh job cancel --id <JOB_ID> [--reason "text"]
```

**API test group names:**
- `DatabaseHighAvailability` (maps to HA_DB_HANA)
- `CentralServicesHighAvailability` (maps to HA_SCS)
- `AzureBackupDatabase` (maps to BACKUP_DB_HANA)

### Schedule Management

```bash
# Create schedule
./scripts/sap_automation_qa.sh schedule create --name "Nightly HA" --cron "0 2 * * *" --workspaces WS1[,WS2]

# List schedules
./scripts/sap_automation_qa.sh schedule list

# Get schedule details
./scripts/sap_automation_qa.sh schedule get --id <SCHEDULE_ID>

# Update schedule
./scripts/sap_automation_qa.sh schedule update --id <SCHEDULE_ID> [--cron "..."] [--enabled true]

# Delete schedule
./scripts/sap_automation_qa.sh schedule delete --id <SCHEDULE_ID>

# Trigger immediately
./scripts/sap_automation_qa.sh schedule trigger --id <SCHEDULE_ID>

# View schedule job history
./scripts/sap_automation_qa.sh schedule jobs --id <SCHEDULE_ID> [--limit N]
```

## Test Catalog

Full test case reference: [references/test-catalog.md](references/test-catalog.md)

## Output Locations

| Output | Path |
|--------|------|
| Test results (JSON lines) | `WORKSPACES/SYSTEM/{name}/logs/{invocation_id}.log` |
| Ansible execution log | `WORKSPACES/SYSTEM/{name}/logs/execution_{timestamp}.log` |
| HTML report | `WORKSPACES/SYSTEM/{name}/quality_assurance/{group}_{invocation}.html` |

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `Workspace not found` | Invalid SYSTEM_CONFIG_NAME in vars.yaml | Check workspace exists |
| `SSH connection failed` | Auth or network issue | Validate SSH key, check connectivity |
| `vars.yaml not found` | Missing config | Create vars.yaml at project root or use CLI flags |
| `API not reachable` | Server not running | Start with `./scripts/setup.sh container start` |
| `Job already running` | Workspace locked | Wait for completion or cancel existing job |
| `Test case not found` | Invalid test-case name | Check test-catalog.md for valid names |

## Pre-Completion Checklist

Before reporting test execution complete:
- [ ] Correct test group and cases selected for the scenario
- [ ] vars.yaml configured with correct SYSTEM_CONFIG_NAME
- [ ] Workspace validated (sap-parameters.yaml + hosts.yaml + SSH)
- [ ] Test completed (check exit code or job status)
- [ ] Results available in logs directory

## Related Skills

| Need to... | Use skill |
|------------|-----------|
| Set up environment first | `setup-guide` |
| Create a workspace | `workspace-creator` |
| Validate workspace before running | `workspace-validator` |
| Analyze test results | `test-result-analyzer` |
