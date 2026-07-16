# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Azure identity protocol
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable
from azure.core.credentials import TokenCredential


@runtime_checkable
class AzureIdentityProvider(Protocol):
    """Protocol for Azure credential acquisition.

    Implementations own the credential lifecycle: creation and close.
    """

    def get_credential(self) -> TokenCredential:
        """Return a usable TokenCredential.

        The credential remains valid until ``close()`` is called on this
        provider. Callers must NOT close the returned credential directly.
        """
        ...

    def close(self) -> None:
        """Release the credential and any underlying resources.

        Idempotent: safe to call multiple times.
        """
        ...
