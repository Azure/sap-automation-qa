# Reliability and Security

Dimensions 2 and 3 detail.

---

# Dimension 2 — Reliability / SRE

## Loops that cannot end

Every worker or poll loop needs a reachable exit — a shutdown or cancellation path, a terminal
event, or a deadline. `while True` on its own is **not** a finding; the repository's own
`src/core/execution/worker.py` uses one correctly:

```python
# correct — bounded by both a deadline and a terminal event
while True:
    try:
        event = await asyncio.wait_for(queue.get(), timeout=timeout)
        yield event
        if event.event_type in (COMPLETED, FAILED, CANCELLED):
            break
    except asyncio.TimeoutError:
        break

# the synchronous form, in src/module_utils/backup_restore.py:534
while elapsed < self._poll_timeout:
    ...
    time.sleep(self._poll_interval)
    elapsed += self._poll_interval
# the deadline is then classified, not raised — map_job_result_status()
# reports a timeout when elapsed >= poll_timeout
```

Flag a loop only when you can trace that **no** reachable path exits it — a blocking `get()`
with no timeout and no terminal-event break, a retry loop with no attempt cap. Quote the lines
that would have to exit and explain why none can. Cite the working example in the fix.

## Calls that cannot time out

| Call type | Gated? | Review action |
|---|---|---|
| `requests.*` | **Reported, not gated** — pylint runs with `--fail-under=9`, so a `missing-timeout` warning does not by itself fail CI | Still in scope. Raise it when the call is on a request path; do not assume CI blocks it |
| Azure SDK clients | **Partly** | azure-core applies default retry and transport timeouts, so "no policy" is wrong. Require explicit values only where the **effective** defaults exceed the request path's budget — and state that budget |
| `subprocess.run` | No | Require `timeout=` where the child can hang |
| Paramiko / SSH | No | Require connect and command timeouts |

`src/core/execution/ssh_provider.py` constructs `SecretClient(...).get_secret(...)` without
overriding the defaults. That is not "no timeout" — azure-core still bounds it — but the
default retry-plus-backoff ceiling can hold a worker far longer than an interactive request
path allows. The finding is only valid if you state the path's budget and show the effective
default exceeds it.

## Retries

- Bounded attempts **and** backoff, or neither is useful.
- A synchronous `time.sleep` backoff inside a request path blocks a worker for the whole
  window — say how long, using the configured values.
- Retrying a non-idempotent operation is a correctness defect, not a reliability one; raise it
  under dimension 1.

## Ownership and teardown

See `correctness-and-contracts.md` §4. The reliability angle: a leaked handle survives the
request that created it and fails a **later** unrelated request, so the defect surfaces far
from its cause. Say that in the finding — it is what makes it blocking rather than cosmetic.

## Failures that do not fail

- `set -o pipefail` before any pipeline whose exit code matters, especially `| tee`.
  Without it the exit status is `tee`'s, which is almost always `0`.
- `set -e` alone does not cover pipelines, command substitutions, or `if` conditions.
- Validate configuration **before** the first side effect. A script that provisions, then
  discovers a bad parameter, leaves a half-built system.
- One inconsistent line among N otherwise-identical blocks is a finding — that is how a
  credential once reached a log.

## Concurrency

- `ThreadPoolExecutor` worker counts must be capped, not derived from an unbounded input.
  `max_workers=min(configured, len(batch))` is the right shape **only with an empty-batch
  guard** — `max_workers=0` raises `ValueError`. Require `max(1, min(configured, len(batch)))`
  or an early return on an empty batch, and say which.
- Shared mutable state across workers needs a lock or an explicit "single writer" statement.
- A shared workspace directory used by concurrent runs needs an ownership marker.

---

# Dimension 3 — Security

## Untrusted input reaching a shell

Validate the **completed** command string, not a fragment assembled earlier — validation of a
piece says nothing about the whole.

Flag:

- `subprocess` with `shell=True` where any component is not a literal;
- a command built by string concatenation or f-string from user, inventory, or discovered
  data;
- an Ansible `shell:` task interpolating a variable that originates outside the repository;
- an Ansible `command:` task **only** where you can show the boundary actually breaks.
  `ansible.builtin.command` does **not** invoke a shell, and `argv` preserves argument
  boundaries, so an interpolated variable there is not injection by itself. Trace what
  validates the value and show how it changes argument boundaries — e.g. the value is
  interpolated mid-string so a space splits it into extra arguments — before flagging it;
- allow-list vs deny-list: a deny-list of dangerous characters is not a control. Require an
  allow-list of permitted values, or `subprocess` with an argument **list** and no shell.

Shell scripts are in scope too: `scripts/sap_automation_qa.sh:626` runs `eval $command`, with
`$command` assembled from `ansible_password=$(cat $password_file)`, `$common_extra_vars`, and
`$ANSIBLE_VERBOSE`. Treat every `eval` under `scripts/` as a live injection sink and re-derive
the sites from the diff.

Note that bandit **cannot** catch the `subprocess` cases above — B602/B603/B604 are in the
`skips` list (see "What the scanners already own"). These are yours to find.

State the concrete injecting input in the finding. "Could be injected" without an input is
Probable at best — see `evidence-and-severity.md`.

## Secrets

A secret must never reach:

