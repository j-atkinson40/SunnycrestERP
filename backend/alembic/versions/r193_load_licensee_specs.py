'''Load the licensee spec sheet: 15 products, 3 variant overrides, 0 inferences

Revision ID: r193_load_licensee_specs
Revises: r192_variant_spec_overrides
Create Date: 2026-10-02

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Writes dimensions,
weights, personalization capability and provenance onto 15 of the 21 platform
products, plus spec overrides onto 3 variants. No row is created or deleted.

SOURCE: `docs/catalog/2026-10-02-sunnycrest-product-specs.csv`, md5
`ab25952750488f826c4738aab9744b18` over the payload. 31 data rows.

⚠️ THAT MD5 IS OF THE PAYLOAD, NOT THE FILE. The committed file prepends a
24-line comment block BEFORE the UTF-8 BOM that opens the original upload, so
`md5 <file>` returns `1157ff1cee4778fbc561036976e6a4e1` and the figure quoted
everywhere else in this arc does not reproduce. To check it:

    tail -c +1347 docs/catalog/2026-10-02-sunnycrest-product-specs.csv | md5

Stated here because a verification that cannot be reproduced from its own
instructions is not a verification.

THIS MIGRATION STORES THE SHEET'S RAW STRINGS AND PARSES THEM AT APPLY TIME.
No dimension is transcribed as a number anywhere in this file. `inside`,
`outside` and `weight` below are the sheet's own cell contents, emitted
mechanically from the CSV, so the transcription-error class that corrupted
r188's first draft cannot occur here — there is nothing to mistype. The parser
is frozen in this file so a later change to any service cannot retroactively
alter what this migration meant.

⚠️ THE PARSER REFUSES RATHER THAN GUESSES, AND ONE FIGURE IS REFUSED.
Payload line 29, `Graveliner Urn Vault`, outside reading ` 151/2 x 18 x 13`.
`151/2` has no separator between a possible whole number and a fraction, so it
reads as either 15½ or 151/2 and NOTHING IN THE SHEET DECIDES WHICH. A parser
that silently returns 15.5 is making a judgment call in a column later read as a
clearance measurement by someone with a vault on a truck.

Its two companions on that line are discarded with it, because the anomaly is
not confined to the unreadable cell: that row's outside WIDTH is 18" against an
inside width of 12", a growth of +6.00". Every other urn vault in the sheet grows
+1.8125", and the widest non-Triune grows +3.00" — so 18 is 2× the next largest
and 3.3× its own class, and under the only plausible reading of `151/2` the width
would also exceed the length. Two independent reasons to distrust the triple, so
all three outside figures for line 29 are left NULL. Its INSIDE triple parses
cleanly and is loaded.

⚠️ AND THE CHECK THAT SHOULD HAVE CAUGHT THE WIDTH DID NOT. A width-exceeds-length
comparison over all 31 rows made 128 comparisons and flagged zero, because line
29's length is the unparseable value — so the comparison was SKIPPED for the one
row it existed for. A control reporting zero is indistinguishable from a control
that never ran on the case in question, which is why the width is evidenced here
by the growth measurement instead. See CLAUDE.md §11, "A control that cannot
distinguish itself from a failure is not a control".

WHAT IS AND IS NOT LOADED, by population:

    31 data rows in the sheet
    -6  non-manufactured burial vaults — NO product exists for these yet.
        Phase 2b-3 adds them. Skipped, not silently dropped: `_OUT_OF_SCOPE`
        names all six lines and the migration asserts it skipped exactly six.
    =25 rows loaded, mapping onto 15 products

    21 products in the catalog
    -6  with NO row in the sheet — Tribute Burial Vault and the five equipment
        products. Every spec column and `personalization_capability` stay NULL.
        Nothing is copied from a sibling and nothing is inferred.
    =15 products touched

OUTSIDE HEIGHT IS ABSENT FOR MOST ROWS BY THE SHEET'S OWN DESIGN. The column is
headed `OUT (inches) LxW` and carries two components for 25 rows and three for
six (lines 27, 28, 29, 30, 31, 32). So `outside_height_in` lands on just 2
products and 3 variants and is NULL elsewhere — an absence in the source, not a
parse failure, and not something to derive from the inside height.

⚠️ 2, NOT 6, AND THE GAP IS WORTH NAMING BECAUSE THIS DOCSTRING FIRST SAID 5. Of
the six three-component rows, three (30, 31, 32) are Loved & Cherished VARIANTS
rather than products, and one (29) has its whole triple refused. 27 and 28 are
the only products left. No stale identifier and no stale figure pointed at it —
it was caught by counting the stored rows, which is the only instrument that
could have.

WEIGHT IS ABSENT FOR 19 OF 31 ROWS — every urn vault, every Loved & Cherished and
every non-manufactured vault. A lift rating and a truck load depend on that
number, so it stays NULL and visibly so rather than being inferred from a
sibling product.

TWO MAPPINGS ARE RULINGS, NOT READINGS, AND ARE RECORDED AS SUCH:

    line 27  `Universal Urn Vault (P400WS)`  ->  universal / urn_vault
    line 28  `Basic Gray Urn Vault (P410)`   ->  salute / urn_vault   (UV-SAL)

The second is the false negative that `docs/catalog/sunnycrest-catalog-review-ANNOTATION.md`
§2 records: Wilbert sells one listing as "Basic Gray/Salute Urn Vault", the sheet
names one half and our catalog names the other. Confirmed one product by the
owner on 2026-10-02. ⚠️ The first is the sheet naming a MODEL where our catalog
names a FINISH — `P400`**WS** is the White & Silver variant — so the row is the
product's, and `UV-UCG` (Cream & Gold) correctly has no row of its own and reads
through. That is the product-level model working, not missing data.

LOVED & CHERISHED IS THE ONLY PRODUCT WHOSE ROWS DISAGREE, and it disagrees in
every dimension: 18⅜ × 8 × 7, 23-5/16 × 9⅛ × 10⅛, 31-1/8 × 10-5/8 × 12¼. Model
is a SIZE axis there rather than a finish, so the product tier has nothing true
to say about dimensions and stores NULL, while all three variants carry
overrides. ⚠️ A consumer reading only the product tier gets NULL for L&C, and
that is correct: there is no product-level dimension for it to read.

⚠️ SO `spec_source` IS THE MEMBERSHIP MARKER, NOT `inside_length_in`. L&C has a
row in the sheet and is the most precisely measured product in it, while its
product-level dimensions are deliberately NULL. A set-equality check written over
dimensions would report it as unmeasured. It is written over `spec_source`.

SAFE TO REVERSE. Downgrade nulls exactly the columns this sets, on exactly the
rows it touched, returning the catalog to its r192 state.
'''
from __future__ import annotations

