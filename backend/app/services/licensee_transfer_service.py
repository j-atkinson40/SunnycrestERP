"""Licensee transfer service — create, accept, fulfill, invoice, passthrough."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.licensee_transfer import LicenseeTransfer, TransferNotification

logger = logging.getLogger(__name__)


def generate_transfer_number(db: Session, tenant_id: str) -> str:
    """Generate next transfer number atomically."""
    company = db.query(Company).filter(Company.id == tenant_id).with_for_update().first()
    if not company:
        return f"TRF-{uuid.uuid4().hex[:6].upper()}"

    settings = company.settings or {}
    prefix = settings.get("transfer_number_prefix", "TRF")
    next_num = settings.get("transfer_number_next", 1001)
    company.set_setting("transfer_number_next", next_num + 1)
    db.flush()
    return f"{prefix}-{next_num}"


def find_area_licensees(
    db: Session,
    cemetery_state: str,
    cemetery_county: str,
    cemetery_zip: str | None,
    requesting_tenant_id: str,
) -> list[dict]:
    """Find platform tenants whose service territory covers the cemetery location."""
    from app.models.service_territory import ManufacturerServiceTerritory

    query = (
        db.query(ManufacturerServiceTerritory)
        .filter(
            ManufacturerServiceTerritory.state == cemetery_state.upper(),
            func.lower(ManufacturerServiceTerritory.county) == cemetery_county.lower(),
            ManufacturerServiceTerritory.tenant_id != requesting_tenant_id,
        )
    )
    territories = query.all()

    tenant_ids = list({t.tenant_id for t in territories})
    if not tenant_ids:
        return []

    tenants = db.query(Company).filter(Company.id.in_(tenant_ids), Company.is_active.is_(True)).all()
    results = []
    for t in tenants:
        covered = [terr.county for terr in territories if terr.tenant_id == t.id]
        results.append({
            "tenant_id": t.id,
            "company_name": t.company_name,
            "city": getattr(t, "city", None),
            "state": getattr(t, "state", None),
            "counties_covered": covered,
            "on_platform": True,
        })
    return results


def check_cemetery_in_territory(
    db: Session, tenant_id: str, state: str, county: str,
) -> bool:
    """Check if a cemetery is within the tenant's service territory."""
    from app.models.service_territory import ManufacturerServiceTerritory

    count = (
        db.query(ManufacturerServiceTerritory)
        .filter(
            ManufacturerServiceTerritory.tenant_id == tenant_id,
            ManufacturerServiceTerritory.state == state.upper(),
            func.lower(ManufacturerServiceTerritory.county) == county.lower(),
        )
        .count()
    )
    return count > 0


def create_transfer(
    db: Session,
    home_tenant_id: str,
    data: dict,
    user_id: str,
) -> LicenseeTransfer:
    """Create a new licensee transfer."""
    transfer_number = generate_transfer_number(db, home_tenant_id)

    transfer = LicenseeTransfer(
        id=str(uuid.uuid4()),
        transfer_number=transfer_number,
        home_tenant_id=home_tenant_id,
        area_tenant_id=data.get("area_tenant_id"),
        area_licensee_name=data.get("area_licensee_name"),
        area_licensee_contact=data.get("area_licensee_contact"),
        is_platform_transfer=data.get("is_platform_transfer", True),
        status="pending" if data.get("is_platform_transfer", True) else "manual_coordination",
        source_order_id=data.get("source_order_id"),
        funeral_home_customer_id=data.get("funeral_home_customer_id"),
        funeral_home_name=data.get("funeral_home_name"),
        deceased_name=data.get("deceased_name"),
        service_date=data.get("service_date"),
        cemetery_name=data.get("cemetery_name"),
        cemetery_address=data.get("cemetery_address"),
        cemetery_city=data.get("cemetery_city"),
        cemetery_state=data.get("cemetery_state"),
        cemetery_county=data.get("cemetery_county"),
        cemetery_zip=data.get("cemetery_zip"),
        cemetery_place_id=data.get("cemetery_place_id"),
        transfer_items=data.get("transfer_items", []),
        special_instructions=data.get("special_instructions"),
        created_by=user_id,
    )
    db.add(transfer)

    # Create notification for area licensee if platform transfer
    if transfer.is_platform_transfer and transfer.area_tenant_id:
        notif = TransferNotification(
            id=str(uuid.uuid4()),
            transfer_id=transfer.id,
            recipient_tenant_id=transfer.area_tenant_id,
            notification_type="transfer_request",
        )
        db.add(notif)

        # Create agent alert
        _create_transfer_alert(
            db, transfer.area_tenant_id,
            "transfer_request_received",
            f"Transfer request from {data.get('home_licensee_name', 'a partner')}",
            f"{transfer.funeral_home_name or 'A funeral home'} has a burial at "
            f"{transfer.cemetery_name or transfer.cemetery_city}, {transfer.cemetery_state} "
            f"on {transfer.service_date}. Fulfillment requested.",
            "Review Request",
            f"/transfers/{transfer.id}",
        )

    db.commit()
    db.refresh(transfer)
    return transfer


