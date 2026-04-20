"""Bridgeable Vault Hub services — cross-cutting platform-infrastructure
registry.

The Vault Hub is the top-level nav entry under which cross-cutting
platform services live (Documents, Intelligence today; CRM,
Notifications, Accounting admin in later V-1 phases). Vertical
workflows (Order Station, Cases, etc.) stay in vertical nav.

This package is distinct from the existing single-file modules
`app.services.vault_service`, `app.services.vault_document_service`,
etc., which deal with `VaultItem` data rows. The Hub registry here is
a UI / orchestration concern, not a data concern.

Usage:

    from app.services.vault.hub_registry import (
        VaultServiceDescriptor,
        register_service,
        list_services,
    )

See `hub_registry.py` for the registry and the V-1a seed registrations.
"""

from app.services.vault.hub_registry import (
    VaultServiceDescriptor,
    list_services,
    register_service,
    reset_registry,
)

__all__ = [
    "VaultServiceDescriptor",
    "list_services",
    "register_service",
    "reset_registry",
]
