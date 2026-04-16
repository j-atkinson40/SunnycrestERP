"""Configurable Item Registry API routes.

Manage master lists of configurable items (compliance, equipment,
training, etc.) with per-tenant enable/disable and custom items.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class EnableItemRequest(BaseModel):
    config: Optional[dict] = None


class CreateCustomItemRequest(BaseModel):
    display_name: str
    description: Optional[str] = None
    config: Optional[dict] = None


class UpdateItemConfigRequest(BaseModel):
    config: Optional[dict] = None
    display_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{type}/master-list")
def get_master_list(
    type: str,
    vertical: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get full master list for a registry type."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        items = ConfigurableItemService.get_master_list(
            db, type, vertical=vertical, tags=tag_list
        )
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{type}/tenant-config")
def get_tenant_config(
    type: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get tenant's current configuration for a registry type."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        config = ConfigurableItemService.get_tenant_config(db, company.id, type)
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{type}/{item_key}/enable")
def enable_item(
    type: str,
    item_key: str,
    data: Optional[EnableItemRequest] = None,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Enable an item from the master list."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        config = data.config if data else None
        result = ConfigurableItemService.enable_item(
            db, company.id, type, item_key, config=config
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{type}/{item_key}/disable")
def disable_item(
    type: str,
    item_key: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Disable an item."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        result = ConfigurableItemService.disable_item(db, company.id, type, item_key)
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{type}/custom", status_code=201)
def create_custom_item(
    type: str,
    data: CreateCustomItemRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a custom item for this tenant."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        result = ConfigurableItemService.create_custom_item(
            db,
            company.id,
            type,
            display_name=data.display_name,
            description=data.description,
            config=data.config,
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{type}/{item_key}")
def update_item_config(
    type: str,
    item_key: str,
    data: UpdateItemConfigRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update config or display name for an item."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        result = ConfigurableItemService.update_item_config(
            db,
            company.id,
            type,
            item_key,
            config=data.config,
            display_name=data.display_name,
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{type}/{item_key}")
def delete_custom_item(
    type: str,
    item_key: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Remove a custom item (only custom items can be deleted)."""
    try:
        from app.services.configurable_item_service import ConfigurableItemService

        ConfigurableItemService.delete_custom_item(db, company.id, type, item_key)
        db.commit()
        return {"status": "ok", "item_key": item_key}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