def accept_transfer(db: Session, transfer_id: str, area_user_id: str) -> LicenseeTransfer | None:
    """Area licensee accepts a transfer."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer or transfer.status != "pending":
        return None

    transfer.status = "accepted"
    transfer.accepted_at = datetime.now(timezone.utc)

    # Notify home licensee
    notif = TransferNotification(
        id=str(uuid.uuid4()),
        transfer_id=transfer.id,
        recipient_tenant_id=transfer.home_tenant_id,
        notification_type="transfer_accepted",
    )
    db.add(notif)

    _create_transfer_alert(
        db, transfer.home_tenant_id,
        "transfer_accepted",
        f"{transfer.area_licensee_name} accepted transfer {transfer.transfer_number}",
        f"Transfer for {transfer.funeral_home_name} at {transfer.cemetery_name} has been accepted.",
        "View Transfer",
        f"/transfers/{transfer.id}",
        severity="info",
    )

    db.commit()
    db.refresh(transfer)
    return transfer


def decline_transfer(db: Session, transfer_id: str, area_user_id: str, reason: str) -> LicenseeTransfer | None:
    """Area licensee declines a transfer."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer or transfer.status != "pending":
        return None

    transfer.status = "declined"
    transfer.decline_reason = reason

    _create_transfer_alert(
        db, transfer.home_tenant_id,
        "transfer_declined",
        f"Transfer {transfer.transfer_number} declined",
        f"{transfer.area_licensee_name} declined. Reason: {reason}",
        "Find Another Licensee",
        f"/transfers/{transfer.id}",
        severity="action_required",
    )

    db.commit()
    db.refresh(transfer)
    return transfer


def fulfill_transfer(db: Session, transfer_id: str, area_user_id: str) -> LicenseeTransfer | None:
    """Mark transfer as fulfilled."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer or transfer.status not in ("accepted", "in_progress"):
        return None

    transfer.status = "fulfilled"
    transfer.fulfilled_at = datetime.now(timezone.utc)

    _create_transfer_alert(
        db, transfer.home_tenant_id,
        "transfer_fulfilled",
        f"Transfer {transfer.transfer_number} fulfilled",
        f"{transfer.area_licensee_name} completed the burial at {transfer.cemetery_name}.",
        "View Transfer",
        f"/transfers/{transfer.id}",
        severity="info",
    )

    db.commit()
    db.refresh(transfer)
    return transfer


def record_off_platform_cost(
    db: Session, transfer_id: str, amount: float, reference: str | None, notes: str | None,
) -> LicenseeTransfer | None:
    """Record cost received from off-platform licensee."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer:
        return None

    transfer.area_charge_amount = Decimal(str(amount))
    transfer.status = "invoiced"
    db.commit()
    db.refresh(transfer)
    return transfer


def create_passthrough(
    db: Session, transfer_id: str, markup_percentage: float, user_id: str,
) -> dict:
    """Calculate and record passthrough invoice amount."""
    transfer = db.query(LicenseeTransfer).filter(LicenseeTransfer.id == transfer_id).first()
    if not transfer or not transfer.area_charge_amount:
        return {"error": "Transfer not found or no charge amount"}

    markup = Decimal(str(markup_percentage))
    charge = transfer.area_charge_amount
    passthrough = (charge * (Decimal("1") + markup / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    transfer.markup_percentage = markup
    transfer.passthrough_amount = passthrough
    transfer.status = "billed_through"
    db.commit()

    return {
        "area_charge": float(charge),
        "markup_percentage": float(markup),
        "passthrough_amount": float(passthrough),
        "margin": float(passthrough - charge),
    }


def get_transfers(
    db: Session, tenant_id: str, direction: str = "all", status: str | None = None,
) -> list[dict]:
    """Get transfers for a tenant."""
    query = db.query(LicenseeTransfer)

    if direction == "outgoing":
        query = query.filter(LicenseeTransfer.home_tenant_id == tenant_id)
    elif direction == "incoming":
        query = query.filter(LicenseeTransfer.area_tenant_id == tenant_id)
    else:
        query = query.filter(
            (LicenseeTransfer.home_tenant_id == tenant_id)
            | (LicenseeTransfer.area_tenant_id == tenant_id)
        )

    if status:
        query = query.filter(LicenseeTransfer.status == status)

    transfers = query.order_by(LicenseeTransfer.created_at.desc()).all()

    return [
        {
            "id": t.id,
            "transfer_number": t.transfer_number,
            "status": t.status,
            "is_platform_transfer": t.is_platform_transfer,
            "home_tenant_id": t.home_tenant_id,
            "area_tenant_id": t.area_tenant_id,
            "area_licensee_name": t.area_licensee_name,
            "funeral_home_name": t.funeral_home_name,
            "deceased_name": t.deceased_name,
            "service_date": str(t.service_date) if t.service_date else None,
            "cemetery_name": t.cemetery_name,
            "cemetery_city": t.cemetery_city,
            "cemetery_state": t.cemetery_state,
            "cemetery_county": t.cemetery_county,
            "transfer_items": t.transfer_items,
            "special_instructions": t.special_instructions,
            "area_charge_amount": float(t.area_charge_amount) if t.area_charge_amount else None,
            "markup_percentage": float(t.markup_percentage) if t.markup_percentage else 0,
            "passthrough_amount": float(t.passthrough_amount) if t.passthrough_amount else None,
            "requested_at": t.requested_at.isoformat() if t.requested_at else None,
            "accepted_at": t.accepted_at.isoformat() if t.accepted_at else None,
            "fulfilled_at": t.fulfilled_at.isoformat() if t.fulfilled_at else None,
            "direction": "outgoing" if t.home_tenant_id == tenant_id else "incoming",
        }
        for t in transfers
    ]


def _create_transfer_alert(
    db: Session, tenant_id: str, alert_type: str, title: str, message: str,
    action_label: str, action_url: str, severity: str = "action_required",
) -> None:
    """Create an agent alert for transfer events."""
    try:
        from app.models.agent import AgentAlert
        alert = AgentAlert(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            action_label=action_label,
            action_url=action_url,
        )
        db.add(alert)
    except Exception as e:
        logger.warning(f"Could not create transfer alert: {e}")
