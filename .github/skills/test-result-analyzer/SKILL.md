---
name: test-result-analyzer
description: >
  Analyze STAF test results and identify root causes. Use when asked about test failures,
  what went wrong, or to interpret test output. Triggered by "analyze results",
  "why did test fail", "test output", "check test status", "read test log",
  "interpret report", or "what happened in test".
allowed-tools: shell
license: MIT
---

# Test Result Analyzer

Analyzes STAF test results from log files, HTML reports, and API job output. Identifies
root causes by classifying failures against known patterns.

## Locate Framework

Before reading logs, locate the STAF framework directory:

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

> **⚠️ This skill is guidance only. Do NOT modify any source code, scripts, or framework files. Only help the user by reading logs, running diagnostic commands, and reporting findings.**

## When to Use

| Trigger | Action |
|---------|--------|
| `analyze results` / `why did test fail` | Root cause analysis |
| `test output` / `read test log` | Parse and interpret logs |
| `check test status` | Review job/test status |
| `interpret report` | Read HTML report |
| `what happened in test` | Timeline reconstruction |

## Result File Locations

### Direct Execution Mode

| File | Path | Format |
|------|------|--------|
| Test results | `WORKSPACES/SYSTEM/{name}/logs/{invocation_id}.log` | JSON lines |
| Execution log | `WORKSPACES/SYSTEM/{name}/logs/execution_{timestamp}.log` | Plain text (Ansible) |
| HTML report | `WORKSPACES/SYSTEM/{name}/quality_assurance/{group}_{invocation}.html` | HTML |

### API Mode

| Source | Command |
|--------|---------|
| Job status | `./scripts/sap_automation_qa.sh job get --id <JOB_ID>` |
| Job log | `./scripts/sap_automation_qa.sh job log --id <JOB_ID> [--tail N]` |
| Job events | `./scripts/sap_automation_qa.sh job events --id <JOB_ID>` |
| List active | `./scripts/sap_automation_qa.sh job list --active` |

## Log File Formats

### JSON Lines Log ({invocation_id}.log)

Each line is a JSON object representing one test case result:

```json
{
  "test_case_name": "ha-config",
  "test_case_id": "ha-config",
  "test_group_name": "DatabaseHighAvailability",
  "test_group_invocation_id": "abc123-def456",
  "status": "PASSED",
  "severity": "CRITICAL",
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T10:05:30Z",
  "duration_seconds": 330,
  "message": "All checks passed",
  "details": {}
}
```

**Status values:** `PASSED`, `FAILED`, `SKIPPED`, `ERROR`
**Severity values:** `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`

### Execution Log (execution_{timestamp}.log)

Raw Ansible output containing:
- Task names and results (`ok`, `changed`, `failed`, `skipped`, `unreachable`)
- Error messages and stack traces
- SSH connection issues
- Command output from remote hosts
- `PLAY RECAP` summary at the end

## Analysis Workflow

### Step 1: Locate Results

```bash
# Direct mode — find latest logs
ls -lt WORKSPACES/SYSTEM/{name}/logs/ | head -5

# API mode — find latest job
./scripts/sap_automation_qa.sh job list --active
```

### Step 2: Parse for Failures

```bash
# Find failed test cases in JSON log
grep '"status": "FAILED"' WORKSPACES/SYSTEM/{name}/logs/{invocation_id}.log

# Find failures in execution log
grep -E "fatal:|FAILED!|UNREACHABLE" WORKSPACES/SYSTEM/{name}/logs/execution_*.log
```

### Step 3: Match Against Known Patterns

Consult [references/known-failures.md](references/known-failures.md) for:
- Exact string matches against log patterns
- Error code matches (exit codes)
- Component matches (pacemaker, sapcontrol, HANA)

> **If no match found**: Report the raw error. Do NOT fabricate root causes.
> Say "Unknown failure pattern — manual investigation needed."

### Step 4: Present Structured Report

Use the Output Format below.

## Parsing Ansible Logs

### Key Patterns (in severity order)

| Pattern | Meaning |
|---------|---------|
| `fatal: [host]: FAILED! => {...}` | Task failed on host |
| `UNREACHABLE! => {...}` | Cannot connect (SSH/network) |
| `NO MORE HOSTS LEFT` | All hosts unreachable, playbook aborted |
| `rescued:` | Failure handled by rescue block |
| `...ignoring` | Failed but `ignore_errors: true` |
| `PLAY RECAP` | Overall summary per host |

### Play Recap Analysis

```
PLAY RECAP ***************
host1 : ok=45 changed=3 unreachable=0 failed=0 skipped=12 rescued=0 ignored=0
host2 : ok=43 changed=2 unreachable=0 failed=1 skipped=14 rescued=0 ignored=0
```

