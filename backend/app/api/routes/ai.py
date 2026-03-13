from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_permission
from app.database import get_db
from app.models.product import Product
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.ai import (
    AIAPParseRequest,
    AIAPParseResponse,
    AIAPParsedResult,
    AIInventoryParseRequest,
    AIInventoryParseResponse,
    AIInventoryParsedCommand,
    AIPromptRequest,
    AIPromptResponse,
)
from app.services.ai_service import call_anthropic, parse_ap_command, parse_inventory_command

router = APIRouter()


@router.post("/prompt", response_model=AIPromptResponse)
def ai_prompt(
    request: AIPromptRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Send a prompt to the AI service and return structured JSON response.
    Requires authentication (any logged-in user).
    """
    result = call_anthropic(
        system_prompt=request.system_prompt,
        user_message=request.user_message,
        context_data=request.context_data,
    )
    return AIPromptResponse(success=True, data=result)


@router.post("/parse-inventory", response_model=AIInventoryParseResponse)
def parse_inventory(
    request: AIInventoryParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.create")),
    _module: User = Depends(require_module("inventory")),
):
    """
    Parse a natural-language inventory command into structured data.
    Requires inventory.create permission and the inventory module.
    """
    # Build product catalog for the user's company
    products = (
        db.query(Product)
        .filter(
            Product.company_id == current_user.company_id,
            Product.is_active == True,  # noqa: E712
        )
        .all()
    )
    catalog = [
        {"id": p.id, "name": p.name, "sku": p.sku}
        for p in products
    ]

    result = parse_inventory_command(request.user_input, catalog)

    # Handle multi-product commands
    if "commands" in result and isinstance(result["commands"], list):
        commands = [AIInventoryParsedCommand(**cmd) for cmd in result["commands"]]
        return AIInventoryParseResponse(success=True, commands=commands)

    # Single command
    command = AIInventoryParsedCommand(**result)
    return AIInventoryParseResponse(success=True, command=command)


@router.post("/parse-ap", response_model=AIAPParseResponse)
def parse_ap(
    request: AIAPParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("ap.view")),
    _module: User = Depends(require_module("purchasing")),
):
    """
    Parse a natural-language AP / purchasing command into structured data.
    Requires ap.view permission and the purchasing module.
    """
    # Build vendor catalog for the user's company
    vendors = (
        db.query(Vendor)
        .filter(
            Vendor.company_id == current_user.company_id,
            Vendor.is_active == True,  # noqa: E712
        )
        .all()
    )
    catalog = [{"id": v.id, "name": v.name} for v in vendors]

    result = parse_ap_command(request.user_input, catalog)
    parsed = AIAPParsedResult(**result)
    return AIAPParseResponse(success=True, result=parsed)
