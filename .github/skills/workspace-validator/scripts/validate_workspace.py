#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Validate SAP Testing Automation Framework workspace configurations.

Checks sap-parameters.yaml, hosts.yaml, and SSH authentication readiness.

Usage:
    python3 validate_workspace.py [WORKSPACE_PATH]

If WORKSPACE_PATH is not provided, discovers and validates all workspaces
in WORKSPACES/SYSTEM/.

Exit codes:
    0 - All critical checks passed
    1 - One or more critical checks failed
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


# --- Constants ---

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

VALID_PLATFORMS = {"HANA", "DB2"}
VALID_NFS_PROVIDERS = {"AFS", "ANF"}
VALID_CLUSTER_TYPES = {"AFA", "ISCSI", "ANF"}
VALID_NODE_TIERS = {"hana", "scs", "ers", "pas", "app"}

SSH_KEY_EXTENSIONS = {
    "ppk", "pem", "key", "private", "rsa", "ed25519", "ecdsa", "dsa"
}

REQUIRED_SAP_PARAMS = [
    "sap_sid",
    "platform",
    "db_sid",
    "db_instance_number",
    "database_high_availability",
    "scs_high_availability",
    "scs_instance_number",
    "ers_instance_number",
    "NFS_provider",
]

REQUIRED_HOST_FIELDS = [
    "ansible_host",
    "ansible_user",
    "ansible_connection",
    "connection_type",
    "virtual_host",
    "become_user",
    "os_type",
    "vm_name",
]

REQUIRED_GROUP_VARS = ["node_tier", "supported_tiers"]

SID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{2}$")
INSTANCE_NUMBER_PATTERN = re.compile(r"^\d{2}$")


# --- Data classes ---


@dataclass
class Finding:
    """A single validation finding."""

    level: str  # "error", "warning", "pass"
    category: str
    message: str


@dataclass
class ValidationResult:
    """Aggregated validation results for a workspace."""

    workspace_name: str
    findings: list[Finding] = field(default_factory=list)

    def error(self, category: str, message: str) -> None:
        """Record an error."""
        self.findings.append(Finding("error", category, message))

    def warn(self, category: str, message: str) -> None:
        """Record a warning."""
        self.findings.append(Finding("warning", category, message))

    def ok(self, category: str, message: str) -> None:
        """Record a pass."""
        self.findings.append(Finding("pass", category, message))

    @property
    def errors(self) -> list[Finding]:
        """Return error findings."""
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        """Return warning findings."""
        return [f for f in self.findings if f.level == "warning"]

    @property
    def passed(self) -> bool:
        """True if no errors."""
        return len(self.errors) == 0


# --- Validation functions ---


