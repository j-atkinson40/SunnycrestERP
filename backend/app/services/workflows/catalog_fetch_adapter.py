"""Wilbert Catalog Auto-Fetch — parity adapter (Workflow Arc Phase 8d).

Wraps the existing `UrnCatalogScraper.fetch_catalog_pdf` +
`WilbertIngestionService.ingest_from_pdf` pipeline with a
triage-gated staging step. Today's auto-fetch upserts products
directly when the MD5 hash differs — no admin review between
"Wilbert shipped a new catalog" and "our retail prices shift in
production." Phase 8d splits the flow:

  1. `run_staged_fetch` (workflow step) — download PDF, MD5-diff,
     upload to R2, create a staging UrnCatalogSyncLog with
     `publication_state='pending_review'`. Products are NOT
     upserted yet.
  2. Triage queue surfaces the staging log as one item.
  3. `approve_publish` (triage action) — fetches the staged PDF
     from R2, runs the legacy `WilbertIngestionService.ingest_from_pdf`
     pipeline on it, marks `publication_state='published'`. THE
     ACTUAL UPSERT LOGIC LIVES IN THE LEGACY SERVICE — zero
     duplication.
  4. `reject_publish` — marks `publication_state='rejected'`, no
     product writes, admin can optionally supply a reason.

Per-job matrix: one triage item per changed-catalog fetch. Most
weeks return "no change" (MD5 matches) so the queue stays empty
except when Wilbert actually ships an updated catalog.

Idempotency + concurrency:
  - A new fetch while an older one is still 'pending_review' marks
    the older row as 'superseded' (terminal) so the queue never
    holds two competing catalogs.
  - Re-running `approve_publish` against a non-pending log raises
    `ValueError` — second approves are a no-op (the first one
    already upserted).

Legacy coexistence:
  - `UrnCatalogScraper.fetch_catalog_pdf` still exists and still
    works the old way when called from non-workflow call sites
    (admin "Fetch catalog now" button, one-off scripts). Pre-r39
    rows land as `publication_state='published'` so legacy runs
    are unaffected.
  - The workflow's `wf_sys_catalog_fetch` seed switches from the
    legacy `system_job` action to `call_service_method` targeting
    `catalog_fetch.run_staged_fetch`.

Public functions:
  run_staged_fetch(db, *, company_id, triggered_by_user_id, dry_run,
                   trigger_source) -> dict
      Workflow-step surface. Stages a pending-review fetch.

  approve_publish(db, *, user, sync_log_id) -> dict
      Triage approve. Publishes the staged ingestion via the legacy
      ingest_from_pdf path. Flips publication_state → 'published'.

  reject_publish(db, *, user, sync_log_id, reason) -> dict
      Triage reject. Flips publication_state → 'rejected', no
      product writes.

  request_review(db, *, user, sync_log_id, note) -> dict
      Triage request-review. Stamps a review note on the log's
      `error_message` column as an audit trail without changing
      state — the item stays pending_review.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
from app.models.urn_tenant_settings import UrnTenantSettings
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Pipeline entry (workflow-step surface) ───────────────────────────


def run_staged_fetch(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Fetch the current Wilbert catalog PDF, hash-diff against the
    tenant's last-seen version, and stage a pending-review sync_log
    row if the PDF changed. Does NOT upsert products.

    Returns a summary dict:
      {
        status, sync_log_id, changed, r2_key, products_preview,
        superseded_log_id, dry_run
      }

    `products_preview` is the count produced by parse-only on the
    staged PDF — lets the triage UI render a headline count without
    re-parsing on every row render.

    No change path returns `{changed: False, sync_log_id: None}`.
    """
    from app.services.urn_catalog_scraper import UrnCatalogScraper
    from app.services.wilbert_pdf_parser import parse_pdf_to_dicts

    # Resolve URL + download bytes — reuses the legacy helpers but
    # we do our own orchestration from here.
    pdf_url = UrnCatalogScraper._resolve_pdf_url()
    if not pdf_url:
        return {
            "status": "applied",
            "changed": False,
            "sync_log_id": None,
            "message": "Could not resolve Wilbert catalog PDF URL",
            "dry_run": dry_run,
        }

    from app.services.urn_catalog_scraper import _get_http_client

    client = _get_http_client()
    try:
        resp = client.get(pdf_url)
        resp.raise_for_status()
        pdf_bytes = resp.content
    except Exception as exc:  # noqa: BLE001 — surface as step error
        logger.exception("Catalog PDF download failed: %s", exc)
        return {
            "status": "errored",
            "error": f"Download failed: {str(exc)[:200]}",
            "dry_run": dry_run,
        }
    finally:
        client.close()

    new_hash = hashlib.md5(pdf_bytes).hexdigest()

    settings = (
        db.query(UrnTenantSettings)
        .filter(UrnTenantSettings.tenant_id == company_id)
        .first()
    )
    if settings is None:
        settings = UrnTenantSettings(tenant_id=company_id)
        db.add(settings)
        db.flush()

    old_hash = settings.catalog_pdf_hash

    if old_hash == new_hash:
        return {
            "status": "applied",
            "changed": False,
            "sync_log_id": None,
            "message": "Catalog PDF unchanged",
            "new_hash": new_hash,
            "dry_run": dry_run,
        }

    # Archive to R2. Keep the hash in the key so multiple pending
    # reviews across different fetches don't overwrite each other.
    r2_key = f"catalogs/wilbert/cremation-choices-{new_hash[:12]}.pdf"
    try:
        from app.services.legacy_r2_client import upload_bytes

        if not dry_run:
            upload_bytes(pdf_bytes, r2_key, content_type="application/pdf")
    except Exception as exc:  # noqa: BLE001 — non-fatal
        logger.warning("Catalog PDF R2 upload failed: %s", exc)

    # Parse-only for the products_preview count. We keep the bytes
    # in a tempfile because `parse_pdf_to_dicts` works on paths.
    products_preview = 0
    tmp_path: str | None = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".pdf", prefix="wilbert_catalog_preview_", delete=False
        )
        tmp.write(pdf_bytes)
        tmp.close()
        tmp_path = tmp.name
        products_preview = len(parse_pdf_to_dicts(tmp_path))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Catalog PDF parse-preview failed (non-fatal): %s", exc
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Supersede any older pending-review fetch for this tenant so
    # the triage queue never shows two competing catalogs.
    superseded_log_id: str | None = None
    older = (
        db.query(UrnCatalogSyncLog)
        .filter(
            UrnCatalogSyncLog.tenant_id == company_id,
            UrnCatalogSyncLog.publication_state == "pending_review",
        )
        .order_by(UrnCatalogSyncLog.started_at.desc())
        .first()
    )
    if older is not None and not dry_run:
        older.publication_state = "superseded"
        older.completed_at = datetime.now(timezone.utc)
        superseded_log_id = older.id
        db.flush()

    # Create the new pending-review sync_log. We stash the R2 key in
    # `pdf_filename` so `approve_publish` can locate the bytes. The
    # products_preview count lands on products_updated (the "would
    # update" estimate) — published-state publish will overwrite.
    new_log = UrnCatalogSyncLog(
        id=str(uuid.uuid4()),
        tenant_id=company_id,
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        status="running",  # legacy semantics — pending publish
        publication_state="pending_review",
        sync_type="pdf_staged",
        pdf_filename=r2_key,  # doubles as R2 key for approve_publish
        products_added=0,
        products_updated=products_preview,  # preview count
        products_discontinued=0,
        products_skipped=0,
    )
    if dry_run:
        return {
            "status": "applied",
            "changed": True,
            "sync_log_id": None,
            "new_hash": new_hash,
            "r2_key": r2_key,
            "products_preview": products_preview,
            "superseded_log_id": None,
            "dry_run": True,
        }
    db.add(new_log)

    # Persist the new hash on tenant settings so the next auto-fetch
    # diffs against this catalog (even if nobody approves yet — the
    # alternative is re-downloading the same PDF every run).
    settings.catalog_pdf_hash = new_hash
    settings.catalog_pdf_last_fetched = datetime.now(timezone.utc)
    settings.catalog_pdf_r2_key = r2_key

    db.commit()
    return {
        "status": "applied",
        "changed": True,
        "sync_log_id": new_log.id,
        "new_hash": new_hash,
        "r2_key": r2_key,
        "products_preview": products_preview,
        "superseded_log_id": superseded_log_id,
        "dry_run": False,
    }


