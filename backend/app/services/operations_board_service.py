"""Operations board service — settings, production log, summaries, replies."""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.operations_board import (
    AnnouncementReply,
    DailyProductionSummary,
    OperationsBoardSettings,
    OpsProductionLogEntry,
)
from app.models.user import User

logger = logging.getLogger(__name__)

# Fixed columns in the settings table — contributor settings go into JSONB
FIXED_SETTING_COLUMNS = {
    "zone_briefing_visible",
    "zone_announcements_visible",
    "zone_production_log_visible",
    "button_log_incident",
    "button_safety_observation",
    "button_qc_check",
    "button_log_product",
    "button_end_of_day",
    "button_equipment_inspection",
    "voice_entry_enabled",
    "eod_reminder_enabled",
    "eod_reminder_time",
}


# ---------------------------------------------------------------------------
# Board Settings — fixed + JSONB hybrid
# ---------------------------------------------------------------------------


def get_or_create_settings(
    db: Session, tenant_id: str, employee_id: str,
) -> OperationsBoardSettings:
    settings = (
        db.query(OperationsBoardSettings)
        .filter(
            OperationsBoardSettings.tenant_id == tenant_id,
            OperationsBoardSettings.employee_id == employee_id,
        )
        .first()
    )
    if not settings:
        settings = OperationsBoardSettings(
            tenant_id=tenant_id,
            employee_id=employee_id,
            contributor_settings={},
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def get_merged_settings(db: Session, tenant_id: str, employee_id: str) -> dict:
    """Return all settings as a flat dict — fixed columns merged with contributor_settings JSONB."""
    settings = get_or_create_settings(db, tenant_id, employee_id)
    result = {}
    for col in FIXED_SETTING_COLUMNS:
        result[col] = getattr(settings, col, True)
    # Merge contributor settings — they override defaults
    result.update(settings.contributor_settings or {})
    return result


def update_setting(
    db: Session, tenant_id: str, employee_id: str, key: str, value,
) -> None:
    """Update a single setting — routes to fixed column or JSONB contributor_settings."""
    settings = get_or_create_settings(db, tenant_id, employee_id)
    if key in FIXED_SETTING_COLUMNS:
        setattr(settings, key, value)
    else:
        cs = dict(settings.contributor_settings or {})
        cs[key] = value
        settings.contributor_settings = cs
    db.commit()


def update_settings_bulk(
    db: Session, tenant_id: str, employee_id: str, updates: dict,
) -> None:
    """Update multiple settings at once."""
    settings = get_or_create_settings(db, tenant_id, employee_id)
    cs = dict(settings.contributor_settings or {})
    for key, value in updates.items():
        if key in FIXED_SETTING_COLUMNS:
            setattr(settings, key, value)
        else:
            cs[key] = value
    settings.contributor_settings = cs
    db.commit()


def initialize_contributor_settings(
    db: Session, tenant_id: str, defaults: dict[str, bool],
) -> None:
    """Set default values for new contributor settings on all employees for a tenant."""
    all_settings = (
        db.query(OperationsBoardSettings)
        .filter(OperationsBoardSettings.tenant_id == tenant_id)
        .all()
    )
    for settings in all_settings:
        cs = dict(settings.contributor_settings or {})
        changed = False
        for key, default_val in defaults.items():
            if key not in cs:
                cs[key] = default_val
                changed = True
        if changed:
            settings.contributor_settings = cs
    if all_settings:
        db.commit()


# ---------------------------------------------------------------------------
# Production Log Entries
# ---------------------------------------------------------------------------


def log_production(
    db: Session,
    tenant_id: str,
    user_id: str,
    product_name_raw: str,
    quantity: int,
    product_id: str | None = None,
    entry_method: str = "manual",
    raw_prompt: str | None = None,
    contributor_key: str | None = "core_product_entry",
    contributor_data: dict | None = None,
    component_type: str = "complete",
    component_reason: str | None = None,
) -> OpsProductionLogEntry:
    entry = OpsProductionLogEntry(
        tenant_id=tenant_id,
        product_id=product_id,
        product_name_raw=product_name_raw,
        quantity=quantity,
        logged_by=user_id,
        entry_method=entry_method,
        raw_prompt=raw_prompt,
        contributor_key=contributor_key,
        contributor_data=contributor_data or {},
        component_type=component_type,
        component_reason=component_reason,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_today_entries(db: Session, tenant_id: str) -> list[dict]:
    today = date.today()
    entries = (
        db.query(OpsProductionLogEntry)
        .filter(
            OpsProductionLogEntry.tenant_id == tenant_id,
            func.date(OpsProductionLogEntry.logged_at) == today,
        )
        .order_by(OpsProductionLogEntry.logged_at.desc())
        .all()
    )
    user_ids = list({e.logged_by for e in entries})
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )
    return [
        {
            "id": e.id,
            "product_id": e.product_id,
            "product_name_raw": e.product_name_raw,
            "quantity": e.quantity,
            "logged_at": e.logged_at.isoformat() if e.logged_at else None,
            "logged_by_name": (
                f"{users[e.logged_by].first_name} {users[e.logged_by].last_name}"
                if e.logged_by in users
                else "Unknown"
            ),
            "qc_status": e.qc_status,
            "qc_notes": e.qc_notes,
            "entry_method": e.entry_method,
            "summary_id": e.summary_id,
            "contributor_key": e.contributor_key,
            "contributor_data": e.contributor_data,
        }
        for e in entries
    ]


def update_qc_status(
    db: Session,
    entry_id: str,
    tenant_id: str,
    user_id: str,
    qc_status: str,
    qc_notes: str | None = None,
) -> bool:
    entry = (
        db.query(OpsProductionLogEntry)
        .filter(
            OpsProductionLogEntry.id == entry_id,
            OpsProductionLogEntry.tenant_id == tenant_id,
        )
        .first()
    )
    if not entry:
        return False
    entry.qc_status = qc_status
    entry.qc_notes = qc_notes
    entry.qc_checked_by = user_id
    entry.qc_checked_at = datetime.now(timezone.utc)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Daily Production Summaries
# ---------------------------------------------------------------------------


def get_or_create_today_summary(db: Session, tenant_id: str) -> DailyProductionSummary:
    today = date.today()
    summary = (
        db.query(DailyProductionSummary)
        .filter(
            DailyProductionSummary.tenant_id == tenant_id,
            DailyProductionSummary.summary_date == today,
        )
        .first()
    )
    if not summary:
        summary = DailyProductionSummary(tenant_id=tenant_id, summary_date=today)
        db.add(summary)
        db.commit()
        db.refresh(summary)
    return summary


def submit_summary(
    db: Session,
    tenant_id: str,
    user_id: str,
    notes_for_tomorrow: str | None = None,
) -> DailyProductionSummary:
    summary = get_or_create_today_summary(db, tenant_id)
    if summary.status != "draft":
        return summary

    today = date.today()
    # Link all today's unlinked entries to this summary
    db.query(OpsProductionLogEntry).filter(
        OpsProductionLogEntry.tenant_id == tenant_id,
        OpsProductionLogEntry.summary_id.is_(None),
        func.date(OpsProductionLogEntry.logged_at) == today,
    ).update({"summary_id": summary.id})

    # Check for QC failures
    has_failures = (
        db.query(OpsProductionLogEntry)
        .filter(
            OpsProductionLogEntry.summary_id == summary.id,
            OpsProductionLogEntry.qc_status == "fail",
        )
        .count()
        > 0
    )

    summary.status = "submitted"
    summary.submitted_at = datetime.now(timezone.utc)
    summary.submitted_by = user_id
    summary.notes_for_tomorrow = notes_for_tomorrow
    summary.has_qc_failures = has_failures
    db.commit()
    db.refresh(summary)
    return summary


def post_summary_to_inventory(
    db: Session,
    summary_id: str,
    tenant_id: str,
    user_id: str,
) -> DailyProductionSummary | None:
    """Post a submitted production summary to inventory.

    Updates inventory_items for each entry:
    - complete: quantity_on_hand += quantity
    - cover: spare_covers += quantity
    - base: spare_bases += quantity
    Creates InventoryTransaction records and checks for pairable spare components.
    """
    from app.models.inventory_item import InventoryItem
    from app.models.inventory_transaction import InventoryTransaction

    summary = (
        db.query(DailyProductionSummary)
        .filter(
            DailyProductionSummary.id == summary_id,
            DailyProductionSummary.tenant_id == tenant_id,
        )
        .first()
    )
    if not summary or summary.status != "submitted":
        return None

    entries = (
        db.query(OpsProductionLogEntry)
        .filter(
            OpsProductionLogEntry.summary_id == summary_id,
            OpsProductionLogEntry.is_excluded_from_inventory.is_(False),
        )
        .all()
    )

    products_updated = set()
    for entry in entries:
        if not entry.product_id or entry.quantity <= 0:
            continue

        inv = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.company_id == tenant_id,
                InventoryItem.product_id == entry.product_id,
            )
            .first()
        )
        if not inv:
            inv = InventoryItem(company_id=tenant_id, product_id=entry.product_id, quantity_on_hand=0)
            db.add(inv)
            db.flush()

        component_type = getattr(entry, "component_type", "complete") or "complete"

        if component_type == "complete":
            inv.quantity_on_hand = (inv.quantity_on_hand or 0) + entry.quantity
            tx_type = "produce"
            tx_ref = f"Production summary {summary.summary_date}"
        elif component_type == "cover":
            inv.spare_covers = (inv.spare_covers or 0) + entry.quantity
            tx_type = "produce_component"
            tx_ref = f"Cover pour {summary.summary_date}"
        elif component_type == "base":
            inv.spare_bases = (inv.spare_bases or 0) + entry.quantity
            tx_type = "produce_component"
            tx_ref = f"Base pour {summary.summary_date}"
        else:
            inv.quantity_on_hand = (inv.quantity_on_hand or 0) + entry.quantity
            tx_type = "produce"
            tx_ref = f"Production summary {summary.summary_date}"

        inv.updated_at = datetime.now(timezone.utc)

        tx = InventoryTransaction(
            company_id=tenant_id,
            product_id=entry.product_id,
            transaction_type=tx_type,
            quantity_change=entry.quantity if component_type == "complete" else 0,
            quantity_after=inv.quantity_on_hand or 0,
            reference=tx_ref,
            notes=getattr(entry, "component_reason", None),
            created_by=user_id,
        )
        db.add(tx)
        products_updated.add(entry.product_id)

    summary.status = "posted_to_inventory"
    summary.posted_at = datetime.now(timezone.utc)
    summary.posted_by = user_id
    db.commit()

    # Check for pairable spare components and create alerts
    _check_spare_component_pairing(db, tenant_id, products_updated)

    db.refresh(summary)
    return summary


