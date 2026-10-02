"""Seed the five platform product aliases we hold, each citing its source line

Revision ID: r191_platform_alias_seed
Revises: r190_graveliner_name_normalise
Create Date: 2026-10-02

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). Five rows into
`platform_product_aliases`, which r189 created and nothing has written to.

EACH ROW IS A CLAIM ABOUT WHAT ONE SOURCE DOCUMENT MEANT, pointing at the ONE
variant that source denotes. It is NOT a stored candidate set.

⚠️ THAT DISTINCTION COST A ROUND TRIP AND IS WORTH STATING. An earlier derivation
matched each alias against our own variant names by substring and produced ten
rows — two candidates for "Veteran", three for "Grave Liner". That manufactured
ambiguity the sources did not have: matching against our names discards the
referent the source already fixed. Ambiguity is a property of a QUERY, not a
stored fact, because what is ambiguous depends on what the catalog holds right
now — onboard a licensee with a product we do not carry and the candidate set
changes underneath a stored row. The resolver computes candidates at query time
over family, product and variant display names PLUS these aliases, so "Veteran"
still returns both `BV-VTRI` (by this alias) and `UV-VET` (by its own name)
without either being stored as a pair.

THE CONVENTION, VERIFIED AGAINST THE DOCUMENT AND NOT AGAINST A DESCRIPTION OF
IT. In `docs/catalog/2026-10-02-sunnycrest-product-specs.csv` the bare name is
the burial form and the urn form is suffixed, in all four cases where the sheet
carries both:

    line  5  Stainless Steel Triune(SST)              Burial Vault
    line  6  Veteran                                  Burial Vault
    line  7  Cameo Rose                               Burial Vault
    line 13  Grave Liner                              Burial Vault
    line 22  Stainless Steel Triune (SST) Urn Vault   Urn Vault
    line 23  Veteran Urn Vault                        Urn Vault
    line 24  Cameo Rose Urn Vault                     Urn Vault
    line 29  Graveliner Urn Vault                     Urn Vault

No bare alias text names both forms, so the referents are read off labels rather
than chosen by elimination — which is the error that dropped `UV-SAL` from r188's
first draft.

`Basic Gray` is the one alias no document can settle by string matching: it
appears in no name we hold. It rests on the owner's ruling of 2026-10-02 that
Wilbert's "Basic Gray/Salute Urn Vault" is one product, and it is corroborated by
`app/services/sunnycrest_product_seeder.py:182-193`, which predates this arc and
already treats Salute, Cream & Gold and White & Silver as three distinct
products — so the conclusion agrees with something that was in the repository
before any of today's reasoning.

Idempotent: deterministic `uuid5` ids plus an existence check on the natural key,
because `alembic upgrade head` runs on every deploy.
"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "r191_platform_alias_seed"
down_revision = "r190_graveliner_name_normalise"
branch_labels = None
depends_on = None

_NS = uuid.UUID("6f1b4a52-0000-5000-8000-000000000001")

#: (alias_text, variant SKU, source, citation)
ALIASES = [
    (
        "Basic Gray", "UV-SAL", "wilbert_store",
        "Wilbert lists one product as 'Basic Gray/Salute Urn Vault'; the spec "
        "sheet has 'Basic Gray Urn Vault (P410)'. Confirmed ONE product by the "
        "owner 2026-10-02. Corroborated by sunnycrest_product_seeder.py:182-193, "
        "which predates this arc and already separates Salute from the two "
        "Universal finishes. No string in our data carries 'Basic Gray', which "
        "is why this alias is load-bearing and why no mechanical check validates it.",
    ),
    (
        "Grave Liner", "GL-STD", "spec_sheet",
        "Spec sheet line 13, 'Grave Liner', Type 'Burial Vault'. Two words on "
        "the sheet, one word in our data. NOT GL-SS, which the sheet does not "
        "carry, and NOT UV-GL, which the sheet calls 'Graveliner Urn Vault' at "
        "line 29.",
    ),
    (
        "Veteran", "BV-VTRI", "spec_sheet",
        "Spec sheet line 6, 'Veteran', Type 'Burial Vault'. The sheet drops "
        "'Triune'; its urn counterpart is 'Veteran Urn Vault' at line 23.",
    ),
    (
        "Cameo Rose", "BV-CRTRI", "spec_sheet",
        "Spec sheet line 7, 'Cameo Rose', Type 'Burial Vault'. The sheet drops "
        "'Triune'; its urn counterpart is 'Cameo Rose Urn Vault' at line 24.",
    ),
    (
        "SST", "BV-SSTRI", "spec_sheet",
        "Spec sheet line 5, 'Stainless Steel Triune(SST)', Type 'Burial Vault'. "
        "The abbreviation appears in no product name in our data, so it is "
        "recorded as the alias. Its urn counterpart is 'Stainless Steel Triune "
        "(SST) Urn Vault' at line 22.",
    ),
]


def _normalize(text: str) -> str:
    """⚠️ A FROZEN COPY OF `ImportAliasService._normalize_text`, ON PURPOSE.

    A migration must not import app code — app code moves and migrations are
    history. The runtime path uses the service's method, which is the single
    implementation for live lookups; this copy exists only to compute the stored
    value at migration time. The two agreeing is asserted by the verification in
    this phase rather than assumed, and if the service's normalisation ever
    changes, the stored values need a migration of their own.
    """
    import re

    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def upgrade() -> None:
    conn = op.get_bind()
    sku_to_id = {
        r[0]: r[1]
        for r in conn.execute(sa.text("SELECT sku, id FROM product_variant_templates"))
    }
    have = {
        (r[0], r[1])
        for r in conn.execute(
            sa.text(
                "SELECT variant_template_id, alias_text_normalized "
                "FROM platform_product_aliases"
            )
        )
    }
    tbl = sa.table(
        "platform_product_aliases",
        sa.column("id", sa.String), sa.column("variant_template_id", sa.String),
        sa.column("alias_text", sa.String),
        sa.column("alias_text_normalized", sa.String),
        sa.column("source", sa.String), sa.column("is_confirmed", sa.Boolean),
        sa.column("note", sa.Text),
    )
    rows = []
    for text, sku, source, note in ALIASES:
        vid = sku_to_id.get(sku)
        if vid is None:
            # The variant is absent — a database that never ran r188's backfill.
            # Skip rather than raise: an alias to a product that does not exist
            # here is meaningless, not an error.
            continue
        norm = _normalize(text)
        if (vid, norm) in have:
            continue
        rows.append({
            "id": str(uuid.uuid5(_NS, f"{sku}|{norm}")),
            "variant_template_id": vid, "alias_text": text,
            "alias_text_normalized": norm, "source": source,
            "is_confirmed": True, "note": note,
        })
    if rows:
        op.bulk_insert(tbl, rows)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM platform_product_aliases WHERE id = ANY(:ids)"),
        {"ids": [
            str(uuid.uuid5(_NS, f"{sku}|{_normalize(t)}"))
            for t, sku, _s, _n in ALIASES
        ]},
    )
