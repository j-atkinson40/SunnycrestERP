"""A held word is the open question's first pill — WHERE THE SERVER SAYS IT FITS.

James, 2026-10-28: *"held words matching the open question are its first pill."*
Narrowed 2026-11-03, after I built the wrong reading of "matching":

    "Don't offer every held word to every question. A date offered as a cemetery is
     noise, and you'd learn to ignore that pill row. Offer only what the server says
     fits."

⚠️ MY FIRST VERSION OFFERED EVERY CHIP FOR EVERY UNGATED FIELD, reasoning that
acceptance belongs to the server and `place_held` would refuse what did not fit. Right
about where acceptance lives, wrong about the default. **The cost of a sometimes-wrong
pill row is not the bad pill — it is that the office stops reading the row**, and the
good pills go with it.

⚠️ SO THE TABLE LISTS FIELDS THAT HAVE A CHECK, NOT FIELDS THAT NEED ONE, and a field
absent from it offers nothing. The rule gets safer as the table grows rather than
needing revisiting.

⚠️ AND THE ORDER IS PART OF THE CLAIM, NOT MERELY THE PRESENCE. A held pill appearing
fourth is not what was ruled and is not useful: the row shows three or four answers, so
"somewhere in the list" and "not offered at all" are the same thing on screen.
"""
from app.services.capture.held import HeldWord
from app.services.capture.pills import held_pills_for


def _held(word: str, held_id: str = "h1", **kw) -> HeldWord:
    return HeldWord(word=word, origin="typed", held_id=held_id, **kw)


def _admit(monkeypatch, verdict: bool = True) -> list:
    """Make the vault check answer `verdict`, and record what it was asked.

    ⚠️ PATCHED AT `pills.admits_name`, NOT AT `vault_form.admits_name`, AND MY FIRST
    VERSION GOT THAT WRONG. `pills.py` does `from … import admits_name` at module
    level, so the name is bound in ITS namespace at import and patching the definition
    site changes nothing the function can see. The failure was loud — the recorder
    stayed empty — but the same mistake on a test asserting a REFUSAL would have
    passed, because a refusal is what an unpatched vault gate returns anyway.
    """
    seen: list = []

    def fake(resolver, name):
        seen.append(name)
        return verdict

    monkeypatch.setattr("app.services.capture.pills.admits_name", fake)
    monkeypatch.setattr(
        "app.services.capture.pills.FormResolver", lambda db, t: object()
    )
    return seen


class TestAFieldWithAServerCheck:
    def test_an_admitted_word_becomes_a_pill(self, monkeypatch):
        _admit(monkeypatch)
        pills = held_pills_for(
            None, tenant_id="t", field_id="vault", held=[_held("monticello 34")]
        )
        assert [p.label for p in pills] == ["monticello 34"]
        # ⚠️ THE VALUE IS THE WORD AS TYPED. The strip's job is "here is what I could
        # not file"; a normalised value would file something nobody wrote.
        assert pills[0].value == "monticello 34"

    def test_a_REFUSED_word_is_not_offered(self, monkeypatch):
        """⚠️ THE CASE THE WHOLE RULING IS ABOUT. "2 chairs" in the vault slot is the
        2026-11-02 defect; a pill offering it would be the sixth repeat."""
        seen = _admit(monkeypatch, verdict=False)
        assert held_pills_for(
            None, tenant_id="t", field_id="vault", held=[_held("2 chairs")]
        ) == []
        # BOTH HALVES: that the check RAN with the right word, and that its answer was
        # acted on. A call whose result is ignored is the shape this ruling is about.
        assert seen == ["2 chairs"]

    def test_the_pill_carries_the_CHIP_not_just_the_word(self, monkeypatch):
        """⚠️ WITHOUT `held_id` THE PILL IS A DIFFERENT, WORSE FEATURE.

        Both endpoints store the same text, so answering by value alone LOOKS right —
        the row fills — and leaves the chip in the strip under its own answer. The id
        is what lets the client reach `/held/{id}/place`, which does both.
        """
        _admit(monkeypatch)
        pills = held_pills_for(
            None, tenant_id="t", field_id="vault", held=[_held("monticello 34", "h7")]
        )
        assert pills[0].held_id == "h7"
        assert pills[0].as_dict()["held_id"] == "h7"

    def test_it_says_where_the_answer_came_from(self, monkeypatch):
        _admit(monkeypatch)
        pills = held_pills_for(
            None, tenant_id="t", field_id="vault", held=[_held("monticello 34")]
        )
        assert pills[0].sub == "not placed yet"

    def test_every_admitted_word_is_offered_in_order(self, monkeypatch):
        _admit(monkeypatch)
        pills = held_pills_for(
            None,
            tenant_id="t",
            field_id="vault",
            held=[_held("monticello 34", "h1"), _held("continental", "h2")],
        )
        assert [p.held_id for p in pills] == ["h1", "h2"]

    def test_a_CHECK_FAILURE_drops_the_pill_rather_than_offering_it(self, monkeypatch):
        """⚠️ FAIL CLOSED. The question stays answerable by typing and the chip stays
        draggable — where `place_held` applies the same check properly. Offering on
        failure would make a resolver outage look like the vault slot accepting
        anything, which is the appearance the ruling exists to prevent."""
        def boom(db, t):
            raise RuntimeError("catalogue unreachable")

        monkeypatch.setattr("app.services.capture.pills.FormResolver", boom)
        assert held_pills_for(
            None, tenant_id="t", field_id="vault", held=[_held("monticello 34")]
        ) == []


