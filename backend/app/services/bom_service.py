import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.bom import BillOfMaterials, BOMLine
from app.models.product import Product
from app.schemas.bom import BOMCreate, BOMUpdate


def list_boms(
    db: Session,
    company_id: str,
    product_id: str | None = None,
    bom_status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Return paginated list of BOMs with summary info."""
    query = db.query(BillOfMaterials).filter(
        BillOfMaterials.company_id == company_id,
        BillOfMaterials.is_active.is_(True),
    )
    if product_id:
        query = query.filter(BillOfMaterials.product_id == product_id)
    if bom_status:
        query = query.filter(BillOfMaterials.status == bom_status)

    total = query.count()
    boms = (
        query.options(joinedload(BillOfMaterials.product))
        .order_by(BillOfMaterials.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for bom in boms:
        line_count = (
            db.query(func.count(BOMLine.id))
            .filter(BOMLine.bom_id == bom.id)
            .scalar()
        )
        cost = _calculate_cost(db, bom.id)
        items.append(
            {
                "bom": bom,
                "line_count": line_count,
                "cost_total": cost,
            }
        )

    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_bom(db: Session, bom_id: str, company_id: str) -> BillOfMaterials:
    """Get a single BOM with lines eagerly loaded."""
    bom = (
        db.query(BillOfMaterials)
        .options(
            joinedload(BillOfMaterials.product),
            joinedload(BillOfMaterials.lines).joinedload(BOMLine.component_product),
            joinedload(BillOfMaterials.creator),
        )
        .filter(
            BillOfMaterials.id == bom_id,
            BillOfMaterials.company_id == company_id,
            BillOfMaterials.is_active.is_(True),
        )
        .first()
    )
    if not bom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="BOM not found"
        )
    return bom


def create_bom(
    db: Session,
    company_id: str,
    data: BOMCreate,
    actor_id: str,
) -> BillOfMaterials:
    """Create a new BOM with lines. Auto-calculates version number."""
    # Verify product exists and belongs to company
    product = (
        db.query(Product)
        .filter(Product.id == data.product_id, Product.company_id == company_id)
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    # Auto-calculate next version for this product
    max_version = (
        db.query(func.max(BillOfMaterials.version))
        .filter(
            BillOfMaterials.product_id == data.product_id,
            BillOfMaterials.company_id == company_id,
        )
        .scalar()
    )
    next_version = (max_version or 0) + 1

    now = datetime.now(timezone.utc)
    bom = BillOfMaterials(
        id=str(uuid.uuid4()),
        company_id=company_id,
        product_id=data.product_id,
        version=next_version,
        name=data.name or product.name,
        status="draft",
        notes=data.notes,
        effective_date=data.effective_date,
        created_by=actor_id,
        modified_by=actor_id,
        created_at=now,
        modified_at=now,
    )
    db.add(bom)
    db.flush()

    for line_data in data.lines:
        _validate_component(db, line_data.component_product_id, company_id)
        line = BOMLine(
            id=str(uuid.uuid4()),
            bom_id=bom.id,
            component_product_id=line_data.component_product_id,
            quantity=line_data.quantity,
            unit_of_measure=line_data.unit_of_measure,
            waste_factor_pct=line_data.waste_factor_pct,
            notes=line_data.notes,
            sort_order=line_data.sort_order,
            is_optional=line_data.is_optional,
        )
        db.add(line)

    db.commit()
    db.refresh(bom)
    return get_bom(db, bom.id, company_id)


def update_bom(
    db: Session,
    bom_id: str,
    company_id: str,
    data: BOMUpdate,
    actor_id: str,
) -> BillOfMaterials:
    """Update a BOM. Only draft BOMs can be edited."""
    bom = get_bom(db, bom_id, company_id)
    if bom.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft BOMs can be edited. Clone this BOM to create a new draft version.",
        )

    now = datetime.now(timezone.utc)
    if data.name is not None:
        bom.name = data.name
    if data.notes is not None:
        bom.notes = data.notes
    if data.effective_date is not None:
        bom.effective_date = data.effective_date
    bom.modified_by = actor_id
    bom.modified_at = now

    # Update lines if provided
    if data.lines is not None:
        # Build map of existing lines
        existing_lines = {line.id: line for line in bom.lines}
        seen_ids: set[str] = set()

        for line_data in data.lines:
            if line_data.id and line_data.id in existing_lines:
                # Update existing line
                line = existing_lines[line_data.id]
                seen_ids.add(line.id)
                if line_data.component_product_id is not None:
                    _validate_component(db, line_data.component_product_id, company_id)
                    line.component_product_id = line_data.component_product_id
                if line_data.quantity is not None:
                    line.quantity = line_data.quantity
                if line_data.unit_of_measure is not None:
                    line.unit_of_measure = line_data.unit_of_measure
                if line_data.waste_factor_pct is not None:
                    line.waste_factor_pct = line_data.waste_factor_pct
                if line_data.notes is not None:
                    line.notes = line_data.notes
                if line_data.sort_order is not None:
                    line.sort_order = line_data.sort_order
                if line_data.is_optional is not None:
                    line.is_optional = line_data.is_optional
            else:
                # Add new line
                _validate_component(
                    db,
                    line_data.component_product_id,
                    company_id,
                )
                new_line = BOMLine(
                    id=str(uuid.uuid4()),
                    bom_id=bom.id,
                    component_product_id=line_data.component_product_id,
                    quantity=line_data.quantity or Decimal("1"),
                    unit_of_measure=line_data.unit_of_measure or "",
                    waste_factor_pct=line_data.waste_factor_pct or Decimal("0"),
                    notes=line_data.notes,
                    sort_order=line_data.sort_order or 0,
                    is_optional=line_data.is_optional or False,
                )
                db.add(new_line)

        # Remove lines not in the update payload
        for line_id, line in existing_lines.items():
            if line_id not in seen_ids:
                db.delete(line)

    db.commit()
    return get_bom(db, bom_id, company_id)


def activate_bom(
    db: Session,
    bom_id: str,
    company_id: str,
    actor_id: str,
) -> BillOfMaterials:
    """Activate a BOM. Archives all other versions for the same product."""
    bom = get_bom(db, bom_id, company_id)
    if bom.status == "active":
        return bom

    if bom.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate an archived BOM. Clone it first.",
        )

    # Verify BOM has at least one line
    if not bom.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate a BOM with no lines.",
        )

    now = datetime.now(timezone.utc)

    # Archive all other active versions for the same product
    db.query(BillOfMaterials).filter(
        BillOfMaterials.product_id == bom.product_id,
        BillOfMaterials.company_id == company_id,
        BillOfMaterials.status == "active",
        BillOfMaterials.id != bom.id,
        BillOfMaterials.is_active.is_(True),
    ).update(
        {"status": "archived", "modified_by": actor_id, "modified_at": now},
        synchronize_session="fetch",
    )

    bom.status = "active"
    bom.modified_by = actor_id
    bom.modified_at = now
    db.commit()
    return get_bom(db, bom_id, company_id)


def archive_bom(
    db: Session,
    bom_id: str,
    company_id: str,
    actor_id: str,
) -> BillOfMaterials:
    """Archive a BOM."""
    bom = get_bom(db, bom_id, company_id)
    if bom.status == "archived":
        return bom

    now = datetime.now(timezone.utc)
    bom.status = "archived"
    bom.modified_by = actor_id
    bom.modified_at = now
    db.commit()
    return get_bom(db, bom_id, company_id)


def clone_bom(
    db: Session,
    bom_id: str,
    company_id: str,
    actor_id: str,
    new_version: int | None = None,
) -> BillOfMaterials:
    """Deep copy a BOM to create a new draft version."""
    source = get_bom(db, bom_id, company_id)

    if new_version is None:
        max_version = (
            db.query(func.max(BillOfMaterials.version))
            .filter(
                BillOfMaterials.product_id == source.product_id,
                BillOfMaterials.company_id == company_id,
            )
            .scalar()
        )
        new_version = (max_version or 0) + 1
    else:
        # Verify requested version is not taken
        exists = (
            db.query(BillOfMaterials.id)
            .filter(
                BillOfMaterials.product_id == source.product_id,
                BillOfMaterials.company_id == company_id,
                BillOfMaterials.version == new_version,
            )
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Version {new_version} already exists for this product.",
            )

    now = datetime.now(timezone.utc)
    new_bom = BillOfMaterials(
        id=str(uuid.uuid4()),
        company_id=company_id,
        product_id=source.product_id,
        version=new_version,
        name=source.name,
        status="draft",
        notes=source.notes,
        effective_date=None,
        created_by=actor_id,
        modified_by=actor_id,
        created_at=now,
        modified_at=now,
    )
    db.add(new_bom)
    db.flush()

    for src_line in source.lines:
        new_line = BOMLine(
            id=str(uuid.uuid4()),
            bom_id=new_bom.id,
            component_product_id=src_line.component_product_id,
            quantity=src_line.quantity,
            unit_of_measure=src_line.unit_of_measure,
            waste_factor_pct=src_line.waste_factor_pct,
            notes=src_line.notes,
            sort_order=src_line.sort_order,
            is_optional=src_line.is_optional,
        )
        db.add(new_line)

    db.commit()
    return get_bom(db, new_bom.id, company_id)


def delete_bom(db: Session, bom_id: str, company_id: str) -> None:
    """Soft-delete a BOM."""
    bom = get_bom(db, bom_id, company_id)
    bom.is_active = False
    bom.modified_at = datetime.now(timezone.utc)
    db.commit()


def calculate_bom_cost(db: Session, bom_id: str, company_id: str) -> Decimal | None:
    """Calculate total BOM cost from component costs.

    Returns None if any required component is missing a cost_price.
    """
    bom = get_bom(db, bom_id, company_id)
    return _calculate_cost(db, bom.id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _calculate_cost(db: Session, bom_id: str) -> Decimal | None:
    """Sum of (component.cost_price * quantity * (1 + waste_factor_pct/100))
    for all non-optional lines.
    """
    lines = (
        db.query(BOMLine)
        .options(joinedload(BOMLine.component_product))
        .filter(BOMLine.bom_id == bom_id)
        .all()
    )
    if not lines:
        return Decimal("0")

    total = Decimal("0")
    has_missing_cost = False
    for line in lines:
        if line.is_optional:
            continue
        cost_price = line.component_product.cost_price if line.component_product else None
        if cost_price is None:
            has_missing_cost = True
            continue
        waste_multiplier = Decimal("1") + (line.waste_factor_pct / Decimal("100"))
        line_cost = cost_price * line.quantity * waste_multiplier
        total += line_cost

    # Return total even if some costs missing (partial rollup is useful),
    # but annotate with None if nothing could be calculated at all
    if has_missing_cost and total == Decimal("0") and not any(
        not l.is_optional and l.component_product and l.component_product.cost_price
        for l in lines
    ):
        return None

    return total.quantize(Decimal("0.01"))


def _validate_component(db: Session, product_id: str, company_id: str) -> Product:
    """Verify a component product exists and belongs to the company."""
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == company_id)
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component product {product_id} not found.",
        )
    return product
