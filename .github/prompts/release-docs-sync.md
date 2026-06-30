# Release Documentation Sync — Agent Protocol

You are running **non-interactively in CI** to keep the public SAP automation
documentation in sync with a new release of the `sap-automation-qa` framework.

---

## Input Variables

| Variable | Description |
|----------|-------------|
| `DOCS_PATH` | Target documentation subtree (e.g., `articles/sap/automation/`) |
| `CONTEXT_REL` | Path to release context artifacts (`.copilot-tracking/release-context/`) |
| `SOURCE_DIR` | Checked-out source repo at the release head ref |
| `HEAD_REF` | Release tag being documented |
| `BASE_REF` | Previous release tag (for diffing) |

## Context Inputs (provided at `CONTEXT_REL/`)

| File | Content |
|------|---------|
| `release-meta.txt` | Base/head refs, release tag, repo, compare URL |
| `changed-files.txt` | Files changed in this release (path + status) |
| `code-diff.patch` | Full unified diff for the release |
| `commit-log.txt` | One-line commit log for the release range |
| `changelog-excerpt.md` | Relevant CHANGELOG.md section |

The **source repository** checkout is available as an added trusted directory
for reading actual source files (CLI flags, API endpoints, roles, modules).

---

## Pipeline Stages

This work is driven as an explicit, staged pipeline. You are invoked as one
specialized agent per stage. Stages exchange state through files under
`.copilot-tracking/`.

| # | Stage | Agent | Output |
|---|-------|-------|--------|
| 1 | Research | task-researcher | `.copilot-tracking/research/*.md` |
| 2 | Plan | task-planner | `.copilot-tracking/plans/*.md` + `details/*.md` |
| 3 | Validate Plan | task-planner (Plan Validator) | Discrepancy Log in plan |
| 4 | Fix Plan | task-planner | Updated plan in-place |
| 4.5 | Challenge | task-challenger | `.copilot-tracking/challenges/*.md` |
| 4.6 | Address Challenges | task-planner | Updated plan in-place |
| 5 | Implement | task-implementor | Edited docs + `.copilot-tracking/changes/*.md` |
| 6 | Review | task-reviewer | `.copilot-tracking/reviews/*.md` |
| 7 | Fix | task-implementor | Updated docs |

Stick to your stage's role. Do not perform another stage's work.

---

## Stage Output Contracts

### Research (Stage 1)

Produce: `.copilot-tracking/research/YYYY-MM-DD-release-sync-research.md`

Required sections:
- `## User-Visible Changes` — table with columns: Change | Source File | Doc Impact
- `## Existing Doc Structure` — list current articles under `DOCS_PATH`
- `## Cross-References` — existing links/includes that touch affected topics
- `## Recommendation` — ONE approach: which files to edit/create, with rationale

### Plan (Stage 2)

Produce: `.copilot-tracking/plans/YYYY-MM-DD-release-sync-plan.instructions.md`

Required format: numbered task list with checkboxes. Each task must specify:
- Target file path (under `DOCS_PATH`)
- Section to edit (heading path) or "new file"
- What to add/change (1-2 sentence summary)
- Source evidence (commit hash or file:line reference)

### Challenge (Stage 4.5)

Produce: `.copilot-tracking/challenges/YYYY-MM-DD-release-sync-challenges.md`

Required sections:
- `## Structural Assumptions` — MS Learn doc patterns the plan assumes incorrectly
- `## Cross-Reference Risk` — edits that could break existing includes or links
- `## Coverage Gaps` — user-visible features the plan fails to document
- `## Over-Documentation` — internal-only changes the plan unnecessarily documents
- `## Verdict` — PASS (no blocking issues) or REWORK (must address before implement)

### Implement (Stage 5)

Produce: edited/new files under `DOCS_PATH` + tracking artifacts:
- `.copilot-tracking/changes/YYYY-MM-DD-release-sync-changes.md`
- `CONTEXT_REL/impact-summary.md` beginning with:
  - `## Impact: DOCS_NEEDED` or `## Impact: NO_DOCS_NEEDED`
  - Followed by: user-visible changes, mapping to doc pages, files created/edited

### Review (Stage 6)

Produce: `.copilot-tracking/reviews/YYYY-MM-DD-release-sync-review.md`

Required sections:
- `## Correctness` — factual accuracy of documented content vs source code
- `## Completeness` — all planned items implemented
- `## Style Compliance` — adherence to `.github/instructions/docs-quality.instructions.md`
- `## Verdict` — APPROVED or REWORK (with specific items to fix)

---

## Protocol (MUST follow)

1. **NEVER** edit files outside `DOCS_PATH` in the working directory.
2. **NEVER** create a new article when an existing article covers the topic — edit it.
3. **ALWAYS** check for existing includes/shared content before duplicating.
4. **ALWAYS** read the previous stage's output before acting.
5. If zero user-visible changes warrant docs, produce `NO_DOCS_NEEDED` and **STOP**.
6. Match Microsoft Learn conventions in neighbouring files (front matter, callouts, links).
7. Reference the `.github/instructions/docs-quality.instructions.md` for style rules.
8. Be **surgical** — only document what the release actually changed.

## Error Handling

| Condition | Action |
|-----------|--------|
| Release context files are empty/missing | Output `NO_DOCS_NEEDED`, stop |
| Existing doc has conflicting front matter | Preserve existing, note discrepancy in plan |
| Planned edit would exceed 50% of article content | Split into new article, link from original |
| Cross-reference target doesn't exist | Create a stub with `[!NOTE] This article is being written` |
| Source file referenced in plan was deleted | Skip that plan item, note in changes log |

## What Requires Documentation

Update docs when the release introduces:
- New **test scenarios** (role task files under `src/roles/`)
- New **CLI flags or parameters** (scripts, vars.yaml options)
- Changed **user-visible behavior**, defaults, or output formats
- New **supported platforms** (OS, database, cluster type)

Do **NOT** document:
- Internal refactors or code-quality changes
- Test-only changes (`tests/` directory)
- CI/CD workflow changes
- Dependency bumps without user-visible impact
