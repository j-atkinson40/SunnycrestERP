"""CRM visibility filtering for company_entities.

Returns SQLAlchemy filter expressions that restrict CRM pages to only
show companies relevant to the tenant's preset and enabled extensions.

This is a VIEW-ONLY filter — AR, AP, order station, aging reports,
and all other operational endpoints remain unaffected.
"""

import sqlalchemy as sa
from sqlalchemy import or_, and_, not_
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.services.extension_service import get_active_extension_keys


def get_crm_visible_filter(db: Session, tenant_id: str):
    """Return a SQLAlchemy filter expression for CRM-visible company_entities.

    Usage:
        filt = get_crm_visible_filter(db, tenant_id)
        query = db.query(CompanyEntity).filter(
            CompanyEntity.company_id == tenant_id,
            filt,
        )
    """
    active_exts = set(get_active_extension_keys(db, tenant_id))

    # ── Always visible ─────────────────────────────────────────────
    always_visible = or_(
        CompanyEntity.is_funeral_home.is_(True),
        CompanyEntity.customer_type == "funeral_home",
        CompanyEntity.is_cemetery.is_(True),
        CompanyEntity.customer_type == "cemetery",
        CompanyEntity.is_licensee.is_(True),
        CompanyEntity.is_crematory.is_(True),
        # Pure vendors (vendor but NOT customer) always visible
        and_(CompanyEntity.is_vendor.is_(True), CompanyEntity.is_customer.is_(False)),
    )

    # ── Extension-gated contractors ────────────────────────────────
    contractor_conditions = []

    if "wastewater" in active_exts:
        contractor_conditions.append(
            and_(
                CompanyEntity.customer_type == "contractor",
                CompanyEntity.contractor_type.in_(["wastewater_only", "full_service"]),
            )
        )

    if "redi_rock" in active_exts:
        contractor_conditions.append(
            and_(
                CompanyEntity.customer_type == "contractor",
                CompanyEntity.contractor_type.in_(["redi_rock_only", "full_service"]),
            )
        )

    if "general_precast" in active_exts:
        contractor_conditions.append(
            and_(
                CompanyEntity.customer_type == "contractor",
                CompanyEntity.contractor_type.in_(["general", "occasional"]),
            )
        )
        # Also show 'other' type when general precast enabled
        contractor_conditions.append(CompanyEntity.customer_type == "other")

    # ── Never visible (excluded even if above rules would include them) ──
    # is_aggregate records are always hidden
    never_visible = or_(
        CompanyEntity.is_aggregate.is_(True),
        # Individuals always hidden
        CompanyEntity.customer_type == "individual",
        # Churches hidden UNLESS also a cemetery or funeral home
        and_(
            CompanyEntity.customer_type == "church",
            CompanyEntity.is_cemetery.is_(False),
            CompanyEntity.is_funeral_home.is_(False),
        ),
        # Government hidden UNLESS also a cemetery
        and_(
            CompanyEntity.customer_type == "government",
            CompanyEntity.is_cemetery.is_(False),
        ),
        # Unclassified (null type without trusted classification source) → data quality only
        and_(
            CompanyEntity.customer_type.is_(None),
            or_(
                CompanyEntity.classification_source.is_(None),
                CompanyEntity.classification_source.notin_(["manual", "auto_high", "auto_google"]),
            ),
        ),
    )

    # Combine: (always_visible OR contractor_conditions) AND NOT never_visible
    visible_conditions = [always_visible]
    if contractor_conditions:
        visible_conditions.extend(contractor_conditions)

    return and_(
        or_(*visible_conditions),
        not_(never_visible),
    )


def is_crm_visible(db: Session, tenant_id: str, entity: "CompanyEntity") -> bool:
    """Quick boolean check for a single company entity."""
    filt = get_crm_visible_filter(db, tenant_id)
    exists = (
        db.query(CompanyEntity.id)
        .filter(CompanyEntity.id == entity.id, filt)
        .first()
    )
    return exists is not None


def get_hidden_count(db: Session, tenant_id: str) -> dict:
    """Return counts of companies hidden from CRM, grouped by reason.

    Used for the "N companies are hidden" banner and the data quality
    hidden tab.
    """
    active_exts = set(get_active_extension_keys(db, tenant_id))
    base = db.query(CompanyEntity).filter(
        CompanyEntity.company_id == tenant_id,
        CompanyEntity.is_active.is_(True),
    )

    # Wastewater contractors (hidden when wastewater extension off)
    ww = 0
    if "wastewater" not in active_exts:
        ww = base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["wastewater_only", "full_service"]),
        ).count()

    # Redi-Rock contractors
    rr = 0
    if "redi_rock" not in active_exts:
        rr = base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["redi_rock_only", "full_service"]),
        ).count()

    # General/precast contractors
    gp = 0
    if "general_precast" not in active_exts:
        gp = base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["general", "occasional"]),
        ).count()

    # Always hidden types
    individuals = base.filter(CompanyEntity.customer_type == "individual").count()

    churches = base.filter(
        CompanyEntity.customer_type == "church",
        CompanyEntity.is_cemetery.is_(False),
        CompanyEntity.is_funeral_home.is_(False),
    ).count()

    government = base.filter(
        CompanyEntity.customer_type == "government",
        CompanyEntity.is_cemetery.is_(False),
    ).count()

    unclassified = base.filter(
        CompanyEntity.customer_type.is_(None),
        or_(
            CompanyEntity.classification_source.is_(None),
            CompanyEntity.classification_source.notin_(["manual", "auto_high", "auto_google"]),
        ),
    ).count()

    aggregates = base.filter(CompanyEntity.is_aggregate.is_(True)).count()

    # "other" type hidden unless general_precast enabled
    other = 0
    if "general_precast" not in active_exts:
        other = base.filter(CompanyEntity.customer_type == "other").count()

    total = ww + rr + gp + individuals + churches + government + unclassified + aggregates + other

    return {
        "contractors_wastewater": ww,
        "contractors_redi_rock": rr,
        "contractors_general": gp,
        "individuals": individuals,
        "churches": churches,
        "government": government,
        "unclassified": unclassified,
        "aggregates": aggregates,
        "other": other,
        "total_hidden": total,
    }