# ── Triage action surface ────────────────────────────────────────────


def _load_sync_log_scoped(
    db: Session, *, sync_log_id: str, company_id: str
) -> UrnCatalogSyncLog:
    row = (
        db.query(UrnCatalogSyncLog)
        .filter(
            UrnCatalogSyncLog.id == sync_log_id,
            UrnCatalogSyncLog.tenant_id == company_id,
        )
        .first()
    )
    if row is None:
        raise ValueError(
            f"Catalog sync log {sync_log_id} not found for this tenant"
        )
    return row


def approve_publish(
    db: Session, *, user: User, sync_log_id: str
) -> dict[str, Any]:
    """Publish the staged catalog ingestion.

    Fetches the staged PDF from R2 (keyed by the log's
    `pdf_filename` column), runs the legacy
    `WilbertIngestionService.ingest_from_pdf` unchanged, then
    flips the staging row's `publication_state='published'`. The
    actual product upsert lives in the legacy service — zero
    duplication.
    """
    log = _load_sync_log_scoped(
        db, sync_log_id=sync_log_id, company_id=user.company_id
    )
    if log.publication_state != "pending_review":
        raise ValueError(
            f"Catalog sync log {sync_log_id} is in state "
            f"{log.publication_state!r}; only pending_review rows "
            "can be approved."
        )

    r2_key = log.pdf_filename
    if not r2_key:
        raise ValueError(
            f"Catalog sync log {sync_log_id} is missing its staged "
            "PDF R2 key (pdf_filename is NULL)."
        )

    # Pull staged PDF bytes from R2 and write to tempfile for the
    # parser. The legacy ingest_from_pdf works on paths.
    from app.services.legacy_r2_client import download_bytes

    pdf_bytes = download_bytes(r2_key)
    if not pdf_bytes:
        raise ValueError(
            f"Staged PDF at {r2_key!r} could not be fetched from R2"
        )

    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdf", prefix="wilbert_catalog_publish_", delete=False
    )
    tmp.write(pdf_bytes)
    tmp.close()
    try:
        from app.services.wilbert_ingestion_service import (
            WilbertIngestionService,
        )

        ingest_log = WilbertIngestionService.ingest_from_pdf(
            db,
            user.company_id,
            tmp.name,
            enrich_from_website=False,
        )
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # Roll the ingest result into the STAGING row (publication row)
    # so the admin-facing log has one canonical record per staged
    # fetch. The legacy ingest_from_pdf also wrote its own row — we
    # mark that one as "superseded" so it doesn't pollute counts.
    log.products_added = ingest_log.products_added
    log.products_updated = ingest_log.products_updated
    log.products_discontinued = ingest_log.products_discontinued
    log.products_skipped = ingest_log.products_skipped
    log.status = "completed"
    log.publication_state = "published"
    log.completed_at = datetime.now(timezone.utc)
    # Mark the legacy-pathway log row as superseded — it represents
    # the implementation detail, not the admin-visible event.
    if ingest_log.id != log.id:
        ingest_log.publication_state = "superseded"
        ingest_log.status = "completed"
    db.commit()

    return {
        "status": "applied",
        "message": (
            f"Published — {log.products_added} added, "
            f"{log.products_updated} updated, "
            f"{log.products_discontinued} discontinued"
        ),
        "sync_log_id": sync_log_id,
        "products_added": log.products_added,
        "products_updated": log.products_updated,
        "products_discontinued": log.products_discontinued,
    }


