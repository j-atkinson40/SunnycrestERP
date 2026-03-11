from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.ai import AIPromptRequest, AIPromptResponse
from app.services.ai_service import call_anthropic

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
