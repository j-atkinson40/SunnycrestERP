"""Abbreviations in capture, and a span that said the opposite of what happened.

James, walk 2026-10-20. He typed `order hopk monti thursday 10 am st. mary's`. The
opener fix worked and the capture started, but the funeral home and the vault came back
as not understood while a single dotted block covered three words — one of which had
fed the service date.

⚠️ BOTH SYMPTOMS WERE ONE CAUSE, AND THAT IS THE FINDING. `parse_date` returned no span,
so the leftover loop claimed the WHOLE fragment it had parsed: `hopk monti thursday`
became one `service_date` claim. `_claim` refuses an overlapping span, so the span that
lied about "hopk" is also the span that made "hopk" unclaimable. Narrowing the claim to
the parser's own evidence fixes the attribution AND unblocks the abbreviation pass.

⚠️ MEASURED ON PRODUCTION BEFORE ANY CHANGE, read-only, from James's exact sentence:

    span [  6, 25) captured ('service_date',) 'hopk monti thursday'
    unrecognized: ()

⚠️ WHICH CORRECTS THE DISPATCH'S PREMISE FOR ITEM 2. It asks why "thursday" landed in
the UNRECOGNIZED span. It did not: `unrecognized` was empty and the over-wide span was
marked `captured`. The instruction — "fix the attribution, not the drawing" — was right
anyway, and is what these tests pin.
"""
from __future__ import annotations

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from datetime import date

from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture.prefix_resolve import (
    KINDS_FUNERAL_HOME,
    KINDS_VAULT,
    MIN_PREFIX,
    consume_loose,
    differ_only_by_form,
    resolve_prefix,
)
from app.services.capture.typed_extraction import extract_text
from app.services.capture.vocabulary import Term, build_vocabulary
from app.services.nl_creation.structured_parsers import parse_date, parse_time

WALK = "order hopk monti thursday 10 am st. mary's"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        s.execute(sql("SELECT 1"))
    except Exception as exc:
        s.close()
        pytest.skip(f"database unavailable: {exc}")
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def tenant(db):
    tid = db.execute(sql("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    if not tid:
        pytest.skip("the testco tenant is not seeded")
    return tid


@pytest.fixture
def vocab(db, tenant):
    return tuple(build_vocabulary(db, tenant))


@pytest.fixture
def carrier(db):
    """A tenant carrying exactly ONE Continental, which is production's shape.

    ⚠️ THIS FIXTURE EXISTS BECAUSE THE BRANCH IT TESTS IS UNREACHABLE ON testco, AND
    THAT IS THE FINDING RATHER THAN AN INCONVENIENCE. The prefix layer's carried filter
    is what narrows "conti" to one term; testco carries neither Continental, so there
    the prefix stays ambiguous and a different branch runs. sunnycrest carries one, so
    production took a path local tests could not reach — which is exactly why "green
    locally" was not evidence and why the defect was found by probing production.

    A `products` row is all `build_vocabulary` needs: it reads product NAMES only to
    decide `carried`.
    """
    # ⚠️ THROUGH THE ORM, NOT RAW SQL. My first version inserted with `INSERT INTO` and
    # failed on `created_at`, then on `updated_at` — column-at-a-time guessing against
    # NOT NULL constraints the models already satisfy. CLAUDE.md's timestamp-convention
    # note says in terms that the two conventions coexist and raw SQL must set them
    # explicitly; the models carry the defaults, so the models are the right instrument.
    from app.models.company import Company
    from app.models.product import Product

    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Carrier Co", slug=f"carrier-{cid[:8]}",
                   is_active=True, vertical="manufacturing"))
    db.flush()
    db.add(Product(id=str(uuid.uuid4()), company_id=cid,
                   name="Continental Burial Vault", is_active=True))
    db.commit()
    try:
        yield cid
    finally:
        db.rollback()
        db.execute(sql("DELETE FROM products WHERE company_id = :c"), {"c": cid})
        db.execute(sql("DELETE FROM companies WHERE id = :c"), {"c": cid})
        db.commit()


def _spans(ex, text):
    return [(text[s.start:s.end], s.state, tuple(s.field_ids)) for s in ex.spans]


# ───────────────────────────────────────────────────────────────────────────
# 1 — the parsers say WHERE they read from
# ───────────────────────────────────────────────────────────────────────────

def test_parse_date_reports_the_words_it_actually_used():
    """⚠️ THE ROOT OF BOTH SYMPTOMS. Without a span the caller cannot mark the right
    words, so it marked all of them."""
    r = parse_date("hopk monti thursday", today=date(2026, 10, 20))
    assert r and r["value"] == "2026-10-22"
    a, b = r["span"]
    assert "hopk monti thursday"[a:b] == "thursday"


@pytest.mark.parametrize(
    "text,evidence",
    [
        ("thursday", "thursday"),
        ("2026-04-20", "2026-04-20"),
        ("4/20/26", "4/20/26"),
        ("April 20", "April 20"),
        ("next week", "next week"),
        ("  tomorrow please", "tomorrow"),
        ("riv conti fri", "fri"),
        ("hop venet sat", "sat"),
    ],
)
def test_every_date_branch_carries_its_own_evidence(text, evidence):
    """⚠️ ALL SIX BRANCHES, BECAUSE A SPAN ADDED TO ONE IS A SPAN MISSING FROM FIVE.
    The leading-whitespace case is here because `parse_date` strips before matching and
    the offsets must be mapped back onto the CALLER's string."""
    r = parse_date(text, today=date(2026, 10, 20))
    assert r is not None, text
    a, b = r["span"]
    assert text[a:b] == evidence


@pytest.mark.parametrize(
    "text,evidence",
    [("hopk monti thursday 10 am", "10 am"), ("10:30", "10:30"),
     ("service at noon", "noon"), ("evening", "evening")],
)
def test_parse_time_carries_its_evidence_too(text, evidence):
    """The sibling defect, fixed in the same pass — CLAUDE.md §11, "the siblings are
    often in the same file"."""
    r = parse_time(text)
    assert r is not None, text
    a, b = r["span"]
    assert text[a:b] == evidence