def _check_spare_component_pairing(
    db: Session, tenant_id: str, product_ids: set[str]
) -> None:
    """Create agent alerts when spare covers and bases can be paired."""
    from app.models.inventory_item import InventoryItem
    from app.models.product import Product

    for product_id in product_ids:
        inv = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.company_id == tenant_id,
                InventoryItem.product_id == product_id,
            )
            .first()
        )
        if not inv:
            continue
        covers = inv.spare_covers or 0
        bases = inv.spare_bases or 0
        if covers > 0 and bases > 0:
            pairs = min(covers, bases)
            product = db.query(Product).filter(Product.id == product_id).first()
            name = product.name if product else "Unknown"
            try:
                from app.models.agent_alert import AgentAlert
                import uuid

                alert = AgentAlert(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    alert_type="spare_component_pairing",
                    severity="info",
                    title=f"Spare components can be paired — {name}",
                    message=(
                        f"You have {covers} spare cover(s) and {bases} spare base(s) "
                        f"for {name}. {pairs} complete vault(s) can be assembled."
                    ),
                    action_label="Mark as assembled",
                    action_url="/inventory",
                )
                db.add(alert)
                db.commit()
            except Exception:
                logger.debug("Could not create spare pairing alert for %s", name)


def get_pending_summaries(db: Session, tenant_id: str) -> list[dict]:
    summaries = (
        db.query(DailyProductionSummary)
        .filter(
            DailyProductionSummary.tenant_id == tenant_id,
            DailyProductionSummary.status == "submitted",
        )
        .order_by(DailyProductionSummary.summary_date.desc())
        .all()
    )
    results = []
    for s in summaries:
        entries = (
            db.query(OpsProductionLogEntry)
            .filter(OpsProductionLogEntry.summary_id == s.id)
            .all()
        )
        submitter = (
            db.query(User).filter(User.id == s.submitted_by).first()
            if s.submitted_by
            else None
        )
        results.append(
            {
                "id": s.id,
                "summary_date": str(s.summary_date),
                "status": s.status,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "submitted_by_name": (
                    f"{submitter.first_name} {submitter.last_name}" if submitter else None
                ),
                "has_qc_failures": s.has_qc_failures,
                "notes_for_tomorrow": s.notes_for_tomorrow,
                "entries": [
                    {
                        "product_name_raw": e.product_name_raw,
                        "quantity": e.quantity,
                        "qc_status": e.qc_status,
                        "qc_notes": e.qc_notes,
                        "contributor_key": e.contributor_key,
                    }
                    for e in entries
                ],
            }
        )
    return results


