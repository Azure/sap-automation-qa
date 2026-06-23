# Release Documentation Sync — Headless Prompt

You are running **non-interactively in CI** to keep the public SAP automation
documentation in sync with a new release of the `sap-automation-qa` framework.

This work is driven as an explicit, staged pipeline. You are invoked as one
specialized agent per stage and exchange state through files under
`.copilot-tracking/`. The stages are:

1. **research** (task-researcher)
2. **plan** (task-planner)
3. **validate plan** (task-planner running its Plan Validator)
4. **fix plan** (task-planner)
5. **implement** (task-implementor)
6. **review** (task-reviewer)
7. **fix** (task-implementor)

Stick to your stage's role and respect the scope and conventions below
regardless of which stage you are.

## Context Inputs

The current working directory is the **docs fork** checkout
(`devanshjainms/azure-docs-pr`). The release change context has been written for
you under `.copilot-tracking/release-context/` in this working directory:

- `release-meta.txt` — base and head refs, release tag, repo, links.
- `changed-files.txt` — files changed in this release (path + change status).
- `code-diff.patch` — the full unified diff for this release.
- `commit-log.txt` — one-line commit log for the release range.
- `changelog-excerpt.md` — the relevant section of the framework `docs/CHANGELOG.md`.

The **source repository** checkout (`sap-automation-qa`) is available as an
added trusted directory so you can read the actual changed source files for
deeper context (new CLI flags, API endpoints, config parameters, HA scenarios,
roles, modules).

## Scope — STRICT

- **Only** create or edit files under `articles/sap/automation/` in this working
  directory. Do **not** modify anything outside that subtree.
- You may both **edit existing pages** and **add new pages**, following the
  existing documentation style, front matter, and formatting conventions of
  neighbouring files in `articles/sap/automation/`.
- Match Microsoft Learn conventions already present in the surrounding docs
  (YAML front matter with `title`, `description`, `ms.date`, `ms.topic`, etc.).

## What requires a documentation change

Update docs when the release introduces user-visible changes, for example:

- New **test scenarios** (new role task files under src/roles/).
- Changed **user-visible behavior**, defaults, or output formats.

Do **not** write documentation for internal-only changes: refactors, test-only
changes, CI/CD workflow changes, or dependency bumps.

## Required Outputs

1. Write a research/impact summary to
   `.copilot-tracking/release-context/impact-summary.md` containing:
   - A one-line verdict: `## Impact: DOCS_NEEDED` or `## Impact: NO_DOCS_NEEDED`.
   - The user-visible changes you analysed and the mapping to doc pages.
   - The list of doc files you created or edited (or "none").
2. If documentation changes are warranted, apply them directly to files under
   `articles/sap/automation/`.
3. If no documentation changes are warranted, make **no** file edits under
   `articles/sap/automation/` and record `NO_DOCS_NEEDED` in the summary.

Be precise and conservative: only document what the release actually changed,
cite the specific changed source files in your summary, and keep edits surgical.
