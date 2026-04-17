"""Credential service — Fernet-encrypted external account credentials.

Credentials are never stored or logged in plaintext. The encryption key
is read from the CREDENTIAL_ENCRYPTION_KEY environment variable at
runtime. If the variable is not set, calls raise ValueError with a
clear message so the operator knows what to configure.

Key generation (run once, store in Railway env vars):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.models.tenant_external_account import TenantExternalAccount


def _get_fernet() -> Fernet:
    key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise ValueError(
            "CREDENTIAL_ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\" and add it to your environment."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


# ─────────────────────────────────────────────────────────── public API

def store_credentials(
    db: Session,
    *,
    company_id: str,
    service_key: str,
    service_name: str,
    credentials: dict[str, str],
    created_by_user_id: str | None = None,
) -> TenantExternalAccount:
    """Encrypt and store credentials for a tenant + service pair.

    ``credentials`` is a plain dict, e.g. ``{"username": "me@co.com",
    "password": "s3cret"}``. Values are encrypted; keys are stored as
    ``credential_fields`` so the UI can show *which* fields are saved
    without revealing values.

    Calling again for an existing (company_id, service_key) pair
    overwrites and clears ``last_verified_at``.
    """
    f = _get_fernet()
    encrypted = f.encrypt(json.dumps(credentials).encode()).decode()

    existing = (
        db.query(TenantExternalAccount)
        .filter(
            TenantExternalAccount.company_id == company_id,
            TenantExternalAccount.service_key == service_key,
        )
        .first()
    )
    if existing:
        existing.encrypted_credentials = encrypted
        existing.credential_fields = list(credentials.keys())
        existing.last_verified_at = None
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    account = TenantExternalAccount(
        id=str(uuid.uuid4()),
        company_id=company_id,
        service_name=service_name,
        service_key=service_key,
        encrypted_credentials=encrypted,
        credential_fields=list(credentials.keys()),
        created_by_user_id=created_by_user_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_credentials(
    db: Session,
    *,
    company_id: str,
    service_key: str,
) -> dict[str, str] | None:
    """Retrieve and decrypt credentials. Returns None if not configured."""
    account = (
        db.query(TenantExternalAccount)
        .filter(
            TenantExternalAccount.company_id == company_id,
            TenantExternalAccount.service_key == service_key,
            TenantExternalAccount.is_active.is_(True),
        )
        .first()
    )
    if not account:
        return None
    try:
        f = _get_fernet()
        decrypted = f.decrypt(account.encrypted_credentials.encode())
        return json.loads(decrypted)
    except (InvalidToken, ValueError, Exception):
        return None


def mark_verified(db: Session, *, company_id: str, service_key: str) -> bool:
    account = (
        db.query(TenantExternalAccount)
        .filter(
            TenantExternalAccount.company_id == company_id,
            TenantExternalAccount.service_key == service_key,
            TenantExternalAccount.is_active.is_(True),
        )
        .first()
    )
    if not account:
        return False
    account.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    return True


def list_accounts(db: Session, *, company_id: str) -> list[TenantExternalAccount]:
    return (
        db.query(TenantExternalAccount)
        .filter(
            TenantExternalAccount.company_id == company_id,
            TenantExternalAccount.is_active.is_(True),
        )
        .order_by(TenantExternalAccount.service_name.asc())
        .all()
    )


def soft_delete(db: Session, *, account: TenantExternalAccount) -> None:
    account.is_active = False
    db.commit()


def serialize(account: TenantExternalAccount) -> dict[str, Any]:
    """Return a safe dict — never exposes encrypted_credentials value."""
    return {
        "id": account.id,
        "service_name": account.service_name,
        "service_key": account.service_key,
        "credential_fields": account.credential_fields or [],
        "last_verified_at": (
            account.last_verified_at.isoformat()
            if account.last_verified_at
            else None
        ),
        "is_active": account.is_active,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }
