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
