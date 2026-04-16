"""Vault compliance sync — scans compliance data and creates/updates VaultItems."""

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.vault_item import VaultItem
from app.services.vault_service import create_vault_item, get_or_create_company_vault

logger = logging.getLogger(__name__)


def sync_compliance_expiries(db: Session, company_id: str) -> dict:
    """Scan all compliance-related data and upsert VaultItems for tracking.

    Creates event-type VaultItems for:
    - Overdue equipment inspections
    - Upcoming training renewals (within 60 days)
    - Known regulatory filing deadlines (OSHA 300A, etc.)

    Returns summary of items created/updated.
    """
    stats = {"created": 0, "updated": 0, "skipped": 0}

    # 1. Overdue and upcoming inspections
    _sync_inspection_expiries(db, company_id, stats)

    # 2. Training certification renewals
    _sync_training_expiries(db, company_id, stats)

    # 3. Static compliance deadlines (OSHA 300A posting, etc.)
    _sync_regulatory_deadlines(db, company_id, stats)

    return stats


def _sync_inspection_expiries(db: Session, company_id: str, stats: dict) -> None:
    """Create vault items for overdue and upcoming inspections."""
    try:
        from app.services.safety_service import get_overdue_inspections

        overdue = get_overdue_inspections(db, company_id)
        for item in overdue:
            source_key = f"inspection_expiry:{item['template_id']}"
            existing = (
                db.query(VaultItem)
                .filter(
                    VaultItem.company_id == company_id,
                    VaultItem.event_type == "compliance_expiry",
                    VaultItem.event_type_sub == "equipment_inspection",
                    VaultItem.source_entity_id == source_key,
                    VaultItem.is_active == True,
                )
                .first()
            )
            if existing:
                # Update metadata
                existing.metadata_json = {
                    "template_id": item["template_id"],
                    "template_name": item["template_name"],
                    "equipment_type": item.get("equipment_type"),
                    "days_overdue": item["days_overdue"],
                    "last_inspection_date": str(item["last_inspection_date"]) if item["last_inspection_date"] else None,
                }
                existing.title = f"Overdue: {item['template_name']} ({item['days_overdue']} days)"
                stats["updated"] += 1
            else:
                create_vault_item(
                    db,
                    company_id=company_id,
                    item_type="event",
                    title=f"Overdue: {item['template_name']} ({item['days_overdue']} days)",
                    event_start=datetime.now(timezone.utc),
                    event_type="compliance_expiry",
                    event_type_sub="equipment_inspection",
                    notify_before_minutes=[2880, 1440, 720],  # 48hr, 24hr, 12hr
                    status="active",
                    source="system_generated",
                    source_entity_id=source_key,
                    metadata_json={
                        "template_id": item["template_id"],
                        "template_name": item["template_name"],
                        "equipment_type": item.get("equipment_type"),
                        "days_overdue": item["days_overdue"],
                        "last_inspection_date": str(item["last_inspection_date"]) if item["last_inspection_date"] else None,
                    },
                )
                stats["created"] += 1
        db.commit()
    except Exception:
        logger.warning("Failed to sync inspection expiries for %s", company_id, exc_info=True)
        db.rollback()


def _sync_training_expiries(db: Session, company_id: str, stats: dict) -> None:
    """Create vault items for expiring training certifications."""
    try:
        from app.services.safety_service import get_training_gaps

        gaps = get_training_gaps(db, company_id)
        for gap in gaps:
            if gap["status"] not in ("expired", "expiring_soon"):
                stats["skipped"] += 1
                continue

            source_key = f"training_expiry:{gap['employee_id']}:{gap['required_training']}"
            existing = (
                db.query(VaultItem)
                .filter(
                    VaultItem.company_id == company_id,
                    VaultItem.event_type == "compliance_expiry",
                    VaultItem.event_type_sub == "training_renewal",
                    VaultItem.source_entity_id == source_key,
                    VaultItem.is_active == True,
                )
                .first()
            )

            expiry_dt = None
            if gap.get("expiry_date"):
                expiry_dt = datetime.combine(gap["expiry_date"], datetime.min.time()).replace(tzinfo=timezone.utc)

            title = f"Training {'Expired' if gap['status'] == 'expired' else 'Expiring'}: {gap['required_training']} — {gap['employee_name']}"

            if existing:
                existing.title = title
                existing.event_start = expiry_dt
                existing.metadata_json = {
                    "employee_id": gap["employee_id"],
                    "employee_name": gap["employee_name"],
                    "required_training": gap["required_training"],
                    "osha_standard_code": gap.get("osha_standard_code"),
                    "status": gap["status"],
                    "days_overdue": gap.get("days_overdue"),
                }
                stats["updated"] += 1
            else:
                create_vault_item(
                    db,
                    company_id=company_id,
                    item_type="event",
                    title=title,
                    event_start=expiry_dt,
                    event_type="compliance_expiry",
                    event_type_sub="training_renewal",
                    related_entity_type="employee",
                    related_entity_id=gap["employee_id"],
                    notify_before_minutes=[2880, 1440, 720],
                    status="active",
                    source="system_generated",
                    source_entity_id=source_key,
                    metadata_json={
                        "employee_id": gap["employee_id"],
                        "employee_name": gap["employee_name"],
                        "required_training": gap["required_training"],
                        "osha_standard_code": gap.get("osha_standard_code"),
                        "status": gap["status"],
                        "days_overdue": gap.get("days_overdue"),
                    },
                )
                stats["created"] += 1
        db.commit()
    except Exception:
        logger.warning("Failed to sync training expiries for %s", company_id, exc_info=True)
        db.rollback()


def _sync_regulatory_deadlines(db: Session, company_id: str, stats: dict) -> None:
    """Create vault items for known regulatory filing deadlines.

    Static deadlines that recur annually:
    - OSHA 300A posting: Feb 1 - Apr 30
    - OSHA 300 log retention deadline
    """
    try:
        today = date.today()
        year = today.year

        deadlines = [
            {
                "sub_type": "osha_300a",
                "title": f"OSHA 300A Posting Period ({year})",
                "start": date(year, 2, 1),
                "end": date(year, 4, 30),
                "description": "Annual OSHA 300A summary must be posted in workplace Feb 1 - Apr 30.",
            },
        ]

        for dl in deadlines:
            source_key = f"regulatory:{dl['sub_type']}:{year}"
            existing = (
                db.query(VaultItem)
                .filter(
                    VaultItem.company_id == company_id,
                    VaultItem.event_type == "compliance_expiry",
                    VaultItem.event_type_sub == dl["sub_type"],
                    VaultItem.source_entity_id == source_key,
                    VaultItem.is_active == True,
                )
                .first()
            )
            if existing:
                stats["skipped"] += 1
                continue

            create_vault_item(
                db,
                company_id=company_id,
                item_type="event",
                title=dl["title"],
                description=dl["description"],
                event_start=datetime.combine(dl["start"], datetime.min.time()).replace(tzinfo=timezone.utc),
                event_end=datetime.combine(dl["end"], datetime.min.time()).replace(tzinfo=timezone.utc),
                event_type="compliance_expiry",
                event_type_sub=dl["sub_type"],
                all_day=True,
                notify_before_minutes=[2880, 1440],
                status="active",
                source="system_generated",
                source_entity_id=source_key,
            )
            stats["created"] += 1

        db.commit()
    except Exception:
        logger.warning("Failed to sync regulatory deadlines for %s", company_id, exc_info=True)
        db.rollback()
