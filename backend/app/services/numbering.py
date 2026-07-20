"""Atomic document numbering (audit #2 KILL 3).

The old allocators were non-atomic max-scans with LEXICAL ordering —
concurrent creates collided, and past 9999 the string max stuck at
"9999" forever (duplicates). This helper is the one allocator:

  * ATOMIC: a pg advisory xact lock keyed on (company, prefix)
    serializes allocation across sessions until the caller's COMMIT —
    two concurrent creates get distinct numbers.
  * NUMERIC max: the suffix is cast to integer (regexp-filtered, so
    convention-breaking rows like SO-LEGACY-* are ignored, never crash
    the cast) — 9999 → 10000 correctly.
  * The r138 UNIQUE constraints are the backstop: a bug here goes LOUD
    (IntegrityError), never silent duplicates.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session


def next_document_number(db: Session, *, table: str, company_id: str,
                         prefix: str) -> str:
    """Allocate `{prefix}-{YYYY}-{####}` atomically for the company."""
    year = datetime.now(timezone.utc).year
    full_prefix = f"{prefix}-{year}-"
    # Serialize allocators for this (company, prefix) until COMMIT.
    db.execute(sql_text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
               {"k": f"num:{company_id}:{full_prefix}"})
    seq = db.execute(sql_text(
        f"SELECT COALESCE(MAX(CAST(SUBSTRING(number FROM :start) AS INTEGER)), 0) "
        f"FROM {table} WHERE company_id = :c AND number ~ :pat"
    ), {
        "start": len(full_prefix) + 1,
        "c": company_id,
        "pat": f"^{full_prefix.replace('-', '[-]')}[0-9]+$",
    }).scalar()
    return f"{full_prefix}{(seq or 0) + 1:04d}"
