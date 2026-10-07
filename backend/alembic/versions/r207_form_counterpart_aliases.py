"""The three aliases that named one form of a two-form product. LOCAL ONLY.

⚠️ NOT TO BE PUSHED WITHOUT A SEPARATE GO. The dispatch of 2026-10-07 ruled "no
migration expected for 1-2; if one is needed, local only." One is needed, and this is
it, and it stays local until James says otherwise.

⚠️ WHY A MIGRATION WAS NEEDED AT ALL, since the ruling did not expect one. The form
filter in `product_name_resolver.resolve` makes "Veteran urn vault" refuse to answer
with a burial vault. It cannot make it answer with UV-VET, because nothing reaches
UV-VET from the word "veteran": the r189 alias names only BV-VTRI, and UV-VET's own
display name is "Veteran Triune Urn Vault". The ruled coverage —
"Veteran / SST / Cameo Rose urn vault -> the UV- variant" — is a DATA gap behind the
code gap, and the filter alone turns a wrong answer into no answer.

⚠️ THE EXPOSURE WAS ENUMERATED, NOT GUESSED. Counterpart = same `family_slug` AND the
same `option_label` in a different `form`. Measured 2026-10-07 over all 53 confirmed
alias rows / 33 distinct alias texts: FOUR aliases reach a variant whose counterpart
they do not.

    Veteran      BV-VTRI    -> UV-VET      added here
    SST          BV-SSTRI   -> UV-SSTRI    added here
    Cameo Rose   BV-CRTRI   -> UV-CRTRI    added here
    Basic Gray   UV-SAL     -> BV-SAL      ⚠️ DELIBERATELY NOT ADDED

⚠️ `Basic Gray` IS NOT AN INSTANCE OF THE DEFECT AND MUST NOT BE "FIXED". Its r189
note records the finding: Wilbert lists one product as "Basic Gray/Salute Urn Vault"
and the spec sheet has "Basic Gray Urn Vault (P410)", confirmed as ONE product by the
owner on 2026-10-02. The phrase names the urn vault specifically. Adding BV-SAL would
make a settled name ambiguous on the strength of a shape match.

Also checked and NOT exposed: `Grave Liner` reaches GL-STD, whose option_label is
`Standard`; UV-GL's is `Graveliner`, so they are not counterparts, and the r189 note
says so in terms ("NOT UV-GL, which the sheet calls 'Graveliner Urn Vault'"). None of
r206's 48 class-alias rows is exposed — measured, not assumed.

⚠️ THIS CHANGES AN ANSWER THAT USED TO BE UNIQUE, ON PURPOSE. "Veteran" alone becomes
TWO candidates asking FORM, where it previously resolved silently to the burial vault.
That is the module's own thesis ("Bronze Triune — burial or urn vault?"), and the
silent unique answer was the defect wearing a resolved result.
"""
from __future__ import annotations

import re
import unicodedata
import uuid

import sqlalchemy as sa
from alembic import op

revision = "r207_form_counterpart_aliases"
down_revision = "r206_oversized_class_aliases"
branch_labels = None
depends_on = None

_TABLE = "platform_product_aliases"

#: (alias_text, sku of the counterpart to add). One list, walked by both directions.
_ROWS: tuple[tuple[str, str], ...] = (
    ("Veteran", "UV-VET"),
    ("SST", "UV-SSTRI"),
    ("Cameo Rose", "UV-CRTRI"),
)

#: The burial-vault row each alias already had, asserted present so this migration
#: cannot quietly become the ONLY row for an alias if r189's seed ever changes.
_EXPECTED_EXISTING: tuple[tuple[str, str], ...] = (
    ("Veteran", "BV-VTRI"),
    ("SST", "BV-SSTRI"),
    ("Cameo Rose", "BV-CRTRI"),
)

_NOTE = (
    "Form counterpart. The r189 alias named only the burial variant, so "
    "'<alias> urn vault' either resolved to the BURIAL vault (before the form filter) "
    "or to nothing (after it). Enumerated 2026-10-07 as one of four aliases reaching a "
    "variant whose same-family same-option_label counterpart it did not; the fourth, "
    "Basic Gray, is a settled single-product name and was deliberately left alone. "
    "See r207."
)

_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:inches|inch|ins|in|\")")


