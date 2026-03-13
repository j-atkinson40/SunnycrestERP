import csv
import io
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sage_export_config import SageExportConfig
from app.services import audit_service, sync_log_service


# Map internal transaction types to Sage-friendly codes
_SAGE_TX_TYPE_MAP = {
    "receive": "RC",
    "sell": "SL",
    "adjust": "AD",
    "production": "PR",
    "write_off": "WO",
    "count": "CT",
    "return": "RT",
}


def get_or_create_config(db: Session, company_id: str) -> SageExportConfig:
    """Get existing config or create one with defaults."""
    config = (
        db.query(SageExportConfig)
        .filter(SageExportConfig.company_id == company_id)
        .first()
    )
    if not config:
        config = SageExportConfig(company_id=company_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def update_config(
    db: Session,
    company_id: str,
    warehouse_code: str | None = None,
    export_directory: str | None = None,
    actor_id: str | None = None,
) -> SageExportConfig:
    """Update the Sage export configuration."""
    config = get_or_create_config(db, company_id)
    old_data = {
        "warehouse_code": config.warehouse_code,
        "export_directory": config.export_directory,
    }

    if warehouse_code is not None:
        config.warehouse_code = warehouse_code
    if export_directory is not None:
        config.export_directory = export_directory

    new_data = {
        "warehouse_code": config.warehouse_code,
        "export_directory": config.export_directory,
    }
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "sage_export_config",
            config.id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(config)
    return config


def generate_sage_csv(
    db: Session,
    company_id: str,
    date_from: datetime,
    date_to: datetime,
    actor_id: str | None = None,
) -> tuple[str, int, str]:
    """Generate a Sage 100-compatible CSV from inventory transactions.

    Returns (csv_string, record_count, sync_log_id).
    """
    config = get_or_create_config(db, company_id)

    # Create sync log entry
    sync_log = sync_log_service.create_sync_log(
        db,
        company_id,
        sync_type="sage_export",
        source="inventory_transactions",
        destination="sage_csv",
    )

    try:
        # Query transactions in date range, joined with product for SKU/cost
        transactions = (
            db.query(InventoryTransaction, Product)
            .join(Product, InventoryTransaction.product_id == Product.id)
            .filter(
                InventoryTransaction.company_id == company_id,
                InventoryTransaction.created_at >= date_from,
                InventoryTransaction.created_at <= date_to,
            )
            .order_by(InventoryTransaction.created_at)
            .all()
        )

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Item Number",
            "Warehouse",
            "Transaction Date",
            "Quantity",
            "Transaction Type",
            "Reference",
            "Unit Cost",
        ])

        for tx, product in transactions:
            sage_type = _SAGE_TX_TYPE_MAP.get(
                tx.transaction_type, tx.transaction_type[:2].upper()
            )
            writer.writerow([
                product.sku or "",
                config.warehouse_code,
                tx.created_at.strftime("%m/%d/%Y"),
                tx.quantity_change,
                sage_type,
                tx.reference or "",
                f"{product.cost_price:.2f}" if product.cost_price else "0.00",
            ])

        record_count = len(transactions)
        csv_string = output.getvalue()

        # Complete sync log
        sync_log_service.complete_sync_log(
            db, sync_log, records_processed=record_count, records_failed=0
        )
        config.last_export_at = datetime.now(timezone.utc)

        audit_service.log_action(
            db,
            company_id,
            "exported",
            "sage_csv",
            sync_log.id,
            user_id=actor_id,
            changes={"records": {"old": None, "new": record_count}},
        )

        db.commit()
        return csv_string, record_count, sync_log.id

    except Exception as exc:
        sync_log_service.complete_sync_log(
            db, sync_log, records_processed=0, records_failed=0,
            error_message=str(exc),
        )
        db.commit()
        raise


def get_export_history(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Get paginated list of sage export sync logs."""
    from app.models.sync_log import SyncLog

    query = db.query(SyncLog).filter(
        SyncLog.company_id == company_id,
        SyncLog.sync_type == "sage_export",
    )
    total = query.count()
    items = (
        query.order_by(SyncLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}
