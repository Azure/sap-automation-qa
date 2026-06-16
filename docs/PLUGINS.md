# AI Assistant Plugins

The SAP Testing Automation Framework provides agent skills for **GitHub Copilot CLI**, **Claude Code**, and **Gemini CLI**. These skills enable AI-assisted test execution, workspace management, and result analysis for SAP deployments on Azure.

## Installation

Install the STAF skills plugin using the command for your AI assistant:

| Platform | Command |
|----------|---------|
| **GitHub Copilot CLI** | `copilot plugin install Azure/sap-automation-qa` |
| **Claude Code** | `/plugin marketplace add Azure/sap-automation-qa` then `/plugin install staf@sap-automation-qa` |
| **Gemini CLI** | `gemini skills install https://github.com/Azure/sap-automation-qa` |

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

## Repository Structure

Skills are maintained in `.github/skills/` as the single source of truth. Platform-specific directories use symlinks to avoid duplication.

```
.github/
├── plugin/
│   ├── marketplace.json             ← Plugin marketplace catalog
│   └── plugin.json                  ← Plugin manifest
├── skills/                          ← Canonical skill definitions
│   ├── setup-guide/
│   ├── test-runner/
│   ├── test-result-analyzer/
│   ├── workspace-creator/
│   └── workspace-validator/
└── copilot-instructions.md          ← Project instructions

.claude-plugin/marketplace.json      ← Claude Code marketplace catalog
.claude-plugin/plugin.json           ← Claude Code plugin manifest
.claude/skills/*                     → symlinks to .github/skills/*
.gemini/skills/*                     → symlinks to .github/skills/*
CLAUDE.md                            → symlink to .github/copilot-instructions.md
GEMINI.md                            → symlink to .github/copilot-instructions.md
```

## Contributing

To add or modify a skill:

1. Edit the skill definition in `.github/skills/<name>/SKILL.md`.
2. Symlinks propagate changes to all platform directories automatically.
3. Run skill validation: `python3 .github/skills/_validation/validate_skills.py`.