def test_a_parser_that_cannot_say_where_keeps_the_OLD_wide_behaviour(db, tenant):
    """⚠️ THE FALLBACK IS THE PREVIOUS BEHAVIOUR, NOT A GUESS. `_evidence` returns the
    whole fragment when no usable span came back, because a position invented for a
    parser that did not report one is exactly the bug this span exists to fix."""
    from app.services.capture.typed_extraction import _evidence

    assert _evidence("hopk monti thursday", 6, {"value": "x"}) == (6, 25)
    assert _evidence("hopk monti thursday", 6, {"span": (11, 19)}) == (17, 25)
    # ⚠️ AND A SPAN THAT CANNOT BE TRUE OF THIS FRAGMENT IS REFUSED, not clamped.
    for bad in ({"span": (11, 99)}, {"span": (-1, 4)}, {"span": (5, 5)},
                {"span": "nope"}, {"span": (1, 2, 3)}):
        assert _evidence("hopk monti thursday", 6, bad) == (6, 25), bad


# ───────────────────────────────────────────────────────────────────────────
# 2 — the prefix rule, which is the ghost's rule
# ───────────────────────────────────────────────────────────────────────────

def test_an_unambiguous_abbreviation_is_the_term(db, tenant, vocab):
    """⚠️ RE-POINTED 2026-10-21 AT THE VALUE RATHER THAN THE INTERMEDIATE TERM.

    It used to assert `resolve_prefix("monti", ...).chosen.text == "Monticello Burial
    Vault"`. Once tenant product names joined the vocabulary that became
    data-dependent: on testco the two Monticello VARIANTS are not carried while the
    product `Monticello` is, so the carried filter (step 4) leaves the product and the
    chosen TERM is now "Monticello" — which then resolves through the ordinary product
    resolver to the same vault.

    ⚠️ THE INTERMEDIATE IS NOT THE CONTRACT; THE FIELD VALUE IS. Asserting the term
    pinned a path, and the path legitimately changes with what a tenant stocks. So the
    rule is tested over an explicit vocabulary below, and the VALUE is tested end to
    end, which is what James retests.
    """
    assert resolve_prefix("hopk", vocab, KINDS_FUNERAL_HOME).chosen.text == \
        "Hopkins Funeral Home"

    # the rule, over a vocabulary this test owns
    v = (
        Term(text="Monticello Burial Vault", kind="vault", carried=True,
             form="burial_vault"),
        Term(text="Monticello Urn Vault", kind="vault", carried=True, form="urn_vault"),
    )
    assert resolve_prefix("monti", v, KINDS_VAULT).chosen.text == \
        "Monticello Burial Vault"

    # the value, over whatever this tenant actually carries
    ex = extract_text(db, tenant_id=tenant, text="order hopk monti thursday")
    assert ex.values.get("vault") == "Monticello Burial Vault"


def test_a_vault_ambiguous_ONLY_by_form_takes_the_burial_vault():
    """The office means a burial vault nine times in ten — ruled 2026-10-13 for the
    capture, extended to the ghost 2026-10-16, and now to the extractor.

    ⚠️ OVER AN OWNED VOCABULARY SINCE 2026-10-21, for the reason given in
    `test_an_unambiguous_abbreviation_is_the_term`: which TERMS survive the carried
    filter depends on what a tenant stocks, and this test is about the form rule.
    """
    v = (
        Term(text="Monticello Burial Vault", kind="vault", carried=True,
             form="burial_vault"),
        Term(text="Monticello Urn Vault", kind="vault", carried=True, form="urn_vault"),
    )
    r = resolve_prefix("monti", v, KINDS_VAULT)
    assert {m.form for m in r.matches} == {"burial_vault", "urn_vault"}
    assert r.chosen.form == "burial_vault"
    assert not r.ambiguous


def test_a_vault_ambiguous_by_ANYTHING_ELSE_asks(db, tenant):
    """⚠️ `discriminators == ("form",)` EXACTLY, MEASURED NOT INFERRED. "Continental"
    matches two BURIAL vaults of different sizes; a check for "form is among the
    discriminators" would silently pick one."""
    v = (
        Term(text='Continental 34"', kind="vault", carried=True, form="burial_vault"),
        Term(text="Continental Burial Vault", kind="vault", carried=True,
             form="burial_vault"),
    )
    r = resolve_prefix("conti", v, KINDS_VAULT)
    assert r.chosen is None and r.ambiguous
    assert len(r.matches) > 1
    assert not differ_only_by_form(r.matches)

    # ⚠️ AND END TO END IT STILL ASKS, whichever route the tenant's data takes it
    # through — on testco via the product name, on sunnycrest via the carried variant.
    # Both arrive at a question, which is the contract.
    ex = extract_text(db, tenant_id=tenant, text="order riv conti fri 11 graveside")
    assert [p.field_id for p in ex.picks] == ["vault"], (ex.values, ex.picks)
    assert "vault" not in ex.values


def test_the_form_test_is_ONLY_BY_FORM_and_not_FORM_IS_AMONG(vocab):
    """⚠️ ADDED AFTER A BREAK TEST FOUND NOTHING RED. Making `differ_only_by_form`
    return True unconditionally left all 39 tests GREEN — because every live case that
    reached the stems check already failed an EARLIER guard (`Continental 34"` is a
    `vault_alias` carrying no form, so `all(m.form)` short-circuited). The stems
    comparison, which is the actual rule, had no test at all.

    These two pairs both have every form populated and two distinct forms, so only the
    stems comparison can separate them. ⚠️ THE SECOND IS THE ONE THAT MATTERS: form is
    AMONG its differences and must not be enough.
    """
    only_form = (
        Term(text="Cameo Rose Burial Vault", kind="vault", form="burial_vault"),
        Term(text="Cameo Rose Urn Vault", kind="vault", form="urn_vault"),
    )
    assert differ_only_by_form(only_form) is True
    r = resolve_prefix("cam", only_form, KINDS_VAULT)
    assert r.chosen is not None and r.chosen.form == "burial_vault"

    form_and_size = (
        Term(text='Continental 34"', kind="vault", form="burial_vault"),
        Term(text="Continental Urn Vault", kind="vault", form="urn_vault"),
    )
    assert differ_only_by_form(form_and_size) is False
    r2 = resolve_prefix("conti", form_and_size, KINDS_VAULT)
    assert r2.chosen is None and r2.ambiguous, "a size difference must still ask"


