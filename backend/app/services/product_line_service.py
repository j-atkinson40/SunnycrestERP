"""Product Line Service — first-class product line primitive.

Product lines represent what a tenant operationally runs (vaults, urns,
redi-rock walls, etc.). Per [BRIDGEABLE_MASTER §5.2.1](../../BRIDGEABLE_MASTER.md):
**Extension = how a line gets installed (or not — vault is built-in).
Product line = the operational reality once installed.**

Two related but distinct concepts:
  - Extensions answer: "is this capability available to this tenant?"
  - Product lines answer: "what does this tenant actually run, in what mode?"

Some product lines arrive via extension activation (urn_sales, wastewater,
redi_rock, rosetta). Vault is a baseline product line auto-seeded for every
manufacturing-vertical tenant — not extension-gated.

Per-line operating mode lives in `TenantProductLine.config["operating_mode"]`
∈ {"production", "purchase", "hybrid"}. Pre-canon `Company.vault_fulfillment_mode`
is the deprecation-target tenant-level field; canon storage is per-line.

Canonical line_keys (per BRIDGEABLE_MASTER §5.2):
  - `vault` — auto-seeded baseline for manufacturing tenants
  - `urn_sales` — activates with `urn_sales` extension
  - `wastewater` — activates with `wastewater` extension
  - `redi_rock` — activates with `redi_rock` extension
  - `rosetta` — activates with `rosetta` extension
  - `funeral_services` — auto-seeded for funeral_home vertical (future)
  - `cemetery_services` — auto-seeded for cemetery vertical (future)
  - `cremation_services` — auto-seeded for crematory vertical (future)

Phase W-3a Drift Correction (April 2026): catalog keys renamed from
implementation-drift values (`burial_vaults` / `urns` / `rosetta_hardscapes`)
to canonical values (`vault` / `urn_sales` / `rosetta`). Per Spec-Override
Discipline: canon is the architectural truth; the implementation drifted
pre-canon; no data was seeded under the drifted keys, so the rename is
safe + isolated (consumers: read-only `/available` endpoint + this module's
own seeder).
"""

from sqlalchemy.orm import Session

from app.models.tenant_product_line import TenantProductLine


# Default catalog of available product lines per vertical.
# `default_for_verticals` drives auto-seeding at tenant creation time
# (see `seed_default_product_lines` below).
AVAILABLE_PRODUCT_LINES = {
    "vault": {
        "display_name": "Burial Vaults",
        "default_for_verticals": ["manufacturing"],
        "replaces_extension": None,
        "default_operating_mode": "production",
    },
    "urn_sales": {
        "display_name": "Urns & Memorial Products",
        "default_for_verticals": [],
        "replaces_extension": "urn_sales",
        # Most Wilbert licensees buy urns from Wilbert directly (drop-ship).
        "default_operating_mode": "purchase",
    },
    "wastewater": {
        "display_name": "Wastewater / Septic",
        "default_for_verticals": [],
        "replaces_extension": "wastewater",
        "default_operating_mode": "production",
    },
    "redi_rock": {
        "display_name": "Redi-Rock Retaining Walls",
        "default_for_verticals": [],
        "replaces_extension": "redi_rock",
        "default_operating_mode": "production",
    },
    "rosetta": {
        "display_name": "Rosetta Hardscapes",
        "default_for_verticals": [],
        "replaces_extension": "rosetta",
        "default_operating_mode": "production",
    },
    "funeral_services": {
        "display_name": "Funeral Services",
        "default_for_verticals": ["funeral_home"],
        "replaces_extension": None,
        "default_operating_mode": "production",
    },
    "cemetery_services": {
        "display_name": "Cemetery Services",
        "default_for_verticals": ["cemetery"],
        "replaces_extension": None,
        "default_operating_mode": "production",
    },
    "cremation_services": {
        "display_name": "Cremation Services",
        "default_for_verticals": ["crematory"],
        "replaces_extension": None,
        "default_operating_mode": "production",
    },
}


def list_lines(db: Session, company_id: str) -> list[TenantProductLine]:
    return (
        db.query(TenantProductLine)
        .filter(TenantProductLine.company_id == company_id)
        .order_by(TenantProductLine.sort_order, TenantProductLine.display_name)
        .all()
    )


