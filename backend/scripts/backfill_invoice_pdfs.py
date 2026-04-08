#!/usr/bin/env python3
"""
One-time backfill: generate and persist PDFs for all invoices missing an R2 document record.

Run from the backend directory:
    python -m scripts.backfill_invoice_pdfs

Optional args:
    --company-id <id>   Only backfill a specific tenant
    --dry-run           Print what would be done without uploading
    --limit <n>         Cap at n invoices (for testing)
"""

import argparse
import logging
import os
import sys
import time

# ---------------------------------------------------------------------------
# Bootstrap — add backend/ to sys.path so we can import app modules
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import and_, exists

from app.database import SessionLocal
from app.models.document import Document
from app.models.invoice import Invoice
from app.services.document_r2_service import save_generated_document
from app.services.pdf_generation_service import generate_invoice_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_invoice_pdfs")


def find_invoices_missing_r2_doc(db, *, company_id: str | None = None, limit: int | None = None):
    """
    Return Invoice rows that do NOT have a corresponding R2-backed Document.

    Uses a NOT EXISTS subquery: skip any invoice where a Document row exists
    with entity_type='invoice', document_type='invoice', and r2_key IS NOT NULL.
    """
    has_r2_doc = exists().where(
        and_(
            Document.entity_type == "invoice",
            Document.entity_id == Invoice.id,
            Document.document_type == "invoice",
            Document.r2_key.isnot(None),
        )
    )

    q = db.query(Invoice).filter(~has_r2_doc)

    if company_id:
        q = q.filter(Invoice.company_id == company_id)

    q = q.order_by(Invoice.created_at.asc())

    if limit:
        q = q.limit(limit)

    return q.all()


def build_metadata(inv: Invoice) -> dict:
    """Build the same metadata dict used in the preview_invoice route."""
    return {
        "invoice_id": str(inv.id),
        "invoice_number": inv.number,
        "customer_id": str(inv.customer_id),
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "total": str(inv.total),
        "amount_paid": str(inv.amount_paid),
        "balance_remaining": str(inv.balance_remaining),
        "status": inv.status,
        "deceased_name": inv.deceased_name,
        "payment_terms": inv.payment_terms,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill invoice PDFs to R2")
    parser.add_argument("--company-id", help="Only backfill a specific tenant")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without uploading")
    parser.add_argument("--limit", type=int, help="Cap at n invoices (for testing)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        logger.info("Querying invoices missing R2-backed PDF documents...")
        invoices = find_invoices_missing_r2_doc(
            db, company_id=args.company_id, limit=args.limit,
        )
        total = len(invoices)

        if total == 0:
            logger.info("All invoices already have R2 documents. Nothing to do.")
            return

        logger.info("Found %d invoices to backfill%s", total, " (DRY RUN)" if args.dry_run else "")

        succeeded = 0
        skipped = 0
        failed = 0

        for i, inv in enumerate(invoices, 1):
            filename = f"Invoice-{inv.number}.pdf"
            r2_key = f"tenants/{inv.company_id}/invoices/{inv.id}/invoice/{filename}"

            if args.dry_run:
                logger.info("[%d/%d] DRY RUN — %s → %s", i, total, inv.number, r2_key)
                succeeded += 1
                continue

            try:
                pdf_bytes = generate_invoice_pdf(db, inv.id, inv.company_id)

                if pdf_bytes is None:
                    logger.warning("[%d/%d] %s — skipped (WeasyPrint returned None)", i, total, inv.number)
                    skipped += 1
                    continue

                metadata = build_metadata(inv)

                save_generated_document(
                    db,
                    company_id=inv.company_id,
                    entity_type="invoice",
                    entity_id=str(inv.id),
                    document_type="invoice",
                    file_name=filename,
                    file_bytes=pdf_bytes,
                    mime_type="application/pdf",
                    generated_by=None,
                    metadata=metadata,
                )

                logger.info("[%d/%d] %s → uploaded (%d bytes)", i, total, inv.number, len(pdf_bytes))
                succeeded += 1

            except Exception as exc:
                logger.error("[%d/%d] %s — FAILED: %s", i, total, inv.number, exc)
                failed += 1
                # Roll back the failed transaction so the session stays usable
                db.rollback()

        logger.info("=" * 60)
        logger.info("Backfill complete%s", " (DRY RUN)" if args.dry_run else "")
        logger.info("  Total:     %d", total)
        logger.info("  Succeeded: %d", succeeded)
        logger.info("  Skipped:   %d", skipped)
        logger.info("  Failed:    %d", failed)
        logger.info("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
