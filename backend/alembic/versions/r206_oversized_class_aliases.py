"""Oversized as a CLASS ALIAS, in the alias table, with no new resolver mechanism.

⚠️ THE RULING (James, 2026-10-07). `oversized | oversize | OS | O/S | OVS` narrow to
the 34" Continental and the 34" and 38" Graveliners and ASK. Combined with a family
name they narrow within it ("oversized Continental" -> BV-CON34). A bare number after
a family name is accepted ("Continental 34").

⚠️ THE DISPATCH SAID: "Use the alias table if a class alias can point at several
variants; otherwise report before inventing a mechanism." IT CAN, AND THE CONSTRAINT
IS WHERE THAT IS VISIBLE: `uq_platform_product_aliases_variant_text` is UNIQUE on
`(variant_template_id, alias_text_normalized)`, NOT on the text alone — so three rows
may carry the same alias text against three different variants, and
`product_name_resolver.build_index` accumulates them into one candidate set
(`index[n].add(c)`). So this migration is DATA ONLY. `resolve()` is untouched, and
every clause of the ruling is expressed as rows.

⚠️ WHY NOT A MECHANISM, STATED, BECAUSE THE CHEAPER-LOOKING OPTION IS THE WRONG ONE.
A composition rule ("strip a class token, resolve the rest, intersect") and a
normalisation rule ("a bare trailing number means inches") would each cover these
cases in a few lines. Both are open-ended: the first makes every alias a potential
prefix of every phrase, and the second rewrites EVERY indexed surface form, because
`build_index` normalises display names through the same function. The catalog's
size-bearing variants are a CLOSED SET OF SIX, so the open-ended mechanism buys
nothing the enumeration does not, and costs a blast radius nobody measured.

⚠️ `alias_text_normalized` IS NOT WHAT THE RESOLVER READS. `build_index` calls
`normalize(a.alias_text)` on the raw text; the stored column feeds only the unique
constraint. So the two could disagree and nothing would notice — which is why
`test_oversized_class_alias.py` asserts the stored column equals
`normalize(alias_text)` for EVERY row in the table, the five pre-existing ones
included. This migration computes it with a LOCAL copy of the folding rather than
importing `normalize`, because a migration that imports application code stops being
reproducible the moment that code moves; the test is the seam.

⚠️ WORD BOUNDARIES ARE FREE HERE AND THAT IS WORTH SAYING OUT LOUD. The ruling asks
for "word boundaries only". `resolve()` is an EXACT lookup of the whole normalised
phrase against `by_form`, so "os" cannot fire inside "Boston" — there is no substring
path to fire through. The guarantee comes from the lookup being exact, not from a
`\b` anywhere, and the test break-tests it by swapping in a substring match.

NOT COVERED, DELIBERATELY, AND REPORTED RATHER THAN GUESSED:
  * reversed word order ("Continental oversized") — the ruling names the
    adjective-first form only.
  * "oversized urn vault" — no urn vault in the catalog carries a size label.
"""
from __future__ import annotations

import re
import unicodedata
import uuid

import sqlalchemy as sa
from alembic import op

revision = "r206_oversized_class_aliases"
down_revision = "r205_cemetery_unique_with_city"
branch_labels = None
depends_on = None

_TABLE = "platform_product_aliases"

#: The ruled surface forms of the class word. ⚠️ "O/S" folds to `o s`, not `os` —
#: the slash becomes a space — so it is a DIFFERENT key from "OS" and both are
#: wanted. Asserted below rather than left to be rediscovered.
_CLASS_FORMS = ("oversized", "oversize", "OS", "O/S", "OVS")

#: The class, bare: every oversized variant in the catalog, so the resolver returns
#: three candidates and the discriminator asks.
_CLASS_SKUS = ("BV-CON34", "GL-34", "GL-38")

#: The class combined with a family name, narrowing within that family.
#:
#: ⚠️ "grave liner" IS INCLUDED BECAUSE THE CATALOG ALREADY ACCEPTS IT. A confirmed
#: r189 alias maps "Grave Liner" (two words) to GL-STD, so a director who spells it
#: that way reaches the standard liner today; leaving "oversized grave liner" dead
#: while "grave liner" works would be an inconsistency introduced by this migration.
_FAMILY_PHRASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Continental", ("BV-CON34",)),
    ("Graveliner", ("GL-34", "GL-38")),
    ("Grave Liner", ("GL-34", "GL-38")),
)

#: A bare number after a family name. ⚠️ THE CLOSED SET THE DOCSTRING CLAIMS: every
#: variant whose `option_label` denotes a size. `Continental 34 inch` already resolves
#: (the index carries `34" continental` from `option_label + product_name`); what is
#: missing is the OTHER WORD ORDER WITHOUT THE UNIT, which is how a person types it.
_BARE_NUMBER: tuple[tuple[str, str], ...] = (
    ("Continental 34", "BV-CON34"),
    ("Graveliner 34", "GL-34"),
    ("Graveliner 38", "GL-38"),
    ("Grave Liner 34", "GL-34"),
    ("Grave Liner 38", "GL-38"),
    ("Loved & Cherished 19", "LC-19"),
    ("Loved & Cherished 24", "LC-24"),
    ("Loved & Cherished 31", "LC-31"),
)

_NOTE = (
    "Class alias. Ruled by James 2026-10-07: oversized/oversize/OS/O/S/OVS narrow to "
    "BV-CON34, GL-34, GL-38 and ask; with a family name they narrow within it; a bare "
    "number after a family name is accepted. Written as alias rows rather than as a "
    "resolver mechanism because the catalog's size-bearing variants are a closed set "
    "of six and an open-ended composition or normalisation rule would have a blast "
    "radius across every indexed surface form. See r206."
)

