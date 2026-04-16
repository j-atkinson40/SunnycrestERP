"""Legacy print service — manages per-tenant Legacy print catalog."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.program_legacy_print import ProgramLegacyPrint


def list_prints(db: Session, company_id: str, program_code: str) -> list[ProgramLegacyPrint]:
    return (
        db.query(ProgramLegacyPrint)
        .filter(
            ProgramLegacyPrint.company_id == company_id,
            ProgramLegacyPrint.program_code == program_code,
        )
        .order_by(ProgramLegacyPrint.is_custom, ProgramLegacyPrint.sort_order, ProgramLegacyPrint.display_name)
        .all()
    )


def get_print(db: Session, company_id: str, print_id: str) -> ProgramLegacyPrint | None:
    return (
        db.query(ProgramLegacyPrint)
        .filter(
            ProgramLegacyPrint.id == print_id,
            ProgramLegacyPrint.company_id == company_id,
        )
        .first()
    )


def set_enabled(
    db: Session, company_id: str, print_id: str, enabled: bool
) -> ProgramLegacyPrint:
    p = get_print(db, company_id, print_id)
    if not p:
        raise ValueError("Legacy print not found")
    p.is_enabled = enabled
    db.commit()
    db.refresh(p)
    return p


def set_price(
    db: Session, company_id: str, print_id: str, price_addition: Decimal | None
) -> ProgramLegacyPrint:
    p = get_print(db, company_id, print_id)
    if not p:
        raise ValueError("Legacy print not found")
    p.price_addition = price_addition
    db.commit()
    db.refresh(p)
    return p


def create_custom(
    db: Session,
    company_id: str,
    program_code: str,
    display_name: str,
    description: str | None = None,
    file_url: str | None = None,
    thumbnail_url: str | None = None,
    price_addition: Decimal | None = None,
) -> ProgramLegacyPrint:
    p = ProgramLegacyPrint(
        company_id=company_id,
        program_code=program_code,
        wilbert_catalog_key=None,
        display_name=display_name,
        description=description,
        file_url=file_url,
        thumbnail_url=thumbnail_url,
        is_enabled=True,
        is_custom=True,
        price_addition=price_addition,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def delete_custom(db: Session, company_id: str, print_id: str) -> bool:
    """Delete a custom (tenant-uploaded) print. Refuses on Wilbert catalog prints."""
    p = get_print(db, company_id, print_id)
    if not p:
        return False
    if not p.is_custom:
        # Cannot delete Wilbert catalog prints — disable instead
        raise ValueError("Cannot delete Wilbert catalog prints. Disable them instead.")
    db.delete(p)
    db.commit()
    return True


def enable_all_wilbert(db: Session, company_id: str, program_code: str) -> int:
    prints = (
        db.query(ProgramLegacyPrint)
        .filter(
            ProgramLegacyPrint.company_id == company_id,
            ProgramLegacyPrint.program_code == program_code,
            ProgramLegacyPrint.is_custom == False,  # noqa: E712
        )
        .all()
    )
    count = 0
    for p in prints:
        if not p.is_enabled:
            p.is_enabled = True
            count += 1
    db.commit()
    return count


def disable_all_wilbert(db: Session, company_id: str, program_code: str) -> int:
    prints = (
        db.query(ProgramLegacyPrint)
        .filter(
            ProgramLegacyPrint.company_id == company_id,
            ProgramLegacyPrint.program_code == program_code,
            ProgramLegacyPrint.is_custom == False,  # noqa: E712
        )
        .all()
    )
    count = 0
    for p in prints:
        if p.is_enabled:
            p.is_enabled = False
            count += 1
    db.commit()
    return count
