# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
SSH credential provisioning from Azure Key Vault or local files.
"""

from __future__ import annotations
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from src.core.execution.exceptions import CredentialProvisionError
from src.core.models.ssh import AuthType, SshCredential
from src.core.observability import get_logger

logger = get_logger(__name__)


class SshCredentialProvider:
    """Provisions SSH credentials for Ansible execution."""

    _SSH_KEY_EXTENSIONS: tuple[str, ...] = (
        "ppk",
        "pem",
        "key",
        "private",
        "rsa",
        "ed25519",
        "ecdsa",
        "dsa",
        "",
    )

    def __init__(
        self,
        workspaces_base: str | Path = "WORKSPACES/SYSTEM",
    ) -> None:
        self._workspaces_base = Path(workspaces_base)

    def provision(
        self,
        workspace_id: str,
        extra_vars: dict[str, Any],
    ) -> Optional[SshCredential]:
        """Provision SSH credentials for a workspace.

        :param workspace_id: Workspace identifier.
        :param extra_vars: Variables from sap-parameters.yaml.
        :returns: Credential, or ``None`` if nothing found.
        :raises CredentialProvisionError: On retrieval failure.
        """
        ws_dir = self._workspaces_base / workspace_id
        auth = self._detect_auth_type(ws_dir)

        logger.info(
            "Auto-detected auth type %s for workspace %s",
            auth.value,
            workspace_id,
        )
        secret_id: str = extra_vars.get("secret_id", "")
        client_id: str = extra_vars.get(
            "user_assigned_identity_client_id",
            "",
        )

        if secret_id and "<" in secret_id:
            secret_id = ""

        if secret_id:
            return self._provision_from_key_vault(
                workspace_id=workspace_id,
                secret_id=secret_id,
                auth_type=auth,
                client_id=client_id,
            )

        return self._provision_from_local(
            workspace_id=workspace_id,
            ws_dir=ws_dir,
            auth_type=auth,
        )

    @staticmethod
    def _detect_auth_type(ws_dir: Path) -> AuthType:
        """
        Detect authentication type from workspace contents.
        """
        if (ws_dir / "password").is_file():
            return AuthType.VMPASSWORD
        return AuthType.SSHKEY

    def _provision_from_key_vault(
        self,
        workspace_id: str,
        secret_id: str,
        auth_type: AuthType,
        client_id: str = "",
    ) -> SshCredential:
        """Fetch secret from Azure Key Vault via MSI.

        :param workspace_id: For logging.
        :param secret_id: Full secret URL
        :param auth_type: SSHKEY or VMPASSWORD.
        :param client_id: User-assigned identity client ID (optional).
        :raises CredentialProvisionError: On any failure.
        """
        logger.info(
            "Fetching %s from Key Vault for workspace %s",
            auth_type.value,
            workspace_id,
        )
        vault_url, secret_name, secret_version = self._parse_secret_id(secret_id)
        secret_value = self._fetch_secret(
            vault_url=vault_url,
            secret_name=secret_name,
            secret_version=secret_version,
            client_id=client_id,
        )
        temp_path = self._write_secure_temp(
            content=secret_value, suffix=".ppk" if auth_type == AuthType.SSHKEY else ""
        )

        if auth_type == AuthType.SSHKEY:
            return SshCredential(
                auth_type=auth_type,
                private_key_path=temp_path,
                temp_files=[temp_path],
            )

        return SshCredential(
            auth_type=auth_type,
            ssh_password=secret_value,
            temp_files=[temp_path],
        )

    @staticmethod
    def _parse_secret_id(
        secret_id: str,
    ) -> tuple[str, str, str]:
        """Extract vault URL, secret name, and version from a"""
        parsed = urlparse(secret_id)
        if not parsed.scheme or not parsed.hostname:
            raise CredentialProvisionError(f"Invalid secret_id URL: {secret_id}")

        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2 or parts[0] != "secrets":
            raise CredentialProvisionError(f"Cannot parse secret name from: {secret_id}")

        secret_name = parts[1]
        secret_version = parts[2] if len(parts) > 2 else ""
        return f"{parsed.scheme}://{parsed.hostname}", secret_name, secret_version

    @staticmethod
    def _fetch_secret(
        vault_url: str,
        secret_name: str,
        secret_version: str = "",
        client_id: str = "",
    ) -> str:
        """Retrieve a secret from Azure Key Vault using MSI.

        :param vault_url: ``https://<vault>.vault.azure.net``
        :param secret_name: Secret name.
        :param secret_version: Optional version; empty → latest.
        :param client_id: User-assigned MSI client ID (optional).
        :raises CredentialProvisionError: On SDK/auth failure.
        """
        try:
            secret = SecretClient(
                vault_url=vault_url,
                credential=(
                    ManagedIdentityCredential(client_id=client_id)
                    if client_id
                    else ManagedIdentityCredential()
                ),
            ).get_secret(
                secret_name,
                version=secret_version or None,
            )
        except Exception as exc:
            raise CredentialProvisionError(f"Key Vault secret retrieval failed: {exc}") from exc

        if not secret.value:
            raise CredentialProvisionError("Key Vault returned an empty secret value")

        logger.info("Successfully retrieved secret from Key Vault")
        return secret.value

    def _provision_from_local(
        self,
        workspace_id: str,
        ws_dir: Path,
        auth_type: AuthType,
    ) -> Optional[SshCredential]:
        """Find SSH key or password file in workspace dir."""
        if auth_type == AuthType.SSHKEY:
            key_path = self._find_local_ssh_key(ws_dir)
            if key_path:
                os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
                logger.info(
                    "Using local SSH key for %s: %s",
                    workspace_id,
                    key_path,
                )
                return SshCredential(
                    auth_type=auth_type,
                    private_key_path=str(key_path),
                )
            logger.debug(
                "No local SSH key for workspace %s",
                workspace_id,
            )
            return None

        password_file = ws_dir / "password"
        if password_file.is_file():
            password = password_file.read_text(
                encoding="utf-8",
            ).strip()
            logger.info(
                "Using local password for workspace %s",
                workspace_id,
            )
            return SshCredential(
                auth_type=auth_type,
                ssh_password=password,
            )

        logger.debug(
            "No local password file for workspace %s",
            workspace_id,
        )
        return None

    @staticmethod
    def _write_secure_temp(
        content: str,
        suffix: str = "",
    ) -> str:
        """Write content to a chmod-600 temporary file."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return path

    def _find_local_ssh_key(
        self,
        workspace_dir: Path,
    ) -> Optional[Path]:
        """Search for a local SSH key file in the workspace."""
        if not workspace_dir.is_dir():
            return None

        for ext in self._SSH_KEY_EXTENSIONS:
            name = f"ssh_key.{ext}" if ext else "ssh_key"
            candidate = workspace_dir / name
            if candidate.is_file():
                return candidate

        matches = list(workspace_dir.glob("*ssh_key*"))
        return matches[0] if matches else None
