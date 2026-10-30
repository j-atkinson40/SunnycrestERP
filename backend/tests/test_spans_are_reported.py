"""The extraction reports WHICH text it claimed, and for which field.

⚠️ JAMES 2026-10-15: "The extraction response returns the claimed spans: field,
start, end, state (captured / conflict / unrecognized)." This file covers the
BACKEND half — the spans themselves. The rendering over the bar is a separate piece.

⚠️ THE COORDINATES ARE WHOLE-TEXT, NOT PER-SEGMENT, and that is the part most likely
to be wrong without noticing. Each segment is extracted in isolation, so every parser
records positions relative to its own segment; `segments_with_offsets` carries the
shift. A span that is correct-but-shifted renders a tint over the wrong words and
looks like a parser bug.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture.typed_extraction import (
    extract_text,
    segments,
    segments_with_offsets,
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
    tid = db.execute(sql("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    assert tid, "testco is not seeded — run scripts/seed_dev.sh"
    return tid


# ── the offsets, before anything is built on them ───────────────────────

CORPUS = [
    "", "   ", "order for hopkins",
    "order for hopkins, monticello, friday 11am",
    "order for hopkins monticello actually continental",
    "a, b; c\nd", "order for hopkins,   monticello  ,  friday",
    "monticello, actually monticello", ",,,", "a,,b",
]


@pytest.mark.parametrize("text", CORPUS)
def test_the_segment_list_is_UNCHANGED(text):
    """⚠️ CHARACTERIZATION. `segments` now delegates to `segments_with_offsets`;
    this is the oracle that the split itself did not move. The old body is
    reproduced here rather than imported, so the two cannot drift into agreement."""
    import re

    from app.services.capture.typed_extraction import _SEGMENT_RE

    old = tuple(p for p in (x.strip() for x in _SEGMENT_RE.split(text or "")) if p)
    assert segments(text) == old, (text, segments(text), old)


@pytest.mark.parametrize("text", CORPUS)
def test_every_offset_QUOTES_its_segment(text):
    """⚠️ THE ONE ASSERTION THAT CANNOT BE SATISFIED BY A PLAUSIBLE-LOOKING WRONG
    NUMBER. An offset is right only if the text at it IS the segment."""
    for off, seg in segments_with_offsets(text):
        assert text[off : off + len(seg)] == seg, (text, off, seg)


def test_offsets_survive_a_repeated_segment():
    """⚠️ `text.find(segment)` IS THE WRONG WAY TO RECOVER AN OFFSET and this is the
    case that proves it. "monticello, actually monticello" has the same words twice;
    a `find`-based implementation returns the FIRST position for both and the second
    tint lands on the first word."""
    offs = segments_with_offsets("monticello, actually monticello")
    assert [o for o, _ in offs] == [0, 21], offs


# ── the spans themselves ────────────────────────────────────────────────

def test_each_span_QUOTES_the_text_it_claims(db, tenant):
    """⚠️ THE SAME ASSERTION ONE LAYER UP, and the reason it is repeated: a correct
    segment offset and a correct in-segment span can still compose into a wrong
    whole-text span if the shift is applied twice or not at all."""
    t = ("order for riverside monticello decedent mary smith, "
         "going to oakwood section 4, 12 chairs, blargle")
    ex = extract_text(db, tenant_id=tenant, text=t)
    assert ex.spans, "no spans at all — the instrument is blind"
    for sp in ex.spans:
        assert 0 <= sp.start < sp.end <= len(t), sp
        quoted = t[sp.start : sp.end]
        assert quoted.strip() == quoted, ("span includes whitespace", sp, quoted)


def test_the_fields_are_the_fields_that_were_FILLED(db, tenant):
    t = "order for riverside monticello decedent mary smith"
    ex = extract_text(db, tenant_id=tenant, text=t)
    by_field = {f: t[sp.start : sp.end] for sp in ex.spans for f in sp.field_ids}
    assert by_field.get("funeral_home") == "riverside", by_field
    assert by_field.get("vault") == "monticello", by_field
    assert by_field.get("deceased_name") == "decedent mary smith", by_field


def test_ONE_SPAN_MAY_CARRY_TWO_FIELDS(db, tenant):
    """⚠️ THE DELIBERATE RELAXATION OF "no span feeds two fields". "1948 to 2026" is
    one claim that settles the birth year AND the death year. Attribution is a tuple so
    the pane can tie one tint to both rows rather than dropping one silently.

    ⚠️ REPOINTED 2026-10-30 (ruling A), AND THE SUBJECT IT LEFT IS THE REASON. This
    test used to read `"12 chairs"` and assert `{"cemetery_equipment",
    "extra_chairs_count"}` — one span settling the package and its count. Ruling A
    SEPARATED those: chairs no longer touch `cemetery_equipment`, so "12 chairs" now
    carries `chairs_total` alone and there is no dual span in that sentence to find.

    ⚠️ AND IT IS REPOINTED RATHER THAN DELETED BECAUSE THE RULE IT GUARDS IS STILL
    LIVE. `_year_pair` was named in the original docstring as "the same shape and the
    same precedent", and `typed_extraction.py` claims its span as a two-field tuple
    exactly as the chairs block once did. Deleting the test with its old subject would
    have retired the only check that a span may carry more than one field at all —
    nothing else asserts the tuple is ever longer than one.
    """
    ex = extract_text(db, tenant_id=tenant,
                      text="order for riverside decedent mary smith 1948 to 2026")
    dual = [sp for sp in ex.spans if len(sp.field_ids) > 1]
    assert dual, [(s.state, s.field_ids) for s in ex.spans]
    assert set(dual[0].field_ids) == {"date_of_birth", "date_of_death"}


def test_CHAIRS_NO_LONGER_CARRY_THE_PACKAGE_ON_THEIR_SPAN(db, tenant):
    """⚠️ RULING A, PINNED FROM THE SPAN SIDE, so the conflation cannot come back by
    tidying. "12 chairs" is one claim about chairs and says nothing about which bundle
    the cemetery is setting out — before 2026-10-30 the same span wrote
    `cemetery_equipment` too, and naming chairs therefore DROPPED whatever bundle the
    director had named (measured: four phrasings, four different outcomes, decided by
    a comma)."""
    ex = extract_text(db, tenant_id=tenant, text="order for riverside 12 chairs")
    by_field = {f: sp for sp in ex.spans for f in sp.field_ids}
    assert "chairs_total" in by_field, [(s.state, s.field_ids) for s in ex.spans]
    assert "cemetery_equipment" not in by_field, (
        "the chair span is writing the equipment package again"
    )
    assert set(by_field["chairs_total"].field_ids) == {"chairs_total"}, (
        by_field["chairs_total"].field_ids
    )


def test_unrecognized_spans_MATCH_the_unrecognized_list(db, tenant):
    """⚠️ ONE PREDICATE, NOT TWO. The spans and the `unrecognized` list are built from
    the same leftover rule, so the bar cannot underline a word the pane does not
    report — or report one it does not underline."""
    t = "order for riverside monticello blargle"
    ex = extract_text(db, tenant_id=tenant, text=t)
    underlined = [t[sp.start : sp.end] for sp in ex.spans if sp.state == "unrecognized"]
    assert underlined == ["blargle"], underlined
    assert ex.unrecognized == ("blargle",), ex.unrecognized


def test_NOISE_WORDS_ARE_NOT_UNDERLINED(db, tenant):
    """⚠️ THE REASON THE SPAN BUILDER REUSES THE LEFTOVER PREDICATE. "order for
    hopkins" leaves "order for " unclaimed; underlining every unclaimed slice would
    put a dotted line under the first two words of almost every order typed."""
    ex = extract_text(db, tenant_id=tenant, text="order for riverside monticello")
    assert [sp for sp in ex.spans if sp.state == "unrecognized"] == []
    assert ex.unrecognized == ()


def test_spans_do_not_OVERLAP(db, tenant):
    """⚠️ THE SPAN RULE, OBSERVED FROM OUTSIDE. `_claim` refuses an overlapping
    interval, so overlapping output would mean the shift composed two segments onto
    the same characters — which is exactly the off-by-offset bug this file exists
    to catch, and it would render as two tints fighting over one word."""
    t = ("order for riverside monticello decedent mary smith, going to oakwood "
         "section 4, friday 11am, 12 chairs")
    ex = extract_text(db, tenant_id=tenant, text=t)
    ordered = sorted(ex.spans, key=lambda s: s.start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.end <= b.start, (a, b, t[a.start:a.end], t[b.start:b.end])
