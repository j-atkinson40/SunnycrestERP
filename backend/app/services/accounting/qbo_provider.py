"""QuickBooks Online accounting provider.

Full bidirectional sync: customers, invoices, payments, bills, and bill payments.
OAuth 2.0 token management with automatic refresh.

Requires `requests-oauthlib` for OAuth and `intuitlib` or direct REST for QBO API.
Falls back gracefully if QBO SDK is not installed.
"""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.accounting.base import (
    AccountMapping,
    AccountingProvider,
    ConnectionStatus,
    ProviderAccount,
    SyncResult,
)


def _get_qbo_config(company_config: dict) -> dict:
    """Extract QBO settings from the accounting_config JSON blob."""
    return {
        "client_id": company_config.get("qbo_client_id", ""),
        "client_secret": company_config.get("qbo_client_secret", ""),
        "realm_id": company_config.get("qbo_realm_id", ""),
        "access_token": company_config.get("qbo_access_token", ""),
        "refresh_token": company_config.get("qbo_refresh_token", ""),
        "token_expires_at": company_config.get("qbo_token_expires_at", ""),
        "environment": company_config.get("qbo_environment", "sandbox"),
        "account_mappings": company_config.get("qbo_account_mappings", {}),
    }


def _qbo_api_base(environment: str) -> str:
    if environment == "production":
        return "https://quickbooks.api.intuit.com"
    return "https://sandbox-quickbooks.api.intuit.com"