def reject_publish(
    db: Session, *, user: User, sync_log_id: str, reason: str
) -> dict[str, Any]:
    """Reject the staged catalog ingestion. Flips
    publication_state → 'rejected'. No product writes. Reason is
    stamped on `error_message` for audit."""
    if not reason:
        raise ValueError("Reason is required to reject a catalog publication")
    log = _load_sync_log_scoped(
        db, sync_log_id=sync_log_id, company_id=user.company_id
    )
    if log.publication_state != "pending_review":
        raise ValueError(
            f"Catalog sync log {sync_log_id} is in state "
            f"{log.publication_state!r}; only pending_review rows "
            "can be rejected."
        )
    log.publication_state = "rejected"
    log.status = "completed"
    log.completed_at = datetime.now(timezone.utc)
    log.error_message = f"Rejected by {user.id}: {reason}"[:2000]
    db.commit()
    return {
        "status": "applied",
        "message": "Catalog publication rejected — no products modified.",
        "sync_log_id": sync_log_id,
    }


def request_review(
    db: Session, *, user: User, sync_log_id: str, note: str
) -> dict[str, Any]:
    """Stamp a review note on the sync log without changing state.
    Item stays pending_review so a teammate can pick it up."""
    if not note:
        raise ValueError("A note is required when requesting review")
    log = _load_sync_log_scoped(
        db, sync_log_id=sync_log_id, company_id=user.company_id
    )
    existing = log.error_message or ""
    stamp = (
        f"[review-requested by {user.id} at "
        f"{datetime.now(timezone.utc).isoformat()}] {note}"
    )
    log.error_message = (
        f"{existing}\n{stamp}" if existing else stamp
    )[:2000]
    db.commit()
    return {
        "status": "applied",
        "message": "Review requested — catalog stays in queue.",
        "sync_log_id": sync_log_id,
    }


__all__ = [
    "run_staged_fetch",
    "approve_publish",
    "reject_publish",
    "request_review",
]
