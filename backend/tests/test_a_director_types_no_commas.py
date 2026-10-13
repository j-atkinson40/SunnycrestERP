"""Run-on text. A director types no punctuation, and nothing may be lost.

⚠️ EVERY SENTENCE IN EVERY OTHER EXTRACTION TEST HAD COMMAS, AND THAT IS WHY THIS
SHIPPED BROKEN. Measured 2026-10-13 by re-running every comma-bearing input from the
extraction suites with its commas removed: **5 of 34 real sentences lost fields**,
and the one James hit lost the funeral home one keystroke after capturing it.

THREE DEFECTS, all the same shape — a span bounded by something other than what it is
matching, which a comma used to hide:

    the FUNERAL-HOME marker   took up to four words after "for" and handed the whole
                              run to the resolver. "order for hopkins continental"
                              asked for "hopkins continental", resolved nothing,
                              claimed nothing, and LOST the funeral home captured a
                              keystroke earlier — taking the vault with it, because
                              "continental" was left glued behind "hopkins".
                              FIXED: longest prefix that resolves.

    the VAULT pass            resolved the WHOLE unclaimed slice as one phrase. As
                              the sentence grew, "continental 34 mary" stopped
                              matching and the vault was LOST.
                              FIXED: an n-gram scan, longest-first, like the party
                              passes already did.

    the CEMETERY TOWN         was a 30-CHARACTER run with a space in its character
                              class, so it crossed word boundaries and stopped
                              wherever character 30 fell — mid-word. It claimed 43
                              characters of "st marys in auburn service at the church
                              thursday 10am" and reported **'ursday'** as unplaceable.
                              ⚠️ AND THERE WERE TWO COPIES of that pattern: a fix
                              landed on the named constant on 2026-10-12 and an
                              inline duplicate in the record-lookup pass kept the old
                              one. FIXED: one pattern, word-bounded, narrowed by the
                              towns we hold records for.

⚠️ THE MONOTONICITY TEST BELOW IS THE ONE THAT WOULD HAVE CAUGHT ALL THREE. Asserting
the final result of a sentence cannot see a field that appears and then vanishes;
only walking every prefix can. It is also exactly what the director experiences,
because the pane re-reads on every pause while they are still typing.

⚠️ REQUIRES THE SEEDED `testco` TENANT and fails loudly rather than skipping.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import extract_text

#: James's own sentence, as he types it: no commas anywhere.
RUN_ON = (
    "order for hopkins continental 34 mary smith 1948 to 2026 "
    "st marys auburn tent only"
)


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


# ── the property: nothing is ever lost as you type ──────────────────────

def test_NO_PREFIX_EVER_LOSES_A_FIELD_IT_HAD(db, tenant):
    """⚠️ THE TEST JAMES ASKED FOR, AND THE ONE THAT CATCHES THIS WHOLE CLASS.

    Walk the sentence word by word. At every prefix, every field captured at the
    previous prefix must still be captured. A field that appears and then vanishes is
    the defect he watched happen on screen — Hopkins captured, then gone when the
    next word landed.

    ⚠️ THERE IS NO EXPLICIT CORRECTION IN THIS SENTENCE, so the rule is absolute
    here. A sentence containing "actually" would legitimately drop a field under
    LAST_WINS, which is why the fixture has none — a test that allowed losses could
    not distinguish a correction from a regression.
    """
    words = RUN_ON.split()
    prev: dict = {}
    losses: list[tuple[int, str, list[str]]] = []
    for i in range(1, len(words) + 1):
        prefix = " ".join(words[:i])
        cur = dict(extract_text(db, tenant_id=tenant, text=prefix).values)
        lost = sorted(k for k in prev if k not in cur)
        if lost:
            losses.append((i, prefix, lost))
        prev = cur

    assert losses == [], "fields were captured and then lost:\n" + "\n".join(
        f"  at word {i} ({p!r}): lost {l}" for i, p, l in losses
    )


def test_the_run_on_sentence_captures_what_it_names(db, tenant):
    """⚠️ THE OTHER HALF. Monotonicity alone is satisfied by capturing NOTHING ever,
    so the property test above needs a companion that says the sentence actually
    works."""
    ex = extract_text(db, tenant_id=tenant, text=RUN_ON)
    v = ex.values
    assert v.get("funeral_home") == "Hopkins Funeral Home", v
    assert v.get("vault") == 'Continental 34"', v
    assert v.get("date_of_birth") == "1948", v
    assert v.get("date_of_death") == "2026", v
    assert v.get("cemetery") == "St. Mary's Cemetery", v
    assert v.get("cemetery_equipment") == "tent_only", v


# ── the marker must not swallow what follows ────────────────────────────

def test_a_marker_led_span_claims_only_the_name_it_matched(db, tenant):
    """The exact phrase from the screenshot."""
    ex = extract_text(db, tenant_id=tenant, text="order for hopkins continental")
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home", ex.values
    # ⚠️ AND "continental" REACHED THE VAULT PASS, which is the half that proves the
    # span was not merely re-bounded but actually LEFT the remainder behind.
    assert [p.field_id for p in ex.picks] == ["vault"], ex.picks
    assert ex.unrecognized == (), ex.unrecognized


def test_the_longest_matching_prefix_wins_not_the_shortest(db, tenant):
    """⚠️ "Hopkins Funeral Home" MUST BEAT "Hopkins" when both are typed. Shortest-
    first would claim one word and leave "Funeral Home" for the service-location
    pass, which reads those words as a venue."""
    ex = extract_text(db, tenant_id=tenant, text="order for hopkins funeral home")
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home", ex.values
    assert ex.values.get("service_location") is None, ex.values
    assert ex.unrecognized == (), ex.unrecognized


@pytest.mark.parametrize("phrase", [
    "continental",
    "order for hopkins continental",
    "hopkins continental",
])
def test_continental_alone_is_a_PICK_never_not_understood(db, tenant, phrase):
    """⚠️ RULED: "'continental' alone gives a vault pick (two sizes), never
    not-understood." Measured before the fix: "hopkins continental" captured NOTHING
    and reported the whole thing unplaced."""
    ex = extract_text(db, tenant_id=tenant, text=phrase)
    picks = {p.field_id: p for p in ex.picks}
    assert "vault" in picks, (phrase, ex.values, ex.unrecognized)
    assert len(picks["vault"].options) >= 2, picks["vault"].options
    assert not any("continental" in u.lower() for u in ex.unrecognized), ex.unrecognized


# ── the town must not swallow the clause behind it ──────────────────────

def test_a_town_span_does_not_eat_the_service_clause(db, tenant):
    """⚠️ THE 'ursday' CASE. A 30-character town run claimed through the middle of
    "thursday" and the service clause was lost with it."""
    ex = extract_text(
        db, tenant_id=tenant,
        text="st marys in auburn service at the church thursday 10am eta 11:30",
    )
    assert ex.values.get("service_location") == "church", ex.values
    assert ex.values.get("service_time") == "10:00", ex.values
    assert ex.values.get("service_date"), ex.values
    # ⚠️ NO FRAGMENT OF A WORD, which is the signature of a claim landing mid-word.
    assert ex.unrecognized == (), ex.unrecognized


def test_a_known_town_bounds_the_span_at_the_town(db, tenant):
    ex = extract_text(db, tenant_id=tenant, text="st marys in skaneateles tent only")
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values
    assert ex.values.get("cemetery_city") == "Skaneateles", ex.values
    # the equipment behind the town survived
    assert ex.values.get("cemetery_equipment") == "tent_only", ex.values
    assert ex.unrecognized == (), ex.unrecognized


def test_there_is_exactly_ONE_town_pattern_in_the_module(db):
    """⚠️ A RATCHET, BECAUSE THE DUPLICATE IS WHAT MADE A FIX NOT TAKE. `_CEM_TOWN`
    gained a period in its charset on 2026-10-12; an inline copy in the record-lookup
    pass kept the old 30-character form, so the record path still could not read
    "St. Albans" and still claimed mid-word. A second copy of a pattern is a second
    place to fix and the one nobody remembers.
    """
    import io

    src = io.open(
        "app/services/capture/typed_extraction.py", encoding="utf-8"
    ).read()
    # ⚠️ A SUBSTRING COUNT, NOT A REGEX. My first version matched the pattern shape
    # with a regex over the source and the escaping was wrong, so it reported zero and
    # the ratchet failed on correct code — an instrument answering an adjacent
    # question. The thing being counted is literal text; count it literally.
    needle = r"\s+in\s+("
    n = src.count(needle)
    assert n == 1, (
        f"{n} town patterns found in the module; there must be exactly ONE, named, "
        f"so a fix reaches every caller. A second copy is how the 2026-10-12 period "
        f"fix failed to reach the record-lookup path."
    )
