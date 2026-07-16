# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Azure identity provider: credential acquisition only (P1-WP-002D).
"""

from __future__ import annotations

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential


class DefaultIdentityProvider:
    """Default implementation wrapping ``DefaultAzureCredential``.

    Owns exactly one ``DefaultAzureCredential`` instance; ``close()``
    releases it.
    """

    def __init__(self) -> None:
        self._credential: DefaultAzureCredential | None = DefaultAzureCredential()

    def get_credential(self) -> TokenCredential:
        """Return the managed ``DefaultAzureCredential``.

        :raises RuntimeError: If the provider has been closed.
        """
        if self._credential is None:
            raise RuntimeError("Identity provider has been closed")
        return self._credential

    def close(self) -> None:
        """Close the credential. Idempotent."""
        if self._credential is not None:
            cred = self._credential
            self._credential = None
            cred.close()
