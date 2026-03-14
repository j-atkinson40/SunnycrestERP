"""Sage 100 CSV accounting provider.

Wraps existing sage_export_service and ap_sage_export_service into the
AccountingProvider interface. Sage is a "push-only" provider — it generates
CSV files but doesn't pull data back.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.services.accounting.base import (
    AccountMapping,
    AccountingProvider,
    ConnectionStatus,
    ProviderAccount,
    SyncResult,
)


class SageCSVProvider(AccountingProvider):
    """Sage 100 CSV export provider.

    Generates CSV files compatible with Sage 100 import format.
    This is a one-way (push) provider — no data is pulled from Sage.
    """

    provider_name = "sage_csv"

    def __init__(self, db: Session, company_id: str, actor_id: str | None = None):
        self.db = db
        self.company_id = company_id
        self.actor_id = actor_id

    def get_connection_status(self) -> ConnectionStatus:
        """Sage CSV is always 'connected' — it's file-based."""
        from app.services.sage_export_service import get_or_create_config

        config = get_or_create_config(self.db, self.company_id)
        return ConnectionStatus(
            connected=config.is_active,
            provider=self.provider_name,
            last_sync_at=config.last_export_at,
            details={
                "warehouse_code": config.warehouse_code,
                "export_directory": config.export_directory,
            },
        )

    def test_connection(self) -> ConnectionStatus:
        """Sage CSV doesn't need a connection test."""
        return self.get_connection_status()

    def sync_customers(self, direction: str = "push") -> SyncResult:
        """Sage CSV does not support customer sync."""
        return SyncResult(
            success=False,
            error_message="Sage CSV provider does not support customer sync. "
            "Export customers manually from the Customers page.",
        )

    def sync_invoices(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Sage CSV does not support invoice sync yet."""
        return SyncResult(
            success=False,
            error_message="Invoice sync not yet implemented for Sage CSV.",
        )

    def sync_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Sage CSV does not support AR payment sync yet."""
        return SyncResult(
            success=False,
            error_message="AR payment sync not yet implemented for Sage CSV.",
        )

    def sync_bills(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Export vendor bills as Sage-compatible CSV."""
        from app.services.ap_sage_export_service import generate_bills_csv

        if not date_from or not date_to:
            return SyncResult(
                success=False,
                error_message="date_from and date_to are required for Sage bill export.",
            )

        try:
            csv_string, count, sync_log_id = generate_bills_csv(
                self.db, self.company_id, date_from, date_to, self.actor_id
            )
            return SyncResult(
                success=True,
                records_synced=count,
                sync_log_id=sync_log_id,
                details={"csv_length": len(csv_string)},
            )
        except Exception as exc:
            return SyncResult(success=False, error_message=str(exc))

    def sync_bill_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Export vendor payments as Sage-compatible CSV."""
        from app.services.ap_sage_export_service import generate_payments_csv

        if not date_from or not date_to:
            return SyncResult(
                success=False,
                error_message="date_from and date_to are required for Sage payment export.",
            )

        try:
            csv_string, count, sync_log_id = generate_payments_csv(
                self.db, self.company_id, date_from, date_to, self.actor_id
            )
            return SyncResult(
                success=True,
                records_synced=count,
                sync_log_id=sync_log_id,
                details={"csv_length": len(csv_string)},
            )
        except Exception as exc:
            return SyncResult(success=False, error_message=str(exc))

    def sync_inventory_transactions(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Export inventory transactions as Sage-compatible CSV."""
        from app.services.sage_export_service import generate_sage_csv

        if not date_from or not date_to:
            return SyncResult(
                success=False,
                error_message="date_from and date_to are required for Sage inventory export.",
            )

        try:
            csv_string, count, sync_log_id = generate_sage_csv(
                self.db, self.company_id, date_from, date_to, self.actor_id
            )
            return SyncResult(
                success=True,
                records_synced=count,
                sync_log_id=sync_log_id,
                details={"csv_length": len(csv_string)},
            )
        except Exception as exc:
            return SyncResult(success=False, error_message=str(exc))

    def get_chart_of_accounts(self) -> list[ProviderAccount]:
        """Sage CSV doesn't provide a chart of accounts."""
        return []

    def get_account_mappings(self) -> list[AccountMapping]:
        """Sage CSV doesn't use account mappings."""
        return []

    def set_account_mapping(
        self,
        internal_id: str,
        provider_id: str,
    ) -> AccountMapping:
        """Sage CSV doesn't support account mappings."""
        return AccountMapping(
            internal_id=internal_id,
            internal_name="",
            provider_id=provider_id,
        )