def enable_line(
    db: Session,
    company_id: str,
    line_key: str,
    display_name: str | None = None,
    operating_mode: str | None = None,
    config: dict | None = None,
) -> TenantProductLine:
    """Enable a product line for a tenant. Idempotent — re-enables an
    existing row if present; creates a new row otherwise.

    Phase W-3a — `operating_mode` is canonical per [BRIDGEABLE_MASTER
    §5.2.2](../../BRIDGEABLE_MASTER.md). Stored in `config["operating_mode"]`
    ∈ {"production", "purchase", "hybrid"}. When omitted, falls back to
    catalog's `default_operating_mode`. Additional config keys may be
    passed via `config` (merged with operating_mode).
    """
    existing = (
        db.query(TenantProductLine)
        .filter(TenantProductLine.company_id == company_id, TenantProductLine.line_key == line_key)
        .first()
    )

    catalog = AVAILABLE_PRODUCT_LINES.get(line_key, {})
    resolved_mode = operating_mode or catalog.get("default_operating_mode") or "production"

    merged_config = dict(config or {})
    # Don't clobber explicit caller-supplied operating_mode in config dict.
    merged_config.setdefault("operating_mode", resolved_mode)

    if existing:
        existing.is_enabled = True
        # Merge new config over existing config — preserves prior keys
        # (e.g., per-line setup wizard output) while updating mode.
        existing_cfg = dict(existing.config or {})
        existing_cfg.update(merged_config)
        existing.config = existing_cfg
        db.commit()
        db.refresh(existing)
        return existing

    name = display_name or catalog.get("display_name") or line_key.replace("_", " ").title()

    line = TenantProductLine(
        company_id=company_id,
        line_key=line_key,
        display_name=name,
        is_enabled=True,
        config=merged_config,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def seed_default_product_lines(
    db: Session,
    company,
    *,
    operating_mode_override: str | None = None,
) -> list[TenantProductLine]:
    """Auto-seed default product lines for a tenant based on their
    vertical. Idempotent — re-enabling existing rows is a no-op write.

    Per [BRIDGEABLE_MASTER §5.2](../../BRIDGEABLE_MASTER.md), each
    vertical has baseline product lines auto-seeded at tenant creation:
      - manufacturing → vault (operating_mode default "production")
      - funeral_home → funeral_services
      - cemetery → cemetery_services
      - crematory → cremation_services

    Walks `AVAILABLE_PRODUCT_LINES` catalog filtering by
    `default_for_verticals`. For each match, calls `enable_line` with
    the catalog's `default_operating_mode` (or override).

    `operating_mode_override` is the migration hook: post-r60 backfill
    copies `Company.vault_fulfillment_mode` value into the seeded
    vault row's `config["operating_mode"]` so existing tenants
    preserve their pre-canon mode setting. New tenants get the catalog
    default.

    Returns the list of TenantProductLine rows seeded (or no-op'd).
    Best-effort behavior: per-line failures log + continue rather than
    block the parent operation.
    """
    import logging

    logger = logging.getLogger(__name__)
    vertical = getattr(company, "vertical", None)
    if not vertical:
        return []

    seeded: list[TenantProductLine] = []
    for line_key, catalog in AVAILABLE_PRODUCT_LINES.items():
        if vertical not in catalog.get("default_for_verticals", []):
            continue
        try:
            mode = operating_mode_override or catalog.get("default_operating_mode")
            line = enable_line(
                db,
                company_id=company.id,
                line_key=line_key,
                operating_mode=mode,
            )
            seeded.append(line)
        except Exception:  # pragma: no cover — best-effort
            logger.exception(
                "Failed to auto-seed product line %s for company %s",
                line_key,
                company.id,
            )
            try:
                db.rollback()
            except Exception:
                pass
    return seeded


def disable_line(db: Session, company_id: str, line_key: str) -> TenantProductLine | None:
    line = (
        db.query(TenantProductLine)
        .filter(TenantProductLine.company_id == company_id, TenantProductLine.line_key == line_key)
        .first()
    )
    if not line:
        return None
    line.is_enabled = False
    db.commit()
    db.refresh(line)
    return line


def has_line(db: Session, company_id: str, line_key: str) -> bool:
    """Primary replacement for has_extension / hasModule('urn_sales')."""
    line = (
        db.query(TenantProductLine)
        .filter(
            TenantProductLine.company_id == company_id,
            TenantProductLine.line_key == line_key,
            TenantProductLine.is_enabled == True,  # noqa: E712
        )
        .first()
    )
    return line is not None


def get_available_lines() -> dict:
    """Return the catalog of all possible product lines."""
    return AVAILABLE_PRODUCT_LINES
