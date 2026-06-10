"""Cross-tenant vault order service — fires a sales_order on the manufacturer tenant.

When a family approves a vault in the Story step, create an order in the
manufacturer's Order table. The order appears in their Order Station exactly
like a regular order. customer is the funeral home. No phone call, no fax.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.funeral_case import (
    CaseDeceased,
    CaseMerchandise,
    CaseService as FHCaseService,
    FuneralCase,
    FuneralCaseNote,
)

logger = logging.getLogger(__name__)


def create_vault_order(db: Session, case_id: str, fh_company_id: str) -> dict:
    """Create a vault order in the manufacturer tenant's sales_orders table.

    Returns:
      {"status": "ordered", "order_id": "...", "manufacturer_id": "..."}
      or
      {"status": "manual", "reason": "no_manufacturer_connection"}
      or
      {"status": "already_ordered", "order_id": "..."}
    """
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case_id).first()
    if not merch or not merch.vault_product_name:
        return {"status": "manual", "reason": "no_vault_selected"}

    if merch.vault_order_id:
        return {"status": "already_ordered", "order_id": merch.vault_order_id}

    mfr_id = case.vault_manufacturer_company_id
    if not mfr_id:
        return {"status": "manual", "reason": "no_manufacturer_connection"}

    # Verify manufacturer exists
    mfr = db.query(Company).filter(Company.id == mfr_id).first()
    if not mfr:
        return {"status": "manual", "reason": "manufacturer_not_found"}

    # Build order payload on manufacturer tenant
    # We use a raw INSERT to avoid importing the heavy SalesOrder ORM graph here
    # and to tolerate different column sets across environments.
    dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case_id).first()
    svc = db.query(FHCaseService).filter(FHCaseService.case_id == case_id).first()

    deceased_name = " ".join([
        p for p in [dec.first_name if dec else None, dec.last_name if dec else None] if p
    ]) or "Cross-tenant case"

    personalization = dict(merch.vault_personalization or {})
    if dec:
        personalization.setdefault("name_display", deceased_name.upper())
        if dec.date_of_birth:
            personalization.setdefault("birth_date_display", dec.date_of_birth.isoformat())
        if dec.date_of_death:
            personalization.setdefault("death_date_display", dec.date_of_death.isoformat())

    order_id = str(uuid.uuid4())
    order_number = f"XT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{order_id[:8].upper()}"
    required_by = svc.service_date if svc and svc.service_date else None

    from sqlalchemy import text as sql_text
    # Minimal SalesOrder insert against the CANONICAL migration-built schema.
    # JCF-1 drift fix (2026-06-10): the original column list referenced
    # `order_number`, `source`, `customer_name`, `metadata`, `updated_at` —
    # none of which exist on sales_orders (the real columns: `number`;
    # sales_orders follows the older `modified_at` audit convention per
    # CLAUDE.md §5). The INSERT failed in EVERY migration-built environment
    # and the except clause silently degraded to {"status": "manual"} — the
    # cross-tenant auto-order never actually landed. Witnessed + pinned by
    # tests/test_cross_tenant_vault_order.py; the JCF assembly e2e consumes
    # the now-real write. Success-path return shape unchanged. The ordering
    # FH's name folds into `notes` (no customer_name column exists).
    fh_name = (
        db.query(Company.name).filter(Company.id == fh_company_id).scalar()
        or "Funeral Home"
    )
    try:
        # sales_orders.customer_id is NOT NULL — the order's customer IS the
        # funeral home (the docstring's contract). Find-or-create the FH as a
        # customer row at the MANUFACTURER tenant (idempotent on name).
        customer_id = db.execute(
            sql_text(
                "SELECT id FROM customers "
                "WHERE company_id = :mfr AND name = :name LIMIT 1"
            ),
            {"mfr": mfr_id, "name": fh_name},
        ).scalar()
        if customer_id is None:
            customer_id = str(uuid.uuid4())
            db.execute(
                sql_text(
                    "INSERT INTO customers (id, company_id, name) "
                    "VALUES (:id, :mfr, :name)"
                ),
                {"id": customer_id, "mfr": mfr_id, "name": fh_name},
            )
        db.execute(
            sql_text(
                """
                INSERT INTO sales_orders (
                    id, company_id, customer_id, number, status, order_type,
                    order_date, deceased_name, required_date, notes,
                    created_at, modified_at
                ) VALUES (
                    :id, :company_id, :customer_id, :number, 'pending', 'vault',
                    now(), :deceased_name, :required_date, :notes,
                    now(), now()
                )
                """
            ),
            {
                "id": order_id,
                "company_id": mfr_id,
                "customer_id": customer_id,
                "number": order_number,
                "deceased_name": deceased_name,
                "required_date": required_by,
                "notes": f"Cross-tenant order from {fh_name} "
                         f"(Bridgeable FH case {case.case_number}). "
                         f"Product: {merch.vault_product_name}. "
                         f"Personalization: {personalization}.",
            },
        )
    except Exception as e:
        # Graceful degrade to "manual" is correct production behavior —
        # family approval must never crash on an order insert — but it must
        # degrade LOUDLY: this silent path masked a schema-drifted INSERT
        # for months (JCF-1 finding). The case note alone proved
        # insufficient observability; the logged exception is the signal.
        logger.exception(
            "[cross_tenant_vault] order INSERT failed for case %s -> "
            "manufacturer %s; degrading to manual",
            case_id,
            mfr_id,
        )
        db.add(FuneralCaseNote(
            id=str(uuid.uuid4()),
            case_id=case_id,
            company_id=fh_company_id,
            note_type="system",
            content=f"Cross-tenant vault order could not be created: {str(e)[:300]}. Treating as manual.",
        ))
        db.commit()
        return {"status": "manual", "reason": "insert_failed", "error": str(e)[:200]}

    # Update case_merchandise
    merch.vault_order_id = order_id
    merch.vault_order_status = "pending"

    # Note on FH side
    db.add(FuneralCaseNote(
        id=str(uuid.uuid4()),
        case_id=case_id,
        company_id=fh_company_id,
        note_type="system",
        content=f"Cross-tenant vault order {order_number} sent to {mfr.name}. Status: pending.",
    ))

    db.commit()
    return {
        "status": "ordered",
        "order_id": order_id,
        "order_number": order_number,
        "manufacturer_id": mfr_id,
        "manufacturer_name": mfr.name,
    }


def sync_order_status(db: Session, order_id: str) -> dict:
    """Sync a manufacturer-side sales_orders status back to case_merchandise.

    Called by the manufacturer when they update their local order. Finds the
    case_merchandise row by vault_order_id and copies status across.
    """
    from sqlalchemy import text as sql_text

    merch = (
        db.query(CaseMerchandise)
        .filter(CaseMerchandise.vault_order_id == order_id)
        .first()
    )
    if not merch:
        return {"status": "not_found"}

    row = db.execute(
        sql_text("SELECT status FROM sales_orders WHERE id = :id"),
        {"id": order_id},
    ).fetchone()
    if not row:
        return {"status": "order_not_found"}

    new_status = row[0]
    if merch.vault_order_status != new_status:
        merch.vault_order_status = new_status
        # Note on FH side
        db.add(FuneralCaseNote(
            id=str(uuid.uuid4()),
            case_id=merch.case_id,
            company_id=merch.company_id,
            note_type="system",
            content=f"Vault order status updated: {new_status}",
        ))
        db.commit()
    return {"status": "synced", "vault_order_status": new_status}