# ---------------------------------------------------------------------------
# Announcement Replies
# ---------------------------------------------------------------------------


def reply_to_announcement(
    db: Session,
    tenant_id: str,
    announcement_id: str,
    employee_id: str,
    reply_type: str,
) -> AnnouncementReply:
    existing = (
        db.query(AnnouncementReply)
        .filter(
            AnnouncementReply.announcement_id == announcement_id,
            AnnouncementReply.employee_id == employee_id,
        )
        .first()
    )
    if existing:
        existing.previous_reply_type = existing.reply_type
        existing.reply_type = reply_type
        existing.replied_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    reply = AnnouncementReply(
        tenant_id=tenant_id,
        announcement_id=announcement_id,
        employee_id=employee_id,
        reply_type=reply_type,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


def get_announcement_replies(db: Session, announcement_id: str) -> list[dict]:
    replies = (
        db.query(AnnouncementReply)
        .filter(AnnouncementReply.announcement_id == announcement_id)
        .all()
    )
    user_ids = [r.employee_id for r in replies]
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )
    return [
        {
            "employee_id": r.employee_id,
            "employee_name": (
                f"{users[r.employee_id].first_name} {users[r.employee_id].last_name}"
                if r.employee_id in users
                else "Unknown"
            ),
            "reply_type": r.reply_type,
            "replied_at": r.replied_at.isoformat() if r.replied_at else None,
        }
        for r in replies
    ]
