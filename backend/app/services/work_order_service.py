"""Work order and production management service."""

import uuid
from datetime import UTC, datetime, date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.models.work_order import WorkOrder
from app.models.pour_event import PourEvent, PourEventWorkOrder
from app.models.batch_ticket import BatchTicket
from app.models.mix_design import MixDesign
from app.models.cure_schedule import CureSchedule
from app.models.work_order_product import WorkOrderProduct
from app.models.stock_replenishment_rule import StockReplenishmentRule

# ---------------------------------------------------------------------------
# Status transition maps
# ---------------------------------------------------------------------------

WO_TRANSITIONS = {
    "draft": {"open"},
    "open": {"in_progress", "cancelled"},
    "in_progress": {"poured", "cancelled"},
    "poured": {"curing"},
    "curing": {"qc_pending"},
    "qc_pending": {"completed"},
}

PE_TRANSITIONS = {
    "planned": {"in_progress"},
    "in_progress": {"poured"},
    "poured": {"curing"},
    "curing": {"released"},
}


def _validate_wo_transition(current: str, target: str) -> None:
    allowed = WO_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid work order status transition: {current} -> {target}",
        )


def _validate_pe_transition(current: str, target: str) -> None:
    allowed = PE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pour event status transition: {current} -> {target}",
        )


# ---------------------------------------------------------------------------
# Work Orders
# ---------------------------------------------------------------------------


