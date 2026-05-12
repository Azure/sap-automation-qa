# SAP Testing Automation Framework - Copilot Instructions

> **Version**: 1.0.2 | **License**: MIT (Microsoft Corporation)
> **Repository**: [Azure/sap-automation-qa](https://github.com/Azure/sap-automation-qa)

## Project Identity

This is the **SAP Testing Automation Framework** -- an open-source orchestration tool
for validating SAP deployments on Microsoft Azure. It provides:

- **HA functional testing** for SAP HANA (Scale-Up, Scale-Out HSR, Scale-Out Standby)
  and SAP Central Services (ENSA1/ENSA2) in Pacemaker clusters.
- **Configuration validation** for HANA, IBM Db2, SCS, and application instances.
- **Offline validation** of HA configurations without live cluster interaction.
- A **FastAPI scheduling service** with async job execution, cron-based scheduling,
  workspace management, and event streaming.
- **Multi-destination telemetry** to Azure Log Analytics and Azure Data Explorer (Kusto).
- A **CLI entrypoint** (`sap_automation_qa.sh`) for both direct Ansible execution
  and API-driven workflows.

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Language** | Python 3.10+ (Docker uses 3.12) |
| **API** | FastAPI, uvicorn, Pydantic v2 |
| **Automation** | Ansible-core 2.17, ansible-runner 2.4, Jinja2 |
| **Azure** | azure-identity, azure-keyvault-secrets, azure-kusto-data/ingest, azure-mgmt-compute/network/loganalytics, azure-storage-blob/queue |
| **Scheduling** | APScheduler (CronTrigger) |
| **Persistence** | SQLite (WAL mode), file-based log/artifact storage |
| **Frontend** | React (port 3000, in development) |
| **Testing** | pytest, pytest-asyncio (auto mode), pytest-cov, pytest-mock, httpx |
| **Code quality** | black (line-length 100), pylint (>=9.0 score, sphinx docstrings), ansible-lint |
| **CI/CD** | GitHub Actions (code coverage, ansible-lint, Docker build, CodeQL, Trivy, OSSF Scorecard) |
| **Container** | Azure Linux 3.12 base, multi-stage Docker build, non-root user |
| **Target OS** | SUSE (crm commands) and RHEL (pcs commands) -- OS-family dispatched |

---

## Project Structure

```
src/
├── api/                    # FastAPI application (routes, middleware, lifespan)
│   ├── app.py              # Entry point: lifespan wires stores, worker, scheduler
│   └── routes/             # health, jobs, schedules, workspaces
├── core/                   # Framework core (no Ansible dependency)
│   ├── execution/          # AnsibleExecutor, JobWorker, SshCredentialProvider
│   ├── models/             # Job, Schedule, SshCredential, TelemetryConfig, Workspace
│   ├── observability/      # StructuredLogger, ObservabilityMiddleware, telemetry handlers
│   ├── services/           # SchedulerService (async background cron loop)
│   └── storage/            # JobStore, ScheduleStore (SQLite WAL)
├── agents/                 # Agent architecture scaffold (not yet implemented)
├── module_utils/           # Shared Python utilities for Ansible modules
│   ├── sap_automation_qa.py  # ABC base for all modules
│   ├── collector.py          # CommandCollector, AzureDataParser (with command sanitization)
│   ├── filesystem_collector.py  # FileSystemCollector (findmnt, df, LVM, ANF, AFS, IMDS)
│   ├── commands.py           # OS-family command constants, DANGEROUS_COMMANDS blocklist
│   ├── enums.py              # TestStatus, TestSeverity, HanaTopology, HanaSRProvider
│   ├── get_cluster_status.py # BaseClusterStatusChecker (template method pattern)
│   ├── get_pcmk_properties.py  # BaseHAClusterValidator (CIB XML validation)
│   └── filter_tests.py      # TestFilter (test group/case selection, extra-vars generation)
├── modules/                # Custom Ansible modules (AnsibleModule pattern)
│   ├── configuration_check_module.py  # Parallel config checks via ThreadPoolExecutor
│   ├── get_cluster_status_db.py       # HANA cluster status (scale-up + scale-out HSR)
│   ├── get_cluster_status_scs.py      # SCS cluster status
│   ├── get_pcmk_properties_db.py      # DB pacemaker CIB validation
│   ├── get_pcmk_properties_scs.py     # SCS pacemaker CIB validation
│   ├── get_azure_lb.py               # Azure Load Balancer validation (MSI auth)
│   ├── send_telemetry_data.py         # ADX/Log Analytics telemetry sender (batch)
│   ├── log_parser.py                  # /var/log/messages parser with time-range filtering
│   ├── render_html_report.py          # Jinja2 HTML report generation
│   ├── check_indexserver.py           # HANA indexserver config check
│   ├── get_package_list.py            # SAP cluster package facts
│   ├── filesystem_freeze.py           # ANF filesystem freeze/unfreeze
│   └── location_constraints.py        # Pacemaker constraint removal
├── roles/                  # Ansible roles (task YAML files)
│   ├── ha_db_hana/tasks/   # 15 HANA HA scenarios
│   ├── ha_scs/tasks/       # 14 SCS HA scenarios
│   ├── configuration_checks/  # Config validation tasks + vars
│   └── misc/tasks/         # 13 shared tasks (pre/post validation, telemetry, cluster report)
├── playbook_00_*.yml       # Top-level playbooks (config checks, DB HA, SCS HA)
├── playbook_01_*.yml       # Offline HA tests
├── templates/              # Jinja2 templates, Azure pipeline template
└── vars/                   # Framework configuration (input-api.yaml)

tests/                      # pytest test suite (85% coverage enforced)
├── api/                    # FastAPI endpoint tests (httpx AsyncClient)
├── core/                   # Execution, models, storage, observability tests
├── modules/                # All 13 Ansible module tests
├── module_utils/           # Utility class tests
└── roles/                  # Role integration tests (RolesTestingBase + ansible_runner)

scripts/                    # Shell CLI and setup scripts
├── sap_automation_qa.sh    # Main CLI: API subcommands + direct Ansible execution
├── api_utils.sh            # REST API CLI wrapper (CRUD, formatting)
├── setup.sh                # Python venv, pip, Azure CLI installation
├── container_setup.sh      # Docker/compose management
├── utils.sh                # Colored logging, distro detection, package install
└── version_check.sh        # GitHub version check with semver comparison

deploy/                     # Docker deployment
├── Dockerfile              # Multi-stage (Azure Linux 3.12, non-root, healthcheck)
└── docker-compose.yml      # Single service, SQLite volume, WORKSPACES bind mount

client/                     # React frontend (in development, port 3000)
WORKSPACES/                 # System-specific configuration and credentials
docs/                       # Architecture, HA guides, setup, telemetry, changelog
```

---

## HA Test Scenarios

### HANA Database HA (`ha_db_hana`)

| Scenario | Task File |
|----------|-----------|
| HA configuration validation (online/offline) | `ha-config.yml`, `ha-config-offline.yml` |
| Azure Load Balancer validation | `azure-lb.yml` |
| Resource migration | `resource-migration.yml` |
| Primary node crash / kill | `primary-node-crash.yml`, `primary-node-kill.yml` |
| Primary indexserver crash / echo-b | `primary-crash-index.yml`, `primary-echo-b.yml` |
| Secondary node kill / indexserver crash / echo-b | `secondary-node-kill.yml`, `secondary-crash-index.yml`, `secondary-echo-b.yml` |
| Network / HANA-shared isolation | `block-network.yml`, `block-hana-shared.yml` |
| Filesystem freeze (ANF) | `fs-freeze.yml` |
| SBD fencing | `sbd-fencing.yml` |

### SAP Central Services HA (`ha_scs`)

| Scenario | Task File |
|----------|-----------|
| HA configuration validation (online/offline) | `ha-config.yml`, `ha-config-offline.yml` |
| Azure Load Balancer / SAP control validation | `azure-lb.yml`, `sapcontrol-config.yml` |
| ASCS migration / node crash | `ascs-migration.yml`, `ascs-node-crash.yml` |
| Kill message/enqueue/replication server | `kill-message-server.yml`, `kill-enqueue-server.yml`, `kill-enqueue-replication.yml` |
| Kill SAPStartSrv process | `kill-sapstartsrv-process.yml` |
| Manual restart / failover to node | `manual-restart.yml`, `ha-failover-to-node.yml` |
| Network isolation | `block-network.yml` |

### HANA Topologies Supported

- **Scale-Up** -- classic two-node HSR (default)
- **Scale-Out HSR** -- multi-node with system replication
- **Scale-Out Standby** -- multi-node with standby nodes

### HANA SR Providers

- **SAPHanaSR** -- classic provider
- **SAPHanaSR-angi** -- next-generation provider (different resource ID discovery)

---

## Key Design Patterns

Follow these established patterns when contributing:

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Protocol (structural typing)** | `ExecutorProtocol` for dependency inversion | `core/execution/executor.py` |
| **ABC + Template Method** | `SapAutomationQA`, `BaseClusterStatusChecker.run()` with abstract hooks | `module_utils/` |
| **State Machine** | `Job` model with explicit transitions (`start()`, `complete()`, `fail()`, `cancel()`) | `core/models/job.py` |
| **Repository** | `JobStore`, `ScheduleStore` -- SQLite-backed, clean interface | `core/storage/` |
| **Factory + Singleton** | `LoggerFactory.get_logger()`, `ObservabilityContextManager` | `core/observability/` |
| **Context Manager (scoped)** | `ObservabilityScope`, `ExecutionScope` -- auto context push/pop | `core/observability/context.py` |
| **ContextVar (async-safe)** | `ContextVarProvider` for thread-safe context propagation + correlation IDs | `core/observability/context.py` |
| **Strategy** | `Collector` hierarchy -- `CommandCollector`, `AzureDataParser`, `FileSystemCollector` | `module_utils/collector.py` |
| **Module-level DI** | API routes wired via `set_job_store()` etc. during FastAPI lifespan | `api/routes/` |
| **Async worker + event queue** | `JobWorker` with `asyncio.create_task()` and SSE event streaming | `core/execution/worker.py` |
| **Background batching** | Telemetry handlers use threaded queues for async batch delivery | `core/observability/telemetry_handlers.py` |
| **Workspace locking** | One active job per workspace enforced in `JobWorker.submit_job()` | `core/execution/worker.py` |
| **Immutable value objects** | `ContextData`, `TelemetryConfig` -- frozen dataclasses | `core/models/`, `core/observability/` |
| **Lifespan** | FastAPI `asynccontextmanager` for service initialization/teardown | `api/app.py` |
| **OS-family dispatching** | Commands differ for SUSE (`crm`) vs RHEL (`pcs`) via filtered command maps | `module_utils/commands.py` |
| **Command sanitization** | `DANGEROUS_COMMANDS` blocklist in `CommandCollector` | `module_utils/collector.py` |

---

## API Reference (Quick)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/healthz` | Health check |
| `GET` | `/api/v1/jobs` | List jobs (filter: workspace, status, active) |
| `POST` | `/api/v1/jobs` | Create and submit a job |
| `GET` | `/api/v1/jobs/{id}` | Get job details |
| `POST` | `/api/v1/jobs/{id}/cancel` | Cancel a running job |
| `GET` | `/api/v1/jobs/{id}/events` | SSE event stream |
| `GET` | `/api/v1/jobs/{id}/log` | Plain-text Ansible log (`?tail=N`) |
| `POST` | `/api/v1/schedules` | Create cron schedule |
| `GET` | `/api/v1/schedules` | List schedules |
| `PATCH` | `/api/v1/schedules/{id}` | Update schedule |
| `DELETE` | `/api/v1/schedules/{id}` | Delete schedule |
| `POST` | `/api/v1/schedules/{id}/trigger` | Trigger schedule immediately |
| `GET` | `/api/v1/workspaces` | List available workspaces |

---

## Coding Standards

### Python

- **Formatter**: `black` with `line_length = 100`.
- **Linter**: `pylint` with minimum score 9.0; sphinx docstring convention.
- **Typing**: Strict type hints on all public signatures. Use `Protocol` for interfaces.
- **Docstrings**: Required on every public class, method, and function (params, returns, raises).
- **Max constraints**: `max-args=5`, `max-line-length=100`, `max-module-lines=1000`, `max-nested-blocks=3`.
- **Async**: Use `asyncio_mode = "auto"` in pytest; prefer native `async`/`await` over threads.
- **Imports**: Ansible modules use dual-import fallback (`from ansible.module_utils...` with `from src.module_utils...` in except).

### Ansible

- **Lint**: `ansible-lint` enforced in CI.
- **Task naming**: Every task MUST have a descriptive `name:` field.
- **Shell tasks**: Always use `set -o pipefail`, `executable: /bin/bash`, and `changed_when: false` for read-only commands.
- **Become**: Explicit `become: true` / `become_user: root` where required.
- **Error handling**: Use `block/rescue/always` patterns; set `failed_when` explicitly.
- **OS dispatching**: Use Jinja2 filters on `commands` list with `ansible_os_family | upper`.

### Testing

- **Coverage**: 85% minimum enforced (`--cov-fail-under=85`).
- **API tests**: Use `httpx.AsyncClient` with FastAPI test client pattern.
- **Core tests**: Use `tmp_path`, mock `subprocess.Popen`, test state machines.
- **Module tests**: Mock `AnsibleModule`; test command execution, XML parsing, edge cases.
- **Role tests**: Extend `RolesTestingBase`; use `ansible_runner` with file-based mock data.
- **Fixtures**: Shared via `conftest.py`; avoid test-to-test coupling.

### Shell Scripts

- **Style**: Consistent function naming (`_prefixed` for internal), colored logging helpers.
- **Safety**: Check tool availability (`command -v`), validate inputs, provide clear error messages.

---

## Enterprise-Grade Defaults (mandatory)

All code must meet these non-negotiable standards:

### Production Readiness

- Safe defaults, clear failure modes, strict typing, deterministic behavior.
- Typed exception hierarchy (`ExecutionError`, `WorkspaceLockError`, `JobNotFoundError`, etc.).
- Pydantic models for API boundaries; frozen dataclasses for internal value objects.

### Observability

- Structured logging via `StructuredLogger` -- JSON for production, color-coded console for dev.
- Correlation IDs (`X-Correlation-ID`) propagated through all layers via `ContextVar`.
- Event-based logging: `ServiceEvent` and `ExecutionEvent` with automatic context population.
- RotatingFileHandler (10 MB, 5 backups) for persistent log storage.
- Multi-destination telemetry: Azure Log Analytics (shared key or MSI) + Azure Data Explorer (Kusto).

### Resilience

- Timeouts on subprocess calls (`execute_command_subprocess` with configurable timeout).
- Workspace locking (one active job per workspace; prevents concurrent execution).
- Crash recovery on worker startup (detects and marks orphaned running jobs).
- Graceful job cancellation via subprocess signal handling.
- SSH credential provisioning with auto-detect (Key Vault MSI or local workspace files).

### Security

- Least privilege: non-root Docker user (`appuser:1000`).
- No plaintext secrets: Azure Key Vault integration for SSH credentials.
- Input validation: Pydantic models, command sanitization (`DANGEROUS_COMMANDS` blocklist).
- CORS configuration via environment variable (`CORS_ORIGINS`).
- Hardened CI: `step-security/harden-runner`, pinned action SHAs, Trivy scanning, OSSF Scorecard.

### Performance

- SQLite WAL mode for concurrent read/write.
- Indexed queries on `workspace_id`, `status`, `schedule_id`, `created_at`.
- Threaded background batching for telemetry delivery.
- `ThreadPoolExecutor` for parallel configuration checks.
- Async job execution with `asyncio.create_task()`.

---

## Object-Oriented Design Principles

Apply these consistently in all contributions:

- Favor well-named classes with **Single Responsibility**; keep modules under 1000 lines.
- Use **dependency inversion**: define interfaces via `Protocol` or ABC; inject collaborators.
- Encapsulate external systems (Azure, OS, Ansible runner) behind **ports/adapters**.
- Model states and workflows as **explicit types** (`JobStatus` enum, `Job` state machine).
- Avoid "stringly typed" protocols -- use enums (`TestStatus`, `HanaTopology`, `AuthType`).
- Provide seams for testing via interfaces and small, mockable collaborators.
- Prefer **composition over inheritance**; use ABCs only for true "is-a" hierarchies.

---

## Coding Partnership Rules

Follow these at all times:

1. **Be critical, not agreeable**
   - Flag missing context, risky designs, and incorrect SAP/Azure assumptions.
   - Provide counterpoints and alternatives -- especially for cluster behavior edge cases.

2. **Apply best design principles**
   - SOLID, DRY, KISS, clear separation of concerns.
   - Maintainability > cleverness. Small units > god-objects.
   - Production SAP constraints: reliability, observability, rollback capability, operability.

3. **Cover edge cases thoroughly**
   - Empty/invalid inputs, boundary conditions, transient Azure failures.
   - Cluster-specific: partial outages, quorum loss, fencing misconfiguration, split-brain,
     storage throttling, DNS/MI/IMDS hiccups, SAPHanaSR vs SAPHanaSR-angi differences.

4. **Output style**
   - Concise, minimal yet complete. Black-formatted, pylint-clean, <=100-char lines.
   - Include types, docstrings, explicit exceptions. Show tests when relevant.
   - Ansible tasks: proper `name`, `become`, `changed_when`, `failed_when`, `block/rescue`.

5. **Collaboration stance**
   - Act as a Principal software reviewer. Push back on weak requests or ambiguous scope.
   - Offer 2-3 viable designs when trade-offs exist, with crisp pros/cons.
   - When modifying HA test scenarios, consider both SUSE and RHEL code paths.

---

## File-Specific Guidance

| When editing... | Remember to... |
|----------------|----------------|
| `src/api/routes/*.py` | Use dependency injection via module-level setters; return Pydantic models; document endpoints |
| `src/core/models/*.py` | Validate state transitions; use frozen dataclasses for value objects; include `is_terminal` helpers |
| `src/core/execution/worker.py` | Respect workspace locking; handle crash recovery; propagate events via `AsyncGenerator` |
| `src/core/observability/*.py` | Maintain correlation ID propagation; use `StructuredLogger` not `print`/raw `logging` |
| `src/module_utils/*.py` | Extend ABCs properly; keep command constants OS-family-aware; sanitize inputs |
| `src/modules/*.py` | Follow `AnsibleModule` + `DOCUMENTATION` string pattern; return standardized result dicts |
| `src/roles/*/tasks/*.yml` | Use `block/rescue/always`; include `test-case-setup.yml`; post telemetry; handle both OS families |
| `tests/` | Maintain 85% coverage; use `conftest.py` fixtures; mock external deps; test failure paths |
| `scripts/*.sh` | Use `_prefixed` internal functions; validate tool availability; provide colored output |
| `deploy/` | Keep non-root; pin base images; test healthcheck; preserve volume mounts |

---

## CI/CD Pipeline

| Workflow | Trigger | Checks |
|----------|---------|--------|
| Code Coverage | push, PR | pytest `--cov-fail-under=85`, pylint `--fail-under=9`, black `--check` |
| Ansible Lint | push, PR | `ansible-lint src/` |
| Docker Build | push (main/dev), PR | Multi-stage build; optional ACR push via OIDC |
| CodeQL | push, PR, weekly | JavaScript + Python security analysis |
| Trivy | PR, merge_group | Filesystem vulnerability scanning |
| Dependency Review | PR | Dependency vulnerability review |
| OSSF Scorecard | push, PR, weekly | Supply-chain security scoring |

---

## Common Workflows

### Running tests locally

```bash
source .venv/bin/activate
pytest tests/ --cov=src --cov-fail-under=85 -v
```

### Starting the full stack (API + React)

```bash
# Backend: uvicorn on port 8000
PYTHONPATH=src uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# Frontend: React on port 3000
cd client && npm start
```

### Running a direct Ansible test

```bash
./scripts/sap_automation_qa.sh --test_groups DatabaseHighAvailability --test_cases ha-config
```

### Docker deployment

```bash
cd deploy && docker compose up -d
```

---

## Copilot CLI Skills

This repo includes skills in `.github/skills/` that provide guided workflows.
Skills activate automatically based on prompt context, or can be invoked directly
with the `/` prefix (e.g., `/test-runner`).

| Skill | When to Use |
|-------|-------------|
| `/setup-guide` | Setup, installation, Docker deployment, `vars.yaml` configuration |
| `/workspace-validator` | Validate workspace config, troubleshoot workspace issues |
| `/workspace-creator` | Create new workspace, onboard SAP system |
| `/test-runner` | Run tests, execute configuration checks, start HA tests |
| `/test-result-analyzer` | Analyze test failures, interpret results, find root causes |
