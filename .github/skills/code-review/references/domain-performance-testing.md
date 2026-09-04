# Domain, Performance, and Testing

Dimensions 4, 5 and 6 detail.

---

# Dimension 4 — Azure / SAP Domain Rules

This is the dimension a general-purpose reviewer cannot cover. Prefer a domain finding over a
generic one when both apply.

## Half a matrix is a defect

The framework supports matrices. A change that handles one axis value and not the other is a
defect even when it is correct for the value it handles.

| Axis | Values that must both be handled |
|---|---|
| Distribution | SUSE (`crm`, `crm_mon`) / RHEL (`pcs`, `pcs status`) |
| HANA topology | Scale-Up / Scale-Out HSR / Scale-Out with Standby |
| Cluster provider | `SAPHanaSR` / `SAPHanaSR-angi` |
| Stack | HANA DB / ASCS-ERS (SCS) |

Name the missing branch and the file that would hold it. Do not accept "handled elsewhere"
without a file path. If the diff adds a new value to one of these axes, every consumer of the
axis is in scope.

## Resource-agent and cluster parameters

Timeout, interval, monitor, and migration-threshold values are **prescribed** by SAP notes,
resource-agent documentation, or Microsoft Learn. They routinely look wrong against general
best practice and are correct anyway.

Cite the source or do not raise it. A finding of the form "this timeout looks high" with no
citation is not a finding.

## Sovereign clouds

An endpoint, suffix, ARM audience, or cloud name assumed from the public cloud is a defect for
US Gov and China deployments. Check for hardcoded `core.windows.net`,
`login.microsoftonline.com`, and management endpoints.

**Do not flag `azureusgovernmentcloud`** as the Pacemaker fencing cloud value — it is a
deliberate contract in this framework and has been raised and rejected repeatedly.

## Naming and sizing contracts

SAP SID (3 alphanumeric, first character alphabetic), instance numbers (2 digits), hostname
length limits, and VM SKU constraints are prescribed. Verify against the repository's distro
and image configuration before calling one wrong.

## Idempotency in HA operations

A test that migrates, fences, or fails over a resource must leave the cluster in a known state
whether it passed or failed. A cleanup step that only runs on success is a defect.

---

# Dimension 5 — Performance

Applies to the platform layer (API, storage, execution) and to Ansible role structure. Report
the **consequence** — added latency, a blocked event loop, N× the calls — not just the shape.

## Blocking I/O inside `async def`

The highest-value performance rule here. A synchronous call inside an `async def` FastAPI
handler blocks the event loop for **every** concurrent request, not just its own.

Flag inside any `async def` handler — **or in a synchronous helper that an `async def` handler
calls without an executor**, which is where these actually live:

- `open()`, `.read_text()`, `.read_bytes()`, `.write_text()`, `Path.iterdir()`, `os.walk`;
- `requests.*` (use an async client);
- `subprocess.run` / `check_output`;
- `time.sleep` (use `asyncio.sleep`);
- any synchronous database or SDK call.

Current instances to use as the pattern:

- `src/api/routes/jobs.py` — `async def get_job_log` calls `log_path.read_text(...)` directly
  in the handler.
- `src/api/routes/workspaces.py` — the blocking `iterdir()` and `open()` are in the
  **synchronous** helper `_load_workspaces_from_directory()` (~lines 71 and 84), which the
  async handlers `list_workspaces` (l.103) and `get_workspace` (l.114) call without an
  executor. The blocking call is one frame down from the coroutine — do not stop at the
  handler body when you look for this.

The fix is `await asyncio.to_thread(...)`, an executor, or making the handler synchronous —
state which.

## Synchronous storage on the event loop

`src/core/storage/job_store.py` and `src/core/storage/schedule_store.py` hold synchronous
`sqlite3` connections. Any storage call reached from an async handler must run off the loop.

Also check: a query inside a loop that could be one query; a connection opened per call
rather than reused; a `SELECT *` where the caller needs two columns.

## Reading a whole file to use part of it

`src/api/routes/jobs.py` reads the full log into memory and then `splitlines()` to return a
tail. Flag whole-file reads where head, tail, or streaming would do — log files grow without
bound, so this is a latency **and** a memory finding.

## Credentials and clients rebuilt per call

