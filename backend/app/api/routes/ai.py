import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_permission
from app.database import get_db

logger = logging.getLogger(__name__)
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
from app.services.ai_manufacturing_intents import parse_manufacturing_command
from app.services.ai_funeral_home_intents import (
    classify_funeral_home_intent,
    dispatch_funeral_home_intent,
)

router = APIRouter()


@router.post("/prompt", response_model=AIPromptResponse)
def ai_prompt(
    request: AIPromptRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    DEPRECATED — sunset planned 2027-04-18.

    Phase 2c-5 status:
      - Endpoint still functional for the 1 frontend allowlisted caller
        (AICommandBar on pages/products.tsx).
      - Internally routed through the managed `legacy.arbitrary_prompt` prompt
        via `intelligence_service.execute()` — every call now produces a real
        audit row with `prompt_id` set (no more `caller_module="legacy"` rows).
      - Deprecation + Sunset headers remain for consumer visibility.
      - This endpoint is the reason `legacy.arbitrary_prompt` exists; that
        prompt will be sunset alongside the endpoint.

    Callers that need new AI functionality MUST create a dedicated managed
    prompt instead of using this endpoint.
    """
    import json as _json

    from app.services.intelligence import intelligence_service

    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Sun, 18 Apr 2027 00:00:00 GMT"
    response.headers["Link"] = (
        '</docs/intelligence>; rel="deprecation"; '
        'type="text/html"'
    )
    logger.warning(
        "Deprecated endpoint /ai/prompt called by user=%s company=%s — "
        "planned for removal 2027-04-18; migrate to intelligence_service.execute "
        "with a managed prompt_key.",
        current_user.id,
        current_user.company_id,
    )

    intel = intelligence_service.execute(
        db,
        prompt_key="legacy.arbitrary_prompt",
        variables={
            "system_prompt": request.system_prompt,
            "user_message": request.user_message,
            "context_data_json": _json.dumps(request.context_data, default=str)
            if request.context_data
            else "",
        },
        company_id=current_user.company_id,
        caller_module="ai.ai_prompt",
        caller_entity_type=None,
    )
    if intel.status != "success" or not isinstance(intel.response_parsed, dict):
        return AIPromptResponse(
            success=False,
            error=intel.error_message or f"status={intel.status}",
        )
    return AIPromptResponse(success=True, data=intel.response_parsed)


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

    # Phase 2c-5 migration — managed extraction.inventory_command prompt
    import json as _json

    from app.services.intelligence import intelligence_service

    intel = intelligence_service.execute(
        db,
        prompt_key="extraction.inventory_command",
        variables={
            "user_input": request.user_input,
            "context_data_json": _json.dumps({"product_catalog": catalog}),
        },
        company_id=current_user.company_id,
        caller_module="ai.parse_inventory",
        caller_entity_type=None,
    )
    if intel.status != "success" or not isinstance(intel.response_parsed, dict):
        return AIInventoryParseResponse(
            success=False, error=intel.error_message or f"status={intel.status}"
        )
    result = intel.response_parsed

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

    # Phase 2c-5 migration — managed extraction.ap_command prompt
    import json as _json

    from app.services.intelligence import intelligence_service

    intel = intelligence_service.execute(
        db,
        prompt_key="extraction.ap_command",
        variables={
            "user_input": request.user_input,
            "context_data_json": _json.dumps({"vendor_catalog": catalog}),
        },
        company_id=current_user.company_id,
        caller_module="ai.parse_ap",
        caller_entity_type=None,
    )
    if intel.status != "success" or not isinstance(intel.response_parsed, dict):
        return AIAPParseResponse(
            success=False, error=intel.error_message or f"status={intel.status}"
        )
    parsed = AIAPParsedResult(**intel.response_parsed)
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
        db=db,
        company_id=current_user.company_id,
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