def load_yaml_file(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Load and parse a YAML file.

    :param path: Path to YAML file.
    :returns: Tuple of (parsed dict or None, error message).
    """
    if not path.exists():
        return None, f"File not found: {path.name}"
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            return None, f"{path.name} is not a YAML mapping"
        return data, ""
    except yaml.YAMLError as exc:
        return None, f"Invalid YAML in {path.name}: {exc}"


def validate_files(workspace: Path, result: ValidationResult) -> tuple[Path | None, Path | None]:
    """Check required files exist.

    :param workspace: Workspace directory path.
    :param result: Result collector.
    :returns: Tuple of (sap_params_path, hosts_path) or None if missing.
    """
    cat = "File Checks"

    # sap-parameters.yaml
    sap_params = workspace / "sap-parameters.yaml"
    if sap_params.exists():
        result.ok(cat, "sap-parameters.yaml found")
    else:
        result.error(cat, "sap-parameters.yaml not found")
        sap_params = None

    # hosts.yaml (or {SID}_hosts.yaml)
    hosts_file = workspace / "hosts.yaml"
    if not hosts_file.exists():
        # Try SID-prefixed variant
        candidates = list(workspace.glob("*_hosts.yaml"))
        if candidates:
            hosts_file = candidates[0]
            result.ok(cat, f"Inventory found: {hosts_file.name}")
        else:
            result.error(cat, "hosts.yaml (or {SID}_hosts.yaml) not found")
            hosts_file = None
    else:
        result.ok(cat, "hosts.yaml found")

    return sap_params, hosts_file


def validate_sap_parameters(
    path: Path, result: ValidationResult
) -> dict[str, Any] | None:
    """Validate sap-parameters.yaml content.

    :param path: Path to sap-parameters.yaml.
    :param result: Result collector.
    :returns: Parsed parameters dict or None.
    """
    cat = "sap-parameters.yaml"
    data, err = load_yaml_file(path)
    if data is None:
        result.error(cat, err)
        return None

    # Check required fields
    for field_name in REQUIRED_SAP_PARAMS:
        if field_name not in data or data[field_name] is None:
            result.error(cat, f"{field_name}: missing (required)")
        else:
            result.ok(cat, f"{field_name}: {data[field_name]}")

    # Validate specific field values
    sap_sid = data.get("sap_sid", "")
    if sap_sid and not SID_PATTERN.match(str(sap_sid)):
        result.error(
            cat,
            f"sap_sid '{sap_sid}' invalid (must be 3 uppercase alphanumeric chars)",
        )

    platform = data.get("platform", "")
    if platform and platform not in VALID_PLATFORMS:
        result.error(cat, f"platform '{platform}' invalid (must be HANA or DB2)")

    nfs = data.get("NFS_provider", "")
    if nfs and nfs not in VALID_NFS_PROVIDERS:
        result.error(cat, f"NFS_provider '{nfs}' invalid (must be AFS or ANF)")

    # Validate instance numbers are 2-digit strings
    for inst_field in ("db_instance_number", "scs_instance_number", "ers_instance_number"):
        val = data.get(inst_field)
        if val is not None and not INSTANCE_NUMBER_PATTERN.match(str(val)):
            result.error(
                cat,
                f"{inst_field} '{val}' invalid (must be 2-digit string, e.g. '00')",
            )

    # Conditional: cluster types when HA is enabled
    if data.get("database_high_availability") is True:
        ct = data.get("database_cluster_type")
        if not ct:
            result.error(cat, "database_cluster_type: missing (required when database_high_availability=true)")
        elif ct not in VALID_CLUSTER_TYPES:
            result.error(cat, f"database_cluster_type '{ct}' invalid (must be AFA, ISCSI, or ANF)")

    if data.get("scs_high_availability") is True:
        ct = data.get("scs_cluster_type")
        if not ct:
            result.error(cat, "scs_cluster_type: missing (required when scs_high_availability=true)")
        elif ct not in VALID_CLUSTER_TYPES:
            result.error(cat, f"scs_cluster_type '{ct}' invalid (must be AFA, ISCSI, or ANF)")

    # Conditional: ANF fields
    if nfs == "ANF" or data.get("database_cluster_type") == "ANF" or data.get("scs_cluster_type") == "ANF":
        if not data.get("ANF_account_rg"):
            result.warn(cat, "ANF_account_rg: missing (needed when ANF is used)")
        if not data.get("ANF_account_name"):
            result.warn(cat, "ANF_account_name: missing (needed when ANF is used)")

    return data


def validate_hosts(
    path: Path, sap_sid: str, result: ValidationResult
) -> None:
    """Validate hosts.yaml inventory structure.

    :param path: Path to hosts.yaml.
    :param sap_sid: SAP SID for group name construction.
    :param result: Result collector.
    """
    cat = "hosts.yaml"
    data, err = load_yaml_file(path)
    if data is None:
        result.error(cat, err)
        return

    # Expected groups
    expected_groups = {
        f"{sap_sid}_DB": ("hana", 2),
        f"{sap_sid}_SCS": ("scs", 1),
        f"{sap_sid}_ERS": ("ers", 1),
        f"{sap_sid}_PAS": ("pas", 1),
        f"{sap_sid}_APP": ("app", 1),
    }

    for group_name, (tier, min_hosts) in expected_groups.items():
        group = data.get(group_name)
        if group is None:
            if tier in ("hana", "scs", "ers"):
                result.warn(cat, f"{group_name} group: not found")
            continue

        hosts = group.get("hosts", {})
        if not hosts:
            result.error(cat, f"{group_name}: no hosts defined")
            continue

        host_count = len(hosts)
        if group_name.endswith("_DB") and host_count < 2:
            result.warn(
                cat,
                f"{group_name}: {host_count} host(s) found (2 expected for HA)",
            )
        else:
            result.ok(cat, f"{group_name} group: {host_count} host(s) found")

        # Validate per-host fields
        for hostname, host_vars in hosts.items():
            if not isinstance(host_vars, dict):
                result.error(cat, f"{group_name}/{hostname}: not a mapping")
                continue
            for req_field in REQUIRED_HOST_FIELDS:
                if req_field not in host_vars or host_vars[req_field] is None:
                    result.error(
                        cat,
                        f"{group_name}/{hostname}: missing '{req_field}'",
                    )

        # Validate group vars
        group_vars = group.get("vars", {})
        if group_vars:
            for gv in REQUIRED_GROUP_VARS:
                if gv not in group_vars:
                    result.warn(cat, f"{group_name} vars: missing '{gv}'")
            tier_val = group_vars.get("node_tier")
            if tier_val and tier_val not in VALID_NODE_TIERS:
                result.error(
                    cat,
                    f"{group_name} vars: node_tier '{tier_val}' invalid",
                )
        else:
            result.warn(cat, f"{group_name}: no group vars defined")


def validate_ssh_auth(
    workspace: Path, sap_params: dict[str, Any] | None, result: ValidationResult
) -> None:
    """Validate SSH authentication configuration.

    :param workspace: Workspace directory path.
    :param sap_params: Parsed sap-parameters.yaml data.
    :param result: Result collector.
    """
    cat = "SSH Authentication"

    # Priority 1: Key Vault
    if sap_params and sap_params.get("secret_id"):
        result.ok(cat, "Key Vault auth configured (secret_id present)")
        if sap_params.get("key_vault_id"):
            result.ok(cat, "key_vault_id present")
        return

    # Priority 2: Local SSH key files
    key_found = False
    for fpath in workspace.iterdir():
        if not fpath.is_file():
            continue
        suffix = fpath.suffix.lstrip(".")
        name = fpath.name
        if suffix in SSH_KEY_EXTENSIONS or name == "ssh_key" or "ssh_key" in name:
            result.ok(cat, f"SSH key file found ({fpath.name})")
            key_found = True
            break

    if key_found:
        return

    # Priority 3: Password file
    password_file = workspace / "password"
    if password_file.exists():
        result.ok(cat, "Password file found (VMPASSWORD auth)")
        return

    result.error(cat, "No SSH authentication found (need Key Vault secret_id, key file, or password file)")


def validate_workspace(workspace: Path) -> ValidationResult:
    """Run full validation on a workspace directory.

    :param workspace: Path to workspace directory.
    :returns: Validation result.
    """
    result = ValidationResult(workspace_name=workspace.name)

    # Step 1: File checks
    sap_params_path, hosts_path = validate_files(workspace, result)

    # Step 2: sap-parameters.yaml
    sap_params = None
    if sap_params_path:
        sap_params = validate_sap_parameters(sap_params_path, result)

    # Step 3: hosts.yaml
    sap_sid = ""
    if sap_params:
        sap_sid = str(sap_params.get("sap_sid", ""))
    if hosts_path and sap_sid:
        validate_hosts(hosts_path, sap_sid, result)
    elif hosts_path:
        result.warn("hosts.yaml", "Cannot validate groups without sap_sid")

    # Step 4: SSH authentication
    validate_ssh_auth(workspace, sap_params, result)

    return result


def print_result(result: ValidationResult) -> None:
    """Print formatted validation result.

    :param result: Validation result to display.
    """
    icons = {"error": FAIL, "warning": WARN, "pass": PASS}
    separator = "═" * 64

    print(f"\n{separator}")
    print(f"  Workspace Validation: {result.workspace_name}")
    print(f"{separator}\n")

    current_cat = None
    for finding in result.findings:
        if finding.category != current_cat:
            current_cat = finding.category
            prefix = "📁" if "File" in current_cat else "📋" if "yaml" in current_cat else "🔐"
            print(f"{prefix} {current_cat}")
        icon = icons[finding.level]
        print(f"  {icon} {finding.message}")

    print(f"\n{'─' * 64}")
    err_count = len(result.errors)
    warn_count = len(result.warnings)
    if result.passed:
        print(f"  Result: {PASS} PASSED ({warn_count} warning(s))")
    else:
        print(f"  Result: {FAIL} FAILED ({err_count} error(s), {warn_count} warning(s))")
    print(f"{'─' * 64}\n")


def discover_workspaces(base_dir: Path) -> list[Path]:
    """Discover workspace directories under WORKSPACES/SYSTEM/.

    :param base_dir: Project root or WORKSPACES directory.
    :returns: List of workspace paths.
    """
    system_dir = base_dir / "WORKSPACES" / "SYSTEM"
    if not system_dir.exists():
        # Maybe base_dir is already WORKSPACES/SYSTEM
        if base_dir.name == "SYSTEM" and base_dir.is_dir():
            system_dir = base_dir
        elif (base_dir / "SYSTEM").is_dir():
            system_dir = base_dir / "SYSTEM"
        else:
            return []

    workspaces = []
    for entry in sorted(system_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            workspaces.append(entry)
    return workspaces


def main() -> int:
    """Entry point for workspace validation.

    :returns: Exit code (0=pass, 1=fail).
    """
    if len(sys.argv) > 1:
        workspace_path = Path(sys.argv[1])
        if not workspace_path.is_dir():
            print(f"{FAIL} Not a directory: {workspace_path}")
            return 1
        workspaces = [workspace_path]
    else:
        # Discover from current directory or project root
        cwd = Path.cwd()
        workspaces = discover_workspaces(cwd)
        if not workspaces:
            print(f"{FAIL} No workspaces found under WORKSPACES/SYSTEM/")
            print("  Provide a workspace path as argument or run from project root.")
            return 1

    all_passed = True
    for ws in workspaces:
        result = validate_workspace(ws)
        print_result(result)
        if not result.passed:
            all_passed = False

    if len(workspaces) > 1:
        print(f"\n{'═' * 64}")
        print(f"  Total: {len(workspaces)} workspace(s) validated")
        if all_passed:
            print(f"  {PASS} ALL PASSED")
        else:
            print(f"  {FAIL} SOME FAILED")
        print(f"{'═' * 64}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