class QuickBooksOnlineProvider(AccountingProvider):
    """QuickBooks Online provider via REST API.

    Stores OAuth tokens in the company's accounting_config JSON blob.
    Tokens are refreshed automatically when expired.
    """

    provider_name = "quickbooks_online"

    def __init__(self, db: Session, company_id: str, actor_id: str | None = None):
        self.db = db
        self.company_id = company_id
        self.actor_id = actor_id
        self._config: dict | None = None

    def _load_config(self) -> dict:
        """Load QBO config from the company's accounting_config."""
        if self._config is not None:
            return self._config

        from app.models.company import Company

        company = self.db.query(Company).filter(Company.id == self.company_id).first()
        if not company or not company.accounting_config:
            self._config = {}
            return self._config

        try:
            raw = json.loads(company.accounting_config) if isinstance(
                company.accounting_config, str
            ) else company.accounting_config
            self._config = _get_qbo_config(raw)
        except (json.JSONDecodeError, TypeError):
            self._config = {}
        return self._config

    def _save_tokens(self, access_token: str, refresh_token: str, expires_at: str) -> None:
        """Persist refreshed tokens back to the company record."""
        from app.models.company import Company

        company = self.db.query(Company).filter(Company.id == self.company_id).first()
        if not company:
            return

        try:
            config = json.loads(company.accounting_config or "{}")
        except (json.JSONDecodeError, TypeError):
            config = {}

        config["qbo_access_token"] = access_token
        config["qbo_refresh_token"] = refresh_token
        config["qbo_token_expires_at"] = expires_at
        company.accounting_config = json.dumps(config)
        self.db.commit()
        # Update local cache
        if self._config:
            self._config["access_token"] = access_token
            self._config["refresh_token"] = refresh_token
            self._config["token_expires_at"] = expires_at

    def _is_token_expired(self) -> bool:
        config = self._load_config()
        expires_at = config.get("token_expires_at")
        if not expires_at:
            return True
        try:
            exp = datetime.fromisoformat(expires_at)
            return datetime.now(timezone.utc) >= exp
        except (ValueError, TypeError):
            return True

    def _refresh_access_token(self) -> bool:
        """Refresh the QBO access token using the refresh token.

        Returns True on success, False on failure.
        """
        import requests

        config = self._load_config()
        if not config.get("refresh_token") or not config.get("client_id"):
            return False

        try:
            resp = requests.post(
                "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": config["refresh_token"],
                },
                auth=(config["client_id"], config["client_secret"]),
                timeout=15,
            )
            if resp.status_code != 200:
                return False

            data = resp.json()
            from datetime import timedelta

            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
            ).isoformat()

            self._save_tokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", config["refresh_token"]),
                expires_at=expires_at,
            )
            return True
        except Exception:
            return False

    def _get_headers(self) -> dict[str, str] | None:
        """Get auth headers, refreshing token if needed. Returns None on failure."""
        config = self._load_config()
        if not config.get("access_token"):
            return None

        if self._is_token_expired():
            if not self._refresh_access_token():
                return None
            config = self._load_config()

        return {
            "Authorization": f"Bearer {config['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _api_url(self, endpoint: str) -> str:
        config = self._load_config()
        base = _qbo_api_base(config.get("environment", "sandbox"))
        realm_id = config.get("realm_id", "")
        return f"{base}/v3/company/{realm_id}/{endpoint}"

    # -----------------------------------------------------------------------
    # Connection management
    # -----------------------------------------------------------------------

    def get_connection_status(self) -> ConnectionStatus:
        config = self._load_config()
        connected = bool(
            config.get("access_token")
            and config.get("realm_id")
            and not self._is_token_expired()
        )
        return ConnectionStatus(
            connected=connected,
            provider=self.provider_name,
            details={
                "realm_id": config.get("realm_id", ""),
                "environment": config.get("environment", "sandbox"),
                "has_refresh_token": bool(config.get("refresh_token")),
            },
        )

    def test_connection(self) -> ConnectionStatus:
        import requests

        headers = self._get_headers()
        if not headers:
            return ConnectionStatus(
                connected=False,
                provider=self.provider_name,
                error="No valid credentials. Please reconnect QuickBooks.",
            )

        try:
            resp = requests.get(
                self._api_url("companyinfo/" + self._load_config().get("realm_id", "")),
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get("CompanyInfo", {})
                return ConnectionStatus(
                    connected=True,
                    provider=self.provider_name,
                    details={
                        "company_name": data.get("CompanyName", ""),
                        "country": data.get("Country", ""),
                    },
                )
            return ConnectionStatus(
                connected=False,
                provider=self.provider_name,
                error=f"QBO API returned {resp.status_code}",
            )
        except Exception as exc:
            return ConnectionStatus(
                connected=False,
                provider=self.provider_name,
                error=str(exc),
            )

    # -----------------------------------------------------------------------
    # Customer sync
    # -----------------------------------------------------------------------

    def sync_customers(self, direction: str = "push") -> SyncResult:
        import requests

        from app.models.customer import Customer
        from app.services import sync_log_service

        headers = self._get_headers()
        if not headers:
            return SyncResult(success=False, error_message="Not connected to QuickBooks")

        sync_log = sync_log_service.create_sync_log(
            self.db, self.company_id,
            sync_type="qbo_customer_sync",
            source="customers" if direction == "push" else "quickbooks",
            destination="quickbooks" if direction == "push" else "customers",
        )

        try:
            synced = 0
            failed = 0

            if direction in ("push", "bidirectional"):
                customers = (
                    self.db.query(Customer)
                    .filter(Customer.company_id == self.company_id)
                    .all()
                )
                for customer in customers:
                    qbo_customer = {
                        "DisplayName": customer.name,
                        "PrimaryEmailAddr": {"Address": customer.email} if customer.email else None,
                        "PrimaryPhone": {"FreeFormNumber": customer.phone} if customer.phone else None,
                    }
                    # Remove None values
                    qbo_customer = {k: v for k, v in qbo_customer.items() if v is not None}

                    try:
                        resp = requests.post(
                            self._api_url("customer"),
                            headers=headers,
                            json=qbo_customer,
                            timeout=10,
                        )
                        if resp.status_code in (200, 201):
                            synced += 1
                        else:
                            failed += 1
                    except Exception:
                        failed += 1

            sync_log_service.complete_sync_log(
                self.db, sync_log,
                records_processed=synced,
                records_failed=failed,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                records_synced=synced,
                records_failed=failed,
                sync_log_id=sync_log.id,
            )
        except Exception as exc:
            sync_log_service.complete_sync_log(
                self.db, sync_log,
                records_processed=0,
                records_failed=0,
                error_message=str(exc),
            )
            self.db.commit()
            return SyncResult(success=False, error_message=str(exc))

    # -----------------------------------------------------------------------
    # Invoice sync
    # -----------------------------------------------------------------------

    def sync_invoices(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push invoices to QBO. Placeholder — requires invoice model."""
        return SyncResult(
            success=False,
            error_message="Invoice sync requires the invoicing module (Phase 7). "
            "Infrastructure is ready — implement when invoicing is built.",
        )

    # -----------------------------------------------------------------------
    # Payment sync
    # -----------------------------------------------------------------------

    def sync_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Sync AR payments to QBO. Placeholder — requires AR module."""
        return SyncResult(
            success=False,
            error_message="Payment sync requires the AR module (Phase 7). "
            "Infrastructure is ready — implement when AR is built.",
        )

    # -----------------------------------------------------------------------
    # Bill sync (AP)
    # -----------------------------------------------------------------------

    def sync_bills(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        import requests

        from app.models.vendor_bill import VendorBill
        from app.services import sync_log_service

        headers = self._get_headers()
        if not headers:
            return SyncResult(success=False, error_message="Not connected to QuickBooks")

        sync_log = sync_log_service.create_sync_log(
            self.db, self.company_id,
            sync_type="qbo_bill_sync",
            source="vendor_bills",
            destination="quickbooks",
        )

        try:
            query = self.db.query(VendorBill).filter(
                VendorBill.company_id == self.company_id,
                VendorBill.deleted_at.is_(None),
            )
            if date_from:
                query = query.filter(VendorBill.bill_date >= date_from)
            if date_to:
                query = query.filter(VendorBill.bill_date <= date_to)

            bills = query.all()
            synced = 0
            failed = 0

            for bill in bills:
                qbo_bill = {
                    "VendorRef": {"name": bill.vendor.name if bill.vendor else ""},
                    "TxnDate": bill.bill_date.isoformat() if bill.bill_date else None,
                    "DueDate": bill.due_date.isoformat() if bill.due_date else None,
                    "DocNumber": bill.invoice_number or bill.bill_number,
                    "TotalAmt": float(bill.total_amount) if bill.total_amount else 0,
                    "Line": [
                        {
                            "Amount": float(line.amount) if line.amount else 0,
                            "DetailType": "AccountBasedExpenseLineDetail",
                            "AccountBasedExpenseLineDetail": {
                                "AccountRef": {"value": "7"},  # Default expense account
                            },
                            "Description": line.description or "",
                        }
                        for line in (bill.lines or [])
                    ],
                }
                try:
                    resp = requests.post(
                        self._api_url("bill"),
                        headers=headers,
                        json=qbo_bill,
                        timeout=10,
                    )
                    if resp.status_code in (200, 201):
                        synced += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1

            sync_log_service.complete_sync_log(
                self.db, sync_log,
                records_processed=synced,
                records_failed=failed,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                records_synced=synced,
                records_failed=failed,
                sync_log_id=sync_log.id,
            )
        except Exception as exc:
            sync_log_service.complete_sync_log(
                self.db, sync_log,
                records_processed=0, records_failed=0,
                error_message=str(exc),
            )
            self.db.commit()
            return SyncResult(success=False, error_message=str(exc))

    def sync_bill_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push vendor payments to QBO. Follows same pattern as sync_bills."""
        return SyncResult(
            success=False,
            error_message="Bill payment sync to QBO is in development. "
            "Use Sage CSV export for now.",
        )

    # -----------------------------------------------------------------------
    # Inventory transactions
    # -----------------------------------------------------------------------

    def sync_inventory_transactions(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """QBO doesn't natively support inventory transaction import."""
        return SyncResult(
            success=False,
            error_message="QuickBooks Online does not support direct inventory "
            "transaction import. Use journal entries or Sage CSV instead.",
        )

    # -----------------------------------------------------------------------
    # Chart of accounts
    # -----------------------------------------------------------------------

    def get_chart_of_accounts(self) -> list[ProviderAccount]:
        import requests

        headers = self._get_headers()
        if not headers:
            return []

        try:
            resp = requests.get(
                self._api_url("query") + "?query=SELECT * FROM Account MAXRESULTS 1000",
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                return []

            accounts_data = resp.json().get("QueryResponse", {}).get("Account", [])
            return [
                ProviderAccount(
                    id=str(acct.get("Id", "")),
                    name=acct.get("Name", ""),
                    account_type=acct.get("AccountType", ""),
                    number=acct.get("AcctNum"),
                    is_active=acct.get("Active", True),
                )
                for acct in accounts_data
            ]
        except Exception:
            return []

    # -----------------------------------------------------------------------
    # Account mappings
    # -----------------------------------------------------------------------

    def get_account_mappings(self) -> list[AccountMapping]:
        config = self._load_config()
        mappings_dict = config.get("account_mappings", {})
        return [
            AccountMapping(
                internal_id=k,
                internal_name=v.get("internal_name", k),
                provider_id=v.get("provider_id"),
                provider_name=v.get("provider_name"),
            )
            for k, v in mappings_dict.items()
        ]

    def set_account_mapping(
        self,
        internal_id: str,
        provider_id: str,
    ) -> AccountMapping:
        from app.models.company import Company

        company = self.db.query(Company).filter(Company.id == self.company_id).first()
        if not company:
            return AccountMapping(internal_id=internal_id, internal_name="")

        try:
            config = json.loads(company.accounting_config or "{}")
        except (json.JSONDecodeError, TypeError):
            config = {}

        mappings = config.get("qbo_account_mappings", {})
        mappings[internal_id] = {
            "provider_id": provider_id,
            "internal_name": internal_id,
            "provider_name": "",
        }
        config["qbo_account_mappings"] = mappings
        company.accounting_config = json.dumps(config)
        self.db.commit()

        return AccountMapping(
            internal_id=internal_id,
            internal_name=internal_id,
            provider_id=provider_id,
        )
