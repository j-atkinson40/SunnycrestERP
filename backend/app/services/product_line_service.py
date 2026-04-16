"""Product Line Service — replaces the extension library with first-class product lines.

Product lines represent what a tenant sells (burial vaults, urns, cemetery products, etc.).
They replace the "extensions" concept, which was confusingly modeled as installable add-ons
when really these are core business lines that every tenant has some combination of.
"""

from sqlalchemy.orm import Session

from app.models.tenant_product_line import TenantProductLine


# Default catalog of available product lines per vertical
AVAILABLE_PRODUCT_LINES = {
    "burial_vaults": {
        "display_name": "Burial Vaults",
        "default_for_verticals": ["manufacturing"],
        "replaces_extension": None,
    },
    "urns": {
        "display_name": "Urns & Memorial Products",
        "default_for_verticals": [],
        "replaces_extension": "urn_sales",
    },
    "wastewater": {
        "display_name": "Wastewater / Septic",
        "default_for_verticals": [],
        "replaces_extension": "wastewater",
    },
    "redi_rock": {
        "display_name": "Redi-Rock Retaining Walls",
        "default_for_verticals": [],
        "replaces_extension": "redi_rock",
    },
    "rosetta_hardscapes": {
        "display_name": "Rosetta Hardscapes",
        "default_for_verticals": [],
        "replaces_extension": "rosetta_hardscapes",
    },
    "funeral_services": {
        "display_name": "Funeral Services",
        "default_for_verticals": ["funeral_home"],
        "replaces_extension": None,
    },
    "cemetery_services": {
        "display_name": "Cemetery Services",
        "default_for_verticals": ["cemetery"],
        "replaces_extension": None,
    },
    "cremation_services": {
        "display_name": "Cremation Services",
        "default_for_verticals": ["crematory"],
        "replaces_extension": None,
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
    db: Session, company_id: str, line_key: str, display_name: str | None = None
) -> TenantProductLine:
    existing = (
        db.query(TenantProductLine)
        .filter(TenantProductLine.company_id == company_id, TenantProductLine.line_key == line_key)
        .first()
    )
    if existing:
        existing.is_enabled = True
        db.commit()
        db.refresh(existing)
        return existing

    catalog = AVAILABLE_PRODUCT_LINES.get(line_key, {})
    name = display_name or catalog.get("display_name") or line_key.replace("_", " ").title()

    line = TenantProductLine(
        company_id=company_id,
        line_key=line_key,
        display_name=name,
        is_enabled=True,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


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
