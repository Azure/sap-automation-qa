#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Validate Copilot CLI skills against the Agent Skills specification.
"""

from __future__ import annotations
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install it with: pip install pyyaml")
    sys.exit(1)

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_LINES = 500
NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
CONSECUTIVE_HYPHENS = re.compile(r"--")
REFERENCE_PATTERN = re.compile(r"\((?:scripts|references|assets|templates)/[^)]+\)")
COMPATIBILITY_PATTERN = re.compile(r"^##\s+Compatibility", re.MULTILINE | re.IGNORECASE)


@dataclass
class Finding:
    """A single validation finding."""

    skill: str
    level: str
    message: str


@dataclass
class ValidationResult:
    """Aggregated validation results."""

    findings: list[Finding] = field(default_factory=list)
    skills_checked: int = 0

    def error(self, skill: str, message: str) -> None:
        """Record an error finding."""
        self.findings.append(Finding(skill, "error", message))

    def warn(self, skill: str, message: str) -> None:
        """Record a warning finding."""
        self.findings.append(Finding(skill, "warning", message))

    def ok(self, skill: str, message: str) -> None:
        """Record a passing check."""
        self.findings.append(Finding(skill, "pass", message))

    @property
    def errors(self) -> list[Finding]:
        """Return all error findings."""
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        """Return all warning findings."""
        return [f for f in self.findings if f.level == "warning"]

    @property
    def passed(self) -> bool:
        """Return True if no errors were found."""
        return len(self.errors) == 0


def parse_frontmatter(skill_md: Path) -> tuple[dict | None, str]:
    """Parse YAML frontmatter from a SKILL.md file.

    :param skill_md: Path to SKILL.md.
    :returns: Tuple of (frontmatter dict or None, error message).
    """
    text = skill_md.read_text(encoding="utf-8")
    lines = text.split("\n")

    if not lines or lines[0].strip() != "---":
        return None, "SKILL.md does not start with YAML frontmatter (---)"

    end_index = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index == -1:
        return None, "YAML frontmatter not closed (missing second ---)"

    frontmatter_text = "\n".join(lines[1:end_index])
    try:
        data = yaml.safe_load(frontmatter_text)
        if not isinstance(data, dict):
            return None, "Frontmatter is not a YAML mapping"
        return data, ""
    except yaml.YAMLError as exc:
        return None, f"Invalid YAML in frontmatter: {exc}"


def validate_name(name: str | None, dir_name: str, result: ValidationResult, skill: str) -> None:
    """Validate the 'name' frontmatter field.

    :param name: Value of the name field (or None).
    :param dir_name: Name of the skill directory.
    :param result: Validation result to append findings to.
    :param skill: Skill identifier for reporting.
    """
    if not name:
        result.error(skill, "Missing required 'name' field in frontmatter")
        return

    if name != dir_name:
        result.error(skill, f"name '{name}' does not match directory name '{dir_name}'")
        return

    has_error = False

    if len(name) > MAX_NAME_LENGTH:
        result.error(
            skill,
            f"name exceeds {MAX_NAME_LENGTH} characters ({len(name)})",
        )
        has_error = True

    if not NAME_PATTERN.match(name):
        result.error(
            skill,
            f"name '{name}' has invalid format " "(must be lowercase a-z, 0-9, hyphens only)",
        )
        has_error = True

    if CONSECUTIVE_HYPHENS.search(name):
        result.error(skill, f"name '{name}' contains consecutive hyphens")
        has_error = True

    if not has_error:
        result.ok(skill, f"name matches directory ({name})")


def validate_description(description: str | None, result: ValidationResult, skill: str) -> None:
    """Validate the 'description' frontmatter field.

    :param description: Value of the description field (or None).
    :param result: Validation result to append findings to.
    :param skill: Skill identifier for reporting.
    """
    if not description:
        result.error(skill, "Missing required 'description' field in frontmatter")
        return

    desc_len = len(description)
    if desc_len > MAX_DESCRIPTION_LENGTH:
        result.error(
            skill,
            f"description exceeds {MAX_DESCRIPTION_LENGTH} " f"characters ({desc_len})",
        )
    else:
        result.ok(skill, f"description present ({desc_len} chars)")


def validate_line_count(skill_md: Path, result: ValidationResult, skill: str) -> None:
    """Check SKILL.md line count against the recommended maximum.

    :param skill_md: Path to SKILL.md.
    :param result: Validation result to append findings to.
    :param skill: Skill identifier for reporting.
    """
    line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
    if line_count > MAX_SKILL_LINES:
        result.warn(
            skill,
            f"SKILL.md has {line_count} lines (recommended: <{MAX_SKILL_LINES})",
        )
    else:
        result.ok(skill, f"Line count OK ({line_count})")


def validate_scripts(
    skill_dir: Path, frontmatter: dict, result: ValidationResult, skill: str
) -> None:
    """Check that scripts are executable and allowed-tools is set.

    :param skill_dir: Path to the skill directory.
    :param frontmatter: Parsed frontmatter dict.
    :param result: Validation result to append findings to.
    :param skill: Skill identifier for reporting.
    """
    scripts = list(skill_dir.rglob("*.sh")) + list(skill_dir.rglob("*.py"))
    scripts = [s for s in scripts if "__pycache__" not in str(s) and s.name != "__init__.py"]

    for script in scripts:
        if not os.access(script, os.X_OK):
            result.error(skill, f"Script not executable: {script.name}")
        else:
            result.ok(skill, f"Script executable: {script.name}")

    allowed_tools = frontmatter.get("allowed-tools", "")
    if scripts and not allowed_tools:
        result.warn(
            skill,
            "Skill has scripts but no 'allowed-tools' in frontmatter",
        )


def validate_references(
    skill_md: Path,
    skill_dir: Path,
    result: ValidationResult,
    skill: str,
) -> None:
    """Check that files referenced in SKILL.md actually exist.

    :param skill_md: Path to SKILL.md.
    :param skill_dir: Path to the skill directory.
    :param result: Validation result to append findings to.
    :param skill: Skill identifier for reporting.
    """
    text = skill_md.read_text(encoding="utf-8")
    refs = REFERENCE_PATTERN.findall(text)

    for ref in refs:
        ref_path = ref.strip("()")
        full_path = skill_dir / ref_path
        if not full_path.exists():
            result.warn(
                skill,
                f"SKILL.md references '{ref_path}' but file not found",
            )


def validate_compatibility_section(
    skill_md: Path, result: ValidationResult, skill: str
) -> None:
    """Check that SKILL.md contains a '## Compatibility' section.

    :param skill_md: Path to SKILL.md.
    :param result: Validation result to append findings to.
    :param skill: Skill identifier for reporting.
    """
    text = skill_md.read_text(encoding="utf-8")
    if COMPATIBILITY_PATTERN.search(text):
        result.ok(skill, "Compatibility section present")
    else:
        result.warn(
            skill,
            "Missing '## Compatibility' section (recommended)",
        )


def validate_skill(skill_dir: Path, result: ValidationResult) -> None:
    """Validate a single skill directory.

    :param skill_dir: Path to the skill directory.
    :param result: Validation result to append findings to.
    """
    dir_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        result.error(dir_name, "Missing SKILL.md")
        return

    result.ok(dir_name, "SKILL.md exists")

    frontmatter, error = parse_frontmatter(skill_md)
    if frontmatter is None:
        result.error(dir_name, error)
        return

    result.ok(dir_name, "YAML frontmatter valid")

    validate_name(frontmatter.get("name"), dir_name, result, dir_name)
    validate_description(frontmatter.get("description"), result, dir_name)
    validate_line_count(skill_md, result, dir_name)
    validate_scripts(skill_dir, frontmatter, result, dir_name)
    validate_references(skill_md, skill_dir, result, dir_name)
    validate_compatibility_section(skill_md, result, dir_name)


def validate_skills_directory(skills_dir: Path) -> ValidationResult:
    """Validate all skills in a directory.

    :param skills_dir: Path to the skills root (e.g., .github/skills).
    :returns: Aggregated validation result.
    """
    result = ValidationResult()

    if not skills_dir.is_dir():
        result.error("(root)", f"Skills directory '{skills_dir}' not found")
        return result

    skip_dirs = {"_validation", "__pycache__"}
    skill_dirs = sorted(
        d
        for d in skills_dir.iterdir()
        if d.is_dir() and d.name not in skip_dirs and not d.name.startswith(".")
    )

    if not skill_dirs:
        result.warn("(root)", "No skill directories found")
        return result

    for skill_dir in skill_dirs:
        result.skills_checked += 1
        validate_skill(skill_dir, result)

    return result


def print_results(result: ValidationResult) -> None:
    """Print validation results to stdout.

    :param result: Validation result to print.
    """
    icons = {"error": "❌", "warning": "⚠️ ", "pass": "✅"}

    current_skill = None
    for finding in result.findings:
        if finding.skill != current_skill:
            current_skill = finding.skill
            print(f"\n--- {current_skill} ---")
        icon = icons[finding.level]
        print(f"  {icon} {finding.message}")

    print(f"\n{'=' * 40}")
    print(f"Skills checked: {result.skills_checked}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")

    if result.passed:
        print("\n✅ ALL SKILLS VALID")
    else:
        print("\n❌ VALIDATION FAILED")
        for err in result.errors:
            print(f"  - [{err.skill}] {err.message}")


def main() -> int:
    """Run skill validation from the command line.

    :returns: Exit code (0=pass, 1=fail).
    """
    skills_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".github/skills")
    result = validate_skills_directory(skills_dir)
    print_results(result)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
