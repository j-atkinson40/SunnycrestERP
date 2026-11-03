'''"Did you mean…?" — the two offers, their answers, and what the answers record.

Slice 2 push 2, items 4 and 6 (James, 2026-10-28):
*"'Did you mean…?' Yes/No pills for Suggestions and PrefixOffers (showing 'instead
of …'); an open pick has priority"* and *"log accepts/rejects to the decision log,
accepted pairs become alias candidates."*

⚠️ BOTH PRODUCERS EXISTED AND NEITHER HAD A CONSUMER BEFORE THIS PUSH, which is
CLAUDE.md's "complete machinery behind an unprovisioned entrance". `did_you_mean` had
ZERO callers in `app/`; `PrefixOffer` was built by `extract_text` into a field nothing
read. The functions were correct and unreachable, so every test below is also the first
evidence that the path runs at all.

⚠️ AND THE TWO OFFERS ARE DIFFERENT CLAIMS, which is why they are separate lists on the
wire. A Suggestion is a TYPO — the word is near the term and wrong. A PrefixOffer is a
correct abbreviation that is being offered rather than applied, because the field was
already settled by a name typed out in full; it therefore has to show what it would
REPLACE, and `instead_of` is that.
'''
import os
from urllib.parse import urlparse

import pytest
from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture import session_service as ss

#: Measured 2026-11-03 against testco: the extractor emits a prefix offer for this text
#: and NOT for the two-segment version. The build site's own comment explains why —
#: *"It is the COMMA that breaks it — three segments, each extracted in isolation, and
#: 'john' settles Johnson knowing nothing about the first."* The trailing word is the
#: third segment and is load-bearing; `"order for Hopkins Funeral Home, john"` produces
#: no offer at all, which is asserted below so the fixture cannot be "simplified".
OFFER_TEXT = "order for Hopkins Funeral Home, john thursday"


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
def clean_aliases(db, world):
    """Remove alias candidates this file creates, before and after.

    ⚠️ ALIASES OUTLIVE A ROLLBACK HERE, which is not obvious and cost a confusing
    measurement. `decision_log.record_ask` calls `db.commit()` — it commits the CALLER's
    pending work, not only its own row — so anything flushed before it lands for real.
    A module-scoped rollback does not undo it. Sweep item 4 in one fixture.
    """
    tid, _uid = world
    def purge():
        db.execute(
            sql("DELETE FROM product_aliases WHERE company_id=:t AND source='did_you_mean'"),
            {"t": tid},
        )
        db.execute(
            sql("DELETE FROM opas_decisions WHERE company_id=:t AND input_text IN "
                "('montcello','continentl','john')"),
            {"t": tid},
        )
        db.commit()
    purge()
    yield
    purge()


def _held_with_typo(db, tid, uid, word="montcello", text="order for x"):
    row = ss.start(db, company_id=tid, user_id=uid)
    ss.set_text(db, row.id, company_id=tid, user_id=uid, text=text)
    ss.hold_words(db, row.id, company_id=tid, user_id=uid, words=[word], text=text)
    return row


