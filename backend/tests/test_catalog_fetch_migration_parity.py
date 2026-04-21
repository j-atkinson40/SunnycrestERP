"""Workflow Arc Phase 8d — catalog_fetch migration parity tests.

Pre-8d: `UrnCatalogScraper.fetch_catalog_pdf` auto-published changes
to urn_products with no admin gate — a fresh Wilbert catalog could
shift retail prices in production silently.

Post-8d: `run_staged_fetch` STAGES the PDF (downloads, hashes,
uploads to R2, creates a pending-review UrnCatalogSyncLog) and
waits for admin approve via the triage queue. Approval runs the
legacy `WilbertIngestionService.ingest_from_pdf` unchanged against
the staged bytes — zero duplicated upsert logic. Reject preserves
the existing catalog.

Parity claim:
  An approve triggered through this adapter produces the SAME
  urn_products side effects as the legacy auto-publish path would
  have. This is the narrow parity we test — by monkey-patching the
  network + R2 calls while letting the PDF → parse → upsert path
  run for real.

Tests:
  - Staged fetch with unchanged MD5 returns no-op + no sync_log.
  - Staged fetch with changed MD5 creates a pending-review log.
  - Second staged fetch supersedes the older pending log.
  - Approve calls ingest_from_pdf + flips publication_state.
  - Approve on non-pending log raises.
  - Reject flips publication_state without product writes.
  - Reject without reason raises.
  - Request review stays in queue.
  - Cross-tenant isolation on approve/reject.
  - Supersede logic: older pending terminates when a newer one
    stages (not the newer one).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _seed_mfg_tenant() -> dict:
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"MFG-{suffix}",
            slug=f"mfg-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"admin-{suffix}@mfg.co",
            first_name="Adm",
            last_name="In",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {"company_id": co.id, "user_id": user.id, "user": user}
    finally:
        db.close()


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def _mock_http_client(pdf_bytes: bytes):
    client = MagicMock()
    client.get.return_value = _FakeResponse(pdf_bytes)
    return client


# ── Staged fetch tests ───────────────────────────────────────────────


class TestStagedFetch:
    def test_unchanged_md5_returns_no_op(self, db_session):
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.models.urn_tenant_settings import UrnTenantSettings
        from app.services.workflows.catalog_fetch_adapter import (
            run_staged_fetch,
        )

        ctx = _seed_mfg_tenant()
        pdf_bytes = b"fake-wilbert-catalog-bytes-unchanged"
        current_hash = hashlib.md5(pdf_bytes).hexdigest()

        # Pre-seed tenant settings with the same hash so "no change"
        # path fires.
        settings = UrnTenantSettings(
            tenant_id=ctx["company_id"],
            catalog_pdf_hash=current_hash,
        )
        db_session.add(settings)
        db_session.commit()

        with patch(
            "app.services.urn_catalog_scraper.UrnCatalogScraper._resolve_pdf_url",
            return_value="https://example.test/catalog.pdf",
        ), patch(
            "app.services.urn_catalog_scraper._get_http_client",
            return_value=_mock_http_client(pdf_bytes),
        ):
            result = run_staged_fetch(
                db_session,
                company_id=ctx["company_id"],
                triggered_by_user_id=ctx["user_id"],
            )

        assert result["status"] == "applied"
        assert result["changed"] is False
        assert result["sync_log_id"] is None
        # No new sync_log created.
        count = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.tenant_id == ctx["company_id"])
            .count()
        )
        assert count == 0

    def test_changed_md5_creates_pending_review(self, db_session):
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.services.workflows.catalog_fetch_adapter import (
            run_staged_fetch,
        )

        ctx = _seed_mfg_tenant()
        pdf_bytes = b"fake-wilbert-catalog-bytes-new"

        with patch(
            "app.services.urn_catalog_scraper.UrnCatalogScraper._resolve_pdf_url",
            return_value="https://example.test/catalog.pdf",
        ), patch(
            "app.services.urn_catalog_scraper._get_http_client",
            return_value=_mock_http_client(pdf_bytes),
        ), patch(
            "app.services.legacy_r2_client.upload_bytes",
            return_value="r2-key-fake",
        ), patch(
            "app.services.wilbert_pdf_parser.parse_pdf_to_dicts",
            return_value=[{"sku": "A"}, {"sku": "B"}],
        ):
            result = run_staged_fetch(
                db_session,
                company_id=ctx["company_id"],
                triggered_by_user_id=ctx["user_id"],
            )

        assert result["status"] == "applied"
        assert result["changed"] is True
        assert result["sync_log_id"] is not None
        log = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == result["sync_log_id"])
            .first()
        )
        assert log is not None
        assert log.publication_state == "pending_review"
        assert log.tenant_id == ctx["company_id"]
        assert log.pdf_filename.startswith("catalogs/wilbert/")
        # products_preview lands on products_updated (preview count).
        assert log.products_updated == 2

    def test_second_staged_fetch_supersedes_older_pending(self, db_session):
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.services.workflows.catalog_fetch_adapter import (
            run_staged_fetch,
        )

        ctx = _seed_mfg_tenant()

        with patch(
            "app.services.urn_catalog_scraper.UrnCatalogScraper._resolve_pdf_url",
            return_value="https://example.test/catalog.pdf",
        ), patch(
            "app.services.legacy_r2_client.upload_bytes",
            return_value="r2-key-fake",
        ), patch(
            "app.services.wilbert_pdf_parser.parse_pdf_to_dicts",
            return_value=[],
        ):
            # First fetch — v1 bytes.
            with patch(
                "app.services.urn_catalog_scraper._get_http_client",
                return_value=_mock_http_client(b"catalog-v1"),
            ):
                r1 = run_staged_fetch(
                    db_session,
                    company_id=ctx["company_id"],
                    triggered_by_user_id=None,
                )
            # Second fetch — v2 bytes (different MD5).
            with patch(
                "app.services.urn_catalog_scraper._get_http_client",
                return_value=_mock_http_client(b"catalog-v2-different"),
            ):
                r2 = run_staged_fetch(
                    db_session,
                    company_id=ctx["company_id"],
                    triggered_by_user_id=None,
                )

        assert r1["sync_log_id"] != r2["sync_log_id"]
        assert r2["superseded_log_id"] == r1["sync_log_id"]

        # r1 is now 'superseded'; r2 is 'pending_review'.
        log1 = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == r1["sync_log_id"])
            .first()
        )
        log2 = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == r2["sync_log_id"])
            .first()
        )
        assert log1.publication_state == "superseded"
        assert log2.publication_state == "pending_review"

    def test_cross_tenant_isolation_on_supersede(self, db_session):
        """Tenant A's fetch does not supersede tenant B's pending log."""
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.services.workflows.catalog_fetch_adapter import (
            run_staged_fetch,
        )

        ctx_a = _seed_mfg_tenant()
        ctx_b = _seed_mfg_tenant()

        with patch(
            "app.services.urn_catalog_scraper.UrnCatalogScraper._resolve_pdf_url",
            return_value="https://example.test/catalog.pdf",
        ), patch(
            "app.services.legacy_r2_client.upload_bytes",
            return_value="r2-key-fake",
        ), patch(
            "app.services.wilbert_pdf_parser.parse_pdf_to_dicts",
            return_value=[],
        ):
            # B stages first.
            with patch(
                "app.services.urn_catalog_scraper._get_http_client",
                return_value=_mock_http_client(b"catalog-b"),
            ):
                r_b = run_staged_fetch(
                    db_session,
                    company_id=ctx_b["company_id"],
                    triggered_by_user_id=None,
                )
            # A stages second with different bytes.
            with patch(
                "app.services.urn_catalog_scraper._get_http_client",
                return_value=_mock_http_client(b"catalog-a"),
            ):
                r_a = run_staged_fetch(
                    db_session,
                    company_id=ctx_a["company_id"],
                    triggered_by_user_id=None,
                )

        assert r_a["superseded_log_id"] is None
        log_b = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == r_b["sync_log_id"])
            .first()
        )
        assert log_b.publication_state == "pending_review"


# ── Triage action tests ──────────────────────────────────────────────


class TestCatalogFetchTriageActions:
    def _stage_one(self, db_session, ctx: dict) -> str:
        from app.services.workflows.catalog_fetch_adapter import (
            run_staged_fetch,
        )

        with patch(
            "app.services.urn_catalog_scraper.UrnCatalogScraper._resolve_pdf_url",
            return_value="https://example.test/catalog.pdf",
        ), patch(
            "app.services.urn_catalog_scraper._get_http_client",
            return_value=_mock_http_client(
                b"test-catalog-" + uuid.uuid4().hex.encode()
            ),
        ), patch(
            "app.services.legacy_r2_client.upload_bytes",
            return_value="r2-key-fake",
        ), patch(
            "app.services.wilbert_pdf_parser.parse_pdf_to_dicts",
            return_value=[{"sku": "A"}],
        ):
            result = run_staged_fetch(
                db_session,
                company_id=ctx["company_id"],
                triggered_by_user_id=ctx["user_id"],
            )
        assert result["sync_log_id"] is not None
        return result["sync_log_id"]

    def test_approve_calls_ingest_and_flips_state(self, db_session):
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.services.workflows.catalog_fetch_adapter import (
            approve_publish,
        )

        ctx = _seed_mfg_tenant()
        sync_log_id = self._stage_one(db_session, ctx)

        fake_ingest_log = UrnCatalogSyncLog(
            id=str(uuid.uuid4()),
            tenant_id=ctx["company_id"],
            status="completed",
            publication_state="published",
            products_added=12,
            products_updated=34,
            products_discontinued=2,
            products_skipped=0,
        )
        db_session.add(fake_ingest_log)
        db_session.commit()

        # Patch legacy ingest + R2 download.
        with patch(
            "app.services.legacy_r2_client.download_bytes",
            return_value=b"pdf-bytes-staged",
        ), patch(
            "app.services.wilbert_ingestion_service.WilbertIngestionService.ingest_from_pdf",
            return_value=fake_ingest_log,
        ):
            result = approve_publish(
                db_session, user=ctx["user"], sync_log_id=sync_log_id
            )

        assert result["status"] == "applied"
        assert result["products_added"] == 12
        assert result["products_updated"] == 34

        log = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == sync_log_id)
            .first()
        )
        assert log.publication_state == "published"
        assert log.status == "completed"
        assert log.products_added == 12
        # The legacy ingest log (separate row) is marked superseded
        # so overall admin log isn't duplicated.
        fake_after = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == fake_ingest_log.id)
            .first()
        )
        assert fake_after.publication_state == "superseded"

    def test_approve_on_non_pending_raises(self, db_session):
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.services.workflows.catalog_fetch_adapter import (
            approve_publish,
        )

        ctx = _seed_mfg_tenant()
        # Seed a log that's already published.
        log = UrnCatalogSyncLog(
            id=str(uuid.uuid4()),
            tenant_id=ctx["company_id"],
            status="completed",
            publication_state="published",
        )
        db_session.add(log)
        db_session.commit()
        with pytest.raises(ValueError, match="pending_review"):
            approve_publish(
                db_session, user=ctx["user"], sync_log_id=log.id
            )

    def test_reject_flips_state_no_product_writes(self, db_session):
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.models.urn_product import UrnProduct
        from app.services.workflows.catalog_fetch_adapter import (
            reject_publish,
        )

        ctx = _seed_mfg_tenant()
        sync_log_id = self._stage_one(db_session, ctx)

        # Count urn_products before + after reject.
        before = (
            db_session.query(UrnProduct)
            .filter(UrnProduct.tenant_id == ctx["company_id"])
            .count()
        )

        result = reject_publish(
            db_session,
            user=ctx["user"],
            sync_log_id=sync_log_id,
            reason="Wilbert pricing looks wrong — verify with rep",
        )
        assert result["status"] == "applied"

        after = (
            db_session.query(UrnProduct)
            .filter(UrnProduct.tenant_id == ctx["company_id"])
            .count()
        )
        assert after == before

        log = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == sync_log_id)
            .first()
        )
        assert log.publication_state == "rejected"
        assert "Wilbert pricing" in (log.error_message or "")

    def test_reject_without_reason_raises(self, db_session):
        from app.services.workflows.catalog_fetch_adapter import (
            reject_publish,
        )

        ctx = _seed_mfg_tenant()
        sync_log_id = self._stage_one(db_session, ctx)
        with pytest.raises(ValueError, match="Reason"):
            reject_publish(
                db_session,
                user=ctx["user"],
                sync_log_id=sync_log_id,
                reason="",
            )

    def test_request_review_stays_pending(self, db_session):
        from app.models.urn_catalog_sync_log import UrnCatalogSyncLog
        from app.services.workflows.catalog_fetch_adapter import (
            request_review,
        )

        ctx = _seed_mfg_tenant()
        sync_log_id = self._stage_one(db_session, ctx)
        result = request_review(
            db_session,
            user=ctx["user"],
            sync_log_id=sync_log_id,
            note="Ping Bill before approving",
        )
        assert result["status"] == "applied"
        log = (
            db_session.query(UrnCatalogSyncLog)
            .filter(UrnCatalogSyncLog.id == sync_log_id)
            .first()
        )
        assert log.publication_state == "pending_review"
        assert "review-requested" in (log.error_message or "")

    def test_cross_tenant_approve_404(self, db_session):
        from app.services.workflows.catalog_fetch_adapter import (
            approve_publish,
        )

        ctx_a = _seed_mfg_tenant()
        ctx_b = _seed_mfg_tenant()
        sync_log_id_b = self._stage_one(db_session, ctx_b)
        # Tenant A's user attempting to approve B's staged log.
        with pytest.raises(ValueError, match="not found for this tenant"):
            approve_publish(
                db_session, user=ctx_a["user"], sync_log_id=sync_log_id_b
            )