from datetime import date
from fractions import Fraction
import json
import re
from typing import NamedTuple

import sqlalchemy as sa
from alembic import op

revision = "r193_load_licensee_specs"
down_revision = "r192_variant_spec_overrides"
branch_labels = None
depends_on = None

SPEC_SOURCE = "docs/catalog/2026-10-02-sunnycrest-product-specs.csv"
SPEC_ASOF = date(2026, 10, 2)

#: The six non-manufactured burial vaults. No product exists for them yet; Phase
#: 2b-3 adds them. Named rather than filtered so the skip is auditable and the
#: count is asserted.
_OUT_OF_SCOPE = {
    14: 'Monticello 34"',
    15: 'Large 34"',
    16: 'Large 36"',
    17: 'Large 40"',
    18: "Youth MT",
    19: "Youth GL",
}

#: The three personalization question ids, verified against
#: `app/services/personalization/questions.py::QUESTIONS` on 2026-10-02 — a
#: 3-tuple, read from the declaration site rather than from a description of it.
#: Stored in that declaration's order so a reader comparing a stored list against
#: the canonical enumeration sees the same sequence.
_QUESTION_IDS = ("legacy_print", "nameplate_cover_emblem", "lifes_reflections")


class _Unparseable(Exception):
    """Raised instead of returning a plausible number."""


_UNICODE_FRACTIONS = {
    "½": Fraction(1, 2), "¼": Fraction(1, 4), "¾": Fraction(3, 4),
    "⅛": Fraction(1, 8), "⅜": Fraction(3, 8), "⅝": Fraction(5, 8),
    "⅞": Fraction(7, 8), "⅓": Fraction(1, 3), "⅔": Fraction(2, 3),
}