class TestAFieldWithNoServerCheck:
    """⚠️ THE RULING'S OWN DEFAULT, AND THE REASON THE TABLE IS SHAPED THIS WAY."""

    def test_a_field_with_no_check_offers_NOTHING(self):
        """Even though the word is perfectly plausible as a cemetery. The chip is not
        lost — it stays in the strip, draggable onto any row, which is the path that
        does not need Opas to have an opinion first."""
        assert held_pills_for(
            None, tenant_id="t", field_id="cemetery", held=[_held("green pastures")]
        ) == []

    def test_the_noise_case_the_ruling_names(self):
        """James's own example: *"A date offered as a cemetery is noise, and you'd learn
        to ignore that pill row."* """
        assert held_pills_for(
            None, tenant_id="t", field_id="cemetery", held=[_held("1948")]
        ) == []

    def test_the_table_lists_fields_that_HAVE_a_check(self):
        """⚠️ THE STRUCTURAL CLAIM, which is what makes the rule safe as it grows:
        "as fields gain server-side acceptance checks, they gain held-word pills
        automatically — never a client-side predicate." A field absent from the table
        offers nothing, so adding a field is additive and forgetting one is quiet."""
        from app.services.capture.pills import _ACCEPTANCE_CHECKS

        assert set(_ACCEPTANCE_CHECKS) == {"vault"}


class TestWhatIsNeverOffered:
    def test_no_open_question_offers_nothing(self, monkeypatch):
        """The ready state sends `question_field_id: null` and one Review pill."""
        _admit(monkeypatch)
        assert held_pills_for(
            None, tenant_id="t", field_id=None, held=[_held("monticello 34")]
        ) == []

    def test_nothing_held_offers_nothing(self, monkeypatch):
        _admit(monkeypatch)
        assert held_pills_for(None, tenant_id="t", field_id="vault", held=[]) == []

    def test_a_DECLINED_word_is_not_re_offered(self, monkeypatch):
        """⚠️ CLAUSE 5'S LIST, HONOURED HERE SO PUSH 2 DOES NOT HAVE TO RETROFIT IT.

        A word the office has already said No to for this field must not come back as
        a pill — re-offering a rejected suggestion is the behaviour that makes an
        assistant feel like it is not listening.
        """
        seen = _admit(monkeypatch)
        word = _held("monticello 34")
        word = type(word)(**{**word.__dict__, "declined": ("vault",)})
        assert held_pills_for(
            None, tenant_id="t", field_id="vault", held=[word]
        ) == []
        # ⚠️ AND IT WAS REFUSED BEFORE THE CHECK RAN, not by the check answering No —
        # otherwise this test would pass against a declined list nobody reads.
        assert seen == []

    def test_a_chip_with_no_id_is_skipped(self, monkeypatch):
        """A chip with no identity cannot be placed, so offering it is a dead pill."""
        _admit(monkeypatch)
        assert held_pills_for(
            None, tenant_id="t", field_id="vault", held=[_held("monticello 34", "")]
        ) == []

    def test_an_empty_word_is_skipped(self, monkeypatch):
        _admit(monkeypatch)
        assert held_pills_for(
            None, tenant_id="t", field_id="vault", held=[_held("", "h1")]
        ) == []


