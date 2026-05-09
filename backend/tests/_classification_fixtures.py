"""Shared fixtures for Phase R-6.1a classification tests.

Two tenants, an EmailAccount per tenant, a User+Role per tenant,
and a Workflow per tenant for end-to-end cascade tests.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Iterator

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("BRIDGEABLE_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.models.company import Company  # noqa: E402
from app.models.email_classification import (  # noqa: E402
    TenantWorkflowEmailCategory,
    TenantWorkflowEmailRule,
    WorkflowEmailClassification,
)
from app.models.email_primitive import (  # noqa: E402
    EmailAccount,
    EmailMessage,
    EmailThread,
)
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workflow import Workflow  # noqa: E402


DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev"),
)
_engine = create_engine(DB_URL)
_SessionLocal = sessionmaker(bind=_engine)


@pytest.fixture
def db() -> Iterator[Session]:
    s = _SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def tenant_pair(db: Session) -> Iterator[tuple[Company, Company]]:
    sfx = _suffix()
    a = Company(
        id=str(uuid.uuid4()),
        name=f"R6.1a Tenant A {sfx}",
        slug=f"r61a-a-{sfx}",
        is_active=True,
        vertical="manufacturing",
    )
    b = Company(
        id=str(uuid.uuid4()),
        name=f"R6.1a Tenant B {sfx}",
        slug=f"r61a-b-{sfx}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add_all([a, b])
    db.commit()

    yield a, b

    db.rollback()
    # Cleanup tenant-scoped descendants.
    cleanup_tables = [
        "workflow_email_classifications",
        "tenant_workflow_email_categories",
        "tenant_workflow_email_rules",
        "email_messages",
        "email_threads",
        "email_accounts",
        "users",
        "roles",
        "workflows",
    ]
    for t in cleanup_tables:
        for cid in (a.id, b.id):
            try:
                col = "tenant_id"
                if t in (
                    "workflows",
                    "users",
                    "roles",
                ):
                    col = "company_id"
                db.execute(
                    sql_text(f"DELETE FROM {t} WHERE {col} = :cid"),
                    {"cid": cid},
                )
                db.commit()
            except Exception:
                db.rollback()
    for cid in (a.id, b.id):
        try:
            db.execute(
                sql_text("DELETE FROM companies WHERE id = :cid"),
                {"cid": cid},
            )
            db.commit()
        except Exception:
            db.rollback()


@pytest.fixture
def admin_user(db: Session, tenant_pair: tuple[Company, Company]) -> User:
    """Returns admin user in tenant A."""
    a, _b = tenant_pair
    role = Role(
        id=str(uuid.uuid4()),
        company_id=a.id,
        name="Admin",
        slug="admin",
    )
    db.add(role)
    db.commit()
    user = User(
        id=str(uuid.uuid4()),
        company_id=a.id,
        email=f"admin-{_suffix()}@r61a.test",
        first_name="Admin",
        last_name="User",
        hashed_password="x",
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_email_account(db: Session, tenant: Company) -> EmailAccount:
    acct = EmailAccount(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        provider_type="gmail",
        account_type="shared",
        email_address=f"ops+{_suffix()}@r61a.test",
        display_name="R6.1a Ops",
        is_active=True,
        provider_config={},
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct


def make_workflow(
    db: Session,
    tenant: Company | None,
    *,
    name: str | None = None,
    tier3_enrolled: bool = False,
    description: str | None = None,
) -> Workflow:
    """Create an email_classification-triggerable workflow.

    ``tenant=None`` creates a platform-global workflow visible to
    every tenant.
    """
    wf = Workflow(
        id=str(uuid.uuid4()),
        company_id=tenant.id if tenant else None,
        name=name or f"Test workflow {_suffix()}",
        description=description,
        tier=2 if tenant is not None else 1,
        scope="tenant" if tenant else "core",
        vertical=tenant.vertical if tenant else None,
        trigger_type="email_classification",
        trigger_config={},
        is_active=True,
        tier3_enrolled=tier3_enrolled,
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


def make_inbound_email(
    db: Session,
    *,
    tenant: Company,
    account: EmailAccount,
    sender_email: str = "fh@hopkins.example.com",
    sender_name: str = "Mary Hopkins",
    subject: str = "Disinterment for Smith family",
    body_text: str = "Hi, please process the disinterment release.",
    direction: str = "inbound",
    message_payload: dict | None = None,
) -> EmailMessage:
    thread = EmailThread(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        account_id=account.id,
        subject=subject,
        participants_summary=[sender_email.lower()],
        first_message_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        message_count=1,
    )
    db.add(thread)
    db.flush()

    msg = EmailMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        tenant_id=tenant.id,
        account_id=account.id,
        provider_message_id=f"pm-{thread.id[:8]}",
        sender_email=sender_email.lower(),
        sender_name=sender_name,
        subject=subject,
        body_text=body_text,
        received_at=datetime.now(timezone.utc),
        direction=direction,
        message_payload=message_payload or {},
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def make_rule(
    db: Session,
    tenant: Company,
    *,
    priority: int,
    name: str = "Test rule",
    match_conditions: dict | None = None,
    fire_workflow_id: str | None = None,
    is_active: bool = True,
) -> TenantWorkflowEmailRule:
    rule = TenantWorkflowEmailRule(
        tenant_id=tenant.id,
        priority=priority,
        name=name,
        match_conditions=match_conditions or {},
        fire_action={"workflow_id": fire_workflow_id},
        is_active=is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def make_category(
    db: Session,
    tenant: Company,
    *,
    label: str,
    description: str | None = None,
    mapped_workflow_id: str | None = None,
    parent_id: str | None = None,
    is_active: bool = True,
) -> TenantWorkflowEmailCategory:
    cat = TenantWorkflowEmailCategory(
        tenant_id=tenant.id,
        parent_id=parent_id,
        label=label,
        description=description,
        mapped_workflow_id=mapped_workflow_id,
        position=0,
        is_active=is_active,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def make_intelligence_result(
    *,
    status: str = "success",
    response_parsed: dict | None = None,
    error_message: str | None = None,
):
    """Build a stub IntelligenceResult matching the canonical shape
    declared in app/services/intelligence/intelligence_service.py."""
    from app.services.intelligence.intelligence_service import IntelligenceResult

    return IntelligenceResult(
        execution_id=f"exec-{_suffix()}",
        prompt_id=None,
        prompt_version_id=None,
        model_used="claude-haiku-4-5-20250514",
        status=status,
        response_text=None,
        response_parsed=response_parsed,
        rendered_system_prompt="",
        rendered_user_prompt="",
        input_tokens=100,
        output_tokens=20,
        latency_ms=350,
        cost_usd=None,
        experiment_variant=None,
        fallback_used=False,
        error_message=error_message,
        extra={},
    )