def test_a_prefix_shorter_than_the_ghosts_minimum_reaches_nothing(vocab):
    assert MIN_PREFIX == 2
    assert resolve_prefix("h", vocab, KINDS_FUNERAL_HOME) is None
    # the control: one more character is enough
    assert resolve_prefix("ho", vocab, KINDS_FUNERAL_HOME) is not None


def test_a_whole_term_is_not_an_abbreviation_of_itself(vocab):
    """⚠️ OTHERWISE TWO WRITERS OWN ONE SPAN. The exact scans already claim a fully
    typed name; this pass must not also claim it."""
    assert resolve_prefix("Hopkins Funeral Home", vocab, KINDS_FUNERAL_HOME) is None


def test_a_word_that_names_nothing_reaches_nothing(vocab):
    assert resolve_prefix("blargle", vocab, KINDS_FUNERAL_HOME) is None
    assert resolve_prefix("zzz", vocab, KINDS_VAULT) is None


def test_the_kind_scopes_the_match(db, tenant):
    """⚠️ MEASURED ON PRODUCTION: a `company_entities` row is named "St. Mary's
    Cemetery", so "st m" reaches a funeral home AND a cemetery. Kind scoping is what
    stops that being an ambiguity it is not.

    ⚠️ REWRITTEN AFTER A BREAK TEST FOUND NOTHING RED. My first version used two terms
    with the SAME TEXT under two kinds and asserted the chosen one was the funeral
    home. Removing kind scoping altogether left it GREEN — both terms matched, their
    texts were identical, and the same-text rule returned the first, which happened to
    be the funeral home. It asserted a true thing about a case that could not
    discriminate. The pair below differ in text AND kind, so ignoring kinds changes the
    answer rather than the ordering.
    """
    v = (
        Term(text="Hopkins Funeral Home", kind="funeral_home", carried=True),
        Term(text="Hopkins Burial Vault", kind="vault", carried=True,
             form="burial_vault"),
    )
    # scoped to the funeral home, "hop" means exactly one thing
    r = resolve_prefix("hop", v, KINDS_FUNERAL_HOME)
    assert r is not None and r.chosen is not None
    assert r.chosen.text == "Hopkins Funeral Home"
    # scoped to the vault, the SAME prefix means a different thing
    r2 = resolve_prefix("hop", v, KINDS_VAULT)
    assert r2 is not None and r2.chosen is not None
    assert r2.chosen.text == "Hopkins Burial Vault"
    # ⚠️ AND UNSCOPED IT IS A QUESTION — which is what proves the scoping did the work.
    r3 = resolve_prefix("hop", v, None)
    assert r3 is not None and r3.chosen is None and r3.ambiguous

    # ⚠️ THE PRODUCTION SHAPE AS WELL, since it is the case that prompted the rule: one
    # name under two kinds is one answer, not a question.
    same = (
        Term(text="St. Mary's Cemetery", kind="funeral_home", carried=True),
        Term(text="St. Mary's Cemetery", kind="cemetery", carried=True),
    )
    rs = resolve_prefix("st m", same, KINDS_FUNERAL_HOME)
    assert rs is not None and rs.chosen is not None
    assert rs.chosen.kind == "funeral_home"


def test_two_terms_with_the_SAME_TEXT_are_one_answer_not_a_question():
    """"Did you mean Monticello Burial Vault or Monticello Burial Vault?" is not a
    question anybody can answer. The vocabulary is keyed on (kind, text), so one name
    carried as both a variant and a confirmed alias appears twice."""
    v = (
        Term(text="Monticello Burial Vault", kind="vault", carried=True,
             form="burial_vault"),
        Term(text="Monticello Burial Vault", kind="vault_alias", carried=True),
    )
    r = resolve_prefix("monti", v, KINDS_VAULT)
    assert r.chosen is not None and not r.ambiguous


def test_carried_terms_win_a_tie():
    v = (
        Term(text="Monticello Burial Vault", kind="vault", carried=True,
             form="burial_vault"),
        Term(text="Monticello Urn Vault", kind="vault", carried=False, form="urn_vault"),
    )
    r = resolve_prefix("monti", v, KINDS_VAULT)
    assert r.chosen.text == "Monticello Burial Vault"
    # ⚠️ AND THE CARRIED FILTER, NOT THE FORM DEFAULT, IS WHAT DECIDED IT — the matches
    # left in play are the carried one alone, so there was no form tie to break.
    assert len(r.matches) == 1


def test_consume_loose_tolerates_the_punctuation_a_director_omits():
    """"st m" against `St. Mary's Cemetery`. A lowercased `startswith` fails on the
    PERIOD, which is why this is a character walk.

    ⚠️ MY FIRST VERSION OF THIS TEST EXPECTED "stm" TO MATCH TOO, AND IT WAS WRONG —
    the code is right and the expectation was mine. Skipping in the TERM stops at a
    SPACE: the period in "St." is skippable, the space after it is not, so an unspaced
    prefix cannot cross a word boundary the director did not type. `ghost.ts` returns
    -1 for the same input by the same line, and the generated corpus holds the pair to
    it. Recorded rather than quietly amended, because "punctuation-tolerant" reads as
    "whitespace-tolerant" and it is not.
    """
    assert consume_loose("St. Mary's Cemetery", "st m") > 0
    assert consume_loose("St. Mary's Cemetery", "st. m") > 0
    assert consume_loose("St. Mary's Cemetery", "st mary's") > 0
    # ⚠️ PUNCTUATION IS SKIPPED, A SPACE IS A BOUNDARY.
    assert consume_loose("St. Mary's Cemetery", "stm") == -1
    # a space in the prefix forces a word boundary, so it cannot match mid-word
    assert consume_loose("Stmichaels Chapel", "st m") == -1


# ───────────────────────────────────────────────────────────────────────────
# 3 — James's sentence, end to end
# ───────────────────────────────────────────────────────────────────────────

def test_JAMESS_SENTENCE_IS_UNDERSTOOD_WHOLE(db, tenant):
    """The retest, as he will type it. Nothing he said is unrecognized."""
    ex = extract_text(db, tenant_id=tenant, text=WALK)
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home"
    assert ex.values.get("vault") == "Monticello Burial Vault"
    assert ex.values.get("service_date") == "2026-10-22"
    assert ex.values.get("service_time") == "10:00"
    assert ex.values.get("cemetery") == "St. Mary's Cemetery"
    assert ex.unrecognized == (), ex.unrecognized
    assert not any(s.state == "unrecognized" for s in ex.spans), _spans(ex, WALK)