# ──────────────────────────────────────────────────────────────────────────────────────
# The ORDER, against a real session and the real acceptance check.
# ──────────────────────────────────────────────────────────────────────────────────────
#
# ⚠️ THE TESTS ABOVE PROVE A HELD WORD BECOMES A PILL, with the check stubbed. They say
# nothing about it being the FIRST one — which is what was actually ruled — and nothing
# about the real `admits_name` admitting anything. Both are checked here, against
# `vault`, because that is the one field with a server-side check today.

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


def _asking_vault(db, tid, uid, held_word: str | None):
    row = session_service.start(db, company_id=tid, user_id=uid)
    session_service.set_text(
        db, row.id, company_id=tid, user_id=uid, text="order for hopkins"
    )
    if held_word is not None:
        session_service.hold_words(
            db, row.id, company_id=tid, user_id=uid,
            words=[held_word], text="order for hopkins",
        )
    return session_service.read_state(
        db, row.id, company_id=tid, user_id=uid, asking="vault"
    )


class TestTheHeldPillComesFirst:
    def test_an_admitted_held_word_LEADS_the_vault_question(self, db, world):
        """⚠️ THE RULING IS ABOUT POSITION. The director's own unplaced word outranks
        anything history can offer — and this runs the REAL `admits_name`, so it also
        proves a tenant product name survives the acceptance check."""
        tid, uid = world
        state = _asking_vault(db, tid, uid, "Continental")
        pills = state.get("pills") or []
        assert pills, "the vault question offered no pills at all"
        assert pills[0]["label"] == "Continental"
        assert pills[0]["held_id"]
        # ⚠️ AND IT DID NOT REPLACE THE REST. "First" means first, not only.
        assert all("held_id" not in p for p in pills[1:])
        assert len(pills) > 1, "no pills behind it, so 'first' would mean nothing"

    def test_a_word_the_vault_slot_REFUSES_is_not_offered(self, db, world):
        """⚠️ THE 2026-11-02 RULING, THROUGH THE REAL CHECK RATHER THAN A STUB. "2
        chairs" is a billing line, not a vault form, and it is the exact phrase that
        filled the vault slot on James's walk."""
        tid, uid = world
        state = _asking_vault(db, tid, uid, "2 chairs")
        pills = state.get("pills") or []
        assert all("held_id" not in p for p in pills)
        # ⚠️ AND THE CHIP IS STILL HELD. Refusing a PILL must not drop the word — it
        # stays in the strip, draggable, where `place_held` applies the same check.
        assert [h["word"] for h in (state.get("held_words") or [])] == ["2 chairs"]

    def test_the_same_chip_is_the_pill_AND_the_strip_entry(self, db, world):
        """⚠️ THE SAME CHIP IN TWO PLACES AT ONCE IS CORRECT: a pill above the bar and
        a chip in the strip, one `held_id`, so taking either removes it from both."""
        tid, uid = world
        state = _asking_vault(db, tid, uid, "Continental")
        held = state.get("held_words") or []
        assert [h["word"] for h in held] == ["Continental"]
        assert state["pills"][0]["held_id"] == held[0]["id"]

    def test_with_NOTHING_held_the_pills_are_unchanged(self, db, world):
        """⚠️ THE CONTROL, and it is what makes the ordering test mean something.
        Without it, "the first pill is the held word" could be passing against a
        question that has no other pills at all."""
        tid, uid = world
        state = _asking_vault(db, tid, uid, None)
        pills = state.get("pills") or []
        assert pills, "the vault question offered no pills at all"
        assert all("held_id" not in p for p in pills)
