# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Azure Storage resource context: unified ownership of shared infrastructure.
"""

from __future__ import annotations
import os
from typing import Mapping
from azure.core.credentials import TokenCredential
from azure.data.tables import TableClient, TableServiceClient
from azure.storage.blob import BlobServiceClient, ContainerClient
from src.core.auth.azure_identity import DefaultIdentityProvider
from src.core.contracts.azure_identity import AzureIdentityProvider
from src.core.observability import get_logger

logger = get_logger(__name__)
DEFAULT_BLOB_CONTAINER = "workspaces"


class AzureStorageContext:
    """Unified ownership of Azure Storage infrastructure resources."""

    def __init__(
        self,
        *,
        identity_provider: AzureIdentityProvider,
        table_service: TableServiceClient | None = None,
        blob_service: BlobServiceClient | None = None,
        table_endpoint: str | None = None,
        blob_endpoint: str | None = None,
        owns_identity: bool = False,
    ) -> None:
        """Initialize the shared Azure Storage context."""
        self.identity_provider = identity_provider
        self.table_service = table_service
        self.blob_service = blob_service
        self.table_endpoint = table_endpoint
        self.blob_endpoint = blob_endpoint
        self._owns_identity = owns_identity
        self._closed = False

    @property
    def credential(self) -> TokenCredential:
        """Return the shared credential."""
        if self._closed:
            raise RuntimeError("AzureStorageContext has been closed")
        return self.identity_provider.get_credential()

    @property
    def has_table(self) -> bool:
        """Whether Table Storage is configured and available."""
        return self.table_service is not None

    @property
    def has_blob(self) -> bool:
        """Whether Blob Storage is configured and available."""
        return self.blob_service is not None

    def get_table_client(self, table_name: str) -> TableClient:
        """Return a non-owning TableClient for the given table."""
        if self.table_service is None:
            raise RuntimeError("Table Storage not configured (AZURE_TABLE_ENDPOINT not set)")
        self.table_service.create_table_if_not_exists(table_name)
        return self.table_service.get_table_client(table_name)

    def get_container_client(self, container_name: str = DEFAULT_BLOB_CONTAINER) -> ContainerClient:
        """Return a non-owning ContainerClient for the given container."""
        if self.blob_service is None:
            raise RuntimeError("Blob Storage not configured (AZURE_BLOB_ENDPOINT not set)")
        return self.blob_service.get_container_client(container_name)

    def close(self) -> None:
        """Close owned resources exactly once. Idempotent."""
        if self._closed:
            return
        self._closed = True

        if self.blob_service is not None:
            try:
                self.blob_service.close()
            except Exception as exc:
                logger.warning("Error closing BlobServiceClient: %s", exc)

        if self.table_service is not None:
            try:
                self.table_service.close()
            except Exception as exc:
                logger.warning("Error closing TableServiceClient: %s", exc)

        if self._owns_identity:
            try:
                self.identity_provider.close()
            except Exception as exc:
                logger.warning("Error closing identity provider: %s", exc)


def create_azure_storage_context(
    *,
    env: Mapping[str, str] | None = None,
    identity_provider: AzureIdentityProvider | None = None,
) -> AzureStorageContext | None:
    """Create the shared Azure Storage context if any Azure endpoint is configured."""
    resolved_env = env if env is not None else os.environ
    table_endpoint = (resolved_env.get("AZURE_TABLE_ENDPOINT") or "").strip() or None
    blob_endpoint = (resolved_env.get("AZURE_BLOB_ENDPOINT") or "").strip() or None

    if not table_endpoint and not blob_endpoint:
        return None

    owns_identity = identity_provider is None
    provider = identity_provider or DefaultIdentityProvider()
    table_service, blob_service = None, None

    try:
        credential = provider.get_credential()
        table_service = (
            TableServiceClient(endpoint=table_endpoint, credential=credential)
            if table_endpoint
            else None
        )
        blob_service = (
            BlobServiceClient(account_url=blob_endpoint, credential=credential)
            if blob_endpoint
            else None
        )
    except Exception:
        if "table_service" in locals() and table_service is not None:
            table_service.close()
        if "blob_service" in locals() and blob_service is not None:
            blob_service.close()
        if owns_identity:
            provider.close()
        raise

    return AzureStorageContext(
        identity_provider=provider,
        table_service=table_service,
        blob_service=blob_service,
        table_endpoint=table_endpoint,
        blob_endpoint=blob_endpoint,
        owns_identity=owns_identity,
    )