def test_the_date_span_is_the_WEEKDAY_ALONE(db, tenant):
    """⚠️ THE SPAN THAT LIED. Before the fix this covered 'hopk monti thursday' — 19
    characters for evidence that is one word — and told the director that the funeral
    home's abbreviation had fed a date."""
    ex = extract_text(db, tenant_id=tenant, text=WALK)
    date_spans = [s for s in ex.spans if "service_date" in s.field_ids]
    assert len(date_spans) == 1
    s = date_spans[0]
    assert WALK[s.start:s.end] == "thursday"


def test_each_abbreviation_is_its_OWN_span_tied_to_its_OWN_field(db, tenant):
    """⚠️ ONE SPAN PER FIELD, WHICH IS WHAT MAKES THE CARET-TO-ROW LINK TRUE. A block
    covering three words can only light one row, and would light the wrong one for two
    of the three."""
    ex = extract_text(db, tenant_id=tenant, text=WALK)
    got = {WALK[s.start:s.end]: s.field_ids for s in ex.spans if s.state == "captured"}
    assert got.get("hopk") == ("funeral_home",)
    assert got.get("monti") == ("vault",)
    assert got.get("thursday") == ("service_date",)


def test_a_span_that_fed_a_field_is_NEVER_marked_unrecognized(db, tenant):
    """James's item 2, stated as the invariant rather than as the example.

    ⚠️ AND IT IS ASSERTED OVER EVERY SPAN, NOT OVER HIS SENTENCE ONLY, because the rule
    is about the two states being exclusive and a single phrase cannot show that.
    """
    for text in (WALK, "order riv conti fri 11 graveside", "order hop venet sat",
                 "hopkins funeral home monticello thursday", "tent only, zzzqqq"):
        ex = extract_text(db, tenant_id=tenant, text=text)
        captured = {
            (s.start, s.end) for s in ex.spans if s.state == "captured"
        }
        unknown = {(s.start, s.end) for s in ex.spans if s.state == "unrecognized"}
        assert not (captured & unknown), text
        # ⚠️ AND NOT MERELY DISJOINT — NO OVERLAP AT ALL, which is the stronger claim
        # and the one his screenshot was about.
        for a, b in unknown:
            for c, d in captured:
                assert not (a < d and c < b), f"{text!r}: [{a},{b}) overlaps [{c},{d})"


# ───────────────────────────────────────────────────────────────────────────
# 4 — unrecognized spans are word-level
# ───────────────────────────────────────────────────────────────────────────

def test_unrecognized_spans_are_WORD_LEVEL(db, tenant):
    """James: "unrecognized spans are word-level". A slice is whatever happened to be
    left between two claims; it is not a unit of meaning."""
    ex = extract_text(db, tenant_id=tenant, text="order zzzqqq wobble thursday")
    unknown = [ex_text for ex_text in
               (("order zzzqqq wobble thursday")[s.start:s.end]
                for s in ex.spans if s.state == "unrecognized")]
    assert unknown == ["zzzqqq", "wobble"], unknown


def test_a_noise_word_is_never_underlined(db, tenant):
    """⚠️ THE OLD CODE TESTED THE SLICE AND MARKED THE SLICE, so "order zzzqqq" put a
    dotted line under "order" — a word the engine deliberately ignores. Per word, the
    test and the mark are the same unit."""
    t = "order zzzqqq"
    ex = extract_text(db, tenant_id=tenant, text=t)
    marked = [t[s.start:s.end] for s in ex.spans if s.state == "unrecognized"]
    assert marked == ["zzzqqq"], marked
    # the control: the unknown word IS reported, so this is about "order" and not about
    # a renderer that marks nothing.
    assert any("zzzqqq" in u for u in ex.unrecognized)


# ───────────────────────────────────────────────────────────────────────────
# 5 — the word under the caret belongs to the ghost
# ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("typed", ["Contin", "Continenta", "34 inch Contin", "Hopk"])
def test_the_FINAL_word_is_still_being_typed_and_is_not_guessed(db, tenant, typed):
    """⚠️ THIS IS WHAT RECONCILES TWO RULINGS THAT LOOK OPPOSED, and the reconciliation
    is the one judgement in this slice.

        2026-10-13  "a half-typed word resolves to nothing"
        2026-10-20  "if hopk can only mean Hopkins, it's Hopkins"

    They are one rule over different words. James's own description says which:
    "once you type a SPACE AND KEEP GOING without pressing Tab". `ghost.ts` already
    draws that line — it completes only when "the caret must be at the END" — so the
    final word is the ghost's and everything before it is committed.

    ⚠️ ALL FOUR OF THE 2026-10-13 CASES SIT AT THE END OF THEIR TEXT. I checked that
    rather than assuming it; had any sat mid-sentence the two rulings really would
    have collided and this would be James's call, not mine.
    """
    ex = extract_text(db, tenant_id=tenant, text=typed)
    assert not ex.values, ex.values
    assert not ex.picks, ex.picks
    assert ex.unrecognized, "the half-typed word vanished instead of being shown"


def test_the_SAME_abbreviation_resolves_once_the_director_moves_past_it(db, tenant):
    """The other half of the rule above, and the pair is the whole point: the same four
    characters are a work in progress at the end and a decision in the middle."""
    assert not extract_text(db, tenant_id=tenant, text="order hopk").values
    moved_on = extract_text(db, tenant_id=tenant, text="order hopk thursday")
    assert moved_on.values.get("funeral_home") == "Hopkins Funeral Home"


def test_an_earlier_SEGMENT_has_moved_on_even_at_its_own_end(db, tenant):
    """"hopk, thursday" — "hopk" ends its segment but the director has plainly moved
    past it. Only the last segment has an open tail.

    ⚠️ THE OPEN-TAIL FLAG IS PASSED AT TWO CALL SITES AND THEY HOLD IT JOINTLY, WHICH I
    MEASURED RATHER THAN ASSUMED. `extract_text` runs two loops over the segments — one
    for values, one for spans — and both compute the same values, so breaking EITHER
    site alone left this test green and breaking BOTH turned it red:

        broken: pass 1 only (values loop)   96 passed
        broken: pass 2 only (spans loop)    96 passed
        broken: BOTH                        1 failed

    So this assertion cannot distinguish them. The one below can: spans come ONLY from
    the second loop, which gives that site a red of its own. CLAUDE.md §11 — half of a
    redundant pair is not the pair.
    """
    ex = extract_text(db, tenant_id=tenant, text="hopk, thursday 10 am")
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home"


