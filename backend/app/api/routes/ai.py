from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_permission
from app.database import get_db
from app.models.customer import Customer
from app.models.product import Product
from app.models.user import User
from app.models.vendor import Vendor
from app.models.company import Company
from app.schemas.ai import (
    AIAPParseRequest,
    AIAPParseResponse,
    AIAPParsedResult,
    AIFuneralHomeCommandRequest,
    AIFuneralHomeCommandResponse,
    AIInventoryParseRequest,
    AIInventoryParseResponse,
    AIInventoryParsedCommand,
    AIManufacturingCommandRequest,
    AIManufacturingCommandResponse,
    AIPromptRequest,
    AIPromptResponse,
)
from app.services.ai_service import call_anthropic, parse_ap_command, parse_inventory_command
from app.services.ai_manufacturing_intents import parse_manufacturing_command
from app.services.ai_funeral_home_intents import (
    classify_funeral_home_intent,
    dispatch_funeral_home_intent,
)

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


@router.post("/command", response_model=AIManufacturingCommandResponse)
def ai_manufacturing_command(
    request: AIManufacturingCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Parse a natural-language manufacturing command into a structured intent.

    This is the primary AI command-bar endpoint for manufacturing tenants.
    It classifies the user's prompt into one of the supported intents
    (log_production, check_inventory, create_order, record_payment,
    log_training, log_incident) and returns structured data for the
    frontend to render a confirmation card or inline result.
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
    product_catalog = [
        {"id": str(p.id), "name": p.name, "sku": p.sku}
        for p in products
    ]

    # Build customer catalog
    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == current_user.company_id,
            Customer.is_active == True,  # noqa: E712
        )
        .all()
    )
    customer_catalog = [
        {"id": str(c.id), "name": c.name}
        for c in customers
    ]

    # Build employee names list
    employee_users = (
        db.query(User)
        .filter(
            User.company_id == current_user.company_id,
            User.is_active == True,  # noqa: E712
        )
        .all()
    )
    employee_names = [u.first_name for u in employee_users if u.first_name]

    result = parse_manufacturing_command(
        user_input=request.prompt,
        product_catalog=product_catalog,
        customer_catalog=customer_catalog,
        employee_names=employee_names,
    )

    intent = result.get("intent", "unknown")
    message = result.get("message", "")

    return AIManufacturingCommandResponse(
        success=True,
        intent=intent,
        data=result,
        message=message,
    )


@router.post("/fh-command", response_model=AIFuneralHomeCommandResponse)
def ai_funeral_home_command(
    request: AIFuneralHomeCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Parse a natural-language funeral home command into a structured intent.

    This is the primary AI command-bar endpoint for funeral home tenants.
    It classifies the user's prompt into one of the supported intents
    (open_case, update_case_status, order_vault, record_payment,
    send_family_portal, update_service_details, check_case_status,
    cremation_auth_signed, cremation_scheduled, cremation_complete,
    remains_released) and returns structured data for the frontend
    to render a confirmation card or inline result.
    """
    # Verify this tenant is a funeral home
    company = (
        db.query(Company)
        .filter(Company.id == current_user.company_id)
        .first()
    )
    tenant_vertical = company.vertical if company else None

    if tenant_vertical != "funeral_home":
        return AIFuneralHomeCommandResponse(
            success=False,
            error="This endpoint is only available for funeral home tenants.",
        )

    # Try keyword-based classification first (fast, no API call)
    intent = classify_funeral_home_intent(request.prompt)

    if intent:
        result = dispatch_funeral_home_intent(
            intent_key=intent["key"],
            prompt=request.prompt,
            tenant_id=str(current_user.company_id),
            user_id=str(current_user.id),
        )
        return AIFuneralHomeCommandResponse(
            success=True,
            intent=result.get("intent", "unknown"),
            data=result.get("extracted"),
            message=result.get("message", ""),
            action_type=result.get("action_type", "confirm"),
            uncertain_fields=result.get("uncertain_fields"),
        )

    # No keyword match — fall through to generic AI prompt
    return AIFuneralHomeCommandResponse(
        success=True,
        intent="unknown",
        message="I'm not sure what you'd like to do. Try something like: 'First call from the Johnson family'",
        action_type="inline",
    )
