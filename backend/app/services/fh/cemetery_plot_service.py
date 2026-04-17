"""Cemetery plot service — reservations, map data, expiry job."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.cemetery_plot import CemeteryMapConfig, CemeteryPlot
from app.models.funeral_case import (
    CaseCemetery,
    FuneralCase,
    FuneralCaseNote,
)


RESERVATION_HOURS = 48


def list_plots(
    db: Session,
    cemetery_company_id: str,
    status: str | None = None,
    plot_type: str | None = None,
    section: str | None = None,
) -> list[CemeteryPlot]:
    q = db.query(CemeteryPlot).filter(CemeteryPlot.company_id == cemetery_company_id, CemeteryPlot.is_active == True)  # noqa: E712
    if status:
        q = q.filter(CemeteryPlot.status == status)
    if plot_type:
        q = q.filter(CemeteryPlot.plot_type == plot_type)
    if section:
        q = q.filter(CemeteryPlot.section == section)
    return q.order_by(CemeteryPlot.section, CemeteryPlot.row, CemeteryPlot.number).all()


def get_map_data(db: Session, cemetery_company_id: str) -> dict:
    """Return config + plots for rendering the plot map."""
    config = db.query(CemeteryMapConfig).filter(CemeteryMapConfig.company_id == cemetery_company_id).first()
    plots = list_plots(db, cemetery_company_id)

    # Status counts for legend badges
    counts: dict[str, int] = {}
    for p in plots:
        counts[p.status] = counts.get(p.status, 0) + 1

    return {
        "config": {
            "map_image_url": config.map_image_url if config else None,
            "map_width_ft": config.map_width_ft if config else None,
            "map_height_ft": config.map_height_ft if config else None,
            "sections": config.sections if config else None,
            "legend": config.legend if config else None,
        } if config else None,
        "plots": [_serialize_plot(p) for p in plots],
        "counts": counts,
    }


def _serialize_plot(p: CemeteryPlot) -> dict:
    return {
        "id": p.id,
        "section": p.section,
        "row": p.row,
        "number": p.number,
        "plot_label": p.plot_label or f"{p.section or ''}-{p.row or ''}-{p.number or ''}".strip("-"),
        "plot_type": p.plot_type,
        "status": p.status,
        "map_x": p.map_x,
        "map_y": p.map_y,
        "map_width": p.map_width,
        "map_height": p.map_height,
        "price": float(p.price) if p.price else None,
        "opening_closing_fee": float(p.opening_closing_fee) if p.opening_closing_fee else None,
        "reserved_for_case_id": p.reserved_for_case_id,
        "reservation_expires_at": p.reservation_expires_at.isoformat() if p.reservation_expires_at else None,
    }


def reserve_plot(
    db: Session,
    plot_id: str,
    case_id: str,
    fh_company_id: str,
) -> dict:
    """Reserve a plot for a case. Optimistic lock — sets status=reserved,
    reservation_expires_at = now + 48h. Simulates payment in Phase 1."""
    plot = db.query(CemeteryPlot).filter(CemeteryPlot.id == plot_id).first()
    if not plot:
        raise ValueError("Plot not found")

    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    if plot.status == "sold":
        return {"status": "already_sold"}
    if plot.status == "reserved" and plot.reservation_expires_at and plot.reservation_expires_at > datetime.now(timezone.utc):
        return {"status": "already_reserved", "plot_id": plot.id}

    now = datetime.now(timezone.utc)
    plot.status = "reserved"
    plot.reserved_at = now
    plot.reserved_for_case_id = case_id
    plot.reserved_by_company_id = fh_company_id
    plot.reservation_expires_at = now + timedelta(hours=RESERVATION_HOURS)

    db.commit()
    return {
        "status": "reserved",
        "plot_id": plot.id,
        "expires_at": plot.reservation_expires_at.isoformat(),
    }


def complete_reservation_payment(
    db: Session,
    plot_id: str,
    case_id: str,
    fh_company_id: str,
) -> dict:
    """Phase 1: simulate payment and mark plot sold.

    Phase 2 will integrate a real payment processor.
    """
    plot = db.query(CemeteryPlot).filter(CemeteryPlot.id == plot_id).first()
    if not plot:
        raise ValueError("Plot not found")

    now = datetime.now(timezone.utc)
    transaction_id = f"demo_transaction_{uuid.uuid4().hex[:12]}"

    plot.status = "sold"
    plot.sold_at = now
    plot.transaction_id = transaction_id

    # Update case_cemetery
    cem = db.query(CaseCemetery).filter(CaseCemetery.case_id == case_id).first()
    if cem:
        cem.plot_id = plot.id
        cem.plot_reserved_at = now
        cem.plot_payment_status = "paid"
        cem.plot_payment_transaction_id = transaction_id
        cem.section = plot.section
        cem.row = plot.row
        cem.plot_number = plot.number

    # Notify cemetery tenant (cross-tenant note — creates an entry for them)
    # Phase 1 writes to funeral_case_notes on the FH side only.
    db.add(FuneralCaseNote(
        id=str(uuid.uuid4()),
        case_id=case_id,
        company_id=fh_company_id,
        note_type="system",
        content=f"Plot {plot.section}-{plot.row}-{plot.number} reserved and paid. Transaction {transaction_id}.",
    ))

    db.commit()
    return {
        "status": "sold",
        "plot_id": plot.id,
        "transaction_id": transaction_id,
    }


def release_expired_reservations(db: Session) -> int:
    """APScheduler job: release plots whose reservation expired without payment."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(CemeteryPlot)
        .filter(
            CemeteryPlot.status == "reserved",
            CemeteryPlot.reservation_expires_at < now,
            CemeteryPlot.sold_at.is_(None),
        )
        .all()
    )
    for p in expired:
        p.status = "available"
        p.reserved_at = None
        p.reserved_for_case_id = None
        p.reserved_by_company_id = None
        p.reservation_expires_at = None
    if expired:
        db.commit()
    return len(expired)