def test_the_SPANS_loop_honours_the_open_tail_too(db, tenant):
    """⚠️ SPANS COME FROM ONE LOOP ONLY, so this is the second gating site's own red.

    Without it, the spans loop could be left passing `tail_open=True` for every segment
    and nothing would say so — the values would still be right, computed by the other
    loop, and the pane would simply stop tinting the abbreviation it had understood.
    """
    t = "hopk, thursday 10 am"
    ex = extract_text(db, tenant_id=tenant, text=t)
    captured = {t[s.start:s.end]: s.field_ids for s in ex.spans if s.state == "captured"}
    assert captured.get("hopk") == ("funeral_home",), [
        (t[s.start:s.end], s.state) for s in ex.spans
    ]


# ───────────────────────────────────────────────────────────────────────────
# 6 — ambiguity asks, and exact names still win
# ───────────────────────────────────────────────────────────────────────────

def test_an_ambiguous_abbreviation_asks_with_the_FULL_names(db, tenant):
    """"never a guess". The options are full names because the row has to show the
    director what the abbreviation would become."""
    t = "order riv conti fri 11 graveside"
    ex = extract_text(db, tenant_id=tenant, text=t)
    vault_picks = [p for p in ex.picks if p.field_id == "vault"]
    assert len(vault_picks) == 1, ex.picks
    labels = [o[0] for o in vault_picks[0].options]
    assert len(labels) > 1
    assert all("Contin" in label for label in labels), labels
    assert "vault" not in ex.values
    # and nothing he typed is unrecognized even so
    assert ex.unrecognized == (), ex.unrecognized


def test_a_FULLY_TYPED_name_is_still_read_by_the_exact_scan(db, tenant):
    """⚠️ THE ABBREVIATION PASS RUNS AFTER THE EXACT SCANS AND MUST NOT DISTURB THEM.
    A fully typed name has already been claimed, and `_claim` then refuses this pass."""
    ex = extract_text(
        db, tenant_id=tenant,
        text="hopkins funeral home monticello burial vault thursday 10 am",
    )
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home"
    assert ex.values.get("vault") == "Monticello Burial Vault"


def test_a_word_reaching_nothing_is_reported_not_invented(db, tenant):
    """⚠️ THIS TEST USED TO BE ABOUT "venet" AND IS SUPERSEDED THERE BY JAMES'S RULING
    OF 2026-10-21. Its original wording is kept in the paragraph below because the
    reasoning was right and only the DATA changed.

        "venet IS AN HONEST MISS AND THE REASON IS THE VOCABULARY, NOT THE RULE. The
        catalog spells them `White Venetian Burial Vault` and `Gold Venetian Burial
        Vault`; "venet" is a prefix of neither, so the GHOST offers nothing there
        either. Accepting it would be a DIFFERENT rule from the ghost's."

    That was accurate and it was the finding James then ruled on: he added tenant
    product names to the vocabulary rather than loosening the matching rule — so the
    ghost and the extractor still agree, and "venet" now reaches the `Venetian` product
    on a tenant that carries one. See `test_a_product_family_mapping_to_SEVERAL_variants_asks`.

    ⚠️ WHAT SURVIVES UNCHANGED IS THE PROPERTY, so it keeps a test: a word that reaches
    nothing is REPORTED, never invented.
    """
    t = "order hop zzzqqq sat"
    ex = extract_text(db, tenant_id=tenant, text=t)
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home"
    assert ex.values.get("service_date") == "2026-10-24"
    assert any("zzzqqq" in u for u in ex.unrecognized), ex.unrecognized
    assert "vault" not in ex.values


# ───────────────────────────────────────────────────────────────────────────
# 7 — the cross-language guard's own other half
# ───────────────────────────────────────────────────────────────────────────

def test_THE_CORPUS_MATCHES_THE_LIVE_RULE():
    """⚠️ ADDED BECAUSE THE DRIFT GUARD WAS ONLY HALF A GUARD, AND A BREAK TEST SHOWED IT.

    `tests/data/opas_prefix_corpus.json` is generated from this module and replayed by
    `ghost-agrees.test.ts`. Breaking the TypeScript rule turns that suite red
    immediately — measured, 7 and 4 failures for two separate mutations. But breaking
    the PYTHON rule left it GREEN for all eight mutations I tried, and the reason is
    obvious once stated: the corpus is a COMMITTED FILE. It does not change when the
    rule changes, so the TypeScript side keeps agreeing with a recording of the old
    rule.

    That is the shape CLAUDE.md §11 calls a check that passes for a reason unrelated to
    what it claims. The pair is only held if BOTH directions have a red:

        change the Python rule, do not regenerate   ->  THIS test fails
        regenerate the corpus, leave the ghost      ->  ghost-agrees.test.ts fails

    ⚠️ IT RECOMPUTES RATHER THAN RE-READS, so it cannot be satisfied by the file being
    self-consistent.
    """
    import json
    import pathlib

    from scripts.gen_prefix_corpus import KIND_SETS, PREFIXES, VOCAB_SPEC

    corpus = json.loads(
        (pathlib.Path(__file__).resolve().parent / "data" / "opas_prefix_corpus.json")
        .read_text(encoding="utf-8")
    )
    assert corpus["min_prefix"] == MIN_PREFIX

    vocab = tuple(Term(text=t, kind=k, carried=c, form=f) for t, k, c, f in VOCAB_SPEC)
    live = []
    for label, kinds in KIND_SETS.items():
        for p in PREFIXES:
            r = resolve_prefix(p, vocab, kinds)
            live.append({
                "prefix": p, "kind_set": label,
                "outcome": ("none" if r is None
                            else "chosen" if r.chosen is not None else "ambiguous"),
                "chosen": (r.chosen.text if r and r.chosen else None),
                "matches": sorted(m.text for m in r.matches) if r else [],
            })
    recorded = [
        {k: c[k] for k in ("prefix", "kind_set", "outcome", "chosen", "matches")}
        for c in corpus["cases"]
    ]
    assert live == recorded, (
        "the corpus is stale — re-run scripts/gen_prefix_corpus.py and re-run the "
        "frontend suite, which will then tell you whether the ghost still agrees"
    )

    # ⚠️ AND THE WALKS, which the resolutions cannot cover: a port can agree on every
    # answer while differing on the walk, and the walk is what draws the suffix.
    live_walks = [
        {"term": t, "prefix": p, "at": consume_loose(t, p)}
        for t in sorted({x[0] for x in VOCAB_SPEC})
        for p in PREFIXES
    ]
    assert live_walks == corpus["walks"]


