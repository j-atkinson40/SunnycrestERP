"""Plaid routes (B-1) — the connect moment, tenant-admin gated.

ISOLATION FIRST: every handler scopes by current_user.company_id inside
the service query; wrong-tenant ids return 404 indistinguishable from
absent. NO response shape carries a token — ``item_summary`` is the only
serializer, and it has no token field by design.

Gating: reads = any tenant user (the setup card's connected state is
visible to everyone; non-admins see who to ask before connecting).
Mutations (link-token, exchange) = tenant admin.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services.plaid import service as plaid_service
from app.services.plaid.client import PlaidApiError, PlaidNotConfiguredError
from app.services.plaid.crypto import PlaidCredentialEncryptionError
from app.services.plaid.service import PlaidNotFoundError

router = APIRouter()


class ExchangeRequest(BaseModel):
    public_token: str
    institution_id: str | None = None
    institution_name: str | None = None


class LinkTokenRequest(BaseModel):
    # UPDATE MODE (re-auth): pass the degraded item's id — the server
    # decrypts its token; the raw token never leaves the backend.
    item_id: str | None = None


def _http_from_plaid_error(exc: PlaidApiError) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "code": "plaid_error",
            "error_type": exc.error_type,
            "error_code": exc.error_code,
            "message": exc.display_message
            or "The bank connection service returned an error.",
            "request_id": exc.request_id,
        },
    )


@router.get("/items")
def list_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tenant's connections + accounts — the setup card's read."""
    items = plaid_service.list_items(db, tenant_id=current_user.company_id)
    return [
        plaid_service.item_summary(
            item,
            plaid_service.list_accounts(
                db, tenant_id=current_user.company_id, item_id=item.id
            ),
        )
        for item in items
    ]


@router.get("/items/{item_id}")
def get_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        item = plaid_service.get_item(
            db, tenant_id=current_user.company_id, item_id=item_id
        )
        accounts = plaid_service.list_accounts(
            db, tenant_id=current_user.company_id, item_id=item_id
        )
    except PlaidNotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")
    return plaid_service.item_summary(item, accounts)


@router.post("/link-token")
def create_link_token(
    body: LinkTokenRequest | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.services.plaid import client as plaid_client

    access_token = None
    if body and body.item_id:
        try:
            item = plaid_service.get_item(
                db, tenant_id=current_user.company_id, item_id=body.item_id
            )
        except PlaidNotFoundError:
            raise HTTPException(status_code=404, detail="Connection not found")
        try:
            access_token = plaid_service.access_token_for(item)
        except PlaidCredentialEncryptionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    try:
        resp = plaid_client.create_link_token(
            client_user_id=current_user.id, access_token=access_token,
        )
    except PlaidNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PlaidApiError as exc:
        raise _http_from_plaid_error(exc)
    return {"link_token": resp["link_token"], "expiration": resp.get("expiration")}


@router.post("/exchange")
def exchange_public_token(
    body: ExchangeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        item = plaid_service.record_item_from_exchange(
            db,
            tenant_id=current_user.company_id,
            public_token=body.public_token,
            institution_id=body.institution_id,
            institution_name=body.institution_name,
        )
    except PlaidNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PlaidCredentialEncryptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PlaidApiError as exc:
        raise _http_from_plaid_error(exc)
    accounts = plaid_service.list_accounts(
        db, tenant_id=current_user.company_id, item_id=item.id
    )
    return plaid_service.item_summary(item, accounts)
