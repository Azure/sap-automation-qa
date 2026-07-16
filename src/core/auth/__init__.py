# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Azure identity/credential acquisition (P1-WP-002D)."""

from src.core.auth.azure_identity import DefaultIdentityProvider
from src.core.contracts.azure_identity import AzureIdentityProvider

__all__ = ["AzureIdentityProvider", "DefaultIdentityProvider"]
