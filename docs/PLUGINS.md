# AI Assistant Plugins

The SAP Testing Automation Framework (STAF) skills can be installed directly into your AI assistant. Users install skills, bring their `WORKSPACES/` directory, and use STAF through natural language.

## Installation

### GitHub Copilot CLI

```bash
copilot plugin install Azure/sap-automation-qa
```

### Claude Code

```bash
/plugin marketplace add Azure/sap-automation-qa
/plugin install staf@sap-automation-qa
```

### Gemini CLI

```bash
gemini skills install https://github.com/Azure/sap-automation-qa
```

## Quick Start

### 1. Bring Your WORKSPACES

Place your workspace directory in your project:

```
WORKSPACES/
└── SYSTEM/
    └── <SYSTEM_CONFIG_NAME>/        # e.g., DEV-WEEU-SAP01-X00
        ├── sap-parameters.yaml      # SAP system parameters
        ├── hosts.yaml               # Ansible inventory
        └── ssh_key.ppk              # SSH key (or use Key Vault)
```

### 2. Ask Your AI Assistant

The skills automatically locate the STAF framework. If not found locally, they clone it to `../sap-automation-qa`.

**Example prompts:**

```
"Set up STAF environment"
"Validate my workspace DEV-WEEU-SAP01-X00"
"Run HA config test on my system"
"Why did my test fail?"
"Create a workspace for my new SAP system"
```

### 3. No Manual Clone Required

The skills handle framework location automatically:
1. Check current directory for `./scripts/sap_automation_qa.sh`
2. Check sibling directory `../sap-automation-qa/`
3. If not found, clone: `git clone https://github.com/Azure/sap-automation-qa.git ../sap-automation-qa`

## Available Skills

| Skill | Description | Triggers |
|-------|-------------|----------|
| `setup-guide` | Environment setup (local, Docker) | "setup environment", "install staf", "container start" |
| `test-runner` | Execute HA tests, config checks | "run test", "execute ha test", "start test" |
| `test-result-analyzer` | Analyze failures, find root causes | "analyze results", "why did test fail" |
| `workspace-creator` | Create workspace configurations | "create workspace", "onboard system" |
| `workspace-validator` | Validate workspace before tests | "validate workspace", "check config" |

## Supported Platforms

| Platform | Instruction File | Skills Path |
|----------|-----------------|-------------|
| GitHub Copilot | `.github/copilot-instructions.md` | `.github/skills/` (native + plugin) |
| Claude Code | `CLAUDE.md` | `.claude/skills/` (symlinks) |
| Gemini CLI | `GEMINI.md` | `.gemini/skills/` (symlinks) |

## Architecture

```
.github/
├── plugin/
│   ├── marketplace.json         ← Copilot CLI marketplace
│   └── plugin.json              ← Copilot CLI plugin manifest
├── skills/                      ← Canonical skills (single source of truth)
│   ├── setup-guide/SKILL.md
│   ├── test-runner/
│   ├── test-result-analyzer/
│   ├── workspace-creator/
│   └── workspace-validator/
└── copilot-instructions.md

.claude-plugin/
├── marketplace.json             ← Claude Code marketplace
└── plugin.json                  ← Claude Code plugin manifest

.claude/skills/*/    → symlinks to .github/skills/*  (for cloned repo users)
.gemini/skills/*/    → symlinks to .github/skills/*  (for cloned repo users)
CLAUDE.md            → symlink to .github/copilot-instructions.md
GEMINI.md            → symlink to .github/copilot-instructions.md
```

## How It Works

Each AI platform discovers skills through its own directory convention:

1. **At session start** — the AI assistant indexes skill names and descriptions
2. **When user asks a relevant question** — the matching skill's `SKILL.md` is loaded into context
3. **The AI follows the skill's guidance** — running commands, creating files, analyzing output

Skills use `allowed-tools: shell` to execute STAF commands (`./scripts/sap_automation_qa.sh`) on behalf of the user.

## Prerequisites

- **SAP system on Azure IaaS** with HA configuration
- **Management server** with network access to SAP VMs
- **Python 3.10+** and either local setup or Docker
- **SSH credentials** (key file or Azure Key Vault)
- **Managed identity** with appropriate Azure RBAC roles

See the `setup-guide` skill or `docs/SETUP.MD` for full setup instructions.

## Contributing

Skills are maintained in `.github/skills/`. To add or modify a skill:

1. Edit the canonical `SKILL.md` in `.github/skills/<name>/`
2. Symlinks in `.agents/`, `.claude/`, and `.gemini/` automatically reflect changes
3. Run the skill validation: `python3 .github/skills/_validation/validate_skills.py`
4. Test with your preferred AI assistant

### Skill Format (Agent Skills Specification)

```yaml
---
name: skill-name
description: >
  What this skill does and when to activate it.
  Triggered by "keyword1", "keyword2", or "keyword3".
allowed-tools: shell
license: MIT
---

# Skill Title

Skill instructions in Markdown...
```

See [agentskills.io](https://agentskills.io) for the full specification.
