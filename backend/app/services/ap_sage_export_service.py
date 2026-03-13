"""Sage 100 CSV export for AP bills and payments."""

import csv
import io
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill
from app.models.vendor_bill_line import VendorBillLine
from app.models.vendor_payment import VendorPayment
from app.models.vendor_payment_application import VendorPaymentApplication
from app.services import audit_service, sync_log_service


# Map payment methods to Sage-friendly codes
_SAGE_PAYMENT_METHOD_MAP = {
    "check": "CHK",
    "ach": "ACH",
    "wire": "WIR",
    "credit_card": "CC",
    "cash": "CSH",
}


def generate_bills_csv(
    db: Session,
    company_id: str,
    date_from: datetime,
    date_to: datetime,
    actor_id: str | None = None,
) -> tuple[str, int, str]:
    """Generate a Sage 100-compatible CSV from vendor bills.

    Returns (csv_string, record_count, sync_log_id).
    """
    sync_log = sync_log_service.create_sync_log(
        db,
        company_id,
        sync_type="ap_bill_sage_export",
        source="vendor_bills",
        destination="sage_csv",
    )

    try:
        bills = (
            db.query(VendorBill)
            .options(
                joinedload(VendorBill.vendor),
                joinedload(VendorBill.lines),
            )
            .filter(
                VendorBill.company_id == company_id,
                VendorBill.bill_date >= date_from,
                VendorBill.bill_date <= date_to,
                VendorBill.deleted_at.is_(None),
            )
            .order_by(VendorBill.bill_date)
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Bill Number",
            "Vendor ID",
            "Vendor Name",
            "Invoice Number",
            "Bill Date",
            "Due Date",
            "Line Description",
            "Line Amount",
            "Tax Amount",
            "Bill Total",
            "Status",
        ])

        record_count = 0
        for bill in bills:
            vendor_name = bill.vendor.name if bill.vendor else ""
            sage_vendor_id = ""
            if bill.vendor and bill.vendor.sage_vendor_id:
                sage_vendor_id = bill.vendor.sage_vendor_id
            elif bill.vendor and bill.vendor.account_number:
                sage_vendor_id = bill.vendor.account_number

            active_lines = [l for l in (bill.lines or []) if l.deleted_at is None]
            if active_lines:
                for line in active_lines:
                    writer.writerow([
                        bill.number,
                        sage_vendor_id,
                        vendor_name,
                        bill.vendor_invoice_number or "",
                        bill.bill_date.strftime("%m/%d/%Y"),
                        bill.due_date.strftime("%m/%d/%Y") if bill.due_date else "",
                        line.description,
                        f"{float(line.amount):.2f}",
                        f"{float(bill.tax_amount):.2f}",
                        f"{float(bill.total):.2f}",
                        bill.status,
                    ])
                    record_count += 1
            else:
                # Bill with no lines — export as a single row
                writer.writerow([
                    bill.number,
                    sage_vendor_id,
                    vendor_name,
                    bill.vendor_invoice_number or "",
                    bill.bill_date.strftime("%m/%d/%Y"),
                    bill.due_date.strftime("%m/%d/%Y") if bill.due_date else "",
                    "",
                    f"{float(bill.subtotal):.2f}",
                    f"{float(bill.tax_amount):.2f}",
                    f"{float(bill.total):.2f}",
                    bill.status,
                ])
                record_count += 1

        csv_string = output.getvalue()

        sync_log_service.complete_sync_log(
            db, sync_log, records_processed=record_count, records_failed=0
        )
        audit_service.log_action(
            db,
            company_id,
            "exported",
            "ap_bill_sage_csv",
            sync_log.id,
            user_id=actor_id,
            changes={"records": {"old": None, "new": record_count}},
        )
        db.commit()
        return csv_string, record_count, sync_log.id

    except Exception as exc:
        sync_log_service.complete_sync_log(
            db, sync_log, records_processed=0, records_failed=0,
            error_message=str(exc),
        )
        db.commit()
        raise


def generate_payments_csv(
    db: Session,
    company_id: str,
    date_from: datetime,
    date_to: datetime,
    actor_id: str | None = None,
) -> tuple[str, int, str]:
    """Generate a Sage 100-compatible CSV from vendor payments.

    Returns (csv_string, record_count, sync_log_id).
    """
    sync_log = sync_log_service.create_sync_log(
        db,
        company_id,
        sync_type="ap_payment_sage_export",
        source="vendor_payments",
        destination="sage_csv",
    )

    try:
        payments = (
            db.query(VendorPayment)
            .options(
                joinedload(VendorPayment.vendor),
                joinedload(VendorPayment.applications).joinedload(
                    VendorPaymentApplication.bill
                ),
            )
            .filter(
                VendorPayment.company_id == company_id,
                VendorPayment.payment_date >= date_from,
                VendorPayment.payment_date <= date_to,
                VendorPayment.deleted_at.is_(None),
            )
            .order_by(VendorPayment.payment_date)
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Payment Date",
            "Vendor ID",
            "Vendor Name",
            "Payment Method",
            "Reference Number",
            "Bill Number",
            "Amount Applied",
            "Payment Total",
        ])

        record_count = 0
        for payment in payments:
            vendor_name = payment.vendor.name if payment.vendor else ""
            sage_vendor_id = ""
            if payment.vendor and payment.vendor.sage_vendor_id:
                sage_vendor_id = payment.vendor.sage_vendor_id
            elif payment.vendor and payment.vendor.account_number:
                sage_vendor_id = payment.vendor.account_number

            sage_method = _SAGE_PAYMENT_METHOD_MAP.get(
                payment.payment_method, payment.payment_method[:3].upper()
            )

            for app in (payment.applications or []):
                bill_number = app.bill.number if app.bill else ""
                writer.writerow([
                    payment.payment_date.strftime("%m/%d/%Y"),
                    sage_vendor_id,
                    vendor_name,
                    sage_method,
                    payment.reference_number or "",
                    bill_number,
                    f"{float(app.amount_applied):.2f}",
                    f"{float(payment.total_amount):.2f}",
                ])
                record_count += 1

        csv_string = output.getvalue()

        sync_log_service.complete_sync_log(
            db, sync_log, records_processed=record_count, records_failed=0
        )
        audit_service.log_action(
            db,
            company_id,
            "exported",
            "ap_payment_sage_csv",
            sync_log.id,
            user_id=actor_id,
            changes={"records": {"old": None, "new": record_count}},
        )
        db.commit()
        return csv_string, record_count, sync_log.id

    except Exception as exc:
        sync_log_service.complete_sync_log(
            db, sync_log, records_processed=0, records_failed=0,
            error_message=str(exc),
        )
        db.commit()
        raise


def get_ap_export_history(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Get paginated list of AP sage export sync logs."""
    from app.models.sync_log import SyncLog

    query = db.query(SyncLog).filter(
        SyncLog.company_id == company_id,
        SyncLog.sync_type.in_(["ap_bill_sage_export", "ap_payment_sage_export"]),
    )
    total = query.count()
    items = (
        query.order_by(SyncLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}
