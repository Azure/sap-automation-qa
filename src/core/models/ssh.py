# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""SSH credential models."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """SSH authentication type matching sap-parameters.yaml."""

    SSHKEY = "SSHKEY"
    VMPASSWORD = "VMPASSWORD"


@dataclass(frozen=False)
class SshCredential:
    """Provisioned SSH credential for an Ansible run.

    :param auth_type: The authentication method used.
    :param private_key_path: Path to SSH private key (SSHKEY).
    :param ssh_password: SSH password value (VMPASSWORD).
    :param temp_files: Temporary files to clean up after execution.
    """

    auth_type: AuthType
    private_key_path: Optional[str] = None
    ssh_password: Optional[str] = None
    temp_files: list[str] = field(default_factory=list)

    def cleanup(self) -> None:
        """Remove any temporary files created during provisioning."""
        for path in self.temp_files:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    logger.debug("Cleaned up temp file: %s", path)
            except OSError as exc:
                logger.warning(
                    "Failed to clean up %s: %s",
                    path,
                    exc,
                )
        self.temp_files.clear()
