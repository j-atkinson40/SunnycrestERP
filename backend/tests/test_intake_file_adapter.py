"""Phase R-6.2a — File intake adapter unit + integration tests.

Covers:
  - Three-scope resolver for file configs
  - presign_file_upload: cap validation + R2 client integration
  - complete_file_upload: persistence + cascade hook
  - canonical R2 key construction from template
"""

from __future__ import annotations

import uuid

import pytest

from tests._classification_fixtures import (  # noqa: F401
    db,
    tenant_pair,
)
from app.models.intake_file_configuration import IntakeFileConfiguration
from app.models.intake_file_upload import IntakeFileUpload
from app.services.intake import (
    FileUploadPayload,
    IntakeValidationError,
    complete_file_upload,
    presign_file_upload,
    resolve_file_config,
)


# ── Three-scope resolver ────────────────────────────────────────────


def test_resolve_file_config_returns_seeded_death_certificate(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    config = resolve_file_config(db, slug="death-certificate", tenant=a)
    assert config is not None
    assert config.scope == "vertical_default"
    assert config.allowed_content_types == ["application/pdf"]


def test_resolve_file_config_tenant_override_wins(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    override = IntakeFileConfiguration(
        id=str(uuid.uuid4()),
        tenant_id=a.id,
        vertical=None,
        scope="tenant_override",
        name="Hopkins death cert (custom)",
        slug="death-certificate",
        allowed_content_types=["application/pdf", "image/jpeg"],
        max_file_size_bytes=20 * 1024 * 1024,
        max_file_count=2,
        r2_key_prefix_template=(
            "tenants/{tenant_id}/intake/{adapter_slug}/{upload_id}"
        ),
        metadata_schema={},
        is_active=True,
    )
    db.add(override)
    db.commit()

    config = resolve_file_config(db, slug="death-certificate", tenant=a)
    assert config is not None
    assert config.scope == "tenant_override"
    assert "image/jpeg" in config.allowed_content_types

    db.delete(override)
    db.commit()


# ── presign_file_upload ─────────────────────────────────────────────


def _setup_funeral_tenant(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    return a


def _stub_presign(monkeypatch):
    """Stub R2 presign so tests don't depend on R2 configuration."""
    from app.services import legacy_r2_client

    def _fake_presign(r2_key, *, content_type, expires_in, max_size_bytes=None):
        return {
            "url": f"https://r2.example.com/{r2_key}?presigned=1",
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "key": r2_key,
        }

    monkeypatch.setattr(
        legacy_r2_client,
        "generate_presigned_upload_url",
        _fake_presign,
        raising=True,
    )


def test_presign_file_upload_happy_path(db, tenant_pair, monkeypatch):
    a = _setup_funeral_tenant(db, tenant_pair)
    _stub_presign(monkeypatch)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    signed = presign_file_upload(
        db,
        config=config,
        original_filename="smith_death_cert.pdf",
        content_type="application/pdf",
        size_bytes=1024 * 1024,
        tenant_id=a.id,
    )
    assert signed["upload_id"]
    assert signed["url"].startswith("https://r2.example.com/")
    assert signed["method"] == "PUT"
    assert signed["headers"]["Content-Type"] == "application/pdf"
    # R2 key follows canonical prefix template.
    assert a.id in signed["r2_key"]
    assert "death-certificate" in signed["r2_key"]
    assert "smith_death_cert.pdf" in signed["r2_key"]


def test_presign_rejects_disallowed_content_type(db, tenant_pair, monkeypatch):
    a = _setup_funeral_tenant(db, tenant_pair)
    _stub_presign(monkeypatch)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    with pytest.raises(IntakeValidationError) as exc:
        presign_file_upload(
            db,
            config=config,
            original_filename="malicious.exe",
            content_type="application/x-msdownload",
            size_bytes=1024,
            tenant_id=a.id,
        )
    assert "allowed" in str(exc.value).lower()


def test_presign_rejects_oversize_file(db, tenant_pair, monkeypatch):
    a = _setup_funeral_tenant(db, tenant_pair)
    _stub_presign(monkeypatch)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    with pytest.raises(IntakeValidationError):
        presign_file_upload(
            db,
            config=config,
            original_filename="huge.pdf",
            content_type="application/pdf",
            size_bytes=20 * 1024 * 1024,  # exceeds 10MB cap
            tenant_id=a.id,
        )


def test_presign_rejects_missing_size(db, tenant_pair, monkeypatch):
    a = _setup_funeral_tenant(db, tenant_pair)
    _stub_presign(monkeypatch)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    with pytest.raises(IntakeValidationError):
        presign_file_upload(
            db,
            config=config,
            original_filename="cert.pdf",
            content_type="application/pdf",
            size_bytes=0,
            tenant_id=a.id,
        )


# ── complete_file_upload ────────────────────────────────────────────


def test_complete_file_upload_persists_upload(db, tenant_pair, monkeypatch):
    a = _setup_funeral_tenant(db, tenant_pair)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    # Stub cascade.
    from app.services.classification import dispatch as dispatch_mod

    def _stub_cascade(db, *, upload, config):
        return {"tier": None}

    monkeypatch.setattr(
        dispatch_mod, "classify_and_fire_file", _stub_cascade, raising=True
    )

    canonical_key = (
        f"tenants/{a.id}/intake/death-certificate/"
        f"{uuid.uuid4()}/smith.pdf"
    )
    payload = FileUploadPayload(
        r2_key=canonical_key,
        original_filename="smith.pdf",
        content_type="application/pdf",
        size_bytes=500_000,
        uploader_metadata={"uploader_email": "mary@hopkins.example.com"},
    )

    upload = complete_file_upload(
        db,
        config=config,
        payload=payload,
        tenant_id=a.id,
        verify_r2_head=False,
    )
    db.commit()

    assert upload.id
    assert upload.tenant_id == a.id
    assert upload.config_id == config.id
    assert upload.r2_key == canonical_key
    assert upload.original_filename == "smith.pdf"

    fresh = (
        db.query(IntakeFileUpload)
        .filter(IntakeFileUpload.id == upload.id)
        .first()
    )
    assert fresh is not None
    assert fresh.uploader_metadata["uploader_email"] == (
        "mary@hopkins.example.com"
    )


def test_complete_rejects_forged_r2_key(db, tenant_pair, monkeypatch):
    """Defense-in-depth — completion endpoint validates r2_key starts
    with the canonical template prefix to prevent forged-key abuse."""
    a = _setup_funeral_tenant(db, tenant_pair)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    forged_key = "tenants/other-tenant/intake/death-certificate/abc/smith.pdf"
    payload = FileUploadPayload(
        r2_key=forged_key,
        original_filename="smith.pdf",
        content_type="application/pdf",
        size_bytes=500_000,
    )
    with pytest.raises(IntakeValidationError):
        complete_file_upload(
            db,
            config=config,
            payload=payload,
            tenant_id=a.id,
            verify_r2_head=False,
        )


def test_complete_rejects_oversize_payload(db, tenant_pair, monkeypatch):
    a = _setup_funeral_tenant(db, tenant_pair)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    canonical_key = (
        f"tenants/{a.id}/intake/death-certificate/"
        f"{uuid.uuid4()}/smith.pdf"
    )
    payload = FileUploadPayload(
        r2_key=canonical_key,
        original_filename="smith.pdf",
        content_type="application/pdf",
        size_bytes=20 * 1024 * 1024,  # 20MB > 10MB cap
    )
    with pytest.raises(IntakeValidationError):
        complete_file_upload(
            db,
            config=config,
            payload=payload,
            tenant_id=a.id,
            verify_r2_head=False,
        )


def test_complete_rejects_disallowed_content_type(db, tenant_pair):
    a = _setup_funeral_tenant(db, tenant_pair)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    canonical_key = (
        f"tenants/{a.id}/intake/death-certificate/"
        f"{uuid.uuid4()}/x.exe"
    )
    payload = FileUploadPayload(
        r2_key=canonical_key,
        original_filename="x.exe",
        content_type="application/x-msdownload",
        size_bytes=1000,
    )
    with pytest.raises(IntakeValidationError):
        complete_file_upload(
            db,
            config=config,
            payload=payload,
            tenant_id=a.id,
            verify_r2_head=False,
        )


def test_complete_cascade_failure_does_not_block_persistence(
    db, tenant_pair, monkeypatch
):
    a = _setup_funeral_tenant(db, tenant_pair)
    config = resolve_file_config(db, slug="death-certificate", tenant=a)

    from app.services.classification import dispatch as dispatch_mod

    def _failing(db, *, upload, config):
        raise RuntimeError("cascade down")

    monkeypatch.setattr(
        dispatch_mod, "classify_and_fire_file", _failing, raising=True
    )

    canonical_key = (
        f"tenants/{a.id}/intake/death-certificate/"
        f"{uuid.uuid4()}/smith.pdf"
    )
    payload = FileUploadPayload(
        r2_key=canonical_key,
        original_filename="smith.pdf",
        content_type="application/pdf",
        size_bytes=500_000,
    )
    upload = complete_file_upload(
        db,
        config=config,
        payload=payload,
        tenant_id=a.id,
        verify_r2_head=False,
    )
    db.commit()
    assert upload.id


def test_complete_personalization_documents_accepts_multiple_types(
    db, tenant_pair, monkeypatch
):
    """personalization-documents config allows PDF/JPEG/PNG."""
    a = _setup_funeral_tenant(db, tenant_pair)
    config = resolve_file_config(
        db, slug="personalization-documents", tenant=a
    )
    assert "image/jpeg" in config.allowed_content_types

    from app.services.classification import dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "classify_and_fire_file",
        lambda db, *, upload, config: {"tier": None},
        raising=True,
    )

    canonical_key = (
        f"tenants/{a.id}/intake/personalization-documents/"
        f"{uuid.uuid4()}/photo.jpg"
    )
    payload = FileUploadPayload(
        r2_key=canonical_key,
        original_filename="photo.jpg",
        content_type="image/jpeg",
        size_bytes=500_000,
    )
    upload = complete_file_upload(
        db,
        config=config,
        payload=payload,
        tenant_id=a.id,
        verify_r2_head=False,
    )
    assert upload.content_type == "image/jpeg"
