#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Validate SAP Testing Automation Framework workspace configurations.
"""

from __future__ import annotations
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

VALID_PLATFORMS = {"HANA", "DB2"}
VALID_NFS_PROVIDERS = {"AFS", "ANF"}
VALID_CLUSTER_TYPES = {"AFA", "ISCSI", "ASD"}
VALID_NODE_TIERS = {"hana", "scs", "ers", "pas", "app"}

SSH_KEY_EXTENSIONS = {"ppk", "pem", "key", "private", "rsa", "ed25519", "ecdsa", "dsa"}

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


@dataclass
class Finding:
    """A single validation finding."""

    level: str
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
    sap_params = workspace / "sap-parameters.yaml"
    if sap_params.exists():
        result.ok(cat, "sap-parameters.yaml found")
    else:
        result.error(cat, "sap-parameters.yaml not found")
        sap_params = None

    hosts_file = workspace / "hosts.yaml"
    if not hosts_file.exists():
        candidates = sorted(workspace.glob("*_hosts.yaml"), key=lambda p: p.name)
        if len(candidates) > 1:
            result.warn(
                cat,
                f"Multiple inventory files found: {[c.name for c in candidates]}. "
                f"Using {candidates[0].name}",
            )
        if candidates:
            hosts_file = candidates[0]
            result.ok(cat, f"Inventory found: {hosts_file.name}")
        else:
            result.error(cat, "hosts.yaml (or {SID}_hosts.yaml) not found")
            hosts_file = None
    else:
        result.ok(cat, "hosts.yaml found")

    return sap_params, hosts_file


def validate_sap_parameters(path: Path, result: ValidationResult) -> dict[str, Any] | None:
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

    for field_name in REQUIRED_SAP_PARAMS:
        if field_name not in data or data[field_name] is None:
            result.error(cat, f"{field_name}: missing (required)")
        else:
            result.ok(cat, f"{field_name}: {data[field_name]}")

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

    for inst_field in ("db_instance_number", "scs_instance_number", "ers_instance_number"):
        val = data.get(inst_field)
        if val is not None and not INSTANCE_NUMBER_PATTERN.match(str(val)):
            result.error(
                cat,
                f"{inst_field} '{val}' invalid (must be 2-digit string, e.g. '00')",
            )

    if data.get("database_high_availability") is True:
        ct = data.get("database_cluster_type")
        if not ct:
            result.error(
                cat,
                "database_cluster_type: missing (required when database_high_availability=true)",
            )
        elif ct not in VALID_CLUSTER_TYPES:
            result.error(cat, f"database_cluster_type '{ct}' invalid (must be AFA, ISCSI, or ASD)")

    if data.get("scs_high_availability") is True:
        ct = data.get("scs_cluster_type")
        if not ct:
            result.error(
                cat, "scs_cluster_type: missing (required when scs_high_availability=true)"
            )
        elif ct not in VALID_CLUSTER_TYPES:
            result.error(cat, f"scs_cluster_type '{ct}' invalid (must be AFA, ISCSI, or ASD)")

    if nfs == "ANF":
        if not data.get("ANF_account_rg"):
            result.warn(cat, "ANF_account_rg: missing (needed when ANF is used)")
        if not data.get("ANF_account_name"):
            result.warn(cat, "ANF_account_name: missing (needed when ANF is used)")

    return data


def validate_hosts(path: Path, sap_sid: str, result: ValidationResult) -> None:
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
                result.error(cat, f"{group_name} group: not found")
            continue

        hosts = group.get("hosts", {})
        if not hosts:
            result.error(cat, f"{group_name}: no hosts defined")
            continue

        host_count = len(hosts)
        if host_count < min_hosts:
            result.warn(
                cat,
                f"{group_name}: {host_count} host(s) found " f"({min_hosts} expected for HA)",
            )
        else:
            result.ok(cat, f"{group_name} group: {host_count} host(s) found")

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

    if sap_params and sap_params.get("secret_id"):
        result.ok(cat, "Key Vault auth configured (secret_id present)")
        if sap_params.get("key_vault_id"):
            result.ok(cat, "key_vault_id present")
        return

    key_found = False
    for fpath in workspace.iterdir():
        if not fpath.is_file():
            continue
        if "ssh_key" in fpath.name:
            result.ok(cat, f"SSH key file found ({fpath.name})")
            key_found = True
            break

    if key_found:
        return

    password_file = workspace / "password"
    if password_file.exists():
        result.ok(cat, "Password file found (VMPASSWORD auth)")
        return

    result.error(
        cat, "No SSH authentication found (need Key Vault secret_id, key file, or password file)"
    )


def validate_ssh_connectivity(
    workspace: Path,
    hosts_data: dict[str, Any] | None,
    sap_params: dict[str, Any] | None,
    result: ValidationResult,
) -> None:
    """Test SSH connectivity to hosts defined in inventory.

    :param workspace: Workspace directory path.
    :param hosts_data: Parsed hosts.yaml data.
    :param sap_params: Parsed sap-parameters.yaml data.
    :param result: Result collector.
    """
    cat = "SSH Connectivity"

    if os.environ.get("STAF_SKIP_SSH") or "--skip-ssh" in sys.argv:
        result.ok(cat, "SSH connectivity check skipped (STAF_SKIP_SSH)")
        return

    use_keyvault = sap_params and sap_params.get("secret_id")
    if use_keyvault:
        result.ok(
            cat,
            "SSH connectivity check skipped "
            "(Key Vault auth — credentials retrieved at runtime)",
        )
        return

    if not hosts_data:
        result.warn(cat, "No hosts data available for connectivity check")
        return

    key_path: Path | None = None
    for fpath in workspace.iterdir():
        if not fpath.is_file():
            continue
        if "ssh_key" in fpath.name:
            key_path = fpath
            break

    targets: list[tuple[str, str, str]] = []
    for group_data in hosts_data.values():
        if not isinstance(group_data, dict):
            continue
        for hostname, host_vars in group_data.get("hosts", {}).items():
            if not isinstance(host_vars, dict):
                continue
            ansible_host = host_vars.get("ansible_host")
            if ansible_host:
                user = host_vars.get("ansible_user", "root")
                targets.append((hostname, str(ansible_host), str(user)))

    if not targets:
        result.warn(cat, "No hosts with ansible_host found in inventory")
        return

    for hostname, ansible_host, user in targets:
        cmd = [
            "ssh",
            "-o", "ConnectTimeout=5",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes",
        ]
        if key_path:
            cmd.extend(["-i", str(key_path)])
        cmd.extend([f"{user}@{ansible_host}", "exit 0"])
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
                check=False,
            )
            if proc.returncode == 0:
                result.ok(
                    cat,
                    f"{hostname} ({ansible_host}): reachable",
                )
            else:
                result.warn(
                    cat,
                    f"{hostname} ({ansible_host}): unreachable",
                )
        except subprocess.TimeoutExpired:
            result.warn(
                cat,
                f"{hostname} ({ansible_host}): connection timed out",
            )


def validate_workspace(workspace: Path) -> ValidationResult:
    """Run full validation on a workspace directory.

    :param workspace: Path to workspace directory.
    :returns: Validation result.
    """
    result = ValidationResult(workspace_name=workspace.name)
    sap_params_path, hosts_path = validate_files(workspace, result)
    sap_params = None
    if sap_params_path:
        sap_params = validate_sap_parameters(sap_params_path, result)
    sap_sid = ""
    if sap_params:
        sap_sid = str(sap_params.get("sap_sid", ""))
    if hosts_path and sap_sid:
        validate_hosts(hosts_path, sap_sid, result)
    elif hosts_path:
        result.warn("hosts.yaml", "Cannot validate groups without sap_sid")
    validate_ssh_auth(workspace, sap_params, result)
    hosts_data = None
    if hosts_path:
        hosts_data, _ = load_yaml_file(hosts_path)
    validate_ssh_connectivity(workspace, hosts_data, sap_params, result)

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
            if "File" in current_cat:
                prefix = "📁"
            elif "yaml" in current_cat:
                prefix = "📋"
            elif "Connectivity" in current_cat:
                prefix = "🌐"
            else:
                prefix = "🔐"
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