```python
# flag — a new credential and client per invocation
credential = DefaultAzureCredential()
client = SecretClient(vault_url=url, credential=credential)

# the correct pattern already in this repo — src/modules/azure_backup_hana.py
if self._client is None:
    self._client = RecoveryServicesBackupClient(...)
```

Credential acquisition performs network calls and token exchange. Inside a loop or a request
path it dominates the operation. Cite the cached example in the fix.

## Unbounded fan-out

`ThreadPoolExecutor(max_workers=...)` must be capped by configuration, not derived from the
size of an input the caller controls.

## Ansible cost

- A `shell`/`command` task inside `loop`/`with_items` over discovered devices or files is one
  fork per item — prefer a batch form or a single script.
- `delegate_to: localhost` combined with `loop` and `wait_for` serialises the whole play on
  the controller.
- `gather_facts` where no fact is used.
- Retry/delay polling whose worst case exceeds a couple of minutes — ask what condition would
  let it exit sooner.

---

# Dimension 6 — Testing Coverage

The question is not "is there a test" but "does the test prove anything".

## A mock assertion is not coverage

```python
# does not demonstrate behaviour — passes if run_test does nothing
assert executor.run_test.called
assert mock_post.call_count == 1
```

Require an assertion on **observable state or output**: the returned value, the persisted
record, the constructed command, the payload that was sent.

**The exception: when dispatch *is* the contract.** For an orchestrator, adapter, or retry
wrapper whose specified behaviour is "call this collaborator once, with these arguments", an
interaction assertion is the behavioural assertion. `assert_called_once_with(...)` — arguments
**and** count together — is legitimate there. What is weak is a bare `.called` or a count with
no argument check on a unit that has its own observable output. Judge by whether the unit
under test has state or a return value to assert on; if it does, an interaction assertion alone
is not enough.

This matters because `pytest --cov=src/ --cov-fail-under=85` measures **line coverage only**.
A test of the weak shape above executes the lines and asserts nothing about them, so the gate
is fully satisfiable without demonstrating correctness. The gate is a floor, not evidence.

## Negative paths

Require at least one failure-path test for every new branch or exception path added by the
diff. The existing suite is happy-path heavy. Specifically ask for:

- the exception the docstring documents, actually raised and asserted;
- the fail-closed branch of any evidence rule (dimension 1);
- the rejected-unknown branch of any default-resolution change.

## Migrations need migration tests

A test that imports the current schema and asserts it matches the current schema is
**permanently green**. A migration test must start from the **previous** schema state and
assert the upgrade path. There are none in this repository today; a persistence change should
add the first.

## Custom modules

A custom module needs a test that exercises the **module entrypoint** (argument spec,
`exit_json`/`fail_json` contract), not only its internal helpers.

## ansible-lint is style, not behaviour

A passing ansible-lint says nothing about whether role logic works. A behavioural change to a
role needs a test.

**A role-test harness exists — point contributors at it, do not claim there is none.**
`tests/roles/roles_testing_base.py` defines `RolesTestingBase`, which drives real playbook runs
through `ansible_runner.run(...)`; it is specialised by `RolesTestingBaseDB` and
`RolesTestingBaseSCS` and subclassed by the role suites under `tests/roles/ha_db_hana/` and
`tests/roles/ha_scs/`. There is no molecule setup, but that is not the same as having no
harness. Require a new or extended `RolesTestingBase` subclass for a behavioural role change; a
reviewer walkthrough is the fallback only when the change genuinely cannot be driven through
the harness, and you should say why.

Role tests that only assert against a mocked runner's canned result validate the mock, not the
tasks — call that out.

## Matrix parity in tests

A platform-matrix feature (see dimension 4) needs parametrised tests covering **each axis the
changed behaviour actually consumes or branches on**, drawn from that dimension's axes —
SUSE `crm` / RHEL `pcs`, Scale-Up / Scale-Out HSR / Scale-Out Standby, and `SAPHanaSR` /
`SAPHanaSR-angi`.

Require parity **per affected axis, not the full cross-product**. The axes are independent: an
OS command-dispatch change that behaves identically across topologies needs SUSE and RHEL
cases, not every topology × provider combination. Demanding the cross-product adds test cost
without exercising another branch. But an axis the code *does* branch on and the tests omit is
a real gap — that is why the two dimensions are reviewed together.

## Tests changed alongside behaviour

If a diff changes behaviour and changes a test's expected value in the same commit, verify the
new expectation is derived from the requirement and not from the new output. An expectation
updated to match observed output is not a test.
