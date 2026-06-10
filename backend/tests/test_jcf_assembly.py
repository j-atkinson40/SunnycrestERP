"""JCF-1 — THE ASSEMBLY TEST IN CODE (de-risk-then-render).

The phase's named proof: every cross-tenant seam of the canonical
scenario exercised server-side, end-to-end, before any UI exists —

  family approves vault at the FH → a REAL sales_order lands at the
  manufacturer (the EXISTING create_vault_order path, consumed not
  modified) → the JCF instance spawns for that job (order-launched,
  idempotent) → a FocusShare grants the FH director → the director READS
  the Focus + the composition template RESOLVES (the read-guard passes) →
  the manufacturer PROPOSES the pickup as a joint event and the FH
  FINALIZES it (the existing CrossTenantEventPairing lifecycle, service
  level) → both sides POST to the Focus-scoped thread → the job
  completes (the task-completion event family) → the instance closes and
  the share AUTO-REVOKES → the director's read now FAILS (the
  decision-bounded expiry proven, not assumed).

Plus the negative guards: no share → no read; revoked → no read; a third
tenant → never.

Unit coverage rides alongside: the grant lifecycle, the guard scopes,
thread auth, spawn idempotency.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.coordination_focus import FocusShare, FocusShareEvent
from app.models.funeral_case import CaseDeceased, CaseMerchandise, FuneralCase
from app.models.platform_tenant_relationship import PlatformTenantRelationship
from app.services import coordination_focus as jcf
from app.services.calendar.cross_tenant_pairing_service import (
    finalize_pairing,
    propose_pairing,
)
from app.services.fh.cross_tenant_vault_service import create_vault_order
from app.services.tasks.subscribers.registry import is_registered

from tests._calendar_step4_fixtures import make_account, make_event


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _mk_company(db, vertical: str) -> Company:
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"JCF-{vertical}-{suffix}",
        slug=f"jcf-{suffix}",
        is_active=True,
        vertical=vertical,
    )
    db.add(co)
    db.commit()
    return co


def _connect(db, a: Company, b: Company) -> PlatformTenantRelationship:
    rel = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        supplier_tenant_id=b.id,
        relationship_type="supplier",
        status="active",
    )
    db.add(rel)
    db.commit()
    return rel


def _land_vault_order(db, fh: Company, mfr: Company) -> str:
    """The EXISTING live path: a case with an approved vault fires a real
    sales_order at the manufacturer."""
    case = FuneralCase(
        id=str(uuid.uuid4()),
        company_id=fh.id,
        case_number=f"FC-{uuid.uuid4().hex[:8]}",
        vault_manufacturer_company_id=mfr.id,
    )
    db.add(case)
    db.commit()  # children reference the case by raw-FK column (no ORM
    # relationship edge), so the unit-of-work can't order the inserts —
    # land the parent first.
    db.add(
        CaseDeceased(
            id=str(uuid.uuid4()),
            case_id=case.id,
            company_id=fh.id,
            first_name="John",
            last_name="Smith",
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
    assert result["status"] == "ordered", result
    order_id = result["order_id"]
    owner = db.execute(
        sql_text("SELECT company_id FROM sales_orders WHERE id = :id"),
        {"id": order_id},
    ).scalar()
    assert owner == mfr.id  # the order genuinely landed at the manufacturer
    return order_id


@pytest.fixture
def world(db):
    fh = _mk_company(db, "funeral_home")
    mfr = _mk_company(db, "manufacturing")
    _connect(db, fh, mfr)
    order_id = _land_vault_order(db, fh, mfr)
    return {"fh": fh, "mfr": mfr, "order_id": order_id}


# ── Unit coverage ───────────────────────────────────────────────────


def test_spawn_is_idempotent_and_owner_scoped(db, world):
    i1 = jcf.ensure_instance_for_order(db, world["order_id"])
    i2 = jcf.ensure_instance_for_order(db, world["order_id"])
    assert i1.id == i2.id
    assert i1.company_id == world["mfr"].id  # owner = where the order landed
    assert i1.status == "active"


def test_grant_requires_active_relationship(db):
    fh = _mk_company(db, "funeral_home")
    mfr = _mk_company(db, "manufacturing")
    _connect(db, fh, mfr)
    order_id = _land_vault_order(db, fh, mfr)
    instance = jcf.ensure_instance_for_order(db, order_id)
    stranger = _mk_company(db, "cemetery")  # no relationship
    with pytest.raises(ValueError, match="relationship"):
        jcf.grant_share(db, instance, target_company_id=stranger.id)


def test_guard_scopes(db, world):
    instance = jcf.ensure_instance_for_order(db, world["order_id"])
    fh, mfr = world["fh"], world["mfr"]
    director = str(uuid.uuid4())
    other_user = str(uuid.uuid4())

    # Owner passes without any share.
    assert jcf.can_access(db, instance, company_id=mfr.id)
    # No share → the FH does NOT pass.
    assert not jcf.can_access(db, instance, company_id=fh.id, user_id=director)

    # Person-scoped share admits THAT user only.
    share = jcf.grant_share(
        db, instance, target_company_id=fh.id, target_user_id=director
    )
    assert jcf.can_access(db, instance, company_id=fh.id, user_id=director)
    assert not jcf.can_access(
        db, instance, company_id=fh.id, user_id=other_user
    )
    # A third tenant NEVER passes, share or no share.
    third = _mk_company(db, "crematory")
    assert not jcf.can_access(db, instance, company_id=third.id)

    # Explicit revoke fails closed.
    jcf.revoke_share(db, share, reason="test")
    assert not jcf.can_access(db, instance, company_id=fh.id, user_id=director)


def test_thread_auth_follows_the_guard(db, world):
    instance = jcf.ensure_instance_for_order(db, world["order_id"])
    fh, mfr = world["fh"], world["mfr"]
    director = str(uuid.uuid4())

    # Unshared FH user can neither post nor read.
    with pytest.raises(jcf.AccessDenied):
        jcf.post_message(
            db, instance.id, company_id=fh.id, user_id=director, body="hi"
        )
    with pytest.raises(jcf.AccessDenied):
        jcf.list_messages(db, instance.id, company_id=fh.id, user_id=director)

    jcf.grant_share(
        db, instance, target_company_id=fh.id, target_user_id=director
    )
    jcf.post_message(
        db, instance.id, company_id=fh.id, user_id=director, body="From FH"
    )
    msgs = jcf.list_messages(
        db, instance.id, company_id=fh.id, user_id=director
    )
    assert [m.body for m in msgs] == ["From FH"]
    assert msgs[0].author_company_id == fh.id


# ── THE ASSEMBLY E2E ────────────────────────────────────────────────


def test_assembly_e2e_canonical_scenario(db):
    """The canonical scenario, server-side, end-to-end."""
    # 1. The world: Hopkins-shaped FH + Sunnycrest-shaped manufacturer,
    #    connected; the family approves a vault.
    fh = _mk_company(db, "funeral_home")
    mfr = _mk_company(db, "manufacturing")
    _connect(db, fh, mfr)
    order_id = _land_vault_order(db, fh, mfr)  # the EXISTING live path

    # 2. The JCF instance spawns for THAT job (order-launched), bound to
    #    the job's task for decision-bounded closure.
    from app.models.vault import Vault
    from app.models.vault_item import VaultItem

    vault = Vault(
        id=str(uuid.uuid4()),
        company_id=mfr.id,
        vault_type="operational",
        name="JCF test vault",
    )
    db.add(vault)
    db.commit()
    task = VaultItem(
        id=str(uuid.uuid4()),
        vault_id=vault.id,
        company_id=mfr.id,
        item_type="task",
        title="Produce + deliver vault",
    )
    db.add(task)
    db.commit()
    instance = jcf.ensure_instance_for_order(db, order_id, task_id=task.id)
    assert instance.company_id == mfr.id

    # 3. FocusShare grants the Hopkins director (person-scoped).
    director = str(uuid.uuid4())
    share = jcf.grant_share(
        db, instance, target_company_id=fh.id, target_user_id=director,
        granted_by_user_id=None,
    )

    # 4. The director READS the Focus; the composition template RESOLVES.
    view = jcf.read_instance(
        db, instance.id, company_id=fh.id, user_id=director
    )
    assert view["is_owner"] is False
    assert view["instance"]["sales_order_id"] == order_id
    comp = view["composition"]
    assert comp is not None and comp["template_slug"] == "job-coordination"
    placed = [
        p["component_name"] for row in comp["rows"] for p in row["placements"]
    ]
    assert "vault_schedule" in placed and "calendar_summary" in placed
    # The cross-tenant read left an 'accessed' audit event.
    events = (
        db.query(FocusShareEvent)
        .filter(FocusShareEvent.share_id == share.id)
        .all()
    )
    assert {"granted", "accessed"}.issubset({e.event_type for e in events})

    # 5. The joint pickup event: the manufacturer PROPOSES, the FH
    #    FINALIZES — the EXISTING CrossTenantEventPairing lifecycle.
    mfr_account = make_account(db, mfr)
    fh_account = make_account(db, fh)
    mfr_event = make_event(db, mfr_account, is_cross_tenant=True)
    pairing = propose_pairing(
        db, initiating_event=mfr_event, partner_tenant_id=fh.id
    )
    assert pairing.paired_at is None  # pending bilateral acceptance
    fh_event = make_event(db, fh_account, is_cross_tenant=True)
    pairing = finalize_pairing(
        db, pairing=pairing, partner_event_id=fh_event.id
    )
    assert pairing.paired_at is not None and pairing.revoked_at is None

    # 6. Both sides post to the Focus-scoped thread.
    jcf.post_message(
        db, instance.id, company_id=mfr.id, user_id=str(uuid.uuid4()),
        body="Vault pours Thursday; pickup Friday 9am works.",
    )
    jcf.post_message(
        db, instance.id, company_id=fh.id, user_id=director,
        body="Confirmed — our driver will be there.",
    )
    msgs = jcf.list_messages(
        db, instance.id, company_id=fh.id, user_id=director
    )
    assert [m.author_company_id for m in msgs] == [mfr.id, fh.id]

    # 7. The job completes: the task-completion event family fires the
    #    jcf_closer sibling subscriber → the instance closes → the share
    #    AUTO-REVOKES.
    assert is_registered("jcf_closer")
    from app.services.tasks.subscribers import jcf_subscriber

    jcf_subscriber._handle(db, {"vault_item_id": task.id})
    db.refresh(instance)
    db.refresh(share)
    assert instance.status == "closed"
    assert share.revoked_at is not None
    assert share.revoke_reason == "job_completed"

    # 8. THE EXPIRY PROVEN: the director's read now FAILS.
    with pytest.raises(jcf.AccessDenied):
        jcf.read_instance(db, instance.id, company_id=fh.id, user_id=director)
    # The thread is sealed with the Focus.
    with pytest.raises(jcf.AccessDenied):
        jcf.list_messages(db, instance.id, company_id=fh.id, user_id=director)
    # The owner still sees the closed instance (their record of the job).
    owner_view = jcf.read_instance(db, instance.id, company_id=mfr.id)
    assert owner_view["instance"]["status"] == "closed"
