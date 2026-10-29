"""Clause 2 of guided capture slice 2. James's dispatch of 2026-10-28: "names mid-sentence".

An unknown word sitting between two things the engine DID understand is the decedent,
without needing "last name" in front of it.

⚠️ THE EVIDENCE IS POSITION, NOT SHAPE, AND THAT IS THE WHOLE DESIGN. The surname rules
in `typed_extraction` all require a marker, and their own comments say why: surnames are
an OPEN set, so any rule about what a name LOOKS like is wrong about somebody's family.
This clause never asks what the word looks like. It asks what surrounds it.

⚠️ FOUND BY JAMES'S OWN WALK. Measured on production 2026-10-29, his step-1 sentence
"new order for hopkins, smith, thursday, 2 chairs, st marys skaneateles" returned
`deceased_name=None` with `unrecognized=('smith',)` — so "nothing should be left
unplaced" was not true, and the marker form worked the whole time.

⚠️ IT RUNS AT WHOLE-TEXT ALTITUDE, AND THE FIRST ATTEMPT PUT IT IN `extract_line` WHERE
IT COULD NOT FIRE. A director's commas SPLIT the text into statements: that sentence is
five segments, and inside the "smith" segment there is nothing before or after it. The
per-line version fired on NOTHING and the probe said so. "Mid-sentence" in this codebase
means mid-TEXT.

### Why this file seeds its own tenant

⚠️ BECAUSE testco's VOCABULARY COLLIDES WITH ORDINARY PERSONAL NAMES, three times over,
and each collision makes a clause-2 test assert the opposite of what it says:

  "smith"    -> **Smith & Sons Funeral Home** exists, so the word resolves to a record
                and the record guard refuses it. `test_a_surname_is_a_name.py` already
                records this and uses "Keegan" for the same reason.
  "john"     -> prefix-matches **Johnson Funeral Home**, measured: "order for riverside,
                john keegan, thursday" sets `funeral_home='Johnson Funeral Home'` and
                leaves only "keegan" for the decedent. A two-word-name test on testco
                therefore tests the prefix resolver, not this clause.
  "riversde" -> a typo of **Riverside**, which is the typo guard's case and not a free
                word either.

A tenant seeded here holds exactly three records, all of them deliberately unlike a
person's name, so every word below is free and the assertions mean what they say.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from urllib.parse import urlparse

import pytest

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.services.capture.typed_extraction import extract_text

from tests._cleanup import purge_companies_by_slug

SLUG = "tc-bare-name"
TODAY = date(2026, 10, 29)


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "")
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture()
def tenant():
    """Three records, none of them shaped like a surname."""
    _local_only()
    db = SessionLocal()
    purge_companies_by_slug(db, SLUG)
    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Bare Name Co", slug=SLUG, vertical="manufacturing"))
    db.flush()
    db.add_all([
        CompanyEntity(id=str(uuid.uuid4()), company_id=cid,
                      name="Lakeshore Funeral Chapel", city="Auburn", state="NY",
                      is_funeral_home=True),
        Cemetery(id=str(uuid.uuid4()), company_id=cid, name="Hillcrest Cemetery",
                 city="Auburn", state="NY", is_active=True),
    ])
    db.commit()
    yield db, cid
    db.rollback()
    purge_companies_by_slug(db, SLUG)
    db.commit()
    db.close()


def _ex(db, cid, text):
    return extract_text(db, tenant_id=cid, text=text)


# ── the controls, first, because every assertion below is about one word ─────


def test_the_VOCABULARY_IS_WHAT_THIS_FILE_CLAIMS(tenant):
    """⚠️ THE POSITIVE CONTROL ON THE FIXTURE ITSELF. This file's whole argument is that
    its words are free of the tenant's records. If the seed silently stopped creating
    them, "lakeshore" would stop resolving, nothing would be claimed, and clause 2 would
    stop firing for a reason that has nothing to do with clause 2."""
    db, cid = tenant
    ex = _ex(db, cid, "order for lakeshore thursday")
    assert ex.values.get("funeral_home") == "Lakeshore Funeral Chapel", ex.values
    assert ex.values.get("service_date"), ex.values


def test_a_BARE_name_was_NOT_captured_before_this_clause(tenant):
    """⚠️ PINS THE GAP, so the test below is known to be testing something. A marker is
    required by every other name rule; this records that the bare form needed a new one."""
    db, cid = tenant
    ex = _ex(db, cid, "order for lakeshore bramwell thursday")
    assert ex.values.get("deceased_name") == "bramwell", ex.values
    # and the marker path, which must keep working untouched
    ex2 = _ex(db, cid, "order for lakeshore last name bramwell thursday")
    assert ex2.values.get("deceased_name") == "bramwell", ex2.values


# ── the clause ───────────────────────────────────────────────────────────────


def test_a_word_between_two_UNDERSTOOD_things_is_the_decedent(tenant):
    """James's own sentence shape, with the commas that split it into statements."""
    db, cid = tenant
    ex = _ex(db, cid, "new order for lakeshore, bramwell, thursday, 2 chairs")
    assert ex.values.get("deceased_name") == "bramwell", ex.values
    assert ex.unrecognized == (), ex.unrecognized


