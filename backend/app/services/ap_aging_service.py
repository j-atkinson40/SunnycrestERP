"""AP Aging calculation service."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill


def get_ap_aging(
    db: Session, company_id: str, as_of_date: datetime | None = None
) -> list[dict]:
    """
    Calculate AP aging buckets per vendor.
    Returns list of dicts: { vendor_id, vendor_name, current, d1_30, d31_60, d61_90, d90_plus, total }
    """
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc)

    bills = (
        db.query(VendorBill)
        .options(joinedload(VendorBill.vendor))
        .filter(
            VendorBill.company_id == company_id,
            VendorBill.deleted_at.is_(None),
            VendorBill.status.in_(["pending", "approved", "partial"]),
        )
        .all()
    )

    vendor_buckets: dict[str, dict] = {}
    zero = Decimal("0.00")

    for bill in bills:
        balance = bill.balance_remaining
        if balance <= zero:
            continue

        vid = bill.vendor_id
        if vid not in vendor_buckets:
            vendor_buckets[vid] = {
                "vendor_id": vid,
                "vendor_name": bill.vendor.name if bill.vendor else "Unknown",
                "current": zero,
                "d1_30": zero,
                "d31_60": zero,
                "d61_90": zero,
                "d90_plus": zero,
                "total": zero,
            }

        days_past = (as_of_date - bill.due_date).days if bill.due_date else 0

        bucket = vendor_buckets[vid]
        if days_past <= 0:
            bucket["current"] += balance
        elif days_past <= 30:
            bucket["d1_30"] += balance
        elif days_past <= 60:
            bucket["d31_60"] += balance
        elif days_past <= 90:
            bucket["d61_90"] += balance
        else:
            bucket["d90_plus"] += balance

        bucket["total"] += balance

    return sorted(vendor_buckets.values(), key=lambda v: v["total"], reverse=True)
