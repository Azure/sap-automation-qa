# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for SshCredentialProvider."""

import os
import stat
from pathlib import Path
import pytest
from pytest_mock import MockerFixture
from src.core.execution.exceptions import CredentialProvisionError
from src.core.execution.ssh_provider import SshCredentialProvider
from src.core.models.ssh import AuthType, SshCredential

SECRET_ID = "https://my-kv.vault.azure.net/secrets/ssh-key/abc123"


class TestSshCredentialProvider:
    """Tests for SshCredentialProvider and SshCredential."""

    def test_cleanup_removes_temp_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "key1.ppk"
        f2 = tmp_path / "key2.ppk"
        f1.write_text("secret")
        f2.write_text("secret")

        cred = SshCredential(
            auth_type=AuthType.SSHKEY,
            private_key_path=str(f1),
            temp_files=[str(f1), str(f2)],
        )
        cred.cleanup()

        assert not f1.exists()
        assert not f2.exists()
        assert cred.temp_files == []

    def test_cleanup_ignores_missing_files(self, tmp_path: Path) -> None:
        cred = SshCredential(
            auth_type=AuthType.SSHKEY,
            temp_files=[str(tmp_path / "gone")],
        )
        cred.cleanup()
        assert cred.temp_files == []

    def test_cleanup_empty(self) -> None:
        cred = SshCredential(auth_type=AuthType.SSHKEY)
        cred.cleanup()
        assert cred.temp_files == []

    def test_parse_full_url_with_version(self) -> None:
        vault, name, ver = SshCredentialProvider._parse_secret_id(
            "https://myvault.vault.azure.net/secrets/mykey/v1"
        )
        assert vault == "https://myvault.vault.azure.net"
        assert name == "mykey"
        assert ver == "v1"

    def test_parse_url_without_version(self) -> None:
        vault, name, ver = SshCredentialProvider._parse_secret_id(
            "https://myvault.vault.azure.net/secrets/mykey"
        )
        assert vault == "https://myvault.vault.azure.net"
        assert name == "mykey"
        assert ver == ""

    def test_parse_invalid_url_raises(self) -> None:
        with pytest.raises(CredentialProvisionError, match="Invalid"):
            SshCredentialProvider._parse_secret_id("not-a-url")

    def test_parse_missing_secrets_segment_raises(self) -> None:
        with pytest.raises(CredentialProvisionError, match="parse"):
            SshCredentialProvider._parse_secret_id("https://vault.azure.net/keys/foo")

    def test_finds_ssh_key_ppk(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        key = ws / "ssh_key.ppk"
        key.write_text("private")
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision("WS1", {})

        assert cred is not None
        assert cred.auth_type == AuthType.SSHKEY
        assert cred.private_key_path == str(key)
        assert cred.temp_files == []

    def test_finds_ssh_key_pem(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        (ws / "ssh_key.pem").write_text("pem")
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision("WS1", {})

        assert cred is not None
        assert cred.private_key_path == str(ws / "ssh_key.pem")

    def test_glob_fallback(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        key = ws / "my_ssh_key_file"
        key.write_text("key")
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision("WS1", {})

        assert cred is not None
        assert cred.private_key_path == str(key)

    def test_no_key_returns_none(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        assert provider.provision("WS1", {}) is None

    def test_password_file(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        (ws / "password").write_text("s3cret\n")
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision("WS1", {})
        assert cred is not None
        assert cred.auth_type == AuthType.VMPASSWORD
        assert cred.ssh_password == "s3cret"
        assert cred.private_key_path is None

    def test_no_password_no_key_returns_none(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        assert provider.provision("WS1", {}) is None

    def test_workspace_dir_missing(self, tmp_path: Path) -> None:
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        assert provider.provision("GONE", {}) is None

    def test_sshkey_from_kv(self, mocker: MockerFixture, tmp_path: Path) -> None:
        mock_fetch = mocker.patch.object(
            SshCredentialProvider,
            "_fetch_secret",
            return_value="private-key-content",
        )
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision("WS1", {"secret_id": SECRET_ID})
        assert cred is not None
        assert cred.auth_type == AuthType.SSHKEY
        assert cred.private_key_path is not None
        assert Path(cred.private_key_path).read_text() == "private-key-content"
        assert len(cred.temp_files) == 1
        mode = os.stat(cred.private_key_path).st_mode
        assert mode & stat.S_IRWXO == 0
        assert mode & stat.S_IRWXG == 0

        mock_fetch.assert_called_once_with(
            vault_url="https://my-kv.vault.azure.net",
            secret_name="ssh-key",
            secret_version="abc123",
            client_id="",
        )
        cred.cleanup()

    def test_vmpassword_from_kv(self, mocker: MockerFixture, tmp_path: Path) -> None:
        mocker.patch.object(
            SshCredentialProvider,
            "_fetch_secret",
            return_value="my-password",
        )
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        (ws / "password").write_text("local-unused")

        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision("WS1", {"secret_id": SECRET_ID})

        assert cred is not None
        assert cred.auth_type == AuthType.VMPASSWORD
        assert cred.ssh_password == "my-password"
        assert cred.private_key_path is None
        cred.cleanup()

    def test_client_id_forwarded(self, mocker: MockerFixture, tmp_path: Path) -> None:
        mock_fetch = mocker.patch.object(
            SshCredentialProvider,
            "_fetch_secret",
            return_value="key",
        )
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision(
            "WS1",
            {"secret_id": SECRET_ID, "user_assigned_identity_client_id": "my-cid"},
        )
        mock_fetch.assert_called_once_with(
            vault_url="https://my-kv.vault.azure.net",
            secret_name="ssh-key",
            secret_version="abc123",
            client_id="my-cid",
        )
        if cred:
            cred.cleanup()

    def test_fetch_failure_raises(self, mocker: MockerFixture, tmp_path: Path) -> None:
        mocker.patch.object(
            SshCredentialProvider,
            "_fetch_secret",
            side_effect=CredentialProvisionError("boom"),
        )
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        with pytest.raises(CredentialProvisionError, match="boom"):
            provider.provision("WS1", {"secret_id": SECRET_ID})

    def test_kv_preferred_over_local(self, mocker: MockerFixture, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        (ws / "ssh_key.ppk").write_text("local")
        mocker.patch.object(
            SshCredentialProvider,
            "_fetch_secret",
            return_value="kv-key",
        )
        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision("WS1", {"secret_id": SECRET_ID})

        assert cred is not None
        assert cred.private_key_path is not None
        assert Path(cred.private_key_path).read_text() == "kv-key"
        assert cred.private_key_path != str(ws / "ssh_key.ppk")
        cred.cleanup()

    def test_fetch_secret_sdk_happy_path(self, mocker: MockerFixture) -> None:
        mock_secret = mocker.MagicMock(value="the-secret")
        mock_client_cls = mocker.patch(
            "src.core.execution.ssh_provider.SecretClient",
        )
        mock_client_cls.return_value.get_secret.return_value = mock_secret
        mock_cred_cls = mocker.patch(
            "src.core.execution.ssh_provider.ManagedIdentityCredential",
        )

        result = SshCredentialProvider._fetch_secret(
            vault_url="https://v.vault.azure.net",
            secret_name="s",
            secret_version="v1",
            client_id="cid",
        )

        assert result == "the-secret"
        mock_cred_cls.assert_called_once_with(client_id="cid")
        mock_client_cls.return_value.get_secret.assert_called_once_with("s", version="v1")

    def test_fetch_secret_auth_failure_raises(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "src.core.execution.ssh_provider.ManagedIdentityCredential",
            side_effect=Exception("MSI unavailable"),
        )
        with pytest.raises(CredentialProvisionError, match="retrieval failed"):
            SshCredentialProvider._fetch_secret(
                vault_url="https://v.vault.azure.net",
                secret_name="s",
            )

    def test_placeholder_values_skipped(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)

        provider = SshCredentialProvider(workspaces_base=tmp_path / "SYSTEM")
        cred = provider.provision(
            "WS1",
            {"secret_id": "https://<kv>.vault.azure.net/secrets/<s>"},
        )
        assert cred is None

    def test_detect_vmpassword_when_password_file_exists(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        (ws / "password").write_text("pw")
        assert SshCredentialProvider._detect_auth_type(ws) == AuthType.VMPASSWORD

    def test_detect_sshkey_when_no_password_file(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "WS1"
        ws.mkdir(parents=True)
        assert SshCredentialProvider._detect_auth_type(ws) == AuthType.SSHKEY

    def test_detect_sshkey_when_dir_missing(self, tmp_path: Path) -> None:
        ws = tmp_path / "SYSTEM" / "GONE"
        assert SshCredentialProvider._detect_auth_type(ws) == AuthType.SSHKEY

    def test_write_secure_temp(self) -> None:
        path = SshCredentialProvider._write_secure_temp("data", ".ppk")
        try:
            assert Path(path).read_text() == "data"
            assert path.endswith(".ppk")
            mode = os.stat(path).st_mode
            assert mode & stat.S_IRWXO == 0
            assert mode & stat.S_IRWXG == 0
        finally:
            os.remove(path)