def test_the_word_STOPS_BEING_HELD_when_it_is_placed(tenant):
    """⚠️ OTHERWISE THE PANE SHOWS IT TWICE — filled on the Deceased row AND in "not
    placed yet". Asserted separately from the value because they are two different
    writes, and the first version of the clause did the first without the second."""
    db, cid = tenant
    ex = _ex(db, cid, "new order for lakeshore, bramwell, thursday")
    assert ex.values.get("deceased_name") == "bramwell"
    assert "bramwell" not in [u.casefold() for u in ex.unrecognized], ex.unrecognized


def test_the_SPAN_reads_as_captured_not_unrecognized(tenant):
    """⚠️ THE BAR UNDERLINES WHAT IT UNDERSTOOD AND DOTS WHAT IT DID NOT. A placed name
    whose span still says `unrecognized` is drawn as unknown text over a filled row."""
    db, cid = tenant
    sent = "new order for lakeshore, bramwell, thursday"
    ex = _ex(db, cid, sent)
    mine = [sp for sp in ex.spans if sent[sp.start:sp.end].casefold() == "bramwell"]
    assert mine, [(sp.start, sp.end, sent[sp.start:sp.end]) for sp in ex.spans]
    assert all(sp.state == "captured" for sp in mine), [(sp.state, sp.field_ids) for sp in mine]
    assert any("deceased_name" in (sp.field_ids or ()) for sp in mine), mine


def test_a_MARKER_still_outranks_the_position_rule(tenant):
    """⚠️ THE CLAUSE FIRES ONLY WHEN NOTHING ELSE SET THE FIELD, so the two name rules
    cannot disagree. Here both would fire and the marker's answer must stand."""
    db, cid = tenant
    ex = _ex(db, cid, "order for lakeshore, last name bramwell, thursday, dunmore")
    assert ex.values.get("deceased_name") == "bramwell", ex.values


# ── what it must refuse ──────────────────────────────────────────────────────


def test_a_NOISE_word_is_never_a_name(tenant):
    """⚠️ C7 OF THE DESIGN REVIEW, which James accepted: *"service monti must not make
    Service the deceased's name"*. `NOISE_WORDS` are the words a director says AROUND a
    value rather than as one."""
    db, cid = tenant
    for word in ("service", "burial", "funeral", "cemetery", "decedent", "date"):
        ex = _ex(db, cid, f"order for lakeshore, {word}, thursday")
        assert ex.values.get("deceased_name") is None, (word, ex.values)


def test_a_FUNCTION_word_is_never_a_name(tenant):
    """⚠️ THE CLOSED CLASS THAT ALREADY EXISTED, reused rather than restated. It was
    built on 2026-10-26 because "last name smith it is 1 oclock" produced the decedent
    "Smith It", and the ruling then was "fix it in the name rules, not a one-word
    stoplist". A bare run that IS a function word falls to the same argument."""
    db, cid = tenant
    for word in ("it", "is", "he", "was", "that", "they", "will"):
        ex = _ex(db, cid, f"order for lakeshore, {word}, thursday")
        assert ex.values.get("deceased_name") is None, (word, ex.values)


def test_a_TYPO_of_a_known_term_is_HELD_rather_than_named(tenant):
    """⚠️ THE GUARD'S FIRST VERSION DID NOT WORK AND A PROBE SHOWED IT, not a review.
    It compared the word to the FULL recorded name, and "lakeshor" is nowhere near
    "Lakeshore Funeral Chapel" as a string — so the typo was filed as the decedent's
    name. The comparison has to reach the words INSIDE a term, which is the same thing
    `held._candidates` says about "montcello".

    ⚠️ AND IT USES `is_typo_of_a_known_term`, NOT `did_you_mean`. The latter answers
    "which ONE term did they mean" and returns None when a word is near several — which
    is exactly the case where this clause must most certainly not claim the word.
    """
    db, cid = tenant
    # ⚠️ TRANSPOSITIONS AND DROPPED INTERIOR LETTERS, NOT TRUNCATIONS, and the
    # distinction was measured rather than assumed. "lakeshor" is a PREFIX of
    # "Lakeshore", so the abbreviation machinery resolves it to the funeral home — it is
    # never unclaimed and this clause never sees it. Including it here asserted that a
    # correctly-resolved word was held, which is the opposite of the truth; it is
    # asserted as resolution in the test below instead.
    for typo in ("lakshore", "lakehsore", "laekshore", "hillcrst", "hilcrest", "hilcrst"):
        ex = _ex(db, cid, f"order for lakeshore, {typo}, thursday")
        assert ex.values.get("deceased_name") is None, (typo, ex.values)
        assert typo in [u.casefold() for u in ex.unrecognized], (typo, ex.unrecognized)


