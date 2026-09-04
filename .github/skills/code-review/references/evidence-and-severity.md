# Evidence and Severity

How to decide whether a finding may be posted, and how to word it. This governs every
dimension. When this file and a dimension rule disagree, this file wins.

## Evidence tiers

Every finding carries a tier, stated **explicitly** as the `Evidence:` line of the output block
(`Evidence: Verified` or `Evidence: Probable`) — never post a Verified claim you cannot
support. Word the finding body to match the tier as well.

| Tier | You have | `Evidence:` line | How to word the body |
|---|---|---|---|
| **Verified** | Read the code path end to end, in this diff or in files you opened | `Evidence: Verified` | Direct assertion. `worker.py` builds the command from `test_type` only, so `offline` never reaches the playbook. |
| **Probable** | A strong pattern match, but one link is unread | `Evidence: Probable` | Name the unread link. This looks like X; I could not open `foo.py` to confirm the caller — can you check? |
| **Unverified** | A suspicion | — | **Do not post it.** |

## Hard prohibitions

Violating any of these is worse than missing the finding.

1. **Never invent a line number, symbol, file path, or error message.** If you cannot cite it,
   describe the location in prose instead.
2. **Never state what a tool reports without its output.** Do not write "bandit flags this",
   "pylint will fail", "ansible-lint flags this", or "CI will reject this" unless you have the
   run's actual output in front of you. Your prediction is not the tool's verdict.
3. **Never claim a sibling file is unfixed without opening it.** If you cannot open it, ask a
   question naming the file.
4. **Never assert a standard, SAP note, or vendor prescription you cannot cite.** No citation,
   no finding.
5. **Never restate a finding a CI gate already owns** — see the ownership table in the
   skill's dimension 7. Duplicating a gate is noise and it trains reviewers to ignore you.
6. **Never post a finding whose only support is that a value is unusual.** Unusual is not
   wrong.

## Known false-positive classes

These have been raised and rejected in this repository's review history. Do not raise them
again without new evidence.

| # | Class | Why it is not a finding |
|---|---|---|
| **F1** | Established default called wrong | A long-standing default is a contract. Changing it is a behaviour change; keeping it is not a defect. |
| **F2** | Convention flagged as duplication | Repetition that is correct in every sibling is the convention. See the discriminator in `correctness-and-contracts.md` §7. |
| **F3** | Sovereign-cloud fencing value | `azureusgovernmentcloud` as the Pacemaker fencing cloud is deliberate. |
| **F4** | Prescribed timeout/interval called excessive | Cluster and resource-agent values come from SAP notes and vendor docs. Cite or drop. |
| **F5** | Style already gated | Formatting the formatter owns. Never propose a formatting-only change. |
| **F6** | Predicted scanner output | See prohibition 2. |
| **F7** | Missing test for documentation or a data-only change | Scope the testing dimension to behaviour. |
| **F8** | "Consider extracting a helper" with no defect | Refactoring suggestions without a demonstrated cost are noise. |

## Severity vocabulary

Use exactly these four labels.

| Label | Meaning | Bar |
|---|---|---|
| **Blocking** | Merging causes incorrect behaviour, data loss, a leaked secret, or an outage | Verified evidence only. Name the wrong outcome. |
| **Should fix** | A real defect with bounded consequence, or a Blocking-shaped issue at Probable evidence | Consequence must be stated |
| **Question** | You need information the diff does not contain to decide | Must be answerable from the PR |
| **Nit** | Genuinely optional, no correctness or reliability consequence | Cap at two per review |

Do not use "consider", "might want to", or "it would be nice if" as a severity. They read as
Nit regardless of what follows, and they bury real findings.

## Volume control

A review with forty comments is not read. Prefer depth over breadth.

- **Cap Nits at two.** Drop the rest.
- **Collapse duplicates.** One repeated defect across N files is **one** comment listing all N
  sites, not N comments.
- **When two findings overlap, keep the one with the more concrete consequence.** A finding
  that names a wrong output beats one that names a smell.
- **If a diff has more than five Blocking findings**, lead the summary with the systemic cause
  rather than enumerating symptoms.

## Actionability

Every comment states three things:

1. **What** is wrong — the specific behaviour, not a category name.
2. **Why** it matters — the concrete wrong outcome, in this system.
3. **How** to fix it — a corrected snippet, a named alternative, an existing correct example
   from this repository, or a citation.

A comment missing (3) is not ready to post. Prefer citing an existing correct implementation
in this repository over describing one in the abstract — it proves the fix fits the codebase.

## The challenge protocol

When an author disagrees:

- **New evidence provided** → say so plainly and withdraw the finding. Do not restate it in a
  softer form.
- **No new evidence** → restate the specific consequence once, more concretely, and stop. Do
  not repeat the same argument.
- **A design decision you disagree with but which is defensible** → withdraw. Design authority
  belongs to the author and the maintainers.
- **Never** escalate severity because a finding was disputed.

## Silence is a valid review

If the diff is small, correct, and consistent, say so in one line and post nothing. Manufactured
findings on a clean diff cost more credibility than a missed nit ever will.
