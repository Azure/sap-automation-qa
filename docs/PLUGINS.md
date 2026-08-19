# AI Assistant Plugins

The SAP Testing Automation Framework (STAF) ships as a plugin for three AI coding assistants: **GitHub Copilot CLI**, **Claude Code**, and **Gemini CLI**. Installing the plugin loads five guided skills that walk you through workspace creation, validation, HA test execution, and result analysis.

This page covers installation, verification, updates, uninstall, the skill layout, and how skills locate a trusted framework checkout. Pick the section for your assistant, copy the commands, and run them.

---

## Install with GitHub Copilot CLI

Run these two commands in your terminal:

```bash
copilot plugin marketplace add Azure/sap-automation-qa
copilot plugin install staf@sap-automation-qa
```

The first command registers the `sap-automation-qa` marketplace catalog with Copilot. The second installs the `staf` plugin from that catalog.

Copilot's older direct form (`copilot plugin install Azure/sap-automation-qa`) still works but the two-step `plugin@marketplace` form above is preferred.

## Install with Claude Code

Run these two slash commands inside a Claude Code session (not in a shell):

```text
/plugin marketplace add Azure/sap-automation-qa
/plugin install staf@sap-automation-qa
```

The first command adds the marketplace catalog. The second installs the `staf` plugin from it.

## Install with Gemini CLI

Run this command in your terminal:

```bash
gemini extensions install https://github.com/Azure/sap-automation-qa
```

Gemini clones the repository and loads it as an extension named `sap-automation-qa`.

---

## Verify the installation

After installing, confirm all five cross-agent skills loaded. The expected set is the same on every runtime:

- `setup-guide`
- `test-runner`
- `test-result-analyzer`
- `workspace-creator`
- `workspace-validator`

Use your assistant's own plugin/extension listing to check:

- **GitHub Copilot CLI:** `copilot plugin list`
- **Claude Code:** run `/plugin` inside a session — the plugin manager UI lists installed plugins and their skills
- **Gemini CLI:** run `/extensions list` inside a Gemini CLI session