def _parse_figure(tok: str) -> Fraction:
    """One dimension figure from the sheet, or _Unparseable.

    ⚠️ FROZEN. This is a copy, deliberately not an import. A migration's meaning
    must not change when a service is refactored.
    """
    t = tok.strip()
    if not t:
        raise _Unparseable("empty")
    uni = [c for c in t if c in _UNICODE_FRACTIONS]
    if len(uni) > 1:
        raise _Unparseable(f"{tok!r}: more than one unicode fraction")
    if uni:
        c = uni[0]
        if not t.endswith(c):
            raise _Unparseable(f"{tok!r}: unicode fraction {c!r} is not final")
        whole, frac = t[: -len(c)].strip(), _UNICODE_FRACTIONS[c]
        if whole == "":
            return frac
        if not re.fullmatch(r"\d+", whole):
            raise _Unparseable(f"{tok!r}: whole part {whole!r} not an integer")
        return Fraction(int(whole)) + frac
    if re.fullmatch(r"\d+", t):
        return Fraction(int(t))
    # "18 3/8" and "31-1/8" — a separator makes the split unambiguous.
    m = re.fullmatch(r"(\d+)[\s-]+(\d+)/(\d+)", t)
    if m:
        return Fraction(int(m[1])) + Fraction(int(m[2]), int(m[3]))
    # A bare fraction is fine only while it is PROPER. "1/2" is a half; "151/2"
    # is a missing separator and is refused — see the module docstring.
    m = re.fullmatch(r"(\d+)/(\d+)", t)
    if m:
        num, den = int(m[1]), int(m[2])
        if num < den:
            return Fraction(num, den)
        raise _Unparseable(
            f"{tok!r}: improper bare fraction {num}/{den} with no separator; "
            f"reads as either {Fraction(num, den)} or a mixed number missing its "
            f"space, and the sheet does not decide which"
        )
    raise _Unparseable(f"{tok!r}: no recognised form")


def _parse_triple(cell: str) -> list[Fraction | None]:
    """L, W, H from one cell. Absent components and refused ones are both None.

    They are distinguishable by the caller: a refusal is counted and asserted,
    an absence is not.
    """
    out: list[Fraction | None] = [None, None, None]
    if not cell.strip():
        return out
    toks = re.split(r"\s*x\s*", cell.strip(), flags=re.I)
    for i, tok in enumerate(toks[:3]):
        try:
            out[i] = _parse_figure(tok)
        except _Unparseable:
            out[i] = None
    return out


def _refusals(cell: str) -> list[str]:
    """Which components of this cell the parser refuses. Drives the assertion."""
    bad: list[str] = []
    if not cell.strip():
        return bad
    for tok in re.split(r"\s*x\s*", cell.strip(), flags=re.I)[:3]:
        try:
            _parse_figure(tok)
        except _Unparseable as e:
            bad.append(str(e))
    return bad


class _Row(NamedTuple):
    # ⚠️ NamedTuple, not a dataclass. Alembic loads a migration module
    # without registering it in sys.modules, and `@dataclass` under
    # `from __future__ import annotations` resolves field types THROUGH
    # sys.modules, so it raises AttributeError at import before any
    # migration runs. Measured 2026-10-02.
    #: Payload line number — header is line 1, matching r189/r191's citations.
    line: int
    #: The sheet's own Product cell, verbatim including trailing space.
    sheet_name: str
    family_slug: str
    form: str
    #: Set only where the row describes a VARIANT rather than a product, which
    #: is Loved & Cherished and nothing else.
    variant_sku: str | None
    inside: str
    outside: str
    weight: str
    personalization: tuple[str, ...]