def list_work_orders(
    db: Session,
    company_id: str,
    status: str | None = None,
    trigger_type: str | None = None,
    product_id: str | None = None,
    priority: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Return paginated list of work orders with optional filters."""
    query = db.query(WorkOrder).filter(WorkOrder.company_id == company_id)

    if status:
        query = query.filter(WorkOrder.status == status)
    if trigger_type:
        query = query.filter(WorkOrder.trigger_type == trigger_type)
    if product_id:
        query = query.filter(WorkOrder.product_id == product_id)
    if priority:
        query = query.filter(WorkOrder.priority == priority)

    total = query.count()
    items = (
        query.order_by(WorkOrder.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_work_order(db: Session, company_id: str, wo_id: str) -> WorkOrder:
    """Get a single work order with all details."""
    wo = (
        db.query(WorkOrder)
        .filter(WorkOrder.id == wo_id, WorkOrder.company_id == company_id)
        .first()
    )
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    return wo


def _next_wo_number(db: Session, company_id: str) -> str:
    """Generate next WO-{year}-{seq:04d} number."""
    year = datetime.now(UTC).year
    prefix = f"WO-{year}-"
    count = (
        db.query(sa_func.count(WorkOrder.id))
        .filter(
            WorkOrder.company_id == company_id,
            WorkOrder.work_order_number.like(f"{prefix}%"),
        )
        .scalar()
    )
    return f"{prefix}{(count or 0) + 1:04d}"


def create_work_order(
    db: Session, company_id: str, data: dict, actor_id: str
) -> WorkOrder:
    """Create a new work order."""
    wo = WorkOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        work_order_number=_next_wo_number(db, company_id),
        trigger_type=data.get("trigger_type", "manual"),
        product_id=data["product_id"],
        product_variant_id=data.get("product_variant_id"),
        quantity_ordered=data["quantity_ordered"],
        needed_by_date=data.get("needed_by_date"),
        priority=data.get("priority", "standard"),
        status="draft",
        notes=data.get("notes"),
        created_by=actor_id,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def create_from_sales_order(
    db: Session,
    company_id: str,
    order_id: str,
    line_id: str,
    product_id: str,
    quantity: int,
    needed_by_date: date,
    actor_id: str,
) -> WorkOrder:
    """Create a WO triggered by a sales order. needed_by_date = delivery - 3 days."""
    adjusted_date = needed_by_date - timedelta(days=3)
    wo = WorkOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        work_order_number=_next_wo_number(db, company_id),
        trigger_type="sales_order",
        source_order_id=order_id,
        source_order_line_id=line_id,
        product_id=product_id,
        quantity_ordered=quantity,
        needed_by_date=adjusted_date,
        priority="standard",
        status="draft",
        created_by=actor_id,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def release_to_production(db: Session, company_id: str, wo_id: str) -> WorkOrder:
    """Transition a work order from draft to open."""
    wo = get_work_order(db, company_id, wo_id)
    _validate_wo_transition(wo.status, "open")
    wo.status = "open"
    wo.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(wo)
    return wo


def cancel_work_order(
    db: Session, company_id: str, wo_id: str, reason: str, actor_id: str
) -> WorkOrder:
    """Cancel a work order. Only allowed if quantity_produced == 0."""
    wo = get_work_order(db, company_id, wo_id)
    if wo.quantity_produced and wo.quantity_produced > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel a work order that has produced units",
        )
    # Allow cancellation from draft, open, or in_progress
    if wo.status not in ("draft", "open", "in_progress"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel a work order in status '{wo.status}'",
        )
    wo.status = "cancelled"
    wo.cancelled_at = datetime.now(UTC)
    wo.cancelled_by = actor_id
    wo.cancellation_reason = reason
    wo.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(wo)
    return wo


def update_priority(
    db: Session, company_id: str, wo_id: str, priority: str
) -> WorkOrder:
    """Update the priority of a work order."""
    wo = get_work_order(db, company_id, wo_id)
    wo.priority = priority
    wo.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(wo)
    return wo


def get_production_board(db: Session, company_id: str) -> dict:
    """
    Return all active WOs grouped by status for the production board.

    Includes calculated fields: days_until_needed, cure_progress_percent.
    """
    active_statuses = ["open", "in_progress", "poured", "curing", "qc_pending"]
    wos = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.company_id == company_id,
            WorkOrder.status.in_(active_statuses),
        )
        .order_by(WorkOrder.priority.desc(), WorkOrder.needed_by_date.asc())
        .all()
    )

    today = date.today()
    board: dict[str, list] = {s: [] for s in active_statuses}

    for wo in wos:
        wo_dict = _wo_to_dict(wo)
        # days_until_needed
        if wo.needed_by_date:
            wo_dict["days_until_needed"] = (wo.needed_by_date - today).days
        else:
            wo_dict["days_until_needed"] = None
        # cure_progress_percent (if curing, look up via pour events)
        wo_dict["cure_progress_percent"] = None
        if wo.status == "curing":
            wo_dict["cure_progress_percent"] = _calc_cure_progress_for_wo(db, wo.id)
        board.setdefault(wo.status, []).append(wo_dict)

    return board


def _calc_cure_progress_for_wo(db: Session, wo_id: str) -> float | None:
    """Calculate cure progress % for a WO by looking at its pour events."""
    links = (
        db.query(PourEventWorkOrder)
        .filter(PourEventWorkOrder.work_order_id == wo_id)
        .all()
    )
    if not links:
        return None
    # Use the latest pour event linked
    pe_ids = [lnk.pour_event_id for lnk in links]
    pe = (
        db.query(PourEvent)
        .filter(PourEvent.id.in_(pe_ids), PourEvent.status == "curing")
        .order_by(PourEvent.cure_start_at.desc())
        .first()
    )
    if not pe or not pe.cure_start_at or not pe.cure_complete_at:
        return None
    return _calc_cure_percent(pe)


def _calc_cure_percent(pe: PourEvent) -> float:
    """Calculate cure progress as a percentage."""
    if not pe.cure_start_at or not pe.cure_complete_at:
        return 0.0
    now = datetime.now(UTC)
    total = (pe.cure_complete_at - pe.cure_start_at).total_seconds()
    if total <= 0:
        return 100.0
    elapsed = (now - pe.cure_start_at).total_seconds()
    pct = min(100.0, max(0.0, (elapsed / total) * 100.0))
    return round(pct, 1)


def _wo_to_dict(wo: WorkOrder) -> dict:
    """Convert a WorkOrder ORM to a serializable dict."""
    return {
        "id": wo.id,
        "company_id": wo.company_id,
        "work_order_number": wo.work_order_number,
        "trigger_type": wo.trigger_type,
        "source_order_id": wo.source_order_id,
        "source_order_line_id": wo.source_order_line_id,
        "product_id": wo.product_id,
        "product_variant_id": wo.product_variant_id,
        "quantity_ordered": wo.quantity_ordered,
        "quantity_produced": wo.quantity_produced,
        "quantity_passed_qc": wo.quantity_passed_qc,
        "needed_by_date": str(wo.needed_by_date) if wo.needed_by_date else None,
        "priority": wo.priority,
        "status": wo.status,
        "notes": wo.notes,
        "created_by": wo.created_by,
        "created_at": wo.created_at.isoformat() if wo.created_at else None,
        "updated_at": wo.updated_at.isoformat() if wo.updated_at else None,
        "completed_at": wo.completed_at.isoformat() if wo.completed_at else None,
        "cancelled_at": wo.cancelled_at.isoformat() if wo.cancelled_at else None,
        "cancelled_by": wo.cancelled_by,
        "cancellation_reason": wo.cancellation_reason,
    }


# ---------------------------------------------------------------------------
# Pour Events
# ---------------------------------------------------------------------------


def list_pour_events(
    db: Session,
    company_id: str,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Return paginated list of pour events."""
    query = db.query(PourEvent).filter(PourEvent.company_id == company_id)
    if status:
        query = query.filter(PourEvent.status == status)

    total = query.count()
    items = (
        query.order_by(PourEvent.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_pour_event(db: Session, company_id: str, pe_id: str) -> dict:
    """Get a single pour event with linked WOs and batch ticket."""
    pe = (
        db.query(PourEvent)
        .filter(PourEvent.id == pe_id, PourEvent.company_id == company_id)
        .first()
    )
    if not pe:
        raise HTTPException(status_code=404, detail="Pour event not found")

    # Linked work orders
    links = (
        db.query(PourEventWorkOrder)
        .filter(PourEventWorkOrder.pour_event_id == pe_id)
        .all()
    )
    linked_wos = []
    for lnk in links:
        wo = db.query(WorkOrder).filter(WorkOrder.id == lnk.work_order_id).first()
        if wo:
            linked_wos.append(
                {
                    "work_order_id": wo.id,
                    "work_order_number": wo.work_order_number,
                    "quantity_in_this_pour": lnk.quantity_in_this_pour,
                    "product_id": wo.product_id,
                    "status": wo.status,
                }
            )

    # Batch ticket
    batch_ticket = None
    if pe.batch_ticket_id:
        bt = db.query(BatchTicket).filter(BatchTicket.id == pe.batch_ticket_id).first()
        if bt:
            batch_ticket = {
                "id": bt.id,
                "mix_design_id": bt.mix_design_id,
                "design_strength_psi": bt.design_strength_psi,
                "water_cement_ratio": float(bt.water_cement_ratio) if bt.water_cement_ratio else None,
                "slump_inches": float(bt.slump_inches) if bt.slump_inches else None,
                "air_content_percent": float(bt.air_content_percent) if bt.air_content_percent else None,
                "ambient_temp_f": bt.ambient_temp_f,
                "concrete_temp_f": bt.concrete_temp_f,
                "yield_cubic_yards": float(bt.yield_cubic_yards) if bt.yield_cubic_yards else None,
                "notes": bt.notes,
            }

    result = _pe_to_dict(pe)
    result["work_orders"] = linked_wos
    result["batch_ticket"] = batch_ticket
    return result


def _next_pe_number(db: Session, company_id: str) -> str:
    """Generate next PE-{year}-{seq:04d} number."""
    year = datetime.now(UTC).year
    prefix = f"PE-{year}-"
    count = (
        db.query(sa_func.count(PourEvent.id))
        .filter(
            PourEvent.company_id == company_id,
            PourEvent.pour_event_number.like(f"{prefix}%"),
        )
        .scalar()
    )
    return f"{prefix}{(count or 0) + 1:04d}"


def create_pour_event(
    db: Session,
    company_id: str,
    data: dict,
    work_order_items: list[dict],
    actor_id: str,
) -> dict:
    """
    Create a pour event and link it to work orders.

    work_order_items: [{work_order_id, quantity_in_this_pour}]
    Also generates WorkOrderProduct records with serial numbers and
    transitions linked WOs to in_progress.
    """
    pe_id = str(uuid.uuid4())
    pe = PourEvent(
        id=pe_id,
        company_id=company_id,
        pour_event_number=_next_pe_number(db, company_id),
        pour_date=data["pour_date"],
        pour_time=data.get("pour_time"),
        crew_notes=data.get("crew_notes"),
        cure_schedule_id=data.get("cure_schedule_id"),
        status="planned",
        created_by=actor_id,
    )
    db.add(pe)

    # Link work orders and generate serial-numbered products
    for item in work_order_items:
        wo = get_work_order(db, company_id, item["work_order_id"])

        # Create link record
        link = PourEventWorkOrder(
            id=str(uuid.uuid4()),
            company_id=company_id,
            pour_event_id=pe_id,
            work_order_id=wo.id,
            quantity_in_this_pour=item["quantity_in_this_pour"],
        )
        db.add(link)

        # Generate work_order_products with serial numbers
        for seq in range(1, item["quantity_in_this_pour"] + 1):
            serial = f"{wo.work_order_number}-{seq:03d}"
            wop = WorkOrderProduct(
                id=str(uuid.uuid4()),
                company_id=company_id,
                work_order_id=wo.id,
                pour_event_id=pe_id,
                serial_number=serial,
                product_id=wo.product_id,
                product_variant_id=wo.product_variant_id,
                status="produced",
            )
            db.add(wop)

        # Update WO quantity_produced
        wo.quantity_produced = (wo.quantity_produced or 0) + item["quantity_in_this_pour"]

        # Transition WO to in_progress if currently open
        if wo.status == "open":
            wo.status = "in_progress"
            wo.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(pe)
    return get_pour_event(db, company_id, pe_id)


def start_pour(db: Session, company_id: str, pe_id: str) -> PourEvent:
    """Transition a pour event from planned to in_progress."""
    pe = _get_pe(db, company_id, pe_id)
    _validate_pe_transition(pe.status, "in_progress")
    pe.status = "in_progress"
    pe.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(pe)
    return pe


def complete_pour(
    db: Session, company_id: str, pe_id: str, batch_data: dict
) -> dict:
    """
    Complete a pour: create BatchTicket, transition PE to curing,
    set cure times, transition linked WOs to curing.
    """
    pe = _get_pe(db, company_id, pe_id)
    _validate_pe_transition(pe.status, "poured")

    # Create batch ticket
    bt = BatchTicket(
        id=str(uuid.uuid4()),
        company_id=company_id,
        pour_event_id=pe_id,
        mix_design_id=batch_data.get("mix_design_id"),
        design_strength_psi=batch_data.get("design_strength_psi"),
        water_cement_ratio=batch_data.get("water_cement_ratio"),
        slump_inches=batch_data.get("slump_inches"),
        air_content_percent=batch_data.get("air_content_percent"),
        ambient_temp_f=batch_data.get("ambient_temp_f"),
        concrete_temp_f=batch_data.get("concrete_temp_f"),
        yield_cubic_yards=batch_data.get("yield_cubic_yards"),
        notes=batch_data.get("notes"),
    )
    db.add(bt)
    db.flush()

    # Update pour event
    pe.batch_ticket_id = bt.id
    pe.status = "curing"
    now = datetime.now(UTC)
    pe.cure_start_at = now
    pe.updated_at = now

    # Calculate cure_complete_at from cure schedule
    if pe.cure_schedule_id:
        schedule = (
            db.query(CureSchedule)
            .filter(CureSchedule.id == pe.cure_schedule_id)
            .first()
        )
        if schedule:
            pe.cure_complete_at = now + timedelta(hours=schedule.duration_hours)
    else:
        # Fallback: use company default or 24 hours
        default_schedule = (
            db.query(CureSchedule)
            .filter(
                CureSchedule.company_id == company_id,
                CureSchedule.is_default.is_(True),
            )
            .first()
        )
        if default_schedule:
            pe.cure_complete_at = now + timedelta(hours=default_schedule.duration_hours)
        else:
            pe.cure_complete_at = now + timedelta(hours=24)

    # Transition linked WOs to curing
    links = (
        db.query(PourEventWorkOrder)
        .filter(PourEventWorkOrder.pour_event_id == pe_id)
        .all()
    )
    for lnk in links:
        wo = db.query(WorkOrder).filter(WorkOrder.id == lnk.work_order_id).first()
        if wo and wo.status == "in_progress":
            wo.status = "poured"
            wo.updated_at = now
        # Also move poured -> curing
        if wo and wo.status == "poured":
            wo.status = "curing"
            wo.updated_at = now

    db.commit()
    db.refresh(pe)
    return get_pour_event(db, company_id, pe_id)


def release_from_cure(
    db: Session,
    company_id: str,
    pe_id: str,
    override_reason: str | None = None,
) -> dict:
    """
    Release a pour event from curing. If before cure_complete_at,
    override_reason is required.
    """
    pe = _get_pe(db, company_id, pe_id)
    _validate_pe_transition(pe.status, "released")

    now = datetime.now(UTC)
    if pe.cure_complete_at and now < pe.cure_complete_at:
        if not override_reason:
            raise HTTPException(
                status_code=400,
                detail="Override reason is required when releasing before cure completion",
            )

    pe.status = "released"
    pe.actual_release_at = now
    pe.updated_at = now

    # Transition linked WOs to qc_pending
    links = (
        db.query(PourEventWorkOrder)
        .filter(PourEventWorkOrder.pour_event_id == pe_id)
        .all()
    )
    for lnk in links:
        wo = db.query(WorkOrder).filter(WorkOrder.id == lnk.work_order_id).first()
        if wo and wo.status == "curing":
            wo.status = "qc_pending"
            wo.updated_at = now

    db.commit()
    db.refresh(pe)
    return get_pour_event(db, company_id, pe_id)


def get_cure_board(db: Session, company_id: str) -> list[dict]:
    """All curing PEs sorted by cure_complete_at ASC with progress and time remaining."""
    pes = (
        db.query(PourEvent)
        .filter(
            PourEvent.company_id == company_id,
            PourEvent.status == "curing",
        )
        .order_by(PourEvent.cure_complete_at.asc())
        .all()
    )

    now = datetime.now(UTC)
    result = []
    for pe in pes:
        d = _pe_to_dict(pe)
        d["cure_progress_percent"] = _calc_cure_percent(pe)
        if pe.cure_complete_at:
            remaining = (pe.cure_complete_at - now).total_seconds()
            d["hours_remaining"] = round(max(0, remaining) / 3600, 1)
        else:
            d["hours_remaining"] = None
        result.append(d)
    return result


def _get_pe(db: Session, company_id: str, pe_id: str) -> PourEvent:
    pe = (
        db.query(PourEvent)
        .filter(PourEvent.id == pe_id, PourEvent.company_id == company_id)
        .first()
    )
    if not pe:
        raise HTTPException(status_code=404, detail="Pour event not found")
    return pe


def _pe_to_dict(pe: PourEvent) -> dict:
    return {
        "id": pe.id,
        "company_id": pe.company_id,
        "pour_event_number": pe.pour_event_number,
        "pour_date": str(pe.pour_date) if pe.pour_date else None,
        "pour_time": pe.pour_time,
        "crew_notes": pe.crew_notes,
        "status": pe.status,
        "batch_ticket_id": pe.batch_ticket_id,
        "cure_schedule_id": pe.cure_schedule_id,
        "cure_start_at": pe.cure_start_at.isoformat() if pe.cure_start_at else None,
        "cure_complete_at": pe.cure_complete_at.isoformat() if pe.cure_complete_at else None,
        "actual_release_at": pe.actual_release_at.isoformat() if pe.actual_release_at else None,
        "created_by": pe.created_by,
        "created_at": pe.created_at.isoformat() if pe.created_at else None,
        "updated_at": pe.updated_at.isoformat() if pe.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Inventory Receiving (WorkOrderProduct)
# ---------------------------------------------------------------------------


def list_wo_products(
    db: Session, company_id: str, wo_id: str
) -> list[WorkOrderProduct]:
    """List all units produced for a work order."""
    return (
        db.query(WorkOrderProduct)
        .filter(
            WorkOrderProduct.company_id == company_id,
            WorkOrderProduct.work_order_id == wo_id,
        )
        .order_by(WorkOrderProduct.serial_number.asc())
        .all()
    )


def receive_unit(
    db: Session,
    company_id: str,
    product_id: str,
    location: str,
    actor_id: str,
) -> WorkOrderProduct:
    """
    Receive a single unit to inventory.

    Validates QC passed (qc_inspection_id is not None), marks in_inventory,
    updates WO quantity_passed_qc, auto-completes WO if all units received.
    """
    wop = (
        db.query(WorkOrderProduct)
        .filter(
            WorkOrderProduct.id == product_id,
            WorkOrderProduct.company_id == company_id,
        )
        .first()
    )
    if not wop:
        raise HTTPException(status_code=404, detail="Work order product not found")

    if wop.status == "in_inventory":
        raise HTTPException(status_code=400, detail="Unit already received to inventory")

    # Validate QC passed
    if not wop.qc_inspection_id:
        raise HTTPException(
            status_code=400,
            detail="Unit must pass QC inspection before receiving to inventory",
        )

    # Check the linked QC inspection status
    from app.models.qc import QCInspection

    inspection = (
        db.query(QCInspection)
        .filter(QCInspection.id == wop.qc_inspection_id)
        .first()
    )
    if not inspection or inspection.status != "passed":
        raise HTTPException(
            status_code=400,
            detail="QC inspection has not passed",
        )

    now = datetime.now(UTC)
    wop.status = "in_inventory"
    wop.received_to_inventory_at = now
    wop.received_by = actor_id
    wop.inventory_location = location
    wop.updated_at = now

    # Update WO quantity_passed_qc
    wo = db.query(WorkOrder).filter(WorkOrder.id == wop.work_order_id).first()
    if wo:
        wo.quantity_passed_qc = (wo.quantity_passed_qc or 0) + 1
        wo.updated_at = now
        # Auto-complete WO if all units received
        if wo.quantity_passed_qc >= wo.quantity_ordered:
            wo.status = "completed"
            wo.completed_at = now

    db.commit()
    db.refresh(wop)
    return wop


def bulk_receive(
    db: Session, company_id: str, wo_id: str, location: str, actor_id: str
) -> list[WorkOrderProduct]:
    """Receive all QC-passed units for a work order at once."""
    from app.models.qc import QCInspection

    products = (
        db.query(WorkOrderProduct)
        .filter(
            WorkOrderProduct.company_id == company_id,
            WorkOrderProduct.work_order_id == wo_id,
            WorkOrderProduct.status != "in_inventory",
            WorkOrderProduct.qc_inspection_id.isnot(None),
        )
        .all()
    )

    received = []
    now = datetime.now(UTC)
    for wop in products:
        # Verify QC inspection passed
        inspection = (
            db.query(QCInspection)
            .filter(QCInspection.id == wop.qc_inspection_id)
            .first()
        )
        if not inspection or inspection.status != "passed":
            continue

        wop.status = "in_inventory"
        wop.received_to_inventory_at = now
        wop.received_by = actor_id
        wop.inventory_location = location
        wop.updated_at = now
        received.append(wop)

    # Update WO
    if received:
        wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
        if wo:
            wo.quantity_passed_qc = (wo.quantity_passed_qc or 0) + len(received)
            wo.updated_at = now
            if wo.quantity_passed_qc >= wo.quantity_ordered:
                wo.status = "completed"
                wo.completed_at = now

    db.commit()
    return received


# ---------------------------------------------------------------------------
# Mix Designs CRUD
# ---------------------------------------------------------------------------


def list_mix_designs(db: Session, company_id: str) -> list[MixDesign]:
    return (
        db.query(MixDesign)
        .filter(MixDesign.company_id == company_id)
        .order_by(MixDesign.mix_design_code.asc())
        .all()
    )


def get_mix_design(db: Session, company_id: str, md_id: str) -> MixDesign:
    md = (
        db.query(MixDesign)
        .filter(MixDesign.id == md_id, MixDesign.company_id == company_id)
        .first()
    )
    if not md:
        raise HTTPException(status_code=404, detail="Mix design not found")
    return md


def create_mix_design(db: Session, company_id: str, data: dict) -> MixDesign:
    md = MixDesign(
        id=str(uuid.uuid4()),
        company_id=company_id,
        mix_design_code=data["mix_design_code"],
        name=data["name"],
        design_strength_psi=data["design_strength_psi"],
        cement_type=data.get("cement_type"),
        description=data.get("description"),
        npca_approved=data.get("npca_approved", False),
        cure_schedule_id=data.get("cure_schedule_id"),
    )
    db.add(md)
    db.commit()
    db.refresh(md)
    return md


def update_mix_design(
    db: Session, company_id: str, md_id: str, data: dict
) -> MixDesign:
    md = get_mix_design(db, company_id, md_id)
    for key in (
        "mix_design_code",
        "name",
        "design_strength_psi",
        "cement_type",
        "description",
        "npca_approved",
        "cure_schedule_id",
        "is_active",
    ):
        if key in data:
            setattr(md, key, data[key])
    md.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(md)
    return md


# ---------------------------------------------------------------------------
# Cure Schedules CRUD
# ---------------------------------------------------------------------------


def list_cure_schedules(db: Session, company_id: str) -> list[CureSchedule]:
    return (
        db.query(CureSchedule)
        .filter(CureSchedule.company_id == company_id)
        .order_by(CureSchedule.name.asc())
        .all()
    )


def get_cure_schedule(db: Session, company_id: str, cs_id: str) -> CureSchedule:
    cs = (
        db.query(CureSchedule)
        .filter(CureSchedule.id == cs_id, CureSchedule.company_id == company_id)
        .first()
    )
    if not cs:
        raise HTTPException(status_code=404, detail="Cure schedule not found")
    return cs


def create_cure_schedule(db: Session, company_id: str, data: dict) -> CureSchedule:
    cs = CureSchedule(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=data["name"],
        description=data.get("description"),
        duration_hours=data["duration_hours"],
        minimum_strength_release_percent=data.get(
            "minimum_strength_release_percent", 70
        ),
        temperature_adjusted=data.get("temperature_adjusted", False),
        notes=data.get("notes"),
        is_default=data.get("is_default", False),
    )
    db.add(cs)
    db.commit()
    db.refresh(cs)
    return cs


def update_cure_schedule(
    db: Session, company_id: str, cs_id: str, data: dict
) -> CureSchedule:
    cs = get_cure_schedule(db, company_id, cs_id)
    for key in (
        "name",
        "description",
        "duration_hours",
        "minimum_strength_release_percent",
        "temperature_adjusted",
        "notes",
        "is_default",
    ):
        if key in data:
            setattr(cs, key, data[key])
    cs.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(cs)
    return cs


# ---------------------------------------------------------------------------
# Stock Replenishment Rules CRUD
# ---------------------------------------------------------------------------


def list_replenishment_rules(
    db: Session, company_id: str
) -> list[StockReplenishmentRule]:
    return (
        db.query(StockReplenishmentRule)
        .filter(StockReplenishmentRule.company_id == company_id)
        .order_by(StockReplenishmentRule.created_at.desc())
        .all()
    )


def create_replenishment_rule(
    db: Session, company_id: str, data: dict
) -> StockReplenishmentRule:
    rule = StockReplenishmentRule(
        id=str(uuid.uuid4()),
        company_id=company_id,
        product_id=data["product_id"],
        product_variant_id=data.get("product_variant_id"),
        minimum_stock_quantity=data["minimum_stock_quantity"],
        target_stock_quantity=data["target_stock_quantity"],
        is_active=data.get("is_active", True),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_replenishment_rule(
    db: Session, company_id: str, rule_id: str, data: dict
) -> StockReplenishmentRule:
    rule = (
        db.query(StockReplenishmentRule)
        .filter(
            StockReplenishmentRule.id == rule_id,
            StockReplenishmentRule.company_id == company_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Replenishment rule not found")
    for key in (
        "product_id",
        "product_variant_id",
        "minimum_stock_quantity",
        "target_stock_quantity",
        "is_active",
    ):
        if key in data:
            setattr(rule, key, data[key])
    rule.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(rule)
    return rule


def delete_replenishment_rule(
    db: Session, company_id: str, rule_id: str
) -> None:
    rule = (
        db.query(StockReplenishmentRule)
        .filter(
            StockReplenishmentRule.id == rule_id,
            StockReplenishmentRule.company_id == company_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Replenishment rule not found")
    db.delete(rule)
    db.commit()
