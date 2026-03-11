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