def test_the_corpus_is_non_empty_and_exercises_every_outcome():
    """⚠️ THE POSITIVE CONTROL FOR THE TEST ABOVE. `[] == []` is True, so an empty or
    single-outcome corpus would satisfy it while proving nothing. CLAUDE.md §11:
    "require the control to be NON-ZERO, and read that number before the result it is
    vouching for."
    """
    import json
    import pathlib

    corpus = json.loads(
        (pathlib.Path(__file__).resolve().parent / "data" / "opas_prefix_corpus.json")
        .read_text(encoding="utf-8")
    )
    assert len(corpus["cases"]) > 50
    assert len(corpus["walks"]) > 50
    assert {c["outcome"] for c in corpus["cases"]} == {"none", "chosen", "ambiguous"}
    assert any(w["at"] > 0 for w in corpus["walks"])
    assert any(w["at"] == -1 for w in corpus["walks"])


# ───────────────────────────────────────────────────────────────────────────
# 8 — ambiguity discovered one layer down
# ───────────────────────────────────────────────────────────────────────────

def test_an_abbreviation_that_narrows_to_ONE_NAME_matching_TWO_VARIANTS_asks(db, carrier):
    """⚠️ FOUND ON PRODUCTION, AFTER LOCAL WAS GREEN. James's second phrase, `order riv
    conti fri 11 graveside`, behaved differently on the two databases:

        testco      "conti" -> 3 vocabulary terms, NONE carried -> ambiguous at the
                    PREFIX layer -> a pick. Green.
        sunnycrest  "conti" -> the carried filter leaves exactly `Continental Burial
                    Vault` -> chosen -> and THAT NAME matches two variants differing by
                    SIZE, so `variant_template_id` is None. My first version returned
                    False there and "conti" came back NOT UNDERSTOOD.

    A word the engine narrowed to two variants is not a word it failed to understand,
    and reporting it as one is the complaint this whole slice answers. `continental b`
    reaches the same branch locally, which is why the test can exist at all.

    ⚠️ IT IS A REMINDER THAT A TENANT'S `carried` FLAGS CHANGE WHICH BRANCH RUNS. Two
    databases, same code, different path — so "green locally" was never evidence here.
    """
    t = "order conti thursday"
    ex = extract_text(db, tenant_id=carrier, text=t)
    vault_picks = [p for p in ex.picks if p.field_id == "vault"]
    assert len(vault_picks) == 1, (ex.values, ex.picks)
    assert len(vault_picks[0].options) == 2
    assert "vault" not in ex.values
    # ⚠️ AND THE WORDS ARE CLAIMED, NOT LEFT DOTTED. The point of asking rather than
    # returning False is that the director sees a question instead of a shrug.
    assert ex.unrecognized == (), ex.unrecognized
    assert not any(s.state == "unrecognized" for s in ex.spans), [
        (t[s.start:s.end], s.state) for s in ex.spans
    ]
    # ⚠️ THE CONTROL: it was MY pass that settled it, not the n-gram scan. "conti" is
    # not a catalog word, so the scan cannot reach it — and on a tenant carrying
    # NEITHER Continental the prefix layer stays ambiguous and a different branch runs.
    assert any(t[sp.start:sp.end] == "conti" for sp in ex.spans
               if "vault" in sp.field_ids), [
        (t[sp.start:sp.end], sp.state, sp.field_ids) for sp in ex.spans
    ]


def test_both_vault_paths_settle_the_same_way(db, tenant):
    """⚠️ THE ABBREVIATION PASS MIRRORS THE N-GRAM SCAN'S DECISION, AND A FORCED COPY
    NEEDS SOMETHING HOLDING IT. Refactoring the n-gram scan — 140 lines of ruled and
    heavily tested behaviour — was outside this dispatch, so the same rule is expressed
    twice: form-only takes the form the slice implies, anything else asks.

    This pins the two to the same answer for the same effective input: a fully typed
    name and an abbreviation of it must settle identically. If someone changes one
    decision and not the other, this is what says so.
    """
    full = extract_text(db, tenant_id=tenant, text="order continental burial vault thursday")
    abbr = extract_text(db, tenant_id=tenant, text="order continental b thursday")
    assert ("vault" in full.values) == ("vault" in abbr.values)
    assert [p.field_id for p in full.picks] == [p.field_id for p in abbr.picks]
    fp = [p for p in full.picks if p.field_id == "vault"]
    ap = [p for p in abbr.picks if p.field_id == "vault"]
    assert len(fp) == len(ap) == 1
    # the OPTIONS are the same set, which is the part that would drift
    assert sorted(o[0] for o in fp[0].options) == sorted(o[0] for o in ap[0].options)

    # ⚠️ AND THE FORM-ONLY CASE TOO, which takes a value plus a Switch rather than a
    # pick — the other half of the mirrored decision.
    full_f = extract_text(db, tenant_id=tenant, text="order monticello thursday")
    abbr_f = extract_text(db, tenant_id=tenant, text="order monti thursday")
    assert full_f.values.get("vault") == abbr_f.values.get("vault")
    assert full_f.values.get("vault") == "Monticello Burial Vault"


@pytest.fixture
def twins(db):
    """A tenant with TWO funeral homes under one name, in two towns.

    ⚠️ A REAL FIXTURE RATHER THAN A CONTRACT ASSERTION, BECAUSE A BREAK TEST SHOWED THE
    DIFFERENCE. My first version of the test below asserted only that
    `resolve_from_rows` refuses to pick between two records — true, and it left the
    branch that USES that refusal completely untested: disabling the funeral-home
    deeper-ambiguity branch kept all 46 tests green. Neither database has a duplicate,
    so the fixture makes one.
    """
    from app.models.company import Company
    from app.models.company_entity import CompanyEntity

    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Twins Co", slug=f"twins-{cid[:8]}",
                   is_active=True, vertical="manufacturing"))
    db.flush()
    for city in ("Auburn", "Skaneateles"):
        db.add(CompanyEntity(id=str(uuid.uuid4()), company_id=cid,
                             name="Hopkins Funeral Home", city=city))
    db.commit()
    try:
        yield cid
    finally:
        db.rollback()
        db.execute(sql("DELETE FROM company_entities WHERE company_id = :c"), {"c": cid})
        db.execute(sql("DELETE FROM companies WHERE id = :c"), {"c": cid})
        db.commit()