You can also confirm by prompt: ask *"Set up STAF environment"* and the assistant should activate the `setup-guide` skill. Other trigger prompts are listed under [Skill layout](#skill-layout).

## Update

Each runtime manages its own plugins and extensions. Use whichever mechanism the runtime already provides — this project does not add a custom update command.

**GitHub Copilot CLI**

```bash
copilot plugin update staf@sap-automation-qa
```

**Claude Code** — run `/plugin` inside a session and use the plugin manager to update `staf`.

**Gemini CLI**

```bash
gemini extensions update sap-automation-qa
```

To update all installed extensions at once:

```bash
gemini extensions update --all
```

## Uninstall

Use your assistant's standard removal command:

- **GitHub Copilot CLI:**

  ```bash
  copilot plugin uninstall staf
  ```

- **Claude Code:** open `/plugin` inside a session and remove `staf` from the manager.
- **Gemini CLI:**

  ```bash
  gemini extensions uninstall sap-automation-qa
  ```

---

## Skill layout

STAF splits its skills into two trees by audience. Only the first tree is what the three CLIs install.

### `skills/` (repository root) — five cross-agent CLI skills

These are the skills loaded by Copilot CLI, Claude Code, and Gemini CLI. All three runtimes load exactly this same set:

- **`setup-guide`** — environment setup, local install, Docker deployment, `vars.yaml`. Triggered by prompts like *"Set up STAF environment"*.
- **`workspace-creator`** — create a new workspace, onboard a new SAP system. Triggered by *"Create a workspace for my new SAP system"*.
- **`workspace-validator`** — validate an existing workspace, troubleshoot config issues. Triggered by *"Validate my workspace DEV-WEEU-SAP01-X00"*.
- **`test-runner`** — run HA tests, configuration checks, backup tests. Triggered by *"Run HA config test on my system"*.
- **`test-result-analyzer`** — analyze test logs and reports, find root causes. Triggered by *"Why did my test fail?"*.

### `.github/skills/code-review/` — server-side Copilot review bot only

This skill is read directly from the repository by the **server-side GitHub Copilot code-review bot** when it reviews pull requests. It is **not** part of the plugin, and none of the three CLIs (Copilot CLI, Claude Code, Gemini CLI) load it.

`.github/skills/_validation/validate_skills.py` also lives in this tree; it is the skill-conformance validator, not a skill.

### How each runtime discovers the root skills

Each runtime discovers the root `skills/` tree through its own manifest, which is why all three CLIs end up with the same five skills:

- **Copilot CLI** — `.github/plugin/plugin.json` (`"skills": ["skills/"]`) and `.github/plugin/marketplace.json` (plugin `source: "."`).
- **Claude Code** — `.claude-plugin/marketplace.json` (plugin `source: "./"`) and `.claude-plugin/plugin.json`; Claude auto-scans the plugin root's `skills/` directory.
- **Gemini CLI** — `gemini-extension.json` at the repo root; Gemini auto-loads the root `skills/` directory.

All skills are plain directories with real `SKILL.md` files — no symlinks — so they load correctly on Windows, macOS, and Linux, and inside every runtime's install cache.

## Framework checkout and setup handoff

Every STAF skill operates from within a **trusted STAF checkout** — a working tree you have verified out-of-band as either the official upstream (`https://github.com/Azure/sap-automation-qa.git`) or a fork of it, at a specific revision, with the framework marker `./scripts/sap_automation_qa.sh` present. You must have verified both the source (upstream URL or fork URL) and the revision through a trusted out-of-band channel. Skills never auto-clone, auto-adopt, or auto-execute against an unverified tree.

The `setup-guide` skill is the single owner of the setup workflow. It walks you through verifying an existing checkout or manually running the `git clone` and `cd` steps to produce a new one. The other four skills (`test-runner`, `test-result-analyzer`, `workspace-creator`, `workspace-validator`) hand off to `setup-guide` when the trusted-checkout state is not confirmed; they do not carry their own setup logic.

## Provide your workspace

Once the skills are installed and the checkout is trusted, place your workspace configuration alongside the framework:

```text
WORKSPACES/SYSTEM/<SYSTEM_CONFIG_NAME>/
├── sap-parameters.yaml      # SAP system parameters
├── hosts.yaml               # Ansible inventory
└── ssh_key.ppk              # SSH private key (or configure Azure Key Vault)
```

Then interact with the framework in natural language — for example, *"Validate my workspace DEV-WEEU-SAP01-X00"* or *"Run HA config test on my system"*.

## Names, identifiers, and versions

Two small details are worth knowing when reading logs or filing issues.

### Identifiers differ by runtime — on purpose

- The **plugin** installed into Copilot CLI and Claude Code is named `staf`.
- The **marketplace catalog** for both is named `sap-automation-qa`.
- The **Gemini extension** is named `sap-automation-qa`. Gemini derives the extension's directory name from the Git repository name on install and requires `gemini-extension.json`'s `name` to match it, so it cannot be `staf`.

### Plugin-package version vs. product version

STAF tracks two version identifiers that are separately governed:

- The **plugin package version** — the `version` field in the five plugin/extension manifests (`.github/plugin/plugin.json`, `.github/plugin/marketplace.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `gemini-extension.json`). It advances whenever the installed skill payload changes, so existing installs can detect the update.
- The **STAF product release version** — the repo-root `VERSION` file and the matching `docs/CHANGELOG.md` stanza.

For the current release both counters happen to be `1.1.4`, because this release ships product changes to the skills alongside the plugin packaging. That alignment is not a rule. A future packaging-only fix (for example, adjusting install-time checks or skill wording without a product release) may bump the five manifests without bumping `VERSION`, and a future product release may bump `VERSION` without changing the manifest contents. The two are permitted to diverge; check both when correlating what a given install has against a release.

## Contributing

To add or modify a **cross-agent** skill (loaded by all three CLIs):

1. Edit the definition in `skills/<name>/SKILL.md`.
2. Validate skill conformance:

   ```bash
   python3 .github/skills/_validation/validate_skills.py skills
   ```

To add or modify the **Copilot-only** code-review skill for the server-side bot:

1. Edit the definition in `.github/skills/<name>/SKILL.md`.
2. Validate skill conformance:

   ```bash
   python3 .github/skills/_validation/validate_skills.py .github/skills
   ```

CI enforces this automatically (`.github/workflows/pr-checks.yml`): the `plugin-install` job derives the expected skill set from the `skills/` directory itself and asserts that all three runtimes load exactly that set. It separately asserts every skill under `.github/skills/` ships as a real (non-symlink) `SKILL.md` so the server-side bot can read it. A newly added skill is covered with no workflow edit.