def get_hidden_companies(db: Session, tenant_id: str) -> dict:
    """Return actual companies hidden from CRM, grouped by reason.

    Used by the data quality hidden tab.
    """
    active_exts = set(get_active_extension_keys(db, tenant_id))
    base = db.query(CompanyEntity).filter(
        CompanyEntity.company_id == tenant_id,
        CompanyEntity.is_active.is_(True),
    )

    def _serialize_list(query):
        return [
            {"id": e.id, "name": e.name, "city": e.city, "state": e.state,
             "customer_type": getattr(e, "customer_type", None),
             "contractor_type": getattr(e, "contractor_type", None)}
            for e in query.order_by(CompanyEntity.name).all()
        ]

    groups = {}

    if "wastewater" not in active_exts:
        q = base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["wastewater_only", "full_service"]),
        )
        items = _serialize_list(q)
        if items:
            groups["contractors_wastewater"] = {
                "label": "Wastewater contractors",
                "description": "Shown in CRM when Wastewater extension is enabled",
                "extension_key": "wastewater",
                "items": items,
            }

    if "redi_rock" not in active_exts:
        q = base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["redi_rock_only", "full_service"]),
        )
        items = _serialize_list(q)
        if items:
            groups["contractors_redi_rock"] = {
                "label": "Redi-Rock contractors",
                "description": "Shown in CRM when Redi-Rock extension is enabled",
                "extension_key": "redi_rock",
                "items": items,
            }

    if "general_precast" not in active_exts:
        q = base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["general", "occasional"]),
        )
        items = _serialize_list(q)
        if items:
            groups["contractors_general"] = {
                "label": "General contractors",
                "description": "Shown in CRM when General Precast extension is enabled",
                "extension_key": "general_precast",
                "items": items,
            }

        q2 = base.filter(CompanyEntity.customer_type == "other")
        items2 = _serialize_list(q2)
        if items2:
            groups["other"] = {
                "label": "Other businesses",
                "description": "Shown in CRM when General Precast extension is enabled",
                "extension_key": "general_precast",
                "items": items2,
            }

    individuals = _serialize_list(base.filter(CompanyEntity.customer_type == "individual"))
    churches = _serialize_list(base.filter(
        CompanyEntity.customer_type == "church",
        CompanyEntity.is_cemetery.is_(False),
        CompanyEntity.is_funeral_home.is_(False),
    ))
    government = _serialize_list(base.filter(
        CompanyEntity.customer_type == "government",
        CompanyEntity.is_cemetery.is_(False),
    ))
    aggregates = _serialize_list(base.filter(CompanyEntity.is_aggregate.is_(True)))

    always_hidden_items = individuals + churches + government + aggregates
    if always_hidden_items:
        groups["always_hidden"] = {
            "label": "Always hidden",
            "description": "Individuals, churches, government entities, and aggregate records are not shown in the CRM.",
            "extension_key": None,
            "items": always_hidden_items,
        }

    unclassified = _serialize_list(base.filter(
        CompanyEntity.customer_type.is_(None),
        or_(
            CompanyEntity.classification_source.is_(None),
            CompanyEntity.classification_source.notin_(["manual", "auto_high", "auto_google"]),
        ),
    ))
    if unclassified:
        groups["unclassified"] = {
            "label": "Unclassified",
            "description": "These companies couldn't be automatically classified. Classify them to include them in the appropriate area.",
            "extension_key": None,
            "items": unclassified,
        }

    return groups


def check_extension_crm_unlock(db: Session, tenant_id: str, extension_key: str) -> int:
    """Check how many companies would become CRM-visible if this extension were enabled.

    Call after enabling an extension to determine if an onboarding item
    should be created to review newly-visible accounts.

    Returns count of companies that would be unlocked.
    """
    base = db.query(CompanyEntity).filter(
        CompanyEntity.company_id == tenant_id,
        CompanyEntity.is_active.is_(True),
    )

    if extension_key == "wastewater":
        return base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["wastewater_only", "full_service"]),
        ).count()
    elif extension_key == "redi_rock":
        return base.filter(
            CompanyEntity.customer_type == "contractor",
            CompanyEntity.contractor_type.in_(["redi_rock_only", "full_service"]),
        ).count()
    elif extension_key == "general_precast":
        return base.filter(
            or_(
                and_(
                    CompanyEntity.customer_type == "contractor",
                    CompanyEntity.contractor_type.in_(["general", "occasional"]),
                ),
                CompanyEntity.customer_type == "other",
            )
        ).count()
    return 0
