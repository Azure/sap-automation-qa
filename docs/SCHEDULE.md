# SAP QA Service

The SAP Testing Automation Framework can be deployed as a Docker container on the management server, referred to as the SAP QA Service. This service exposes a REST API for managing test execution against SAP systems on Azure, providing an alternative to running playbooks directly from the command line. The key capabilities include:

- **Scheduling** — supports cron-based automated test execution for recurring validation
- **Job execution** — allows you to trigger test suites on-demand
- **Workspace discovery** — automatically detects system configurations from the `WORKSPACES/SYSTEM/` directory


## Pre-requisites

1. Complete the environment setup (steps 1.1–1.3) and system configuration (section 2) in the [Setup Guide](./SETUP.MD). The container reads workspace files from `WORKSPACES/SYSTEM/`.
2. Complete the container setup (step 1.4.2) in the [Setup Guide: Container Setup](./SETUP.MD#142-container-setup-optional) to build and start the service.

Once the service is running, you can verify its health by executing:

```bash
./scripts/sap_automation_qa.sh health
```

You should see a response similar to:

```json
{"status":"healthy","timestamp":"...","version":"1.0.0","services":{"scheduler":true}}
```

Interactive API documentation is available at `http://localhost:8000/docs` for programmatic access.

For container lifecycle commands (start, stop, update, remove), see the [Setup Guide — Container Setup](./SETUP.MD#142-container-setup-optional).

### CLI

The same `sap_automation_qa.sh` script you use for direct playbook execution also supports service commands:

```bash
./scripts/sap_automation_qa.sh health
./scripts/sap_automation_qa.sh workspace
./scripts/sap_automation_qa.sh job <action> [OPTIONS]
./scripts/sap_automation_qa.sh schedule <action> [OPTIONS]
```

Each command includes built-in help. Pass `--help` to see all available options:

```bash
./scripts/sap_automation_qa.sh job --help
./scripts/sap_automation_qa.sh schedule --help
```

By default, the CLI connects to `http://localhost:8000`. You can override this by setting the `SAP_QA_API_URL` environment variable before running commands:

```bash
export SAP_QA_API_URL=http://my-server:8000
```

## API Reference

The API is available at `http://localhost:8000`. All resource endpoints are prefixed with `/api/v1`.

### Schedules

Schedules allow you to automate recurring test execution using standard cron expressions. When a schedule fires, the service automatically creates and runs jobs for each configured workspace.

#### Create a schedule

To create a new schedule that runs tests automatically:

```bash
./scripts/sap_automation_qa.sh schedule create \
  --name "Nightly HA DB tests" --cron "0 2 * * *" \
  --workspaces DEV-WEEU-SAP01-X00 --test-group HA_DB_HANA
```

The following table describes the available options:

| CLI Flag | Required | Description |
|----------|:--------:|-------------|
| `--name` | Yes | A human-readable name for the schedule |
| `--cron` | Yes | Standard 5-field cron expression (e.g., `"0 2 * * *"` for daily at 02:00) |
| `--workspaces` | Yes | Comma-separated workspace IDs to run tests against |
| `--timezone` | No | IANA timezone identifier (default: `UTC`) |
| `--test-group` | No | The test group to execute |
| `--description` | No | A description for the schedule |
| `--disabled` | No | Create the schedule in a disabled state (default: enabled) |

#### List schedules

To view all configured schedules:

```bash
./scripts/sap_automation_qa.sh schedule list
./scripts/sap_automation_qa.sh schedule list --enabled
```

#### Get schedule details

To retrieve the full configuration and status of a specific schedule:

```bash
./scripts/sap_automation_qa.sh schedule get --id <schedule_id>
```

#### Update a schedule

You can update any field on a schedule. Only the flags you pass will be modified:

```bash
./scripts/sap_automation_qa.sh schedule update --id <schedule_id> --cron "0 3 * * *" --disable
```

The update command accepts any combination of `--name`, `--cron`, `--workspaces`, `--test-group`, `--timezone`, `--description`, `--enable`, and `--disable`.

#### Delete a schedule

To permanently remove a schedule:

```bash
./scripts/sap_automation_qa.sh schedule delete --id <schedule_id>
```

#### Trigger a schedule immediately

If you need to run a schedule's jobs without waiting for the next cron tick, you can trigger it manually. Note that the schedule must be enabled for this to work:

```bash
./scripts/sap_automation_qa.sh schedule trigger --id <schedule_id>
```

#### Get jobs for a schedule

To view the execution history for a specific schedule:

```bash
./scripts/sap_automation_qa.sh schedule jobs --id <schedule_id> --limit 10
```

### Jobs

A job represents a single test execution run against a workspace. When you create a job, the service launches the corresponding Ansible playbook and tracks its progress through completion.

#### Create a job

To create and start a new test execution job:

```bash
./scripts/sap_automation_qa.sh job create --workspace DEV-WEEU-SAP01-X00 --test-group HA_DB_HANA
```

The following table describes the available options:

| CLI Flag | Required | Description |
|----------|:--------:|-------------|
| `--workspace` | Yes | Must match a directory under `WORKSPACES/SYSTEM/` |
| `--test-group` | Yes | One of: `CONFIG_CHECKS`, `HA_DB_HANA`, `HA_SCS`, `HA_OFFLINE` |
| `--test-ids` | No | Comma-separated test case IDs. If omitted, all tests in the group are executed |

#### List jobs

You can list jobs with various filters:

```bash
./scripts/sap_automation_qa.sh job list
./scripts/sap_automation_qa.sh job list --workspace DEV-WEEU-SAP01-X00
./scripts/sap_automation_qa.sh job list --status running
./scripts/sap_automation_qa.sh job list --active
```

#### Get job details

To check the current status and details of a specific job:

```bash
./scripts/sap_automation_qa.sh job get --id <job_id>
```

#### Get job log

To retrieve the raw Ansible output for a job. This is useful for debugging test failures or reviewing execution details:

```bash
./scripts/sap_automation_qa.sh job log --id <job_id>
./scripts/sap_automation_qa.sh job log --id <job_id> --tail 50
```

#### Get job events

To view the lifecycle events for a job (created, started, completed, failed, cancelled):

```bash
./scripts/sap_automation_qa.sh job events --id <job_id>
```

#### Cancel a job

If you need to stop a running job, you can cancel it with an optional reason:

```bash
./scripts/sap_automation_qa.sh job cancel --id <job_id> --reason "manual cancellation"
```


## Troubleshooting

### Service fails to start

If the service does not start, begin by checking the Docker container logs for error messages:

```bash
docker logs sap-qa-service --tail 100
```

You should also verify that port 8000 is not already in use by another process:

```bash
lsof -i :8000
```

### Health check returns unhealthy

If the health endpoint does not return a healthy status, you can inspect the response for details:

```bash
./scripts/sap_automation_qa.sh health
```

If `services.scheduler` shows `false` in the response, this indicates that the scheduler component failed to initialize. Check the service log for more details:

```bash
cat data/logs/service/sap-qa-service.log | tail -20
```

## Data Storage

The following table summarizes where the service stores its data:

| Resource | Storage |
|----------|---------|
| Schedules | `data/scheduler.db` (SQLite) |
| Jobs | `data/scheduler.db` (SQLite) |
| Job logs | `data/logs/jobs/` (one file per job) |
| Service log | `data/logs/service/sap-qa-service.log` |
| Workspaces | `WORKSPACES/SYSTEM/` (read-only mount) |