def _fold(s: str) -> str:
    """A local copy of `product_name_resolver.normalize`, for the same reason r206
    carries one: a migration that imports application code stops being reproducible
    when that code moves. `test_oversized_class_alias.py` asserts the stored column
    equals `normalize(alias_text)` over every row, which is the seam check."""
    if not s:
        return ""
    for mark in ("™", "®", "©", "℠"):
        s = s.replace(mark, "")
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("”", '"').replace("“", '"')
    s = s.replace("’", "'").replace("‘", "'")
    s = s.lower()
    s = re.sub(r"\band\b", "&", s)
    s = _SIZE_RE.sub(r'\1"', s)
    s = re.sub(r"[^a-z0-9\"&' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _row_id(normalized: str, variant_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"r207:{normalized}:{variant_id}"))


def upgrade() -> None:
    conn = op.get_bind()

    tables = {r[0] for r in conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ))}
    assert len(tables) > 100, f"saw {len(tables)} tables; the reader is blind"
    assert _TABLE in tables, f"{_TABLE} is missing"

    by_sku = {sku: vid for sku, vid in conn.execute(sa.text(
        "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
    ))}
    assert len(by_sku) > 40, f"only {len(by_sku)} active variants — catalog unseeded"
    missing = [sku for _, sku in _ROWS if sku not in by_sku]
    assert not missing, f"these urn variants are absent: {missing}"

    # ⚠️ THE POSITIVE CONTROL. Each alias must ALREADY reach its burial variant. If
    # r189's rows were ever reshaped away, these inserts would make this migration the
    # alias's only row and silently invert the answer instead of widening it.
    for alias_text, sku in _EXPECTED_EXISTING:
        n = _fold(alias_text)
        got = conn.execute(sa.text(
            f"SELECT count(*) FROM {_TABLE} a JOIN product_variant_templates v "
            "ON v.id = a.variant_template_id "
            "WHERE a.alias_text_normalized = :n AND v.sku = :s AND a.is_confirmed IS TRUE"
        ), {"n": n, "s": sku}).scalar()
        assert got == 1, (
            f"expected the r189 row {alias_text!r} -> {sku}; found {got}. Widening an "
            f"alias that does not already exist would INVERT it, not widen it."
        )

    before = conn.execute(sa.text(f"SELECT count(*) FROM {_TABLE}")).scalar()
    for alias_text, sku in _ROWS:
        n = _fold(alias_text)
        conn.execute(sa.text(
            f"INSERT INTO {_TABLE} "
            "(id, variant_template_id, alias_text, alias_text_normalized, source, "
            " is_confirmed, note) "
            "VALUES (:i, :v, :t, :n, 'manual', TRUE, :note) "
            "ON CONFLICT (variant_template_id, alias_text_normalized) DO NOTHING"
        ), {"i": _row_id(n, by_sku[sku]), "v": by_sku[sku], "t": alias_text,
            "n": n, "note": _NOTE})
    after = conn.execute(sa.text(f"SELECT count(*) FROM {_TABLE}")).scalar()
    assert after - before == len(_ROWS), f"grew by {after - before}, planned {len(_ROWS)}"

    # ⚠️ ASSERTED AS THE CANDIDATE SET EACH ALIAS NOW REACHES, not as a row count.
    sku_of = {vid: sku for sku, vid in by_sku.items()}
    for alias_text, urn_sku in _ROWS:
        burial_sku = dict(_EXPECTED_EXISTING)[alias_text]
        got = {sku_of.get(vid, vid) for (vid,) in conn.execute(sa.text(
            f"SELECT variant_template_id FROM {_TABLE} "
            "WHERE alias_text_normalized = :n AND is_confirmed IS TRUE"
        ), {"n": _fold(alias_text)})}
        assert got == {burial_sku, urn_sku}, f"{alias_text}: {sorted(got)}"


def downgrade() -> None:
    conn = op.get_bind()
    by_sku = {sku: vid for sku, vid in conn.execute(sa.text(
        "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
    ))}
    ids = [
        _row_id(_fold(alias_text), by_sku[sku])
        for alias_text, sku in _ROWS
        if sku in by_sku
    ]
    if ids:
        conn.execute(sa.text(f"DELETE FROM {_TABLE} WHERE id = ANY(:ids)"), {"ids": ids})