SPEC_ROWS: tuple[_Row, ...] = (
    _Row(
        line=2,
        sheet_name='Wilbert Bronze ',
        family_slug='wilbert-bronze',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='91¼ x 35¼',
        weight='3000',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=3,
        sheet_name='Bronze Triune',
        family_slug='triune',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='91¼ x 35¼',
        weight='3000',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=4,
        sheet_name='Copper Triune ',
        family_slug='triune',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='91¼ x 35¼',
        weight='3000',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=5,
        sheet_name='Stainless Steel Triune(SST)',
        family_slug='triune',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='91¼ x 35¼',
        weight='3000',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=6,
        sheet_name='Veteran',
        family_slug='triune',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='91¼ x 35¼',
        weight='3000',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=7,
        sheet_name='Cameo Rose',
        family_slug='triune',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='91¼ x 35¼',
        weight='3000',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=8,
        sheet_name='Venetian',
        family_slug='venetian',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='90½ x 34½',
        weight='2800',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=9,
        sheet_name='Continental',
        family_slug='continental',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='90½ x 34½',
        weight='2700',
        personalization=('nameplate_cover_emblem',),
    ),
    _Row(
        line=10,
        sheet_name='Salute',
        family_slug='salute',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='90½ x 34½',
        weight='2000',
        personalization=('nameplate_cover_emblem',),
    ),
    _Row(
        line=11,
        sheet_name='Monticello',
        family_slug='monticello',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='90½ x 34½',
        weight='2000',
        personalization=(),
    ),
    _Row(
        line=12,
        sheet_name='Monarch',
        family_slug='monarch',
        form='burial_vault',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='89½ x 33½',
        weight='1800',
        personalization=(),
    ),
    _Row(
        line=13,
        sheet_name='Grave Liner',
        family_slug='graveliner',
        form='grave_liner',
        variant_sku=None,
        inside='86 x 30 x 25½',
        outside='89½ x 33½',
        weight='1800',
        personalization=(),
    ),
    _Row(
        line=20,
        sheet_name='Bronze Triune Urn Vault',
        family_slug='triune',
        form='urn_vault',
        variant_sku=None,
        inside='12½ x 12½ x 13¾',
        outside='14-5/16 x 14-5/16',
        weight='',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=21,
        sheet_name='Copper Triune Urn Vault',
        family_slug='triune',
        form='urn_vault',
        variant_sku=None,
        inside='12½ x 12½  x 13¾',
        outside='14-5/16 x 14-5/16',
        weight='',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=22,
        sheet_name='Stainless Steel Triune (SST) Urn Vault',
        family_slug='triune',
        form='urn_vault',
        variant_sku=None,
        inside='12½ x 12½  x 13¾',
        outside='14-5/16 x 14-5/16',
        weight='',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=23,
        sheet_name='Veteran Urn Vault',
        family_slug='triune',
        form='urn_vault',
        variant_sku=None,
        inside='12½ x 12½ x 13¾',
        outside='14-5/16 x 14-5/16',
        weight='',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=24,
        sheet_name='Cameo Rose Urn Vault',
        family_slug='triune',
        form='urn_vault',
        variant_sku=None,
        inside='12½ x 12½ x 13¾',
        outside='14-5/16 x 14-5/16',
        weight='',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=25,
        sheet_name='Venetian Urn Vault',
        family_slug='venetian',
        form='urn_vault',
        variant_sku=None,
        inside='12½ x 12½ x 13¾',
        outside='14-5/16 x 14-5/16',
        weight='',
        personalization=('legacy_print', 'nameplate_cover_emblem', 'lifes_reflections'),
    ),
    _Row(
        line=26,
        sheet_name='Monticello Urn Vault',
        family_slug='monticello',
        form='urn_vault',
        variant_sku=None,
        inside='12½ x 12½ x 13¾',
        outside='14-5/16 x 14-5/16',
        weight='',
        personalization=(),
    ),
    _Row(
        line=27,
        sheet_name='Universal Urn Vault (P400WS)',
        family_slug='universal',
        form='urn_vault',
        variant_sku=None,
        inside='13 x 10¼ x 10',
        outside='16  x  13¼ x 13',
        weight='',
        personalization=(),
    ),
    _Row(
        line=28,
        sheet_name='Basic Gray Urn Vault (P410)',
        family_slug='salute',
        form='urn_vault',
        variant_sku=None,
        inside='13 x 10¼ x 10',
        outside='16  x  13¼ x 13',
        weight='',
        personalization=(),
    ),
    _Row(
        line=29,
        sheet_name='Graveliner Urn Vault',
        family_slug='graveliner',
        form='urn_vault',
        variant_sku=None,
        inside='14½ x 12 x 10 ',
        outside=' 151/2 x 18 x 13',
        weight='',
        personalization=(),
    ),
    _Row(
        line=30,
        sheet_name='Loved & Cherished  31',
        family_slug='loved-and-cherished',
        form='infant',
        variant_sku='LC-31',
        inside='31-1/8 x 10-5/8 x 12-1/4',
        outside='36-1/4 x 15-3/8 x 14',
        weight='',
        personalization=(),
    ),
    _Row(
        line=31,
        sheet_name='Loved & Cherished  24',
        family_slug='loved-and-cherished',
        form='infant',
        variant_sku='LC-24',
        inside='23-5/16 x 9-1/8 x 10-1/8',
        outside='26 x 11-13/16 x 11-1/4',
        weight='',
        personalization=(),
    ),
    _Row(
        line=32,
        sheet_name='Loved & Cherished 19',
        family_slug='loved-and-cherished',
        form='infant',
        variant_sku='LC-19',
        inside='18 3/8 x 8 x 7',
        outside='20 1/16 x 9 ¾ x 8 3/4',
        weight='',
        personalization=(),
    ),
)



