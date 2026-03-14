"""Abstract base class for accounting providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SyncResult:
    """Standard result from any sync operation."""

    success: bool
    records_synced: int = 0
    records_failed: int = 0
    sync_log_id: str | None = None
    error_message: str | None = None
    details: dict | None = None


@dataclass
class AccountMapping:
    """A mapping between an internal account/category and a provider account."""

    internal_id: str
    internal_name: str
    provider_id: str | None = None
    provider_name: str | None = None


@dataclass
class ProviderAccount:
    """An account from the external provider's chart of accounts."""

    id: str
    name: str
    account_type: str  # e.g., "Income", "Expense", "Asset", etc.
    number: str | None = None
    is_active: bool = True


@dataclass
class ConnectionStatus:
    """Status of the provider connection."""

    connected: bool
    provider: str
    last_sync_at: datetime | None = None
    error: str | None = None
    details: dict = field(default_factory=dict)


class AccountingProvider(ABC):
    """Abstract interface for accounting system integrations.

    Each provider (Sage CSV, QuickBooks Online, etc.) implements this
    interface. The factory resolves the correct provider per tenant.
    """

    provider_name: str = "unknown"

    @abstractmethod
    def get_connection_status(self) -> ConnectionStatus:
        """Check if the provider is connected and healthy."""
        ...

    @abstractmethod
    def test_connection(self) -> ConnectionStatus:
        """Actively test the provider connection (e.g., make an API call)."""
        ...

    # --- Customer sync ---

    @abstractmethod
    def sync_customers(self, direction: str = "push") -> SyncResult:
        """Sync customers to/from the provider.

        direction: "push" (internal -> provider), "pull" (provider -> internal),
                   or "bidirectional"
        """
        ...

    # --- Invoice sync ---

    @abstractmethod
    def sync_invoices(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push invoices to the accounting system."""
        ...

    # --- Payment sync ---

    @abstractmethod
    def sync_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Sync payment records."""
        ...

    # --- Bill sync (AP) ---

    @abstractmethod
    def sync_bills(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push vendor bills to the accounting system."""
        ...

    # --- Bill payment sync (AP) ---

    @abstractmethod
    def sync_bill_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push vendor bill payments to the accounting system."""
        ...

    # --- Inventory transactions ---

    @abstractmethod
    def sync_inventory_transactions(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Export inventory transactions to the accounting system."""
        ...

    # --- Chart of accounts ---

    @abstractmethod
    def get_chart_of_accounts(self) -> list[ProviderAccount]:
        """Fetch chart of accounts from the provider."""
        ...

    # --- Account mapping ---

    @abstractmethod
    def get_account_mappings(self) -> list[AccountMapping]:
        """Get current account mappings."""
        ...

    @abstractmethod
    def set_account_mapping(
        self,
        internal_id: str,
        provider_id: str,
    ) -> AccountMapping:
        """Set a mapping between internal and provider accounts."""
        ...