- a log line, including debug and error logs;
- a captured stdout/stderr that is stored or returned;
- an exception message or traceback;
- an unmasked Ansible task result (`no_log: true` is required on tasks handling credentials);
- a telemetry payload.

When reviewing a change to an environment-filter or exclusion list, check **every** caller —
each script receives a different set of injected credentials, so each list must be checked
against its own caller. A secret added to one list and not its siblings is the exact defect
this rule exists for.

## Credentials and identity

- Prefer managed identity over a secret; flag a new secret where an identity would work.
- A credential fetched per call is both a performance and a blast-radius concern — see
  dimension 5.
- Never widen an existing authentication requirement without saying so in the PR description.

## File and path handling

- Path built from user input without normalisation → traversal. Require resolution plus a
  containment check against the intended root.
- World-readable permissions on anything holding a credential or a key.
- Temp files created without `O_EXCL` in a shared directory.

## What the scanners already own

| Gate | Where | Scope |
|---|---|---|
| `bandit -r src/ -c pyproject.toml --severity-level medium` | `.github/workflows/pr-checks.yml` | Medium and High only, **minus** `skips = ["B101","B314","B506","B602","B603","B604","B608"]` |
| `github-advanced-security` | repo scanning | CodeQL findings |

**Do not restate a finding either tool already reports.** Its output is authoritative, yours
is a prediction.

**bandit LOW is not gated,** and neither are the skipped checks. Low-severity findings — weak
randomness for non-crypto use, `assert` in shipped code, hardcoded temp paths,
`try/except/pass` — are **review territory**, as are everything in `skips`: `shell=True` and
`subprocess` (B602/B603/B604), SQL string-building (B608), `yaml.load` without a safe loader
(B506), unsafe XML (B314), and `assert` (B101). Raise them at Should-fix or below, with the
concrete consequence.

Never state what a scanner reports without its actual output.

## CI and workflow security

Workflow files under `.github/workflows/` are executable, privileged code. Review them as
such.

| Check | What to flag |
|---|---|
| Action pinning | This repo pins every `uses:` to a full commit SHA with a `# vX.Y.Z` comment (`actions/checkout@9c091bb…  # v7.0.0`). A new step pinned to a **tag or branch** is a finding — a tag is mutable. |
| Trigger | `pull_request_target` or `workflow_run` **combined with a checkout of the PR head** gives fork-authored code a token. There are none today; a new one is Blocking. |
| `permissions:` | All 9 workflow files set an explicit **top-level** block. Flag a **new workflow** with no top-level block, or a **job-level** block that *widens* what the workflow-level block grants. A job with no block inherits the workflow-level block — which is restrictive here, not GitHub's default — so an added job without one is usually correct. Evaluate the **effective** permission and name it. |
| Untrusted interpolation | `${{ github.event.pull_request.title }}`, `…head_ref`, `…body`, or any `github.event.*` field interpolated into a `run:` block is script injection. Require an intermediate `env:` variable. |
| Dependency pinning | A new `pip install` or `ansible-galaxy install` without a pinned version, or a new install from a URL, in a workflow. |
| Secret exposure | A secret echoed, written to an artifact, or exposed via `set -x` in a workflow step. |

## Privilege escalation in Ansible

There are ~253 `become` references across the roles, so **`become` on its own is not a
finding** — do not re-litigate the baseline. Flag the deltas:

- `become: true` added to a task or block that did not have it, with no stated reason;
- `become_user:` changed, especially to `root` or to an `<sid>adm` account it was not before;
- a **new** `NOPASSWD` sudoers entry, or a widened one — name the exact command allowed;
- `become` on a task that runs a command built from an interpolated variable — that combines
  Dimension 3's injection rule with root, and is Blocking;
- a `become` block that widened in scope because a task moved inside it.

## Transport and host-key verification

`ANSIBLE_HOST_KEY_CHECKING=False` is already exported in `scripts/sap_automation_qa.sh:59` and
`scripts/setup.sh:143`. That is the existing baseline — do not raise it as new.

Flag anything that **extends** the weakening:

- a **new** `ANSIBLE_HOST_KEY_CHECKING=False`, `StrictHostKeyChecking=no`, or
  `UserKnownHostsFile=/dev/null` in a script or connection path that did not have one;
- `paramiko.AutoAddPolicy()`;
- `validate_certs: false` on an Ansible module, `verify=False` on a `requests` call, or
  `curl -k` / `wget --no-check-certificate`;
- a TLS version or cipher pinned downward.

## Deserialization and outbound requests

- `yaml.load` **without** a safe loader. Note the existing call at
  `src/module_utils/sap_automation_qa.py:161` already uses `CSafeLoader`/`SafeLoader` and is
  correct — a new one that does not is a finding, and bandit will not catch it because B506
  is skipped.
- `pickle.load`, `marshal`, or `eval`/`exec` on any value that is not a literal.
- A server-side request from a FastAPI handler to a URL derived from request data, with no
  allow-list — SSRF. Name the parameter that reaches the URL.

## Secrets in logs and artifacts

Beyond the `no_log` rule above:

- a command run under `set -x` while a secret is in its argument list or environment;
- a secret written into an uploaded artifact, a test fixture, or a captured `stdout` that is
  later logged;
- a credential file created without restrictive permissions, or left behind after use;
- a new environment variable carrying a secret that is not added to the existing
  credential-exclusion list.