def test_a_funeral_home_abbreviation_matching_two_RECORDS_asks(db, twins):
    """The same shape on the party side: one NAME, two RECORDS.

    ⚠️ THE VOCABULARY DEDUPES ON (kind, text), so two identical names are ONE term and
    the prefix layer resolves cleanly — the ambiguity only appears when the expanded
    name goes back through `resolve_funeral_home`. That is precisely the "one layer
    down" case, and it must ask rather than report the word as unplaced.
    """
    t = "order hopk thursday"
    ex = extract_text(db, tenant_id=twins, text=t)
    fh_picks = [p for p in ex.picks if p.field_id == "funeral_home"]
    assert len(fh_picks) == 1, (ex.values, ex.picks)
    assert len(fh_picks[0].options) == 2
    assert "funeral_home" not in ex.values
    assert ex.unrecognized == (), ex.unrecognized
    assert any(t[sp.start:sp.end] == "hopk" for sp in ex.spans
               if "funeral_home" in sp.field_ids), [
        (t[sp.start:sp.end], sp.state, sp.field_ids) for sp in ex.spans
    ]


def test_the_resolver_itself_refuses_to_pick_between_two_records():
    """The contract the branch above depends on, kept as its own assertion."""
    from app.services.party_resolver import resolve_from_rows

    fr = resolve_from_rows(
        [("a", "Hopkins Funeral Home", "Auburn"),
         ("b", "Hopkins Funeral Home", "Skaneateles")],
        "Hopkins Funeral Home", None,
    )
    assert fr.party_id is None, "two records must not resolve to one"
    assert len(fr.candidates) == 2
    assert fr.discriminators, "the resolver must say what would narrow it"


# ───────────────────────────────────────────────────────────────────────────
# 9 — two paths, one artefact
# ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "backend_rel,frontend_rel",
    [
        ("data/opas_prefix_corpus.json",
         "src/components/opas/__fixtures__/opas_prefix_corpus.json"),
        ("data/opas_requests.jsonl",
         "src/components/opas/__fixtures__/opas_requests.jsonl"),
    ],
)
def test_the_frontend_copy_is_BYTE_IDENTICAL(backend_rel, frontend_rel):
    """⚠️ THESE FILES EXIST TWICE AND THAT IS A DEPLOY CONSTRAINT, NOT A DESIGN CHOICE.

    My first version had the TypeScript suites import the backend paths directly
    (`../../../../backend/tests/data/...`). It typechecked, it built, every suite was
    green — and it FROZE THE FRONTEND DEPLOY. The Docker build copies only `frontend/`,
    `tsconfig.app.json` includes `src`, and `npm run build` is `tsc -b && vite build`:
    so `tsc` could not resolve a path outside the container, vite never ran, and no new
    bundle was ever emitted. The symptom was a deploy sitting at the previous commit
    with nothing failing anywhere I had looked.

    ⚠️ SO THE COPIES ARE HELD BYTE-IDENTICAL RATHER THAN TRUSTED. Without this
    assertion, two paths holding the same data is the two-lists defect: the frontend
    would keep scoring against a stale recording and report green while the rule moved.
    The corpus is written to both paths by one generator; the request set is curated and
    copied. Either way, this is what says so when they diverge.
    """
    import pathlib

    be = pathlib.Path(__file__).resolve().parent / backend_rel
    fe = pathlib.Path(__file__).resolve().parents[2] / "frontend" / frontend_rel
    assert be.exists(), be
    assert fe.exists(), (
        f"{fe} is missing — re-run scripts/gen_prefix_corpus.py, or copy the set"
    )
    # ⚠️ BYTES, NOT PARSED CONTENT. A JSON comparison would pass over a file the
    # frontend's `?raw` import reads differently (line endings, trailing newline).
    assert be.read_bytes() == fe.read_bytes(), (
        f"{backend_rel} and {frontend_rel} have diverged"
    )
    # the control: the files are not both empty
    assert len(be.read_bytes()) > 500


def test_no_frontend_source_file_imports_across_the_repo_boundary():
    """⚠️ THE RATCHET FOR THE DEFECT ABOVE, because the assertion above only catches a
    DIVERGENCE and the deploy freeze was caused by an IMPORT PATH.

    Anything under `frontend/src` that reaches into `backend/` typechecks locally and
    cannot resolve inside the frontend build container. One failing import takes the
    whole bundle down, silently, because `tsc -b` runs before `vite build` and a deploy
    that emits no bundle looks exactly like a deploy that has not happened yet.
    """
    import pathlib
    import re

    src = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
    offenders = []
    for path in src.rglob("*.ts*"):
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"""from\s+["']([^"']+)["']|import\s+["']([^"']+)["']""", text):
            spec = m.group(1) or m.group(2) or ""
            if "backend/" in spec or re.match(r"^(\.\./){3,}", spec):
                offenders.append(f"{path.relative_to(src)}: {spec}")
    assert offenders == [], offenders

    # ⚠️ THE POSITIVE CONTROL: the scan really does walk files and really would match.
    # An empty `offenders` is satisfied by a glob that found nothing at all.
    assert sum(1 for _ in src.rglob("*.ts*")) > 100
    probe = 'import x from "../../../../backend/tests/data/thing.json"'
    assert re.search(r"""from\s+["']([^"']+)["']""", probe)
    assert "backend/" in re.search(r"""from\s+["']([^"']+)["']""", probe).group(1)


# ───────────────────────────────────────────────────────────────────────────
# 10 — tenant product names (James, 2026-10-21)
# ───────────────────────────────────────────────────────────────────────────

