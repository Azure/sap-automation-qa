# Correctness and Contracts — worked examples

Dimension 1 detail. Every example below is a defect that was found in review in this
repository, or a shape derived directly from one. Use them as the pattern to match against,
not as a list of files to re-check.

## 1. Accepted then discarded

The single most frequent real defect in this repository's review history.

**Shape.** A field is accepted at a boundary — an API request, a Pydantic model, a CLI
argument, an Ansible variable — and every layer below it either ignores it or overwrites it.
The request succeeds. The behaviour is the default. Nothing errors.

**Worked example.** An `offline` flag was added to the test-request model. It was carried by
the model, stored, and returned in the response — but the worker that built the Ansible
command never read it. A caller asking for offline validation got the destructive online
playbook. It survived five pull requests in that state.

**How to review.** For every new field, flag, or parameter in the diff, trace it forward:

```text
request schema → model → store/serialisation → worker → command construction → execution
```

Flag the **first** link that drops it. Name that layer explicitly and state the wrong
behaviour that results. "This field is unused" is not the finding; "a request with
`offline=True` still dispatches the online playbook because `worker.py` builds the command
from `test_type` alone" is.

**Do not** accept "it will be wired up in a follow-up" without a linked issue in the PR.

## 2. Evidence discarded, verdict still rendered

**Shape.** The system collects facts, throws some away, and then classifies as if it had them
all. The verdict is clean because the contradicting evidence is gone.

Sub-shapes to match:

| Sub-shape | What to look for |
|---|---|
| Truncation | `[:n]`, `head`, `\| first`, any slice applied to collected facts before classification |
| Masking union | evidence from several nodes merged with `union`/`+` where disagreement should fail closed |
| Empty as negative | `{}` or `[]` read as "not installed"/"not configured" rather than "unknown" |
| Guard-as-skip | `when: x \| length > 0`, `is defined`, `\| default([])` with no preceding `assert` |
| Name-based identity | type or role inferred from a hostname, path, or filename rather than collected proof |
| Silenced evidence task | `failed_when: false` / `ignore_errors: true` on a task whose output decides pass/fail |

**Fail-closed alternative.** Required in every comment of this class. Disagreement between
peers must produce an error or an `unknown` verdict, never the majority answer. A missing
input must fail the check, not skip it.

**Legitimate exceptions.** `failed_when: false` and `ignore_errors: true` are correct for
best-effort telemetry, cleanup, and `rescue` blocks. Say which applies when you accept one.

## 3. Contracts an object claims but does not keep

### Shallow immutability

```python
class Result(BaseModel):
    model_config = ConfigDict(frozen=True)
    details: dict[str, str]      # ← still mutable
```

`frozen=True` prevents rebinding the attribute. It does not freeze the `dict`. Any holder can
mutate `details` and every other holder sees it. Flag `frozen=True` over a mutable `dict`,
`list`, or `set` field. The fix is an immutable mapping or a defensive copy on access — state
which.

### Exception contract breaks

A method documenting `:raises ConfigurationError:` must not let a foreign exception escape.
Common escapes here: Pydantic `ValidationError`, `OSError`/`FileNotFoundError`,
`subprocess.TimeoutExpired`, `json.JSONDecodeError`.

**Note the CI gap.** `W0702` and `W0703` (bare and broad `except`) are globally disabled in
`pyproject.toml`, so CI will not catch a handler that swallows the wrong thing. This is
review territory — see dimension 7.

### Docstrings that promise cleanup

If a docstring says a method releases, closes, or removes something, verify it on every path
including the early-return and exception paths.

## 4. Ownership and teardown

**Shape.** `close()` owns several resources and returns early on the first failure, leaking
the rest.

```python
def close(self) -> None:
    self._closed = True          # ← set before cleanup succeeded
    self._job_store.close()      # ← raises, and schedule_store is never closed
    self._schedule_store.close()
```

Rules to apply:

- set the closed flag **after** successful cleanup, not before;
- close each owned resource independently — one failure must not skip the others;
- re-raise the original error after attempting the rest;
- clear `app.state` as well as module-level globals, or the next startup reuses a dead
  handle.

Flag an early `return` in a `close()`/`shutdown()`/`__aexit__` **only when you can show it is
reachable while a sibling resource is still open** — name the resource and the path. An
idempotent guard (`if self._closed: return`) or a return taken before anything was acquired is
correct; owning several resources does not by itself prove a leak.

## 5. Check-then-act and previews that mutate

- `exists()` followed by a write — the window between them is the defect. Prefer atomic
  create (`O_EXCL`, `os.replace` onto a temp file) and state which.
- A value displayed to a human and then **re-derived** before use — the human approved a
  different value than the one that executes. Pass the shown value through.
- A dry-run or preview path that touches persistent state. A preview must be a pure read.
- Concurrent runs sharing a workspace with no ownership marker or lock.

## 6. Silent default resolution

A detector may fill an **absent** value. It must **reject** a present-but-unrecognised one.

```python
# wrong — an unknown agent silently becomes the default and the verdict is clean
agent = KNOWN_AGENTS.get(detected, DEFAULT_AGENT)

# right — absent is defaulted, unrecognised is an error naming the valid set
if detected is None:
    agent = DEFAULT_AGENT
elif detected not in KNOWN_AGENTS:
    raise ConfigurationError(f"unknown agent {detected!r}; expected one of {sorted(KNOWN_AGENTS)}")
```

The comment must name the valid set. This is the same failure as §2 in a different costume:
an unknown input produces a clean verdict.

## 7. Repetition — the discriminator

The rule that decides between "you fixed one of three copies" and "that is our convention".

**Test:** is the repeated thing *correct where it appears*?

- Correct in the sibling → **contract**. Constants, defaults, naming schemes, and structural
  patterns that are the same everywhere and are doing their job. Stay silent. Examples that
  have been wrongly flagged before: `azureusgovernmentcloud` as the Pacemaker fencing cloud;
  an established workspace-name default.
- Wrong in the sibling too → **defect**, and it is **one finding across N sites**. Report it
  once and list every unfixed sibling. Do not open one comment per file.

If you cannot open the sibling, say so and phrase the finding as a question naming the file.

## 8. Persisted-schema semantics

- A new column added to a `CREATE TABLE IF NOT EXISTS` statement is **not** a migration —
  existing databases never see it.
- A stored `schema_version` must be **read and acted on**, not defaulted to the current value.
- A migration test that imports the current schema and asserts it matches the current schema
  is permanently green. See dimension 6.
