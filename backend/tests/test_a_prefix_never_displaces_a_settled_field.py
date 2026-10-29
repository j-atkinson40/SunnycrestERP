"""Ruling 2 of 2026-10-29: a partial match is too weak to replace something settled.

James, from a finding in clause 2's own report: *"'john' prefix-matched Johnson Funeral
Home and silently overwrote the funeral home. 'Last mention wins' was meant for a word
that names the thing outright. A partial match is too weak to replace something already
settled."*

⚠️ THE DEFECT WAS AT THE SEGMENT MERGE, NOT IN THE PREFIX PASS, AND MEASURING IT IS WHAT
SHOWED THAT. Within ONE segment the field was always safe — `once()` refuses the prefix
pass when the field is set — so:

    'order for hopkins john thursday'    -> Hopkins   (one segment, always correct)
    'order for hopkins, john, thursday'  -> Johnson   (three segments, displaced)

It is the COMMA. Each segment is extracted in isolation, so "john" settles Johnson
knowing nothing about the first segment, and last-mention-wins then took the later one.

⚠️ AND IT IS PASS 1, NOT PASS 2, WHICH THE FIRST IMPLEMENTATION GOT WRONG. `extract_text`
runs two passes and takes `decided = frozenset(last)` BETWEEN them, so by pass 2 the
field is already decided and its loop skips it entirely. A guard added to pass 2 could
not fire, and the probe said so — the same altitude mistake clause 2's first version
made, one layer in.

### What is NOT being changed

"Last mention wins" stands. An exact or alias match still replaces an earlier exact one —
that is the whole of the existing ruling and every test of it is untouched. What this
narrows is only the case where the LATER mention is a partial match and the earlier one
was a name typed out.

### Why this matters now rather than later

⚠️ NO REAL ORDER HAS BEEN AFFECTED, and the first report of this overstated it. Measured
on production: `river` and `rivers` displace *Riverside Memorial Chapel* — but Riverside
is DEMO SEED and SO-2026-0001..0005 are seed orders. James corrected the claim that this
"could already have happened on a real order". The exposure is prospective, which is why
the ruling lands before the onboarding cutover; `scripts/check_prefix_name_collisions.py`
is re-run against Sunnycrest's real records then.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

import pytest

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.services.capture.typed_extraction import extract_text

from tests._cleanup import purge_companies_by_slug

SLUG = "tc-prefix-displace"


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "")
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture()
def tenant():
    """Two funeral homes where one is reached by a prefix of a personal name.

    ⚠️ "Hartwell" IS CHOSEN SO THAT "hart" REACHES IT, and "Hart" is a surname that
    already occurs in this database (SO-2026-0004's decedent is `hart`). The collision is
    therefore real rather than contrived, which is the whole subject of the ruling.
    """
    _local_only()
    db = SessionLocal()
    purge_companies_by_slug(db, SLUG)
    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Prefix Co", slug=SLUG, vertical="manufacturing"))
    db.flush()
    db.add_all([
        CompanyEntity(id=str(uuid.uuid4()), company_id=cid, name="Bellweather Chapel",
                      city="Auburn", state="NY", is_funeral_home=True),
        CompanyEntity(id=str(uuid.uuid4()), company_id=cid, name="Hartwell Funeral Home",
                      city="Cortland", state="NY", is_funeral_home=True),
        Cemetery(id=str(uuid.uuid4()), company_id=cid, name="Pinegrove Cemetery",
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


# ── the controls ─────────────────────────────────────────────────────────────


def test_the_PREFIX_really_does_reach_the_other_record(tenant):
    """⚠️ THE POSITIVE CONTROL, AND WITHOUT IT EVERY ASSERTION BELOW IS VACUOUS. The
    whole file is about a prefix match being REFUSED; if "hart" stopped reaching
    Hartwell at all, the refusals would all pass for the wrong reason."""
    db, cid = tenant
    ex = _ex(db, cid, "order for hart, thursday")
    assert ex.values.get("funeral_home") == "Hartwell Funeral Home", ex.values


def test_an_EXACT_name_still_replaces_an_exact_name(tenant):
    """⚠️ LAST MENTION WINS, UNTOUCHED. This is the rule the ruling narrows, so it is
    asserted here rather than left to the suites that already cover it — if this test
    ever fails, the narrowing went too far."""
    db, cid = tenant
    ex = _ex(db, cid, "order for bellweather, hartwell funeral home, thursday")
    assert ex.values.get("funeral_home") == "Hartwell Funeral Home", ex.values
    assert ex.prefix_offers == (), ex.prefix_offers


# ── the ruling ───────────────────────────────────────────────────────────────


def test_a_PREFIX_does_not_displace_a_name_typed_out(tenant):
    """James's own test case, in this tenant's vocabulary."""
    db, cid = tenant
    ex = _ex(db, cid, "order for bellweather, hart, thursday")
    assert ex.values.get("funeral_home") == "Bellweather Chapel", ex.values


def test_the_refused_word_is_HELD_not_dropped(tenant):
    """⚠️ REFUSING TO ACT ON A WORD IS NOT LICENCE TO STOP SHOWING IT. The director typed
    it; the pane has to say so, or the engine has quietly ignored input — which is the
    class the queued sweep's item 1 is about."""
    db, cid = tenant
    ex = _ex(db, cid, "order for bellweather, hart, thursday")
    assert "hart" in [u.casefold() for u in ex.unrecognized], ex.unrecognized


def test_it_carries_the_QUESTION_including_what_the_field_says_now(tenant):
    """⚠️ "Did you mean Hartwell Funeral Home?" IS ONLY ANSWERABLE IF THE DIRECTOR CAN
    SEE IT CURRENTLY SAYS BELLWEATHER, which is why the offer carries `instead_of`. A
    question that names only the alternative asks the director to remember the state.

    ⚠️ THE Yes/No SURFACE IS CLAUSE 5's AND IS NOT BUILT YET. The offer is produced now
    so the protection lands now; this test pins the data the surface will need, so the
    two cannot drift apart before they meet.
    """
    db, cid = tenant
    ex = _ex(db, cid, "order for bellweather, hart, thursday")
    assert len(ex.prefix_offers) == 1, ex.prefix_offers
    off = ex.prefix_offers[0]
    assert off.word == "hart", off
    assert off.term == "Hartwell Funeral Home", off
    assert off.instead_of == "Bellweather Chapel", off
    assert off.kind == "funeral_home", off


def test_a_PrefixOffer_is_not_a_typo_Suggestion(tenant):
    """⚠️ TWO DIFFERENT THINGS THAT BOTH RENDER AS "Did you mean X?". A `Suggestion` is a
    TYPO — the word is near the term and wrong. A `PrefixOffer` is a word that is a
    correct, exact prefix of the term, refused only because the field was already
    settled. `Suggestion.distance`'s own docstring says "0 never occurs here — an exact
    match is not a typo", so reusing it would have put a forbidden value in that field.
    """
    from app.services.capture.held import PrefixOffer, Suggestion

    db, cid = tenant
    ex = _ex(db, cid, "order for bellweather, hart, thursday")
    assert isinstance(ex.prefix_offers[0], PrefixOffer)
    assert not isinstance(ex.prefix_offers[0], Suggestion)
    assert not hasattr(ex.prefix_offers[0], "distance")


# ── what must keep working ───────────────────────────────────────────────────


def test_a_PREFIX_still_works_when_NOTHING_is_settled(tenant):
    """⚠️ THE ABBREVIATION MACHINERY IS HOW THE OFFICE TYPES and the ruling does not
    touch it. "hart" with no funeral home settled still resolves outright."""
    db, cid = tenant
    ex = _ex(db, cid, "order for hart, thursday")
    assert ex.values.get("funeral_home") == "Hartwell Funeral Home", ex.values
    assert ex.prefix_offers == (), ex.prefix_offers
    assert ex.unrecognized == (), ex.unrecognized


def test_ONE_segment_was_always_safe_and_still_is(tenant):
    """⚠️ THE MEASUREMENT THAT LOCATED THE DEFECT, KEPT AS A TEST. Without the comma the
    two words are one segment and `once()` already refused the prefix pass. If this ever
    starts failing, the defect has moved INTO the per-line path and the merge guard will
    not be where to look."""
    db, cid = tenant
    ex = _ex(db, cid, "order for bellweather hart thursday")
    assert ex.values.get("funeral_home") == "Bellweather Chapel", ex.values


def test_a_prefix_reaching_the_SAME_value_is_not_a_displacement(tenant):
    """⚠️ "bellweather, bellw" NAMES THE SAME RECORD TWICE and must be silent. Holding a
    word that changes nothing would put a question on the pane with no decision in it."""
    db, cid = tenant
    ex = _ex(db, cid, "order for bellweather, bellw, thursday")
    assert ex.values.get("funeral_home") == "Bellweather Chapel", ex.values
    assert ex.prefix_offers == (), ex.prefix_offers
    assert "bellw" not in [u.casefold() for u in ex.unrecognized], ex.unrecognized


def test_a_PREFIX_still_replaces_another_PREFIX(tenant):
    """⚠️ ADDED BECAUSE A BREAK TEST SHOWED NOTHING GUARDED THIS. Two partial matches are
    equals, so last-mention-wins applies between them untouched — the ruling is about a
    partial match displacing an OUTRIGHT name, not about prefixes generally.

    ⚠️ AND IT IS THE CLAUSE `field_id not in _approx_fields` THAT MAKES IT TRUE. Forcing
    that clause to `True` — i.e. treating whatever is already there as always outright —
    left every other test in this file green while silently freezing the first prefix in
    place. That is the half a reader would assume was covered and was not.
    """
    db, cid = tenant
    ex = _ex(db, cid, "order for hart, bellw, thursday")
    assert ex.values.get("funeral_home") == "Bellweather Chapel", ex.values
    assert ex.prefix_offers == (), ex.prefix_offers
    assert ex.unrecognized == (), ex.unrecognized


def test_an_EXACT_match_still_replaces_a_PREFIX_match(tenant):
    """⚠️ THE ASYMMETRY IS THE POINT, AND IT IS THE HALF A SIMPLER RULE WOULD HAVE LOST.
    "first mention wins" or "never overwrite" would both keep the prefix's answer here.
    The ruling is about STRENGTH, not order: an outright name beats a partial one in
    either direction, so a prefix settled first is replaced by a name typed out after.
    """
    db, cid = tenant
    ex = _ex(db, cid, "order for hart, bellweather chapel, thursday")
    assert ex.values.get("funeral_home") == "Bellweather Chapel", ex.values
    assert ex.prefix_offers == (), ex.prefix_offers