def test_a_product_name_is_the_route_to_a_family_the_variants_cannot_spell(db, tenant):
    """⚠️ RULED 2026-10-21: "People say 'a Venetian', not 'a White Venetian Burial
    Vault'."

    The catalog spells them `White Venetian Burial Vault` and `Gold Venetian Burial
    Vault`, so "venet" is a prefix of NEITHER — the ghost offered nothing there either,
    which is why the previous slice reported it as an honest miss rather than fixing it
    unilaterally. A tenant's `products` row is named the way the office talks.
    """
    v = tuple(build_vocabulary(db, tenant))
    assert any(t.kind == "product" for t in v), "no product terms in the vocabulary"
    r = resolve_prefix("venet", v, KINDS_VAULT)
    assert r is not None and r.chosen is not None
    assert r.chosen.text == "Venetian"
    assert r.chosen.kind == "product"


def test_a_product_family_mapping_to_SEVERAL_variants_asks(db, tenant):
    """"it never guesses" — the family resolves, then the ordinary product resolver
    finds several variants and the choice list appears. End to end, through the bar."""
    t = "order hop venet sat"
    ex = extract_text(db, tenant_id=tenant, text=t)
    vault_picks = [p for p in ex.picks if p.field_id == "vault"]
    assert len(vault_picks) == 1, (ex.values, ex.picks)
    labels = [o[0] for o in vault_picks[0].options]
    assert len(labels) > 1
    assert all("Venetian" in label for label in labels), labels
    assert "vault" not in ex.values
    # the funeral home and the date are unaffected, and nothing is left dotted
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home"
    assert ex.values.get("service_date")
    assert ex.unrecognized == (), ex.unrecognized


def test_A_PRODUCT_NAME_NEVER_OUTRANKS_A_REACHABLE_VARIANT(db, tenant):
    """⚠️ THE REGRESSION THIS RULING COULD HAVE CAUSED, AND THE REASON FOR STEP 4a.

    sunnycrest's `products` table holds `Monticello Burial Vault` and `Continental
    Burial Vault` — so adding product names to the vocabulary puts a second term in
    play for "monti", and two terms with different texts ASK. That would have turned
    the phrasing James had just confirmed working back into a question.

    A product name is a route of LAST RESORT: it adds reach where the variants' own
    spellings cannot be prefixed, and says nothing new where they can.
    """
    v = tuple(build_vocabulary(db, tenant))
    r = resolve_prefix("monti", v, KINDS_VAULT)
    assert r is not None and r.chosen is not None
    assert not r.ambiguous, [m.text for m in r.matches]
    # ⚠️ AND IT IS STILL THE RIGHT VAULT END TO END, which is what James retests.
    ex = extract_text(db, tenant_id=tenant, text=WALK)
    assert ex.values.get("vault") == "Monticello Burial Vault"
    assert ex.unrecognized == (), ex.unrecognized


@pytest.fixture
def both(db):
    """A tenant carrying BOTH a family name and a specific variant.

    ⚠️ THIS FIXTURE EXISTS BECAUSE A BREAK TEST FOUND THE RANKING STEP UNPINNED.
    Removing `_rank_down_products` turned only the corpus-freshness check red — no
    behavioural test moved — because on testco the carried filter already removes the
    uncarried variants before the ranking can see them, and on sunnycrest the product
    row is spelled IDENTICALLY to the variant so the same-text rule collapses it.

    The step bites exactly when a tenant carries a variant AND a differently-spelled
    family name, which is ordinary data: a price list naming both "Monticello" and
    "Monticello Burial Vault". Without the ranking, "monti" matches two different texts
    and ASKS — the regression James's own retest would have caught.
    """
    from app.models.company import Company
    from app.models.product import Product

    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Both Co", slug=f"both-{cid[:8]}",
                   is_active=True, vertical="manufacturing"))
    db.flush()
    for name in ("Monticello", "Monticello Burial Vault"):
        db.add(Product(id=str(uuid.uuid4()), company_id=cid, name=name, is_active=True))
    db.commit()
    try:
        yield cid
    finally:
        db.rollback()
        db.execute(sql("DELETE FROM products WHERE company_id = :c"), {"c": cid})
        db.execute(sql("DELETE FROM companies WHERE id = :c"), {"c": cid})
        db.commit()


def test_the_ranking_is_what_keeps_monti_AN_ANSWER_not_a_question(db, both):
    """⚠️ THE BEHAVIOURAL RED FOR STEP 4a. Both a carried variant and a carried family
    name match "monti"; the variant must win and the value must still be the vault.
    """
    v = tuple(build_vocabulary(db, both))
    kinds = {t.kind for t in v if t.text.lower().startswith("monti")}
    assert "product" in kinds and "vault" in kinds, kinds

    r = resolve_prefix("monti", v, KINDS_VAULT)
    assert r is not None and r.chosen is not None
    assert not r.ambiguous, [(m.text, m.kind) for m in r.matches]
    assert r.chosen.kind != "product", (r.chosen.text, r.chosen.kind)

    ex = extract_text(db, tenant_id=both, text="order monti thursday")
    assert ex.values.get("vault") == "Monticello Burial Vault", dict(ex.values)
    assert not [p for p in ex.picks if p.field_id == "vault"], ex.picks


def test_products_still_ask_when_NO_variant_is_reachable(db, tenant):
    """⚠️ THE OTHER SIDE OF STEP 4a, so it cannot be read as "products never win".
    Two product names and no variant must still produce a question.
    """
    v = (
        Term(text="Tent Only (with)", kind="product", carried=True),
        Term(text="Tent Only (without)", kind="product", carried=True),
    )
    r = resolve_prefix("tent", v, KINDS_VAULT)
    assert r is not None and r.chosen is None and r.ambiguous


def test_the_equipment_row_still_owns_tent_only(db, tenant):
    """⚠️ A PRODUCT NAMED "Tent Only" IS NOW IN THE VAULT VOCABULARY, AND THE EQUIPMENT
    PASS MUST STILL WIN. Measured rather than assumed: "tent only" is
    `cemetery_equipment`, and a vault pass that claimed it would turn a correction to
    the equipment into an ambiguous question about a product — which is the exact
    defect `once()`'s docstring records from 2026-10-13.
    """
    for t in ("tent only", "order hopk tent only thursday"):
        ex = extract_text(db, tenant_id=tenant, text=t)
        assert ex.values.get("cemetery_equipment") == "tent_only", (t, dict(ex.values))
        assert "vault" not in ex.values, (t, dict(ex.values))
        assert not [p for p in ex.picks if p.field_id == "vault"], (t, ex.picks)
