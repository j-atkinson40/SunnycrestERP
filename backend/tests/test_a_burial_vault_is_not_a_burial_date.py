"""The word "burial" appears in the product name, and it used to eat the burial date.

⚠️ FOUND 2026-10-13 WHILE BUILDING APPROVE, AND IT MADE A COMPLETE ORDER
IMPOSSIBLE. `burial_date` is REQUIRED on the template, so review — and therefore
Approve — is unreachable without it. The marker was:

    re.search(r"\\b(?:burial|interment|graveside)\\s+(?:is\\s+|on\\s+|:\\s*)?(.{3,30})", ...)

and the phrase every director types is "monticello BURIAL VAULT". So the marker
matched inside the PRODUCT NAME, took the next 30 characters ("vault Mary Smith 1948
to 2026" or whatever followed), handed that to `parse_date`, got nothing — and
because the field is wrapped in `once()`, the real "burial thursday 11am" later in
the same sentence was never tried.

⚠️ THE 30-CHARACTER RUN IS THE THIRD INSTANCE OF ONE DEFECT IN THIS FILE.
`_CEM_TOWN` carried `[A-Za-z'\\-. ]{2,30}` and ran across word boundaries until it
was word-bounded on 2026-10-13; its duplicate inline copy carried the same flaw.
A character count cannot find the end of a clause in comma-free text.

⚠️ AND THE SYMPTOM POINTED SOMEWHERE ELSE ENTIRELY. What you see is `service_date`
holding the burial day and `burial_date` empty, because the generic date fallback
picks up what this pass failed to claim. The field that looks wrong is not the field
that is broken.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import extract_text


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def tenant(db) -> str:
    tid = db.execute(text("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    assert tid, "testco is not seeded — run scripts/seed_dev.sh"
    return tid


def test_the_product_name_does_not_consume_the_burial_date(db, tenant):
    """⚠️ THE EXACT PHRASING FROM THE WALK, AND THE REGRESSION TEST FOR THE DEFECT."""
    ex = extract_text(
        db,
        tenant_id=tenant,
        text="order for riverside monticello burial vault burial thursday 11am",
    )
    assert ex.values.get("burial_date"), (
        f"the burial date was eaten by 'burial vault': {ex.values}"
    )


def test_the_vault_still_resolves_from_the_same_phrase(db, tenant):
    # ⚠️ THE POSITIVE CONTROL. A fix that stopped the marker matching "burial vault"
    # by claiming those words for the date would break the product resolution.
    ex = extract_text(
        db,
        tenant_id=tenant,
        text="order for riverside monticello burial vault burial thursday 11am",
    )
    assert ex.values.get("vault") == "Monticello Burial Vault", ex.values


@pytest.mark.parametrize(
    "phrase",
    [
        "monticello burial vault burial thursday 11am",
        "burial thursday 11am monticello burial vault",
        "monticello urn vault burial thursday 11am",
        "veteran burial vault interment thursday 11am",
        "monticello burial vaults burial thursday 11am",
    ],
)
def test_the_date_survives_whatever_order_the_words_come_in(db, tenant, phrase):
    # ⚠️ "burial vaultS" IS IN THE LIST DELIBERATELY. A lookahead written `(?!vault\\b)`
    # passes on the plural — `\\b` fails between "vault" and "s" — so the plural would
    # still eat the date. It has to be `vaults?\\b`.
    ex = extract_text(db, tenant_id=tenant, text=f"order for riverside {phrase}")
    assert ex.values.get("burial_date"), (phrase, ex.values)


@pytest.mark.parametrize(
    "middle",
    [
        "Mary Smith 1948 to 2026",
        "Mary Smith 1948 to 2026 section 4 lot 12",
        "Mary Smith",
        "Mary Smith 1948 to 2026 going to oakwood",
    ],
)
def test_WHAT_FOLLOWS_THE_PRODUCT_NAME_DOES_NOT_DECIDE_IT(db, tenant, middle):
    """The reproducing cases, and the reason the short ones passed all along.

    ⚠️ THE OLD MARKER WORKED BY LUCK AND THE LUCK WAS THE SENTENCE LENGTH. Its tail
    was a fixed 30-CHARACTER window after the first "burial" it found — which is the
    one inside "monticello burial vault". In a short sentence that window happened to
    reach the real clause:

        'vault burial thursday 11am'          -> parse_date gives 2026-10-15

    Put a decedent between them and the window falls short:

        'vault Mary Smith 1948 to 2026 '      -> parse_date gives None

    and because the field is wrapped in `once()`, the real "burial thursday 11am"
    further along was never tried. Every test above this one passed against the
    defect for exactly this reason, which is why these cases exist.
    """
    ex = extract_text(
        db,
        tenant_id=tenant,
        text=(
            f"order for riverside monticello burial vault {middle} "
            f"burial thursday 11am"
        ),
    )
    assert ex.values.get("burial_date"), (middle, ex.values)


def test_a_sentence_with_no_burial_clause_captures_no_burial_date(db, tenant):
    # ⚠️ THE NEGATIVE CONTROL. A fix that made the marker looser could start reading
    # the product name itself as a date.
    ex = extract_text(
        db, tenant_id=tenant, text="order for riverside monticello burial vault"
    )
    assert ex.values.get("burial_date") is None, ex.values


def test_the_burial_and_service_dates_are_different_days_when_said_so(db, tenant):
    # ⚠️ THE WHOLE REASON `burial_date` HAS ITS OWN MARKER: burial and service are
    # different days. The defect put the burial day into `service_date`, which is
    # the shape that made it look like a service-date problem.
    ex = extract_text(
        db,
        tenant_id=tenant,
        text=(
            "order for riverside monticello burial vault burial friday 11am "
            "service at the church thursday 10am"
        ),
    )
    assert ex.values.get("burial_date"), ex.values
    assert ex.values.get("service_date"), ex.values
    assert ex.values["burial_date"] != ex.values["service_date"], ex.values
