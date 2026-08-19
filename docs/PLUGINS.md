# AI Assistant Plugins

The SAP Testing Automation Framework provides agent skills for **GitHub Copilot CLI**, **Claude Code**, and **Gemini CLI**. These skills enable AI-assisted test execution, workspace management, and result analysis for SAP deployments on Azure.

## Installation

Install the STAF skills plugin using the command for your AI assistant:

| Platform | Command |
|----------|---------|
| **GitHub Copilot CLI** | `copilot plugin marketplace add Azure/sap-automation-qa` then `copilot plugin install staf@sap-automation-qa` |
| **Claude Code** | `/plugin marketplace add Azure/sap-automation-qa` then `/plugin install staf@sap-automation-qa` |
| **Gemini CLI** | `gemini extensions install https://github.com/Azure/sap-automation-qa` |

> **Note on names.** The identifiers differ per runtime, and this is intentional:
> - The **plugin** installed into Copilot and Claude Code is named `staf`.
> - The **marketplace** catalog (Copilot and Claude Code) is named `sap-automation-qa`.
> - The **Gemini extension** is named `sap-automation-qa`. Gemini derives the
>   extension directory name from the repository name on a Git install and
>   requires `gemini-extension.json`'s `name` to match it, so it cannot be `staf`.
>
> Copilot's older direct form (`copilot plugin install Azure/sap-automation-qa`)
> still works but is deprecated in favour of the two-step `plugin@marketplace`
> form shown above.

## Usage

Once the skills are installed, bring your `WORKSPACES/` directory and interact with the framework through natural language prompts.

### Step 1: Provide Your Workspace

Place your workspace configuration directory alongside the framework:

```
WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/
├── sap-parameters.yaml      # SAP system parameters
├── hosts.yaml               # Ansible inventory
└── ssh_key.ppk              # SSH private key (or configure Azure Key Vault)
```

### Step 2: Interact with the Framework

The following example prompts activate the corresponding skills:

| Prompt | Skill Activated |
|--------|----------------|
| *"Set up STAF environment"* | `setup-guide` |
| *"Validate my workspace DEV-WEEU-SAP01-X00"* | `workspace-validator` |
| *"Run HA config test on my system"* | `test-runner` |
| *"Why did my test fail?"* | `test-result-analyzer` |
| *"Create a workspace for my new SAP system"* | `workspace-creator` |

### Framework Auto-Discovery

The skills automatically locate the STAF framework in the following order:

1. Current directory (`./scripts/sap_automation_qa.sh`)
2. Sibling directory (`../sap-automation-qa/`)
3. If not found, the framework is cloned automatically: `git clone https://github.com/Azure/sap-automation-qa.git ../sap-automation-qa`

## Available Skills

| Skill | Description |
|-------|-------------|
| `setup-guide` | Guides through environment setup including local installation and Docker container deployment |
| `test-runner` | Executes HA functional tests, configuration checks, and backup tests via direct Ansible or API mode |
| `test-result-analyzer` | Analyzes test logs, classifies failures against known patterns, and surfaces root causes |
| `workspace-creator` | Generates workspace configuration files (`sap-parameters.yaml`, `hosts.yaml`) from templates |
| `workspace-validator` | Validates workspace files, field completeness, SSH authentication, and inventory structure |
| `code-review` _(bot-only)_ | Reviews a PR or diff for correctness, reliability, security, Azure/SAP domain rules, performance, test coverage, and maintainability. Read directly from `.github/skills/` by the server-side GitHub Copilot code-review bot; not loaded by any CLI (Copilot, Claude Code or Gemini) |

## Repository Structure

Every skill lives in **exactly one location** — there is no mirror and no
generator. Skills are plain directories with real `SKILL.md` files (symlinks do
**not** materialise on Windows clones or inside a tool's install cache, where
they appear as tiny text stubs that load nothing), so each skill is a real
directory that loads correctly on every platform.

The skills are split into two trees by audience:

- **`skills/` (repository root)** — the **cross-agent** skills that all three
  CLIs load: `setup-guide`, `test-runner`, `test-result-analyzer`,
  `workspace-creator`, `workspace-validator`.
- **`.github/skills/`** — **Copilot-only** skills. `code-review` lives here
  because the **server-side GitHub Copilot code-review bot** discovers review
  skills from `.github/skills/` and reads them directly from the repository. This
  skill is not a cross-agent plugin skill and is **not** loaded by any CLI
  (Copilot, Claude Code or Gemini) — only by the bot. `_validation/validate_skills.py`
  (the skill-conformance validator) also lives here; it is tooling, not a skill.

Each runtime discovers skills through its own manifest:

- **Copilot CLI** reads `.github/plugin/plugin.json`, whose `skills` field points
  at `skills/`, plus `.github/plugin/marketplace.json` (plugin `source: "."`). It
  loads exactly the cross-agent set — the same five skills as Claude and Gemini.
  It does **not** load `code-review` (that skill is consumed only by the
  server-side bot, described above).
- **Claude Code** reads `.claude-plugin/marketplace.json` (plugin `source: "./"`)
  and auto-scans `<plugin-root>/skills/` — the root tree only (no `code-review`).
- **Gemini CLI** reads `gemini-extension.json` at the repo root and auto-loads
  the root `skills/` tree only (no `code-review`).

```
skills/                              ← CROSS-AGENT skills (Copilot + Claude + Gemini)
├── setup-guide/
├── test-runner/
├── test-result-analyzer/
├── workspace-creator/
└── workspace-validator/

.github/
├── skills/                          ← COPILOT-ONLY skills + validator tooling
│   ├── code-review/                 ← read by the server-side Copilot code-review bot
│   └── _validation/validate_skills.py   ← skill-conformance validator (not a skill)
├── plugin/
│   ├── marketplace.json             ← Copilot marketplace catalog (source ".")
│   └── plugin.json                  ← Copilot manifest ("skills": ["skills/"])
└── copilot-instructions.md          ← Project instructions

gemini-extension.json                ← Gemini CLI extension manifest (repo root)
.claude-plugin/marketplace.json      ← Claude Code marketplace catalog (source "./")
.claude-plugin/plugin.json           ← Claude Code plugin manifest (default skills/ scan)
CLAUDE.md                            → symlink to .github/copilot-instructions.md
GEMINI.md                            → symlink to .github/copilot-instructions.md
```

There are **no symlinks in any skill payload** — both `skills/` and
`.github/skills/` contain real directories and real `SKILL.md` files, so they
load correctly on every platform and inside every tool's install cache.

## Contributing

To add or modify a **cross-agent** skill (loaded by all three CLIs):

1. Edit the definition in `skills/<name>/SKILL.md`.
2. Validate skill conformance: `python3 .github/skills/_validation/validate_skills.py skills`.

To add or modify a **Copilot-only** skill (e.g. a code-review skill for the
server-side bot):

1. Edit the definition in `.github/skills/<name>/SKILL.md`.
2. Validate skill conformance: `python3 .github/skills/_validation/validate_skills.py .github/skills`.

CI enforces this automatically (`.github/workflows/pr-checks.yml`): the
`plugin-install` job derives the expected skill set **from the `skills/`
directory itself** and asserts that all three runtimes load exactly that set. It
separately asserts every skill under `.github/skills/` ships as a real (non-symlink)
`SKILL.md` so the server-side bot can read it. A newly added skill is therefore
covered with no workflow edit.
