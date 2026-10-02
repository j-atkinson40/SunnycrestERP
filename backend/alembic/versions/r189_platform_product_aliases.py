"""Platform product aliases — one alias text, N candidate variants

Revision ID: r189_platform_product_aliases
Revises: r188_platform_catalog_backfill
Create Date: 2026-10-02

⚠️ RUNS AGAINST PRODUCTION ON DEPLOY (`railway-start.sh:45`). One new table, no
data, no consumer.

WHY A SECOND TABLE RATHER THAN WIDENING `product_aliases`. That table is
`company_id NOT NULL` with an FK to `companies`, so it cannot hold a
platform-level alias, and making its tenant column nullable would change the
meaning of every existing row. Its shape is mirrored where that lets one matching
routine serve both: `alias_text` and `alias_text_normalized` at varchar(500),
`source` at varchar(50), and `is_confirmed`.

⚠️ ALIASES ARE NOT FUZZY MATCHING. Three sources we already own — production's
catalog, the licensee spec sheet, and Wilbert's consumer store — each name the
same products differently. This table is the precondition for treating those
three as one catalog, not a convenience for interpreting speech.

⚠️ ALIAS TEXT RESOLVES TO A VARIANT, WHICH IS THE BILLABLE THING. Ambiguity is
expressed as SEVERAL ROWS SHARING ONE `alias_text_normalized`: "Veteran" names
both `BV-VTRI` (Veteran Triune Burial Vault) and `UV-VET` (Veteran Urn Vault), so
it gets a row for each and the resolver returns candidates to the existing
numbered-disambiguation pattern. There is deliberately NO family or product alias
tier — multiple rows already express it, and a tier would invite a default.

⚠️ AND NEVER A DEFAULT. The unique constraint is on the PAIR
`(variant_template_id, alias_text_normalized)`, not on the alias text alone.
Making the text unique would force exactly one winner per alias, which is the
elimination-where-a-label-exists error that dropped a real product from r188's
first draft. The schema has to permit the ambiguity for the resolver to be able
to report it.

COLUMNS DELIBERATELY NOT MIRRORED FROM `product_aliases`:
  - `confidence` (float). That is a fuzzy-matcher's score. A platform alias is
    curated by a person, so the column would be 1.0 on every row — a field the
    table claims to model and does not, which is the defect this arc already
    found in `product_catalog_templates`.
  - `historical_product_id`. Import-lineage, not platform naming.
`is_confirmed` IS kept: it is the curated-versus-learned marker, and a future
Wilbert catalog import could propose aliases that a person has not yet accepted.

`source` is constrained rather than free text because an alias whose provenance
nobody can judge is worse than no alias — these four sources are the ones that
exist today and a fifth is a deliberate addition.
"""
from alembic import op
import sqlalchemy as sa

revision = "r189_platform_product_aliases"
down_revision = "r188_platform_catalog_backfill"
branch_labels = None
depends_on = None

_SOURCES = ("production_catalog", "spec_sheet", "wilbert_store", "manual")


def upgrade() -> None:
    op.create_table(
        "platform_product_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("variant_template_id", sa.String(36), nullable=False),
        sa.Column("alias_text", sa.String(500), nullable=False),
        #: Produced by `ImportAliasService._normalize_text`, which is a pure
        #: staticmethod over a string with no tenant scope — so ONE
        #: normalisation serves both alias tables. A second implementation would
        #: drift, and the drift would be invisible until a lookup silently missed.
        sa.Column("alias_text_normalized", sa.String(500), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["variant_template_id"], ["product_variant_templates.id"],
            name="fk_platform_product_aliases_variant",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "variant_template_id", "alias_text_normalized",
            name="uq_platform_product_aliases_variant_text",
        ),
        sa.CheckConstraint(
            "source IN ('" + "', '".join(_SOURCES) + "')",
            name="ck_platform_product_aliases_source",
        ),
    )
    #: The lookup index. Not unique — several variants legitimately share one
    #: normalized alias, which is how ambiguity is represented.
    op.create_index(
        "ix_platform_product_aliases_normalized",
        "platform_product_aliases",
        ["alias_text_normalized"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_product_aliases_normalized",
        table_name="platform_product_aliases",
    )
    op.drop_table("platform_product_aliases")