- `failed > 0` → test failed
- `unreachable > 0` → connectivity issue
- `rescued > 0` → errors caught by block/rescue
- `ignored > 0` → non-critical failures suppressed

## Output Format

### Test Result Analysis

```
## Test Result Analysis: {workspace_name}

**Invocation:** {invocation_id}
**Test Group:** {group_name}
**Duration:** {total_duration}
**Overall:** X/Y passed, Z failed

### Failed Tests

#### 1. {test_case_name} (FAILED)
- **Severity:** CRITICAL
- **Duration:** 5m 30s
- **Root Cause:** [classification]
- **Error:** [exact error from log]
- **Fix:** [recommended action]
- **Confidence:** Known pattern / Likely match / Unknown

### Passed Tests
- ha-config: PASSED (2m 15s)
- azure-lb: PASSED (1m 30s)

### PLAY RECAP
{paste PLAY RECAP}

### Prioritized Fix Plan
1. Critical: {fix this first}
2. Important: {fix this next}

### Re-Run Command
./scripts/sap_automation_qa.sh --test-groups={group} --test-cases=[{failed-tests}]
```

## Failure Classification

| Category | Pattern | Common Causes |
|----------|---------|---------------|
| SSH/Connection | `Connection refused`, `timeout` | Network, key mismatch, host down |
| Cluster | `resource not found`, `CIB error` | Cluster not configured, node offline |
| SAP | `HDB info failed`, `sapcontrol error` | SAP not running, wrong SID/instance |
| Azure | `MSI auth failed`, `subscription error` | Identity issues, permissions |
| Configuration | `parameter missing`, `invalid value` | Workspace misconfiguration |
| Timeout | `exceeded timeout`, `no response` | Slow recovery, resource contention |
| Fencing | `fence agent failed`, `SBD error` | Fencing misconfiguration |

See [references/known-failures.md](references/known-failures.md) for detailed patterns.

## Advanced Analysis

### Cascading Failures

Identify the root failure (earliest in chain):
- SSH fails → All tasks on that host UNREACHABLE
- Cluster constraint not cleared → Migration fails → Failover tests fail
- HANA not running → All HANA-specific checks fail

### Intermittent Failures

Patterns suggesting transient issues:
- "Timeout waiting for resource" (retry may succeed)
- "Connection reset by peer" (network hiccup)
- "Resource is starting" (timing issue)

### Log Noise (Safe to Ignore)

- `[DEPRECATION WARNING]:` — informational
- `[WARNING]: Platform ... discovered Python interpreter` — safe
- `skipping: [host]` — expected conditionals
- `ok: [host]` with `changed=false` — idempotent checks

## Historical Comparison

Compare current results against previous runs to detect regressions or intermittent failures.

### Compare Two Invocations

```bash
# List recent invocations
ls -lt WORKSPACES/SYSTEM/{name}/logs/*.log | head -10

# Diff two JSON-lines logs (compare test statuses)
diff <(grep -o '"test_case_name": "[^"]*", "status": "[^"]*"' {old_invocation}.log | sort) \
     <(grep -o '"test_case_name": "[^"]*", "status": "[^"]*"' {new_invocation}.log | sort)
```

### Regression Detection Patterns

| Pattern | Meaning |
|---------|---------|
| Test was PASSED, now FAILED | Regression — investigate recent changes |
| Test was FAILED, now PASSED | Fix confirmed — or intermittent issue |
| Test was SKIPPED, now FAILED | New test coverage — expected first-time failure |
| Duration increased >50% | Performance regression — check resource contention |

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| No log files found | Test not yet run | Check path, run test first |
| Empty log file | Test crashed | Check execution log for errors |
| JSON parse error | Corrupted log | Use execution log instead |
| No HTML report | Report not triggered | Check if test completed normally |
| Unknown failure pattern | Not in known-failures.md | Report raw error, flag as Unknown |

## Pre-Completion Checklist

Before reporting analysis complete:
- [ ] ALL failed tests analyzed (not just first failure)
- [ ] Each failure has exact error text from log (not paraphrased)
- [ ] Root causes matched from known-failures.md or flagged Unknown
- [ ] Remediation steps are specific and actionable
- [ ] Re-run command provided for failed tests
- [ ] PLAY RECAP included in report

## Related Skills

| Need to... | Use skill |
|------------|-----------|
| Re-run failed tests | `test-runner` |
| Fix workspace config issues | `workspace-validator` |
| Understand test cases | `test-runner` skill, see its test-catalog.md |
| Set up environment | `setup-guide` |
