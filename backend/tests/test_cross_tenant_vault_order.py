"""Pin create_vault_order's INSERT against the live migration-built schema.

JCF-1 finding (2026-06-10): the INSERT was schema-drifted on 5 columns
(`order_number`/`source`/`customer_name`/`metadata`/`updated_at`) and the
except clause silently degraded EVERY cross-tenant auto-order to
{"status": "manual"} — a broken trigger masquerading as a live one. The
lesson registered: a "live path" claim requires a WITNESSED EFFECT, not
inspection of the plumbing. This test is that witness, permanently: it
calls the real function against the real schema and asserts the row
landed. The next schema drift fails HERE instead of hiding in the
except clause.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.funeral_case import CaseDeceased, CaseMerchandise, FuneralCase
from app.services.fh.cross_tenant_vault_service import (
    create_vault_order,
    sync_order_status,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _co(db, vertical):
    c = Company(
        id=str(uuid.uuid4()),
        name=f"PIN-{vertical}-{uuid.uuid4().hex[:6]}",
        slug=f"pin-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical=vertical,
    )
    db.add(c)
    db.commit()
    return c


def test_vault_order_insert_lands_a_real_row(db):
    fh = _co(db, "funeral_home")
    mfr = _co(db, "manufacturing")
    case = FuneralCase(
        id=str(uuid.uuid4()),
        company_id=fh.id,
        case_number=f"FC-{uuid.uuid4().hex[:8]}",
        vault_manufacturer_company_id=mfr.id,
    )
    db.add(case)
    db.commit()
    db.add(
        CaseDeceased(
            id=str(uuid.uuid4()),
            case_id=case.id,
            company_id=fh.id,
            first_name="Jane",
            last_name="Doe",
        )
    )
    db.add(
        CaseMerchandise(
            id=str(uuid.uuid4()),
            case_id=case.id,
            company_id=fh.id,
            vault_product_name="Monticello",
        )
    )
    db.commit()

    result = create_vault_order(db, case.id, fh.id)
    # THE WITNESS: a successful write, never "manual"/insert_failed.
    assert result["status"] == "ordered", result

    row = db.execute(
        sql_text(
            "SELECT company_id, number, status, order_type, deceased_name, "
            "notes FROM sales_orders WHERE id = :id"
        ),
        {"id": result["order_id"]},
    ).first()
    assert row is not None  # the row genuinely exists at the manufacturer
    assert row.company_id == mfr.id
    assert row.number == result["order_number"]
    assert row.status == "pending"
    assert row.order_type == "vault"
    assert row.deceased_name == "Jane Doe"
    assert fh.name in row.notes  # the ordering FH is legible on the order

    # The FH-side linkage updated (vault_order_id + status).
    db.refresh(
        db.query(CaseMerchandise)
        .filter(CaseMerchandise.case_id == case.id)
        .first()
    )
    merch = (
        db.query(CaseMerchandise)
        .filter(CaseMerchandise.case_id == case.id)
        .first()
    )
    assert merch.vault_order_id == result["order_id"]
    assert merch.vault_order_status == "pending"

    # Idempotency: re-calling reports already_ordered, no second row.
    again = create_vault_order(db, case.id, fh.id)
    assert again["status"] == "already_ordered"

    # The status BACK-SYNC witnessed too (the same class of claim): the
    # manufacturer updates their order; the FH case sees it.
    db.execute(
        sql_text("UPDATE sales_orders SET status='in_production' WHERE id=:id"),
        {"id": result["order_id"]},
    )
    db.commit()
    synced = sync_order_status(db, result["order_id"])
    assert synced["status"] == "synced", synced
    merch = (
        db.query(CaseMerchandise)
        .filter(CaseMerchandise.case_id == case.id)
        .first()
    )
    assert merch.vault_order_status == "in_production"