class TestTheTypoSuggestion:
    def test_the_dispatch_s_HEADLINE_case_is_offered(self, db, world):
        """⚠️ THE CASE THE WHOLE FEATURE WAS SPECIFIED AROUND, and the one that fails if
        the comparison is whole-term: measured, sunnycrest has no term "Monticello" —
        only `Monticello Burial Vault` and `Monticello Urn Vault`, from which "montcello"
        is distance 11. The suggestion reaches it only because `_candidates` expands
        interior words."""
        tid, uid = world
        row = _held_with_typo(db, tid, uid)
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert [d["term"] for d in state["did_you_mean"]] == ["Monticello"]
        assert state["did_you_mean"][0]["word"] == "montcello"
        assert state["did_you_mean"][0]["distance"] == 1
        assert state["did_you_mean"][0]["held_id"]

    def test_YES_corrects_the_order_and_takes_the_chip_away(self, db, world, clean_aliases):
        """⚠️ THE FIELD IS FILLED BY RE-EXTRACTION, NOT BY A `kind`-TO-FIELD TABLE.
        `did_you_mean` returns `kind="vault"`, but three of the vocabulary's ten kinds do
        not name a field at all — so Yes appends the term to the text and lets the one
        authority decide. The proof is that `vault` ends up holding the FULL product
        name, which no client-side mapping supplied."""
        tid, uid = world
        row = _held_with_typo(db, tid, uid)
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        held_id = state["did_you_mean"][0]["held_id"]

        _row, term = ss.answer_suggestion(
            db, row.id, company_id=tid, user_id=uid, held_id=held_id, accept=True
        )
        after = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert term == "Monticello"
        # the form-default rule of 2026-10-16 turns the bare word into the burial vault
        assert after["values"].get("vault") == "Monticello Burial Vault"
        # ⚠️ AND THE CHIP IS GONE. Leaving it would show the corrected value in its row
        # AND the typo still sitting in "Not placed yet" — the same word twice.
        assert after["held_words"] == []
        assert after["did_you_mean"] == []

    def test_NO_keeps_the_chip_and_never_asks_again(self, db, world, clean_aliases):
        """Clause 5: *"No keeps it held and never asks about that word again."*"""
        tid, uid = world
        row = _held_with_typo(db, tid, uid)
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        held_id = state["did_you_mean"][0]["held_id"]

        ss.answer_suggestion(
            db, row.id, company_id=tid, user_id=uid, held_id=held_id, accept=False
        )
        after = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert after["did_you_mean"] == []
        # the word is still the director's to drag or edit
        assert [h["word"] for h in after["held_words"]] == ["montcello"]
        # ⚠️ THE TERM IS RECORDED, NOT A FLAG, which is what lets a later EDIT of the
        # word be suggested about again. `HeldWord.declined` holds terms — a point this
        # codebase has already got wrong once, in `pills.held_pills_for`.
        assert after["held_words"][0]["declined"] == ["Monticello"]

    def test_an_EDIT_recomputes_the_suggestion_and_clears_the_No(self, db, world, clean_aliases):
        """⚠️ THE EDIT IS THE ONE EVENT THAT CHANGES THE ANSWER, so the hint cannot be
        carried across it. Declining "Monticello" for "montcello" says nothing about
        what "continentl" means."""
        tid, uid = world
        row = _held_with_typo(db, tid, uid)
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        held_id = state["did_you_mean"][0]["held_id"]
        ss.answer_suggestion(
            db, row.id, company_id=tid, user_id=uid, held_id=held_id, accept=False
        )

        ss.edit_held(
            db, row.id, company_id=tid, user_id=uid, held_id=held_id, word="continentl"
        )
        after = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert [d["term"] for d in after["did_you_mean"]] == ["Continental"]
        assert after["held_words"][0].get("declined") in (None, [])

    def test_a_word_near_NOTHING_is_not_asked_about(self, db, world):
        """⚠️ THE CONTROL ON THE WHOLE FEATURE. Without it every test above passes
        against a build that suggests something for any word, which would make the pill
        row permanent noise."""
        tid, uid = world
        row = _held_with_typo(db, tid, uid, word="zzqqxw")
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert state["did_you_mean"] == []
        assert [h["word"] for h in state["held_words"]] == ["zzqqxw"]

    def test_a_STALE_answer_is_not_an_error(self, db, world):
        """The chip may be dropped between the question being drawn and the click
        landing. That is a race on a live pane, not a fault."""
        tid, uid = world
        row = _held_with_typo(db, tid, uid)
        _row, term = ss.answer_suggestion(
            db, row.id, company_id=tid, user_id=uid, held_id="nosuchchip", accept=True
        )
        assert term is None


class TestAnOpenPickHasPriority:
    def test_a_suggestion_is_WITHHELD_while_a_pick_is_open(self, db, world):
        """⚠️ THE DISCRIMINATING FORM: the suggestion EXISTS on the chip either way, and
        only the SERVING changes. A test that merely held a typo with no pick open would
        pass against a build that had no priority rule at all.

        James, item 4: *"an open pick has priority."* A pick is a question the director
        must answer before the order can move; a correction is Opas volunteering. Both at
        once asks two questions in one pill row, and ⌃1 would mean two things.
        """
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        # "graveliner" is ambiguous — measured 5 candidates — so it opens a pick
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text="order for graveliner")
        ss.hold_words(
            db, row.id, company_id=tid, user_id=uid,
            words=["montcello"], text="order for graveliner",
        )
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)

        assert len(state["pending_picks"]) == 1
        # the hint IS on the chip
        assert state["held_words"][0]["suggest"]["term"] == "Monticello"
        # and is NOT offered
        assert state["did_you_mean"] == []

    def test_and_it_returns_once_the_pick_is_settled(self, db, world):
        """The other half: withheld, not discarded."""
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text="order for graveliner")
        ss.hold_words(
            db, row.id, company_id=tid, user_id=uid,
            words=["montcello"], text="order for graveliner",
        )
        pick = ss.read_state(db, row.id, company_id=tid, user_id=uid)["pending_picks"][0]
        ss.choose(
            db, row.id, company_id=tid, user_id=uid,
            field_id=pick["field_id"], index=1,
        )
        after = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert after["pending_picks"] == []
        assert [d["term"] for d in after["did_you_mean"]] == ["Monticello"]