_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:inches|inch|ins|in|\")")


def _fold(s: str) -> str:
    """⚠️ A LOCAL COPY OF `product_name_resolver.normalize`, ON PURPOSE.

    Importing it would couple this migration to a module that may move; the two are
    held together by a test asserting the stored column equals `normalize(alias_text)`
    for every row, which is a louder failure than a silent divergence in a column the
    resolver does not read.
    """
    if not s:
        return ""
    for mark in ("™", "®", "©", "℠"):
        s = s.replace(mark, "")
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("”", '"').replace("“", '"')
    s = s.replace("’", "'").replace("‘", "'")
    s = s.lower()
    s = _SIZE_RE.sub(r'\1"', s)
    s = re.sub(r"[^a-z0-9\"&' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _planned() -> list[tuple[str, str]]:
    """(alias_text, sku) pairs, in a stable order. One list, walked by both directions."""
    rows: list[tuple[str, str]] = []
    for form in _CLASS_FORMS:
        for sku in _CLASS_SKUS:
            rows.append((form, sku))
    for family, skus in _FAMILY_PHRASES:
        for form in _CLASS_FORMS:
            for sku in skus:
                rows.append((f"{form} {family}", sku))
    rows.extend(_BARE_NUMBER)
    return rows


def _row_id(normalized: str, variant_id: str) -> str:
    """Deterministic, so a re-run is a no-op and the downgrade can name its own rows."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"r206:{normalized}:{variant_id}"))


def upgrade() -> None:
    conn = op.get_bind()

    # ── pre-flight ────────────────────────────────────────────────────────
    # ⚠️ A POSITIVE CONTROL FIRST: the reader must be able to SEE the table before
    # an empty result from it is allowed to mean anything.
    tables = {r[0] for r in conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ))}
    assert len(tables) > 100, f"saw {len(tables)} tables; the reader is blind"
    assert _TABLE in tables, f"{_TABLE} is missing; r189 should have created it"

    # ⚠️ ASSERT THE FOLD DISAGREES ON "OS" AND "O/S" RATHER THAN ASSUMING IT. If a
    # future fold mapped the slash away this migration would write two rows with the
    # same normalized text against one variant and trip the unique constraint; better
    # to fail here, with the reason, than on an INSERT.
    assert _fold("OS") == "os", _fold("OS")
    assert _fold("O/S") == "o s", _fold("O/S")

    by_sku = {sku: vid for sku, vid in conn.execute(sa.text(
        "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
    ))}
    assert len(by_sku) > 40, f"only {len(by_sku)} active variants — catalog unseeded"
    planned = _planned()
    needed = sorted({sku for _, sku in planned})
    missing = [s for s in needed if s not in by_sku]
    assert not missing, (
        f"these SKUs are absent, so the phrases naming them would silently resolve to "
        f"nothing: {missing}"
    )

    before = conn.execute(sa.text(f"SELECT count(*) FROM {_TABLE}")).scalar()

    # ── write ─────────────────────────────────────────────────────────────
    ids: list[str] = []
    for alias_text, sku in planned:
        vid = by_sku[sku]
        norm = _fold(alias_text)
        assert norm, f"{alias_text!r} folds to nothing"
        rid = _row_id(norm, vid)
        ids.append(rid)
        conn.execute(sa.text(
            f"INSERT INTO {_TABLE} "
            "(id, variant_template_id, alias_text, alias_text_normalized, source, "
            " is_confirmed, note) "
            "VALUES (:i, :v, :t, :n, 'manual', TRUE, :note) "
            "ON CONFLICT (variant_template_id, alias_text_normalized) DO NOTHING"
        ), {"i": rid, "v": vid, "t": alias_text, "n": norm, "note": _NOTE})

    # ── post-flight ───────────────────────────────────────────────────────
    assert len(set(ids)) == len(ids), "two planned rows collided on their id"
    after = conn.execute(sa.text(f"SELECT count(*) FROM {_TABLE}")).scalar()
    assert after - before == len(planned), (
        f"planned {len(planned)} rows, table grew by {after - before}"
    )

    # ⚠️ ASSERTED AS CANDIDATE SETS, NOT AS A ROW COUNT. A count is satisfied by rows
    # pointing at the wrong variants; what the ruling is about is which variants a
    # phrase reaches, so that is what is checked.
    sku_of = {vid: sku for sku, vid in by_sku.items()}
    got: dict[str, set[str]] = {}
    for norm, vid in conn.execute(sa.text(
        f"SELECT alias_text_normalized, variant_template_id FROM {_TABLE} "
        "WHERE note LIKE 'Class alias.%'"
    )):
        got.setdefault(norm, set()).add(sku_of.get(vid, vid))
    assert got.get("oversized") == set(_CLASS_SKUS), got.get("oversized")
    assert got.get("os") == set(_CLASS_SKUS), got.get("os")
    assert got.get("o s") == set(_CLASS_SKUS), got.get("o s")
    assert got.get("oversized continental") == {"BV-CON34"}, got.get("oversized continental")
    assert got.get("oversized graveliner") == {"GL-34", "GL-38"}, got.get("oversized graveliner")
    assert got.get("continental 34") == {"BV-CON34"}, got.get("continental 34")


def downgrade() -> None:
    conn = op.get_bind()
    by_sku = {sku: vid for sku, vid in conn.execute(sa.text(
        "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
    ))}
    ids = [
        _row_id(_fold(alias_text), by_sku[sku])
        for alias_text, sku in _planned()
        if sku in by_sku
    ]
    if ids:
        conn.execute(
            sa.text(f"DELETE FROM {_TABLE} WHERE id = ANY(:ids)"), {"ids": ids}
        )
