"""A vault resolved through its LINKED VARIANT must not crash the read.

James's walk, 2026-11-03, session 8a3ea0aa on sunnycrest: the pane showed only "The
order did not reach the server" and every captured field vanished from the screen.

⚠️ THE SERVER CAUSE, MEASURED ON PRODUCTION RATHER THAN INFERRED:

    AttributeError: 'NoneType' object has no attribute 'variant_template_id'
    session_service.read_state  ->  "resolved": bool(resolution.variant_template_id)

`evaluate_typed` sets `resolution = None` and only builds one in its ELSE branch:

    resolution = None
    if linked is not None:          # products.variant_template_id is populated
        vault_product_id = linked.variant_template_id
    else:
        resolution = resolve_vault(build_index(db), phrase or None)

So `resolution is None` is exactly `linked is not None` — the vault IS resolved, by the
stronger of the two paths — and `read_state` dereferenced it anyway. Every read of such
a session returned 500, so the pane could not recover by retrying either.

⚠️ A LATENT BUG ARMED BY DATA, NOT BY CODE. Both lines predate the walk. The linked
path was unreachable while nothing was linked — CLAUDE.md still records
`products.variant_template_id` as "populated on 0 of 39 rows" on sunnycrest. Measured
on production 2026-11-03: **3 of 11**, one of them `Monticello Burial Vault`, the
product James typed. The catalogue work armed it; he was the first to walk into it.

⚠️ AND THE ORDER WAS NEVER LOST. After the crash the session still held
`{vault, funeral_home, cemetery_equipment}`. The pane discarded the SCREEN, which is
the separate defect the keep-the-last-good-state ruling fixes.
"""
import os
from urllib.parse import urlparse

import pytest
from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture import session_service


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture(scope="module")
def db():
    _local_only()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def world(db):
    tid = db.execute(sql("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    if not tid:
        pytest.skip("no testco tenant")
    uid = db.execute(
        sql("SELECT id FROM users WHERE company_id = :t LIMIT 1"), {"t": tid}
    ).scalar()
    if not uid:
        pytest.skip("no user on testco")
    return tid, uid


@pytest.fixture
def vault_is_linked(monkeypatch):
    """Make the vault resolve through its tenant link, as sunnycrest's now does.

    ⚠️ IT RETURNS A REAL `VaultVariant`, AND MY FIRST VERSION HAND-ROLLED A STUB WITH
    `variant_template_id` AND `form` ONLY. That raised
    `AttributeError: '_Linked' object has no attribute 'via'` — because the branch is
    `if linked.via is not None`, not `if linked is not None`. A fixture built from what
    I assumed the shape was, rather than from the type the function returns, which is
    the "fixtures modelled on the implementation" trap in its most ordinary form. The
    stub failed loudly here; the same guess in a test asserting a refusal would have
    passed.

    ⚠️ STUBBED RATHER THAN SEEDED, so the test does not depend on which catalogue rows
    happen to be linked locally. The production arming condition is DATA — 3 of 11 rows
    — and a test needing that data would pass or fail by accident.
    """
    from app.services.capture.vault_form import VIA_TENANT_LINK, VaultVariant

    linked = VaultVariant(
        "8a3c6253-7de4-5dac-8d6b-7071f63d13ec", "burial_vault", VIA_TENANT_LINK
    )
    monkeypatch.setattr(
        "app.services.capture.vault_form.linked_variant",
        lambda db, *, tenant_id, vault: linked,
    )


def test_read_state_does_not_RAISE_for_a_linked_vault(db, world, vault_is_linked):
    """⚠️ THE REGRESSION, AND IT IS A CRASH RATHER THAN A WRONG VALUE. Before the fix
    this raised `AttributeError`, which FastAPI turns into a 500 — so the pane's only
    recourse was the error state, and a retry would have hit the same 500."""
    tid, uid = world
    row = session_service.start(db, company_id=tid, user_id=uid)
    session_service.set_text(
        db, row.id, company_id=tid, user_id=uid, text="monticello burial vault"
    )
    state = session_service.read_state(db, row.id, company_id=tid, user_id=uid)
    assert state["vault_resolution"]["resolved"] is True


def test_the_captured_VALUES_survive_a_linked_vault(db, world, vault_is_linked):
    """⚠️ THE HALF THAT MATTERS TO THE DIRECTOR. The crash was in the serializer, so
    everything it was about to report was already correct — which is why James's
    session still held all three values after his pane went blank."""
    tid, uid = world
    row = session_service.start(db, company_id=tid, user_id=uid)
    session_service.set_text(
        db, row.id, company_id=tid, user_id=uid, text="monticello burial vault"
    )
    state = session_service.read_state(db, row.id, company_id=tid, user_id=uid)
    assert state["values"].get("vault")


def test_the_UNLINKED_path_still_reports_its_candidates(db, world):
    """⚠️ THE CONTROL. Without it the fix could have hard-coded `resolved: True` for
    every vault, and the ambiguous case — two candidates, no pick yet — would silently
    read as settled. No stub here: this is the path the resolver actually builds."""
    tid, uid = world
    row = session_service.start(db, company_id=tid, user_id=uid)
    session_service.set_text(
        db, row.id, company_id=tid, user_id=uid, text="order for hopkins"
    )
    state = session_service.read_state(db, row.id, company_id=tid, user_id=uid)
    vr = state["vault_resolution"]
    # No vault typed, so the resolver ran and found nothing resolved.
    assert vr["resolved"] is False
    assert isinstance(vr["candidates"], list)