class TestThePrefixOffer:
    def test_it_is_offered_WITH_what_it_would_replace(self, db, world):
        """⚠️ `instead_of` IS THE QUESTION'S OTHER HALF. "Did you mean Johnson Funeral
        Home?" is only answerable if the director can see it currently says Hopkins."""
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text=OFFER_TEXT)
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)

        assert len(state["prefix_offers"]) == 1
        offer = state["prefix_offers"][0]
        assert offer["word"] == "john"
        assert offer["term"] == "Johnson Funeral Home"
        assert offer["kind"] == "funeral_home"
        assert offer["instead_of"] == "Hopkins Funeral Home"
        # ⚠️ AND THE FIELD IS UNCHANGED WHILE IT IS ONLY AN OFFER. James, 2026-10-29:
        # "a partial match is too weak to replace something already settled."
        assert state["values"].get("funeral_home") == "Hopkins Funeral Home"

    def test_the_THIRD_SEGMENT_is_what_produces_it(self, db, world):
        """⚠️ PINNED SO THE FIXTURE CANNOT BE "TIDIED". The build site's comment says
        three segments are needed; measured, dropping the trailing word produces NO
        offer. A shorter `OFFER_TEXT` would make every test in this class vacuous while
        still reading sensibly."""
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(
            db, row.id, company_id=tid, user_id=uid,
            text="order for Hopkins Funeral Home, john",
        )
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert state["prefix_offers"] == []

    def test_YES_replaces_the_settled_value(self, db, world, clean_aliases):
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text=OFFER_TEXT)
        ss.answer_prefix_offer(
            db, row.id, company_id=tid, user_id=uid,
            field_id="funeral_home", term="Johnson Funeral Home", accept=True,
        )
        after = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert after["values"].get("funeral_home") == "Johnson Funeral Home"

    def test_NO_survives_the_next_RE_EXTRACTION(self, db, world, clean_aliases):
        """⚠️ THE TEST THAT MATTERS MOST HERE, because the offer is rebuilt from the text
        on every pause. A decline that lived only in the client would be re-asked on the
        next keystroke, forever — which is the opposite of "never asks again"."""
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text=OFFER_TEXT)
        ss.answer_prefix_offer(
            db, row.id, company_id=tid, user_id=uid,
            field_id="funeral_home", term="Johnson Funeral Home", accept=False,
        )
        assert ss.read_state(db, row.id, company_id=tid, user_id=uid)["prefix_offers"] == []

        # the director keeps typing — the abbreviation is still in the text
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text=OFFER_TEXT + " x")
        after = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert after["prefix_offers"] == []
        assert after["values"].get("funeral_home") == "Hopkins Funeral Home"

    def test_an_open_pick_withholds_offers_too(self, db, world):
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(
            db, row.id, company_id=tid, user_id=uid,
            text=OFFER_TEXT + ", graveliner",
        )
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        if not state["pending_picks"]:
            pytest.skip("that text did not open a pick on this tenant's data")
        assert state["prefix_offers"] == []

    def test_a_STALE_offer_answer_is_not_an_error(self, db, world):
        tid, uid = world
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text=OFFER_TEXT)
        _row, note = ss.answer_prefix_offer(
            db, row.id, company_id=tid, user_id=uid,
            field_id="funeral_home", term="Nobody Funeral Home", accept=True,
        )
        assert note is None
        assert (
            ss.read_state(db, row.id, company_id=tid, user_id=uid)["values"]
            .get("funeral_home") == "Hopkins Funeral Home"
        )


