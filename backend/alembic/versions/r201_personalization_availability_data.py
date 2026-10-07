"""Per-vault personalization availability — DATA ONLY, no schema change.

⚠️ DATA, NOT SCHEMA. Adds no column, drops none, alters none. It writes one key —
`availability` — inside the existing `wilbert_program_enrollments.personalization_config`
JSONB, for every enrollment that already has a config.

⚠️ KEYED BY `product_variant_templates.id`, RESOLVED FROM SKU AT RUN TIME. The map
below is by SKU because SKUs are stable identifiers the catalog owns, while variant
ids are per-database uuids — a migration carrying hardcoded uuids would write
nothing on any database but the one it was authored against, silently, because an
unmatched key is simply a key nobody reads.

⚠️ AND IT FAILS LOUDLY IF A SKU IS MISSING rather than skipping it. A skipped SKU
means that vault gets no availability entry, which `read_availability` reads as
NOT_CONFIGURED — indistinguishable from a licensee who has said nothing, which is
the one state this whole mechanism exists to keep separate. Silence is the failure
mode that cannot be detected afterwards, so it raises.

⚠️ THE MAP IS A FROZEN COPY OF `scripts/seed_personalization_availability.py` AND
THAT DUPLICATION IS DELIBERATE. A migration that imported the script would replay
differently every time the script changed: running the chain on a fresh database in
six months would write whatever the script says then, not what this revision wrote.
A migration's data has to be fixed at the revision. `test_r201_matches_the_seed_map`
asserts the two agree TODAY, so the copy cannot drift unnoticed while both are live.

⚠️ EVERY ENTRY IS JAMES'S RULING OF 2026-10-07. The ordering portal's vault list is
ambiguous between burial and urn forms for twelve names; the ruling is that a plain
portal name means the BURIAL vault and urn forms take theirs from the portal's
separate "... Urn Vault" rows. Two entries carry known caveats, recorded in STATE:
`UV-SAL` follows the portal against the spec sheet's empty "Basic Gray Urn Vault
(P410)" row, and the twelve P-series urns are deliberately absent (pending James).
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "r201_personalization_availability_data"
down_revision = "r200_order_capture_part1_columns"
branch_labels = None
depends_on = None

_QUESTION = "personalization"

_ALL = [
    "legacy_print",
    "nameplate_only",
    "nameplate_and_cover_emblem",
    "cover_emblem_only",
    "lifes_reflections",
    "nameplate_and_lifes_reflections",
]
_NAMEPLATE_OR_EMBLEM = [
    "nameplate_only",
    "cover_emblem_only",
    "nameplate_and_cover_emblem",
]
_NAMEPLATE_ONLY = ["nameplate_only"]
_NONE: list = []

#: SKU -> permitted answers. 40 entries; the 12 P-series urns are absent on purpose.
AVAILABILITY_BY_SKU: dict[str, list[str]] = {
    "BV-WBR": _ALL, "BV-BTRI": _ALL, "BV-CTRI": _ALL, "BV-SSTRI": _ALL,
    "BV-CRTRI": _ALL, "BV-VTRI": _ALL, "BV-WTRIB": _ALL, "BV-GTRIB": _ALL,
    "BV-GVEN": _ALL, "BV-WVEN": _ALL,
    "BV-CON": _NAMEPLATE_ONLY, "BV-CON34": _NAMEPLATE_ONLY,
    "BV-SAL": _NAMEPLATE_OR_EMBLEM,
    "BV-MON": _NONE, "BV-MRC": _NONE,
    "UV-BTRI": _ALL, "UV-CTRI": _ALL, "UV-SSTRI": _ALL, "UV-CRTRI": _ALL,
    "UV-VET": _ALL, "UV-GVEN": _ALL, "UV-WVEN": _ALL,
    "UV-SAL": _NAMEPLATE_OR_EMBLEM,
    "UV-MON": _NONE, "UV-UCG": _NONE, "UV-UWS": _NONE, "UV-GL": _NONE,
    "GL-STD": _NONE, "GL-34": _NONE, "GL-38": _NONE, "GL-SS": _NONE,
    "LC-19": _NONE, "LC-24": _NONE, "LC-31": _NONE,
    "CE-LD": _NONE, "CE-TS": _NONE, "CE-TD": _NONE, "CE-GM": _NONE,
    "CE-CH": _NONE, "CE-CT": _NONE,
}


def _variant_ids(conn) -> dict[str, str]:
    """SKU -> variant_template_id, raising if any mapped SKU is absent."""
    rows = conn.execute(sa.text(
        "SELECT sku, id FROM product_variant_templates WHERE is_active IS TRUE"
    )).all()
    by_sku = {sku: vid for sku, vid in rows}
    # ⚠️ POSITIVE CONTROL BEFORE THE LOOKUP. An empty catalog would make every
    # "missing SKU" check below fire at once with a confusing message; worse, a
    # near-empty one could satisfy a weaker check. Require the catalog to be there.
    assert len(by_sku) > 40, (
        f"only {len(by_sku)} active variants — the catalog is not seeded, so this "
        f"data migration has nothing to key against"
    )
    missing = sorted(set(AVAILABILITY_BY_SKU) - set(by_sku))
    assert not missing, (
        f"these SKUs are not in the catalog, so the vaults they name would silently "
        f"get NO availability entry and read as NOT_CONFIGURED: {missing}"
    )
    return by_sku


def _enrollments(conn):
    return conn.execute(sa.text(
        "SELECT id, personalization_config FROM wilbert_program_enrollments "
        "WHERE personalization_config IS NOT NULL ORDER BY id"
    )).all()


def upgrade() -> None:
    conn = op.get_bind()
    by_sku = _variant_ids(conn)
    desired = {
        by_sku[sku]: {_QUESTION: list(answers)}
        for sku, answers in AVAILABILITY_BY_SKU.items()
    }

    written = 0
    for eid, config in _enrollments(conn):
        config = config if isinstance(config, dict) else {}
        # ⚠️ MERGE INTO THE EXISTING KEY, NEVER REPLACE THE COLUMN. `options` is the
        # pre-r185 shape and other keys may arrive later; a whole-column write would
        # drop them. Idempotent because an already-current entry is overwritten with
        # an identical value.
        availability = dict(config.get("availability") or {})
        if availability == desired and "availability" in config:
            continue
        availability.update(desired)
        new = dict(config)
        new["availability"] = availability
        conn.execute(sa.text(
            "UPDATE wilbert_program_enrollments "
            "SET personalization_config = CAST(:p AS jsonb) WHERE id = :i"
        ), {"p": json.dumps(new), "i": eid})
        written += 1

    # ⚠️ VERIFIED BY READING BACK, not by trusting the UPDATE's rowcount. A JSONB
    # cast that silently produced the wrong shape would still report rows affected.
    for eid, config in _enrollments(conn):
        got = (config or {}).get("availability") or {}
        for vid, entry in desired.items():
            assert got.get(vid) == entry, (
                f"enrollment {eid} did not take the availability entry for {vid}"
            )
    print(f"r201: availability written to {written} enrollment(s); "
          f"{len(desired)} variants mapped")


def downgrade() -> None:
    """Remove ONLY the entries this revision added.

    ⚠️ NOT `config.pop("availability")`. Another revision, or an operator, may add
    entries for variants this map does not name — the twelve P-series urns are the
    obvious candidates — and dropping the whole key would take those with it. This
    removes the mapped variant ids and then removes the now-empty container only if
    nothing else is left in it.
    """
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT sku, id FROM product_variant_templates"
    )).all()
    by_sku = {sku: vid for sku, vid in rows}
    # ⚠️ NO assertion here. A downgrade must work on a database whose catalog has
    # moved on; a SKU that no longer exists simply has no entry to remove.
    mine = {by_sku[sku] for sku in AVAILABILITY_BY_SKU if sku in by_sku}

    for eid, config in _enrollments(conn):
        config = config if isinstance(config, dict) else {}
        availability = dict(config.get("availability") or {})
        if not availability:
            continue
        kept = {k: v for k, v in availability.items() if k not in mine}
        new = dict(config)
        if kept:
            new["availability"] = kept
        else:
            new.pop("availability", None)
        conn.execute(sa.text(
            "UPDATE wilbert_program_enrollments "
            "SET personalization_config = CAST(:p AS jsonb) WHERE id = :i"
        ), {"p": json.dumps(new), "i": eid})
