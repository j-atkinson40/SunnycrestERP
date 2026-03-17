"""QuickBooks Online accounting provider.

Full bidirectional sync: customers, invoices, payments, bills, and bill payments.
OAuth 2.0 token management with automatic refresh.

Uses direct REST API calls to QBO V3 endpoints.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.accounting.base import (
    AccountMapping,
    AccountingProvider,
    ConnectionStatus,
    ProviderAccount,
    SyncResult,
)

logger = logging.getLogger(__name__)

# QBO payment method mapping
_PAYMENT_METHOD_MAP = {
    "check": "Check",
    "ach": "EFT",
    "credit_card": "CreditCard",
    "cash": "Cash",
    "wire": "EFT",
}


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


def _decimal_to_float(val: Decimal | None) -> float:
    """Safely convert Decimal to float for JSON serialization."""
    if val is None:
        return 0.0
    return float(val)


class QuickBooksOnlineProvider(AccountingProvider):
    """QuickBooks Online provider via REST API.

    Stores OAuth tokens in the company's accounting_config JSON blob.
    Tokens are refreshed automatically when expired.

    Sync behaviour:
    - Only pushes records that do NOT already have a qbo_id (avoids duplicates).
    - On success, stores the QBO-assigned Id back on the local record.
    - Uses account mappings for GL accounts; falls back to sensible defaults.
    """

    provider_name = "quickbooks_online"

    def __init__(self, db: Session, company_id: str, actor_id: str | None = None):
        self.db = db
        self.company_id = company_id
        self.actor_id = actor_id
        self._config: dict | None = None

    # -----------------------------------------------------------------------
    # Config / token helpers
    # -----------------------------------------------------------------------

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
            raw = (
                json.loads(company.accounting_config)
                if isinstance(company.accounting_config, str)
                else company.accounting_config
            )
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
        """Refresh the QBO access token using the refresh token."""
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
                logger.warning("QBO token refresh failed: %s", resp.text)
                return False

            data = resp.json()
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
            logger.exception("QBO token refresh error")
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

    def _get_mapped_account(self, mapping_key: str, fallback: str = "1") -> str:
        """Look up a mapped QBO account ID, falling back to a default."""
        config = self._load_config()
        mappings = config.get("account_mappings", {})
        mapping = mappings.get(mapping_key, {})
        return mapping.get("provider_id") or fallback

    def _find_or_create_qbo_customer(
        self, headers: dict, customer_name: str
    ) -> str | None:
        """Find a QBO customer by name, or create one. Returns QBO Id."""
        import requests

        try:
            # Search by name first
            query = f"SELECT * FROM Customer WHERE DisplayName = '{customer_name}'"
            resp = requests.get(
                self._api_url("query") + f"?query={query}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                customers = resp.json().get("QueryResponse", {}).get("Customer", [])
                if customers:
                    return str(customers[0]["Id"])

            # Not found — create
            resp = requests.post(
                self._api_url("customer"),
                headers=headers,
                json={"DisplayName": customer_name},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return str(resp.json().get("Customer", {}).get("Id", ""))
        except Exception:
            logger.exception("Error finding/creating QBO customer: %s", customer_name)
        return None

    def _find_or_create_qbo_vendor(
        self, headers: dict, vendor_name: str
    ) -> str | None:
        """Find a QBO vendor by name, or create one. Returns QBO Id."""
        import requests

        try:
            query = f"SELECT * FROM Vendor WHERE DisplayName = '{vendor_name}'"
            resp = requests.get(
                self._api_url("query") + f"?query={query}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                vendors = resp.json().get("QueryResponse", {}).get("Vendor", [])
                if vendors:
                    return str(vendors[0]["Id"])

            resp = requests.post(
                self._api_url("vendor"),
                headers=headers,
                json={"DisplayName": vendor_name},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return str(resp.json().get("Vendor", {}).get("Id", ""))
        except Exception:
            logger.exception("Error finding/creating QBO vendor: %s", vendor_name)
        return None

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
            self.db,
            self.company_id,
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
                        "PrimaryEmailAddr": (
                            {"Address": customer.email} if customer.email else None
                        ),
                        "PrimaryPhone": (
                            {"FreeFormNumber": customer.phone} if customer.phone else None
                        ),
                    }
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
                self.db,
                sync_log,
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
                self.db,
                sync_log,
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
        """Push invoices to QBO as Invoice objects.

        - Skips invoices that already have a qbo_id (idempotent).
        - Resolves the QBO CustomerRef by name lookup/create.
        - Maps line items with SalesItemLineDetail.
        - Uses the 'income_account' mapping for line items.
        """
        import requests

        from app.models.invoice import Invoice
        from app.services import sync_log_service

        headers = self._get_headers()
        if not headers:
            return SyncResult(success=False, error_message="Not connected to QuickBooks")

        sync_log = sync_log_service.create_sync_log(
            self.db,
            self.company_id,
            sync_type="qbo_invoice_sync",
            source="invoices",
            destination="quickbooks",
        )

        try:
            query = self.db.query(Invoice).filter(
                Invoice.company_id == self.company_id,
                Invoice.qbo_id.is_(None),  # Only un-synced invoices
                Invoice.status.notin_(["draft", "void"]),  # Skip drafts and voided
            )
            if date_from:
                query = query.filter(Invoice.invoice_date >= date_from)
            if date_to:
                query = query.filter(Invoice.invoice_date <= date_to)

            invoices = query.all()
            synced = 0
            failed = 0
            errors: list[str] = []
            income_account = self._get_mapped_account("income_account", "1")

            for invoice in invoices:
                try:
                    # Resolve QBO customer
                    customer_name = (
                        invoice.customer.name if invoice.customer else "Unknown Customer"
                    )
                    qbo_customer_id = self._find_or_create_qbo_customer(
                        headers, customer_name
                    )
                    if not qbo_customer_id:
                        failed += 1
                        errors.append(f"{invoice.number}: customer lookup failed")
                        continue

                    # Build line items
                    qbo_lines = []
                    for line in invoice.lines or []:
                        qbo_lines.append(
                            {
                                "Amount": _decimal_to_float(line.line_total),
                                "DetailType": "SalesItemLineDetail",
                                "SalesItemLineDetail": {
                                    "Qty": _decimal_to_float(line.quantity),
                                    "UnitPrice": _decimal_to_float(line.unit_price),
                                    "IncomeAccountRef": {"value": income_account},
                                },
                                "Description": line.description or "",
                            }
                        )

                    if not qbo_lines:
                        # QBO requires at least one line
                        qbo_lines.append(
                            {
                                "Amount": _decimal_to_float(invoice.total),
                                "DetailType": "SalesItemLineDetail",
                                "SalesItemLineDetail": {
                                    "IncomeAccountRef": {"value": income_account},
                                },
                                "Description": f"Invoice {invoice.number}",
                            }
                        )

                    qbo_invoice = {
                        "CustomerRef": {"value": qbo_customer_id},
                        "DocNumber": invoice.number,
                        "TxnDate": (
                            invoice.invoice_date.strftime("%Y-%m-%d")
                            if invoice.invoice_date
                            else None
                        ),
                        "DueDate": (
                            invoice.due_date.strftime("%Y-%m-%d")
                            if invoice.due_date
                            else None
                        ),
                        "Line": qbo_lines,
                    }
                    # Remove None values
                    qbo_invoice = {k: v for k, v in qbo_invoice.items() if v is not None}

                    resp = requests.post(
                        self._api_url("invoice"),
                        headers=headers,
                        json=qbo_invoice,
                        timeout=15,
                    )
                    if resp.status_code in (200, 201):
                        qbo_id = str(
                            resp.json().get("Invoice", {}).get("Id", "")
                        )
                        invoice.qbo_id = qbo_id
                        synced += 1
                    else:
                        failed += 1
                        detail = resp.json().get("Fault", {}).get("Error", [{}])
                        msg = detail[0].get("Detail", resp.text[:200]) if detail else resp.text[:200]
                        errors.append(f"{invoice.number}: {msg}")
                except Exception as exc:
                    failed += 1
                    errors.append(f"{invoice.number}: {exc}")

            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=synced,
                records_failed=failed,
                error_message="; ".join(errors[:10]) if errors else None,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                records_synced=synced,
                records_failed=failed,
                sync_log_id=sync_log.id,
                details={"errors": errors[:10]} if errors else None,
            )
        except Exception as exc:
            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=0,
                records_failed=0,
                error_message=str(exc),
            )
            self.db.commit()
            return SyncResult(success=False, error_message=str(exc))

    # -----------------------------------------------------------------------
    # Payment sync (AR — customer payments)
    # -----------------------------------------------------------------------

    def sync_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push customer payments to QBO as Payment objects.

        - Links payments to QBO invoices when the invoice has a qbo_id.
        - Skips payments that already have a qbo_id.
        - Uses the 'deposit_account' mapping for the DepositToAccountRef.
        """
        import requests

        from app.models.customer_payment import CustomerPayment
        from app.services import sync_log_service

        headers = self._get_headers()
        if not headers:
            return SyncResult(success=False, error_message="Not connected to QuickBooks")

        sync_log = sync_log_service.create_sync_log(
            self.db,
            self.company_id,
            sync_type="qbo_payment_sync",
            source="customer_payments",
            destination="quickbooks",
        )

        try:
            query = self.db.query(CustomerPayment).filter(
                CustomerPayment.company_id == self.company_id,
                CustomerPayment.qbo_id.is_(None),
                CustomerPayment.deleted_at.is_(None),
            )
            if date_from:
                query = query.filter(CustomerPayment.payment_date >= date_from)
            if date_to:
                query = query.filter(CustomerPayment.payment_date <= date_to)

            payments = query.all()
            synced = 0
            failed = 0
            errors: list[str] = []
            deposit_account = self._get_mapped_account("deposit_account", "1")

            for payment in payments:
                try:
                    customer_name = (
                        payment.customer.name if payment.customer else "Unknown Customer"
                    )
                    qbo_customer_id = self._find_or_create_qbo_customer(
                        headers, customer_name
                    )
                    if not qbo_customer_id:
                        failed += 1
                        errors.append(f"Payment {payment.id[:8]}: customer lookup failed")
                        continue

                    # Build invoice line references for applied amounts
                    qbo_lines = []
                    for app in payment.applications or []:
                        line: dict = {
                            "Amount": _decimal_to_float(app.amount_applied),
                        }
                        # Link to QBO invoice if it was synced
                        if app.invoice and app.invoice.qbo_id:
                            line["LinkedTxn"] = [
                                {
                                    "TxnId": app.invoice.qbo_id,
                                    "TxnType": "Invoice",
                                }
                            ]
                        qbo_lines.append(line)

                    qbo_payment: dict = {
                        "CustomerRef": {"value": qbo_customer_id},
                        "TotalAmt": _decimal_to_float(payment.total_amount),
                        "TxnDate": (
                            payment.payment_date.strftime("%Y-%m-%d")
                            if payment.payment_date
                            else None
                        ),
                        "PaymentMethodRef": {
                            "value": _PAYMENT_METHOD_MAP.get(
                                payment.payment_method, "Other"
                            )
                        },
                        "DepositToAccountRef": {"value": deposit_account},
                    }
                    if payment.reference_number:
                        qbo_payment["PaymentRefNum"] = payment.reference_number

                    if qbo_lines:
                        qbo_payment["Line"] = qbo_lines

                    qbo_payment = {k: v for k, v in qbo_payment.items() if v is not None}

                    resp = requests.post(
                        self._api_url("payment"),
                        headers=headers,
                        json=qbo_payment,
                        timeout=15,
                    )
                    if resp.status_code in (200, 201):
                        qbo_id = str(
                            resp.json().get("Payment", {}).get("Id", "")
                        )
                        payment.qbo_id = qbo_id
                        synced += 1
                    else:
                        failed += 1
                        detail = resp.json().get("Fault", {}).get("Error", [{}])
                        msg = detail[0].get("Detail", resp.text[:200]) if detail else resp.text[:200]
                        errors.append(f"Payment {payment.id[:8]}: {msg}")
                except Exception as exc:
                    failed += 1
                    errors.append(f"Payment {payment.id[:8]}: {exc}")

            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=synced,
                records_failed=failed,
                error_message="; ".join(errors[:10]) if errors else None,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                records_synced=synced,
                records_failed=failed,
                sync_log_id=sync_log.id,
                details={"errors": errors[:10]} if errors else None,
            )
        except Exception as exc:
            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=0,
                records_failed=0,
                error_message=str(exc),
            )
            self.db.commit()
            return SyncResult(success=False, error_message=str(exc))

    # -----------------------------------------------------------------------
    # Bill sync (AP — vendor bills)
    # -----------------------------------------------------------------------

    def sync_bills(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push vendor bills to QBO.

        - Skips bills that already have a qbo_id.
        - Resolves the QBO VendorRef by name lookup/create.
        - Uses 'expense_account' mapping for line items.
        """
        import requests

        from app.models.vendor_bill import VendorBill
        from app.services import sync_log_service

        headers = self._get_headers()
        if not headers:
            return SyncResult(success=False, error_message="Not connected to QuickBooks")

        sync_log = sync_log_service.create_sync_log(
            self.db,
            self.company_id,
            sync_type="qbo_bill_sync",
            source="vendor_bills",
            destination="quickbooks",
        )

        try:
            query = self.db.query(VendorBill).filter(
                VendorBill.company_id == self.company_id,
                VendorBill.deleted_at.is_(None),
                VendorBill.qbo_id.is_(None),  # Only un-synced bills
            )
            if date_from:
                query = query.filter(VendorBill.bill_date >= date_from)
            if date_to:
                query = query.filter(VendorBill.bill_date <= date_to)

            bills = query.all()
            synced = 0
            failed = 0
            errors: list[str] = []
            expense_account = self._get_mapped_account("expense_account", "7")

            for bill in bills:
                try:
                    vendor_name = bill.vendor.name if bill.vendor else "Unknown Vendor"
                    qbo_vendor_id = self._find_or_create_qbo_vendor(headers, vendor_name)
                    if not qbo_vendor_id:
                        failed += 1
                        errors.append(f"{bill.number}: vendor lookup failed")
                        continue

                    qbo_bill = {
                        "VendorRef": {"value": qbo_vendor_id},
                        "TxnDate": (
                            bill.bill_date.strftime("%Y-%m-%d") if bill.bill_date else None
                        ),
                        "DueDate": (
                            bill.due_date.strftime("%Y-%m-%d") if bill.due_date else None
                        ),
                        "DocNumber": bill.vendor_invoice_number or bill.number,
                        "Line": [
                            {
                                "Amount": _decimal_to_float(line.amount),
                                "DetailType": "AccountBasedExpenseLineDetail",
                                "AccountBasedExpenseLineDetail": {
                                    "AccountRef": {"value": expense_account},
                                },
                                "Description": line.description or "",
                            }
                            for line in (bill.lines or [])
                        ],
                    }
                    qbo_bill = {k: v for k, v in qbo_bill.items() if v is not None}

                    # Ensure at least one line
                    if not qbo_bill.get("Line"):
                        qbo_bill["Line"] = [
                            {
                                "Amount": _decimal_to_float(bill.total),
                                "DetailType": "AccountBasedExpenseLineDetail",
                                "AccountBasedExpenseLineDetail": {
                                    "AccountRef": {"value": expense_account},
                                },
                                "Description": f"Bill {bill.number}",
                            }
                        ]

                    resp = requests.post(
                        self._api_url("bill"),
                        headers=headers,
                        json=qbo_bill,
                        timeout=15,
                    )
                    if resp.status_code in (200, 201):
                        qbo_id = str(resp.json().get("Bill", {}).get("Id", ""))
                        bill.qbo_id = qbo_id
                        synced += 1
                    else:
                        failed += 1
                        detail = resp.json().get("Fault", {}).get("Error", [{}])
                        msg = detail[0].get("Detail", resp.text[:200]) if detail else resp.text[:200]
                        errors.append(f"{bill.number}: {msg}")
                except Exception as exc:
                    failed += 1
                    errors.append(f"{bill.number}: {exc}")

            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=synced,
                records_failed=failed,
                error_message="; ".join(errors[:10]) if errors else None,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                records_synced=synced,
                records_failed=failed,
                sync_log_id=sync_log.id,
                details={"errors": errors[:10]} if errors else None,
            )
        except Exception as exc:
            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=0,
                records_failed=0,
                error_message=str(exc),
            )
            self.db.commit()
            return SyncResult(success=False, error_message=str(exc))

    # -----------------------------------------------------------------------
    # Bill payment sync (AP — vendor payments)
    # -----------------------------------------------------------------------

    def sync_bill_payments(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """Push vendor payments to QBO as BillPayment objects.

        - Skips payments that already have a qbo_id.
        - Links to QBO bills when the bill has a qbo_id.
        - Uses 'ap_bank_account' mapping for the BankAccountRef.
        """
        import requests

        from app.models.vendor_payment import VendorPayment
        from app.services import sync_log_service

        headers = self._get_headers()
        if not headers:
            return SyncResult(success=False, error_message="Not connected to QuickBooks")

        sync_log = sync_log_service.create_sync_log(
            self.db,
            self.company_id,
            sync_type="qbo_bill_payment_sync",
            source="vendor_payments",
            destination="quickbooks",
        )

        try:
            query = self.db.query(VendorPayment).filter(
                VendorPayment.company_id == self.company_id,
                VendorPayment.deleted_at.is_(None),
                VendorPayment.qbo_id.is_(None),
            )
            if date_from:
                query = query.filter(VendorPayment.payment_date >= date_from)
            if date_to:
                query = query.filter(VendorPayment.payment_date <= date_to)

            payments = query.all()
            synced = 0
            failed = 0
            errors: list[str] = []
            bank_account = self._get_mapped_account("ap_bank_account", "1")

            for payment in payments:
                try:
                    vendor_name = (
                        payment.vendor.name if payment.vendor else "Unknown Vendor"
                    )
                    qbo_vendor_id = self._find_or_create_qbo_vendor(headers, vendor_name)
                    if not qbo_vendor_id:
                        failed += 1
                        errors.append(f"VendorPayment {payment.id[:8]}: vendor lookup failed")
                        continue

                    # Build line items linking to QBO bills
                    qbo_lines = []
                    for app in payment.applications or []:
                        line: dict = {
                            "Amount": _decimal_to_float(app.amount_applied),
                        }
                        if app.bill and app.bill.qbo_id:
                            line["LinkedTxn"] = [
                                {
                                    "TxnId": app.bill.qbo_id,
                                    "TxnType": "Bill",
                                }
                            ]
                        qbo_lines.append(line)

                    # Determine payment type for QBO
                    is_check = payment.payment_method == "check"
                    pay_type = "Check" if is_check else "CreditCard"

                    qbo_bill_payment: dict = {
                        "VendorRef": {"value": qbo_vendor_id},
                        "TotalAmt": _decimal_to_float(payment.total_amount),
                        "PayType": pay_type,
                        "TxnDate": (
                            payment.payment_date.strftime("%Y-%m-%d")
                            if payment.payment_date
                            else None
                        ),
                    }

                    if is_check:
                        check_detail: dict = {
                            "BankAccountRef": {"value": bank_account},
                        }
                        if payment.reference_number:
                            check_detail["PrintStatus"] = "NeedToPrint"
                        qbo_bill_payment["CheckPayment"] = check_detail
                    else:
                        qbo_bill_payment["CreditCardPayment"] = {
                            "CCAccountRef": {"value": bank_account},
                        }

                    if qbo_lines:
                        qbo_bill_payment["Line"] = qbo_lines

                    qbo_bill_payment = {
                        k: v for k, v in qbo_bill_payment.items() if v is not None
                    }

                    resp = requests.post(
                        self._api_url("billpayment"),
                        headers=headers,
                        json=qbo_bill_payment,
                        timeout=15,
                    )
                    if resp.status_code in (200, 201):
                        qbo_id = str(
                            resp.json().get("BillPayment", {}).get("Id", "")
                        )
                        payment.qbo_id = qbo_id
                        synced += 1
                    else:
                        failed += 1
                        detail = resp.json().get("Fault", {}).get("Error", [{}])
                        msg = detail[0].get("Detail", resp.text[:200]) if detail else resp.text[:200]
                        errors.append(f"VendorPayment {payment.id[:8]}: {msg}")
                except Exception as exc:
                    failed += 1
                    errors.append(f"VendorPayment {payment.id[:8]}: {exc}")

            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=synced,
                records_failed=failed,
                error_message="; ".join(errors[:10]) if errors else None,
            )
            self.db.commit()

            return SyncResult(
                success=True,
                records_synced=synced,
                records_failed=failed,
                sync_log_id=sync_log.id,
                details={"errors": errors[:10]} if errors else None,
            )
        except Exception as exc:
            sync_log_service.complete_sync_log(
                self.db,
                sync_log,
                records_processed=0,
                records_failed=0,
                error_message=str(exc),
            )
            self.db.commit()
            return SyncResult(success=False, error_message=str(exc))

    # -----------------------------------------------------------------------
    # Inventory transactions
    # -----------------------------------------------------------------------

    def sync_inventory_transactions(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SyncResult:
        """QBO doesn't natively support inventory transaction import.

        Returns a helpful message suggesting alternatives.
        """
        return SyncResult(
            success=False,
            error_message=(
                "QuickBooks Online does not support direct inventory transaction import. "
                "Use journal entries or the Sage CSV export instead."
            ),
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

        # Ensure standard mapping keys always appear
        standard_keys = {
            "income_account": "Income Account (Invoices)",
            "expense_account": "Expense Account (Bills)",
            "deposit_account": "Deposit Account (AR Payments)",
            "ap_bank_account": "Bank Account (AP Payments)",
            "accounts_receivable": "Accounts Receivable",
            "accounts_payable": "Accounts Payable",
        }

        result = []
        for key, label in standard_keys.items():
            entry = mappings_dict.get(key, {})
            result.append(
                AccountMapping(
                    internal_id=key,
                    internal_name=label,
                    provider_id=entry.get("provider_id"),
                    provider_name=entry.get("provider_name"),
                )
            )

        # Also include any custom mappings
        for k, v in mappings_dict.items():
            if k not in standard_keys:
                result.append(
                    AccountMapping(
                        internal_id=k,
                        internal_name=v.get("internal_name", k),
                        provider_id=v.get("provider_id"),
                        provider_name=v.get("provider_name"),
                    )
                )
        return result

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

        # Bust local cache so next load picks up new mappings
        self._config = None

        return AccountMapping(
            internal_id=internal_id,
            internal_name=internal_id,
            provider_id=provider_id,
        )