_PRODUCT_SPEC_COLS = (
    "inside_length_in", "inside_width_in", "inside_height_in",
    "outside_length_in", "outside_width_in", "outside_height_in",
    "weight_lb",
)


def _figures(row: _Row) -> tuple[Fraction | None, ...]:
    """The seven figures for one row, as (in L,W,H, out L,W,H, weight).

    ⚠️ A CELL WITH ANY REFUSED COMPONENT IS DISCARDED WHOLE. Line 29's outside
    reading is anomalous beyond its unreadable first component (see the module
    docstring), so keeping the two that happen to parse would store figures from
    a triple we have decided not to trust.
    """
    inside = (
        [None, None, None] if _refusals(row.inside) else _parse_triple(row.inside)
    )
    outside = (
        [None, None, None] if _refusals(row.outside) else _parse_triple(row.outside)
    )
    weight: Fraction | None = None
    if row.weight.strip() and not _refusals(row.weight):
        weight = _parse_figure(row.weight)
    return (*inside, *outside, weight)


def _as_decimal(f: Fraction | None):
    if f is None:
        return None
    # Every figure in the sheet is sixteenths-exact, asserted below, so this is
    # exact rather than rounded.
    return float(f)


def upgrade() -> None:
    bind = op.get_bind()

    # ---- preconditions on the embedded data itself -------------------------
    lines = [r.line for r in SPEC_ROWS]
    assert len(lines) == len(set(lines)), "duplicate payload line in SPEC_ROWS"
    assert len(SPEC_ROWS) == 25, f"expected 25 in-scope rows, have {len(SPEC_ROWS)}"
    overlap = set(lines) & set(_OUT_OF_SCOPE)
    assert not overlap, f"out-of-scope lines present in SPEC_ROWS: {sorted(overlap)}"
    assert len(_OUT_OF_SCOPE) == 6, "expected 6 non-manufactured rows skipped"
    # 25 in scope + 6 skipped must account for the sheet's 31 data rows.
    assert len(SPEC_ROWS) + len(_OUT_OF_SCOPE) == 31

    # ⚠️ EXACTLY ONE FIGURE IS REFUSED, AND IT IS THE ONE NAMED IN THE DOCSTRING.
    # A positive control on the parser's ability to refuse at all: if a later
    # edit to the sheet makes `151/2` readable, or makes something else
    # unreadable, this migration fails rather than quietly storing a guess.
    refused = [
        (r.line, cell, msg)
        for r in SPEC_ROWS
        for cell in (r.inside, r.outside, r.weight)
        for msg in _refusals(cell)
    ]
    assert len(refused) == 1, f"expected exactly 1 refused figure, got {refused}"
    assert refused[0][0] == 29, f"the refused figure moved off line 29: {refused}"
    assert "151/2" in refused[0][2], f"unexpected refusal: {refused}"

    for qid in (q for r in SPEC_ROWS for q in r.personalization):
        assert qid in _QUESTION_IDS, f"unknown personalization question {qid!r}"

    # ---- resolve the catalog ----------------------------------------------
    products = {
        (r.family_slug, r.form): r.id
        for r in bind.execute(
            sa.text("SELECT id, family_slug, form FROM product_templates")
        )
    }
    variants = {
        r.sku: r.id
        for r in bind.execute(
            sa.text("SELECT id, sku FROM product_variant_templates")
        )
    }

    groups: dict[tuple[str, str], list[_Row]] = {}
    for row in SPEC_ROWS:
        key = (row.family_slug, row.form)
        assert key in products, f"line {row.line}: no product for {key}"
        groups.setdefault(key, []).append(row)

    sixteenths_checked = 0
    product_dims_set = 0
    product_dims_null = 0
    variant_overrides_set = 0

    for key, rows in sorted(groups.items()):
        product_id = products[key]
        figure_sets = {_figures(r) for r in rows}

        # --- personalization: every row for a product must agree -----------
        pers = {r.personalization for r in rows}
        assert len(pers) == 1, (
            f"{key}: rows disagree on personalization capability: "
            f"{ {r.line: r.personalization for r in rows} }"
        )
        capability = list(next(iter(pers)))

        # --- dimensions ----------------------------------------------------
        if len(figure_sets) == 1:
            figures = next(iter(figure_sets))
            assert all(r.variant_sku is None for r in rows), (
                f"{key}: rows agree on dimensions but carry variant skus; a "
                f"variant override is only for a product whose rows DISAGREE"
            )
            params = {"pid": product_id}
            for col, f in zip(_PRODUCT_SPEC_COLS, figures):
                params[col] = _as_decimal(f)
                if f is not None:
                    assert (f * 16).denominator == 1, (
                        f"{key} {col}: {float(f)} is not sixteenths-exact"
                    )
                    sixteenths_checked += 1
            sets = ", ".join(f"{c} = :{c}" for c in _PRODUCT_SPEC_COLS)
            bind.execute(
                sa.text(f"UPDATE product_templates SET {sets} WHERE id = :pid"),
                params,
            )
            product_dims_set += 1
        else:
            # ⚠️ Rows disagree. The product tier has nothing true to say, so it
            # stores nothing and every row must name the variant it describes.
            assert all(r.variant_sku is not None for r in rows), (
                f"{key}: rows DISAGREE on dimensions but not every row names a "
                f"variant, so there is no tier that can hold them: "
                f"{ {r.line: r.variant_sku for r in rows} }"
            )
            product_dims_null += 1
            for row in rows:
                assert row.variant_sku in variants, (
                    f"line {row.line}: no variant {row.variant_sku!r}"
                )
                params = {"vid": variants[row.variant_sku]}
                for col, f in zip(_PRODUCT_SPEC_COLS, _figures(row)):
                    params[col] = _as_decimal(f)
                    if f is not None:
                        assert (f * 16).denominator == 1, (
                            f"line {row.line} {col}: {float(f)} not "
                            f"sixteenths-exact"
                        )
                        sixteenths_checked += 1
                sets = ", ".join(f"{c} = :{c}" for c in _PRODUCT_SPEC_COLS)
                bind.execute(
                    sa.text(
                        f"UPDATE product_variant_templates SET {sets} "
                        f"WHERE id = :vid"
                    ),
                    params,
                )
                variant_overrides_set += 1

        # --- capability + provenance, on every covered product -------------
        bind.execute(
            sa.text(
                "UPDATE product_templates SET "
                "personalization_capability = CAST(:cap AS json), "
                "spec_source = :src, spec_asof = :asof "
                "WHERE id = :pid"
            ),
            {
                "cap": json.dumps(capability),
                "src": SPEC_SOURCE,
                "asof": SPEC_ASOF,
                "pid": product_id,
            },
        )

    # ---- postconditions, read back from the database ----------------------
    # ⚠️ Counted from what the UPDATEs actually touched, not predicted.
    assert len(groups) == 15, f"expected 15 covered products, touched {len(groups)}"
    assert product_dims_set == 14, f"expected 14 with product dims, {product_dims_set}"
    assert product_dims_null == 1, (
        f"expected exactly 1 product whose rows disagree (Loved & Cherished), "
        f"got {product_dims_null}"
    )
    assert variant_overrides_set == 3, (
        f"expected 3 variant overrides, got {variant_overrides_set}"
    )
    assert sixteenths_checked > 0, "sixteenths check never ran — positive control"

    with_source = bind.execute(
        sa.text("SELECT count(*) FROM product_templates WHERE spec_source IS NOT NULL")
    ).scalar_one()
    assert with_source == 15, f"spec_source set on {with_source} products, want 15"

    uncovered = bind.execute(
        sa.text(
            "SELECT count(*) FROM product_templates "
            "WHERE spec_source IS NULL "
            "AND personalization_capability IS NOT NULL"
        )
    ).scalar_one()
    assert uncovered == 0, (
        f"{uncovered} products with no CSV row carry a personalization claim; "
        f"they must stay NULL"
    )


def downgrade() -> None:
    cols = ", ".join(f"{c} = NULL" for c in _PRODUCT_SPEC_COLS)
    op.execute(
        f"UPDATE product_templates SET {cols}, "
        f"personalization_capability = NULL, spec_source = NULL, spec_asof = NULL "
        f"WHERE spec_source = '{SPEC_SOURCE}'"
    )
    op.execute(f"UPDATE product_variant_templates SET {cols}")
