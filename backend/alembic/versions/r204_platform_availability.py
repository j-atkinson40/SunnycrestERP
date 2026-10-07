"""Platform-default personalization availability — section C.

⚠️ THE SCOPE CHANGE, AND THE REASON IT IS A TABLE RATHER THAN A CONSTANT. Availability
was per-licensee only: r201 wrote it into each `wilbert_program_enrollments` row, so a
new licensee started with none and read NOT_CONFIGURED on every vault. Measured
2026-10-07: enrolling Sunnycrest would have produced exactly that, because
`enroll_in_program` leaves `personalization_config` NULL and r201 selected only rows
where it was already NOT NULL.

It is a TABLE and not a code constant because this is CATALOG DATA keyed by
`product_variant_templates.id`, and a constant keyed by uuid cannot exist — variant ids
are per-database. The SKU map is frozen in this revision (same argument as r201) and
resolved to ids at run time.

THE THREE SCOPES, resolved at READ time, same shape as `platform_themes` and
`component_configurations`:

    platform default   this table — the Wilbert line, out of the box
      + tenant override  `wilbert_program_enrollments.personalization_config.availability`

⚠️ THE OVERRIDE IS PER VARIANT, NOT WHOLE-CONFIG. A licensee who says something about
one vault has said nothing about the others, and replacing the whole map would turn one
statement into silence about 39 products. `enrollment.resolve_availability_config` does
the merge.

⚠️ NOT_CONFIGURED STAYS DISTINCT FROM NOT_OFFERED AT EVERY SCOPE, which is the property
the whole mechanism exists for:

    absent at both scopes            NOT_CONFIGURED  — nobody has said
    platform `[]`, tenant absent     NOT_OFFERED     — the platform says none
    platform non-empty, tenant `[]`  NOT_OFFERED     — the LICENSEE says none
    platform `[]`, tenant non-empty  OFFERED         — the licensee offers it anyway

The third and fourth are why the merge is per variant and why an empty list must survive
it. A merge that treated `[]` as "nothing to say" would collapse both into the platform's
answer and silently overrule the licensee.

⚠️ NO ROW FOR THE 12 P-SERIES URNS, deliberately — they are pending James, and an entry
would assert a measurement nobody made. Their absence IS the NOT_CONFIGURED state.
"""
import sqlalchemy as sa
from alembic import op

revision = "r204_platform_availability"
down_revision = "r203_capture_sessions"
branch_labels = None
depends_on = None

_TABLE = "platform_personalization_availability"
_QUESTION = "personalization"

_ALL = [
    "legacy_print", "nameplate_only", "nameplate_and_cover_emblem",
    "cover_emblem_only", "lifes_reflections", "nameplate_and_lifes_reflections",
]
_NPE = ["nameplate_only", "cover_emblem_only", "nameplate_and_cover_emblem"]
_NP = ["nameplate_only"]
_NONE: list = []

#: ⚠️ A FROZEN COPY OF r201's MAP, and `test_r201_availability_data.py` is extended to
#: assert all three copies agree while all three are live. A migration's data must be
#: fixed at the revision; see r201's docstring for the full argument.
AVAILABILITY_BY_SKU: dict[str, list[str]] = {
    "BV-WBR": _ALL, "BV-BTRI": _ALL, "BV-CTRI": _ALL, "BV-SSTRI": _ALL,
    "BV-CRTRI": _ALL, "BV-VTRI": _ALL, "BV-WTRIB": _ALL, "BV-GTRIB": _ALL,
    "BV-GVEN": _ALL, "BV-WVEN": _ALL,
    "BV-CON": _NP, "BV-CON34": _NP,
    "BV-SAL": _NPE,
    "BV-MON": _NONE, "BV-MRC": _NONE,
    "UV-BTRI": _ALL, "UV-CTRI": _ALL, "UV-SSTRI": _ALL, "UV-CRTRI": _ALL,
    "UV-VET": _ALL, "UV-GVEN": _ALL, "UV-WVEN": _ALL,
    "UV-SAL": _NPE,
    "UV-MON": _NONE, "UV-UCG": _NONE, "UV-UWS": _NONE, "UV-GL": _NONE,
    "GL-STD": _NONE, "GL-34": _NONE, "GL-38": _NONE, "GL-SS": _NONE,
    "LC-19": _NONE, "LC-24": _NONE, "LC-31": _NONE,
    "CE-LD": _NONE, "CE-TS": _NONE, "CE-TD": _NONE, "CE-GM": _NONE,
    "CE-CH": _NONE, "CE-CT": _NONE,
}


def _tables(conn) -> set[str]:
    return {
        r[0] for r in conn.execute(sa.text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
    }


def upgrade() -> None:
    conn = op.get_bind()
    before = _tables(conn)
    assert len(before) > 100, f"saw {len(before)} tables; the reader is blind"
    assert "product_variant_templates" in before, "the catalog table is missing"
    assert _TABLE not in before, f"{_TABLE} already exists"

    op.create_table(
        _TABLE,
        sa.Column("variant_template_id", sa.String(36),
                  sa.ForeignKey("product_variant_templates.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("question_id", sa.String(40), primary_key=True),
        # ⚠️ NOT NULL, because `[]` and NULL would mean different things and only one of
        # them is wanted here: a row EXISTS to say something, and "says nothing" is the
        # absence of a row. A nullable column would add a third state nobody needs.
        sa.Column("permitted_answers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    by_sku = {
        sku: vid for sku, vid in conn.execute(sa.text(
            "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
        ))
    }
    assert len(by_sku) > 40, f"only {len(by_sku)} active variants — catalog unseeded"
    missing = sorted(set(AVAILABILITY_BY_SKU) - set(by_sku))
    assert not missing, (
        f"these SKUs are absent, so the vaults they name would silently get NO platform "
        f"default and read NOT_CONFIGURED: {missing}"
    )

    import json
    for sku, answers in AVAILABILITY_BY_SKU.items():
        conn.execute(sa.text(
            f"INSERT INTO {_TABLE} (variant_template_id, question_id, permitted_answers) "
            "VALUES (:v, :q, CAST(:p AS json))"
        ), {"v": by_sku[sku], "q": _QUESTION, "p": json.dumps(answers)})

    n = conn.execute(sa.text(f"SELECT count(*) FROM {_TABLE}")).scalar()
    assert n == len(AVAILABILITY_BY_SKU), f"wrote {n} of {len(AVAILABILITY_BY_SKU)}"

    # ⚠️ READ BACK AND COMPARE, not just count. An equal count passes while the mapping
    # is wrong — the equal-cardinalities failure CLAUDE.md §12 names.
    got = {
        r[0]: r[1] for r in conn.execute(sa.text(
            f"SELECT variant_template_id, permitted_answers FROM {_TABLE}"
        ))
    }
    for sku, answers in AVAILABILITY_BY_SKU.items():
        stored = got[by_sku[sku]]
        if isinstance(stored, str):
            stored = json.loads(stored)
        assert sorted(stored) == sorted(answers), f"{sku}: {stored} != {answers}"
    print(f"r204: platform availability for {n} variants")


def downgrade() -> None:
    conn = op.get_bind()
    if _TABLE in _tables(conn):
        op.drop_table(_TABLE)
    assert _TABLE not in _tables(conn), f"{_TABLE} survived the downgrade"
