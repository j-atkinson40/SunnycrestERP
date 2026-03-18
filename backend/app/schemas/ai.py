from pydantic import BaseModel, Field


class AIPromptRequest(BaseModel):
    system_prompt: str = Field(..., min_length=1, description="System prompt for the AI")
    user_message: str = Field(..., min_length=1, description="User's message/question")
    context_data: dict | None = Field(
        default=None, description="Optional context data for the AI"
    )


class AIPromptResponse(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Inventory-specific AI schemas
# ---------------------------------------------------------------------------


class AIInventoryParseRequest(BaseModel):
    user_input: str = Field(
        ..., min_length=1, description="Natural language inventory command"
    )


class AIInventoryParsedCommand(BaseModel):
    action: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    product_sku: str | None = None
    quantity: int | None = None
    location: str | None = None
    reference: str | None = None
    reason: str | None = None
    notes: str | None = None
    confidence: str = "low"
    ambiguous: bool = False
    clarification_message: str | None = None


class AIInventoryParseResponse(BaseModel):
    success: bool
    command: AIInventoryParsedCommand | None = None
    commands: list[AIInventoryParsedCommand] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# AP / Purchasing AI schemas
# ---------------------------------------------------------------------------


class AIAPParseRequest(BaseModel):
    user_input: str = Field(
        ..., min_length=1, description="Natural language AP / purchasing command"
    )


class AIAPParsedResult(BaseModel):
    intent: str | None = None  # create_po, create_bill, query_aging, record_payment
    vendor_name: str | None = None
    vendor_id: str | None = None
    items: list[dict] | None = None  # [{description, quantity, unit_cost}]
    invoice_number: str | None = None
    amount: float | None = None
    payment_method: str | None = None
    reference_number: str | None = None
    date: str | None = None
    notes: str | None = None
    confidence: str = "low"
    ambiguous: bool = False
    clarification_message: str | None = None


class AIAPParseResponse(BaseModel):
    success: bool
    result: AIAPParsedResult | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Manufacturing AI command schemas
# ---------------------------------------------------------------------------


class AIManufacturingCommandRequest(BaseModel):
    prompt: str = Field(
        ..., min_length=1, description="Natural language manufacturing command"
    )


class AIManufacturingCommandResponse(BaseModel):
    success: bool
    intent: str | None = None
    data: dict | None = None
    message: str | None = None
    error: str | None = None