def test_a_PREFIX_of_a_known_term_resolves_rather_than_being_held(tenant):
    """⚠️ THE CASE THE TYPO TEST ABOVE MUST NOT CONFLATE WITH A TYPO. A truncation is how
    the office abbreviates — "lakeshor" for Lakeshore — and `prefix_resolve` answers it.
    The word is CLAIMED, so it is neither a held typo nor a candidate decedent, and the
    three outcomes are genuinely different: resolved, held, named."""
    db, cid = tenant
    ex = _ex(db, cid, "order for lakeshore, lakeshor, thursday")
    assert ex.values.get("funeral_home") == "Lakeshore Funeral Chapel", ex.values
    assert ex.values.get("deceased_name") is None, ex.values
    assert ex.unrecognized == (), ex.unrecognized


def test_a_MULTI_WORD_run_containing_a_typo_is_refused_WHOLE(tenant):
    """⚠️ THE ASSERTION THAT MAKES THE PER-WORD HALF OF THE TYPO GUARD LOAD-BEARING, and
    it was added only because a break test showed the half was doing nothing. For a
    ONE-word run the two halves are identical — disabling the per-word check alone left
    everything green. They diverge exactly here: "bramwell hilcrest" is nowhere near any
    known term AS A WHOLE, so the whole-name check passes it, while the word "hilcrest"
    is one letter from Hillcrest.

    Without the per-word half the decedent becomes "bramwell hilcrest" — a real name
    welded to a misspelt cemetery, which is worse than holding both, because the
    director sees a filled row and no question.
    """
    db, cid = tenant
    ex = _ex(db, cid, "order for lakeshore, bramwell hilcrest, thursday")
    assert ex.values.get("deceased_name") is None, ex.values
    assert "bramwell hilcrest" in [u.casefold() for u in ex.unrecognized], ex.unrecognized


def test_a_LEADING_run_is_not_claimed(tenant):
    """⚠️ BOUNDED ON BOTH SIDES, BY THE DISPATCH'S OWN WORD "mid-sentence". A run with
    nothing understood before it is the opening of the text, which is where an
    unresolved funeral home or a stray opener lands — claiming it as a name would take
    the one word most likely to be a misspelt customer."""
    db, cid = tenant
    # ⚠️ THE INPUT MATTERS AND THE FIRST ONE CHOSEN DID NOT DISCRIMINATE. "bramwell,
    # order for lakeshore thursday" is refused by the NOISE skip, because "order" and
    # "for" are in the run — so removing the leading bound left this green and the test
    # was asserting someone else's rule. A break test found it. This phrasing puts the
    # claimed funeral home immediately after the run, so only the bound can refuse it.
    ex = _ex(db, cid, "bramwell, lakeshore, thursday")
    assert ex.values.get("deceased_name") is None, ex.values
    assert "bramwell" in [u.casefold() for u in ex.unrecognized], ex.unrecognized


def test_a_TRAILING_run_is_not_claimed(tenant):
    """⚠️ THE OTHER END, AND THE SAME ARGUMENT. Nothing understood follows it, so the
    word is not between two understandings. ⚠️ THIS IS A REAL LIMIT James may want
    changed: "order for lakeshore thursday bramwell" leaves the name held. It is
    asserted as unsupported rather than left undiscovered — the honest version of a
    boundary, and this is the line to change if he rules otherwise."""
    db, cid = tenant
    ex = _ex(db, cid, "order for lakeshore thursday, bramwell")
    assert ex.values.get("deceased_name") is None, ex.values
    assert "bramwell" in [u.casefold() for u in ex.unrecognized], ex.unrecognized


def test_a_word_that_IS_a_record_is_still_refused(tenant):
    """⚠️ THE RULING OF 2026-10-12 REACHES THIS CLAUSE TOO: "never take a funeral-home,
    cemetery or catalog word". Such a word is not UNCLAIMED in the first place — the
    resolver took it — so the clause never sees it. Asserted because the mechanism being
    indirect is exactly why it could regress unnoticed."""
    db, cid = tenant
    ex = _ex(db, cid, "order for lakeshore, hillcrest, thursday")
    assert ex.values.get("deceased_name") is None, ex.values
    assert ex.values.get("cemetery") == "Hillcrest Cemetery", ex.values