class TestClause6TheDecisionLogAndAliasCandidates:
    def _decisions(self, db, tid):
        return db.execute(
            sql("SELECT count(*) FROM opas_decisions WHERE company_id=:t"), {"t": tid}
        ).scalar()

    def _aliases(self, db, tid):
        return db.execute(
            sql("SELECT count(*) FROM product_aliases WHERE company_id=:t "
                "AND source='did_you_mean'"),
            {"t": tid},
        ).scalar()

    def test_a_YES_writes_a_decision_AND_an_alias_candidate(self, db, world, clean_aliases):
        """James, clause 6: *"log accepts/rejects to the decision log, accepted pairs
        become alias candidates."*"""
        tid, uid = world
        before_d, before_a = self._decisions(db, tid), self._aliases(db, tid)

        row = _held_with_typo(db, tid, uid, word="continentl")
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        assert [d["term"] for d in state["did_you_mean"]] == ["Continental"]
        ss.answer_suggestion(
            db, row.id, company_id=tid, user_id=uid,
            held_id=state["did_you_mean"][0]["held_id"], accept=True,
        )
        db.commit()

        assert self._decisions(db, tid) == before_d + 1
        assert self._aliases(db, tid) == before_a + 1
        alias = db.execute(
            sql("SELECT alias_text, alias_text_normalized, canonical_product_id, "
                "confidence, is_confirmed FROM product_aliases "
                "WHERE company_id=:t AND source='did_you_mean' "
                "ORDER BY created_at DESC LIMIT 1"),
            {"t": tid},
        ).fetchone()
        assert alias[0] == "continentl"
        assert alias[1] == "continentl"
        # ⚠️ IT POINTS AT A REAL PRODUCT. An alias with a null canonical id is a row the
        # resolver cannot use, which is why a term that is only an interior WORD is
        # skipped rather than written.
        assert alias[2] is not None
        # ⚠️ AND IT IS A CANDIDATE, NOT A DECISION. One director's Yes is evidence that
        # the office types "continentl"; it is not authority to teach the resolver.
        assert alias[4] is False
        assert float(alias[3]) < 1.0

    def test_a_NO_is_logged_and_seeds_NOTHING(self, db, world, clean_aliases):
        """⚠️ BOTH HALVES. The rejection is evidence too — it says the suggestion was
        wrong, which is what makes the log usable as test cases — and it must not teach
        the resolver a name the office just refused."""
        tid, uid = world
        before_d, before_a = self._decisions(db, tid), self._aliases(db, tid)

        row = _held_with_typo(db, tid, uid, word="continentl")
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        ss.answer_suggestion(
            db, row.id, company_id=tid, user_id=uid,
            held_id=state["did_you_mean"][0]["held_id"], accept=False,
        )
        db.commit()

        assert self._decisions(db, tid) == before_d + 1
        assert self._aliases(db, tid) == before_a

    def test_the_same_correction_twice_seeds_ONE_candidate(self, db, world, clean_aliases):
        """The same office types the same typo repeatedly. One candidate per pair is the
        evidence; fifty are noise."""
        tid, uid = world
        for _ in range(2):
            row = _held_with_typo(db, tid, uid, word="continentl")
            state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
            ss.answer_suggestion(
                db, row.id, company_id=tid, user_id=uid,
                held_id=state["did_you_mean"][0]["held_id"], accept=True,
            )
            db.commit()
        assert self._aliases(db, tid) == 1

    def test_a_NON_PRODUCT_term_is_logged_but_seeds_no_alias(self, db, world, clean_aliases):
        """⚠️ THE SCOPE LINE, MEASURED RATHER THAN ASSUMED. `_PRODUCT_KINDS` names the
        four vocabulary kinds whose terms are product names. A funeral home is not one:
        an alias row needs a `canonical_product_id`, and pointing it at a company entity
        would put a non-product in a column the resolver joins on products."""
        tid, uid = world
        before_a = self._aliases(db, tid)
        row = ss.start(db, company_id=tid, user_id=uid)
        ss.set_text(db, row.id, company_id=tid, user_id=uid, text="order for x")
        ss.hold_words(
            db, row.id, company_id=tid, user_id=uid, words=["hopkns"], text="order for x"
        )
        state = ss.read_state(db, row.id, company_id=tid, user_id=uid)
        if not state["did_you_mean"]:
            pytest.skip("no single-term suggestion for that misspelling on this data")
        assert state["did_you_mean"][0]["kind"] == "funeral_home"
        ss.answer_suggestion(
            db, row.id, company_id=tid, user_id=uid,
            held_id=state["did_you_mean"][0]["held_id"], accept=True,
        )
        db.commit()
        assert self._aliases(db, tid) == before_a

    def test_the_product_kinds_are_the_four_measured_ones(self):
        """⚠️ PINNED BECAUSE WIDENING IT IS THE EASY MISTAKE. Measured on testco's
        vocabulary: vault 34 terms, vault_alias 33, product 14, equipment 6 name
        products; funeral_home 13, cemetery 3, service_location 4, personalization 6 and
        chairs 2 do not.

        ⚠️ AND THIS IS THE ONLY ASSERTION THE GUARD CAN CARRY, which a break test
        established rather than my reading. Deleting `if kind not in _PRODUCT_KINDS`
        leaves the whole file green: the product lookup beneath it already refuses a
        term no product is named after. So the guard is defensive, its short-circuit has
        no observable effect, and a probe raising inside `_seed_alias_candidate` to
        prove otherwise is swallowed by that function's own `except Exception`. Pinning
        the SET is still worth doing — it makes widening it deliberate — but it is not
        evidence that the guard prevents anything today, and this docstring says so
        rather than implying coverage that does not exist."""
        from app.services.capture.session_service import _PRODUCT_KINDS

        assert set(_PRODUCT_KINDS) == {"vault", "vault_alias", "product", "equipment"}
