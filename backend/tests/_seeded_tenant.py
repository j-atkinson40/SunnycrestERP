"""The shared fixture for tests that need a tenant with a REAL catalog.

⚠️ ITS SCOPE IS NARROWER THAN THE REASON IT WAS ORDERED, AND THE FIRST DRAFT OF THIS
DOCSTRING GOT IT WRONG. It claimed a bare tenant made the whole availability layer
unreachable and that all five of the 2026-10-12 live defects lived there. Measured
afterwards, on a tenant consisting of one `companies` row and nothing else:

    catalog index + 56 aliases .......... reachable  (platform-level, not tenant)
    "Continental 34" resolves ........... yes
    availability config ................. present, narrows to ['nameplate_only']
    the conflict behind the HTTP 500 .... arises
    cemeteries .......................... 0   <- the ONLY thing missing

The catalog, the alias table and the availability config are PLATFORM-level. A bare
tenant inherits all three. **Four of the five defects were reachable without this
fixture.** What hid them was that no session test ever typed a phrase resolving a
vault to ONE variant — the inputs were `tent only`, `nameplate only`, `years only`,
`full setup`, and `Continental`, which is ambiguous and yields a pick. The
conditional layer was never entered, whatever the tenant held.

⚠️ SO THIS FIXTURE IS LOAD-BEARING FOR EXACTLY ONE DEFECT — the cemetery name that
overwrote the decedent, which needs a seeded cemetery to match. Demonstrated: on a
bare tenant that test is RED BEFORE ANYTHING IS BROKEN, so it is saturated there and
reports the same result whether the defect is present or not.

    1  UnpermittedAnswer raised into HTTP 500          reachable on a bare tenant
    2  the withheld answer was still rendered          reachable on a bare tenant
    3  rows read "not configured" over real values     reachable on a bare tenant
    4  a cemetery name overwrote the decedent          NEEDS THIS FIXTURE
    5  "cross" captured as nothing, reported unplaced  reachable on a bare tenant

⚠️ IT IS KEPT ANYWAY, FOR A STATED REASON RATHER THAN THE ORDERED ONE. The four
assertions below are a tripwire on the ENVIRONMENT, which is the thing nobody was
checking; cemetery matching is where a whole class of director phrasing lives; and
the platform/tenant split measured above is not guaranteed to hold — if availability
or aliases ever become tenant-scoped, every test on a bare tenant goes quietly blind
and this fixture is what would notice.

See `docs/investigations/2026-10-12-the-bare-tenant-gap.md`.

⚠️ THE FIXTURE ASSERTS BEHAVIOUR, NOT ROW COUNTS, AND THAT IS WHAT IT IS ACTUALLY
FOR. A fixture that merely resolved `testco` and handed back its id would be the same
blindness one level up: the tenant could lose its catalog, or availability could stop narrowing,
and every test depending on it would go green while measuring nothing. So
`seeded_tenant` proves, on every use, that

    a vault RESOLVES to exactly one variant,
    availability NARROWS a conditional question to a real permitted set,
    an ALIAS resolves to a variant it does not name literally,
    and a CEMETERY exists to be matched.

If any of those stops being true the fixture fails loudly with the reason, rather
than letting the suite report a result about a world it is not in.

⚠️ IT REFUSES TO SKIP. A `pytest.skip` when `testco` is absent would restore exactly
the condition this module was written to end — a green run that tested nothing. The
assertion names `scripts/seed_dev.sh`, which is the one command that produces a
complete database (CLAUDE.md §7).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

#: The canonical manufacturing dev tenant (CLAUDE.md §7, "Canonical development
#: tenants"). ⚠️ NOT Sunnycrest — that is the real company and is deliberately not a
#: dev tenant.
SEEDED_SLUG = "testco"

#: ⚠️ A VAULT THAT RESOLVES TO EXACTLY ONE VARIANT AND WHOSE AVAILABILITY EXCLUDES
#: SOMETHING. Measured: the Continental 34" permits `nameplate_only` alone, which is
#: what makes it the vault the conflict defect reproduces on.
NARROW_VAULT = "Continental 34"

#: ⚠️ A VAULT THAT PERMITS VINYL. Measured. The symbol tests need availability to
#: ALLOW the thing, not refuse it, or they measure a refusal instead of a symbol.
VINYL_VAULT = "Bronze Triune Burial Vault"

#: ⚠️ AN ALIAS, NOT A NAME. `oversized` appears in no product name — it resolves only
#: through `platform_product_aliases`, so it proves the alias table is loaded rather
#: than that the catalog is.
ALIAS_PHRASE = "oversized"

#: A seeded cemetery whose stored name carries punctuation a director will not type.
SEEDED_CEMETERY = "St. Mary's Cemetery"


@dataclass(frozen=True)
class SeededTenant:
    """What a test needs to drive capture against a real tenant."""

    company_id: str
    user_id: str


def assert_the_world_is_real(db: Session, company_id: str) -> None:
    """Prove the four facts every one of the five defects depended on.

    ⚠️ CALLED BY THE FIXTURE ON EVERY USE, not once at import. A session that
    rolled back a seed, or a database rebuilt halfway, is exactly when a test most
    needs to be told it is not in the world it thinks it is.
    """
    from app.services.capture.typed_extraction import evaluate_typed
    from app.services.party_resolver import cemetery_rows
    from app.services.personalization.enrollment import resolve_availability_config
    from app.services.product_name_resolver import build_index
    from app.services.product_name_resolver import resolve as resolve_vault

    index = build_index(db)

    # 1 — a vault resolves to exactly one variant
    r = resolve_vault(index, NARROW_VAULT)
    assert r.variant_template_id, (
        f"{NARROW_VAULT!r} does not resolve on this database, so no availability can "
        f"narrow and the whole conditional layer is unreachable — run "
        f"scripts/seed_dev.sh"
    )

    # 2 — the alias table is loaded
    assert index.alias_count > 0, (
        "platform_product_aliases is empty; alias-only phrases cannot resolve"
    )
    alias = resolve_vault(index, ALIAS_PHRASE)
    assert alias.candidates, (
        f"{ALIAS_PHRASE!r} matched nothing — it appears in no product NAME, so this "
        f"is the alias table being absent rather than the catalog"
    )

    # 3 — availability narrows a conditional question to a REAL permitted set
    cfg = resolve_availability_config(db, company_id)
    assert cfg is not None, "no personalization availability config for this tenant"
    _, state, _ = evaluate_typed(
        db, tenant_id=company_id, answers={"vault": NARROW_VAULT}
    )
    by_id = {f.field_id: f for f in state.resolved_fields}
    pers = by_id.get("personalization")
    assert pers is not None, (
        "the personalization field is not applicable even with a resolved vault — "
        "availability is not reaching capture"
    )
    assert pers.permitted_answers, (
        f"availability permitted NOTHING for {NARROW_VAULT!r}. An empty permitted set "
        f"makes `_reject_unpermitted` return early by design, which is precisely the "
        f"blindness this fixture exists to end"
    )

    # 4 — a cemetery exists to be matched
    names = {n for _i, n, _c in cemetery_rows(db, company_id)}
    assert SEEDED_CEMETERY in names, (
        f"{SEEDED_CEMETERY!r} is not among this tenant's cemeteries ({sorted(names)})"
    )


def resolve_seeded_tenant(db: Session) -> str:
    company_id = db.execute(
        text("SELECT id FROM companies WHERE slug = :s"), {"s": SEEDED_SLUG}
    ).scalar()
    assert company_id, (
        f"the {SEEDED_SLUG!r} tenant is not seeded. These tests MUST NOT skip — a "
        f"green run against a bare database is what let five live defects through. "
        f"Run `bash backend/scripts/seed_dev.sh`."
    )
    return company_id


@pytest.fixture
def seeded(db) -> SeededTenant:
    """A tenant with the real catalog, availability and aliases, plus a fresh user.

    ⚠️ A FRESH USER INSIDE A SAVEPOINT, NOT THE SEEDED ADMIN. Capture sessions are
    scoped to `(company_id, user_id)`, and reusing the seeded admin would let one
    test's half-typed order be visible to another's read. The user is created and
    rolled back; the tenant's catalog is left alone.

    ⚠️ THE SAVEPOINT ROLLS BACK, SO NOTHING THIS FIXTURE WRITES SURVIVES. The seeded
    catalog is READ, never modified — a test that mutated it would change the world
    every later test is asserting against.
    """
    company_id = resolve_seeded_tenant(db)
    assert_the_world_is_real(db, company_id)

    from app.models.role import Role
    from app.models.user import User

    sp = db.begin_nested()
    try:
        role_id = db.execute(
            text("SELECT id FROM roles WHERE company_id = :c LIMIT 1"),
            {"c": company_id},
        ).scalar()
        if role_id is None:
            role_id = str(uuid.uuid4())
            db.add(Role(id=role_id, company_id=company_id, name="Admin", slug="admin"))
            db.flush()
        user_id = str(uuid.uuid4())
        db.add(
            User(
                id=user_id,
                company_id=company_id,
                email=f"{user_id[:8]}@capture-tests.example.com",
                hashed_password="x",
                first_name="Capture",
                last_name="Test",
                role_id=role_id,
                is_active=True,
            )
        )
        db.flush()
        yield SeededTenant(company_id=company_id, user_id=user_id)
    finally:
        sp.rollback()
