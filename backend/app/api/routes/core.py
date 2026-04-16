"""Core UI API routes — command bar, recent actions, action logging."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import core_command_service

router = APIRouter()


class CommandContext(BaseModel):
    current_route: Optional[str] = None
    recent_actions: Optional[list[str]] = None
    user_role: Optional[str] = None
    time_of_day: Optional[str] = None


class CommandRequest(BaseModel):
    input: str
    context: Optional[CommandContext] = None


class LogActionRequest(BaseModel):
    action_id: str
    raw_input: Optional[str] = None
    result_title: str
    result_type: str
    action_data: Optional[dict] = None
    input_method: str = "keyboard"


@router.post("/command")
def process_command(
    request: CommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process natural language command input. Returns ranked results with actions."""
    context = {}
    if request.context:
        context = request.context.model_dump(exclude_none=True)
    context["user_role"] = getattr(current_user, "role", "user")
    context["company_id"] = current_user.company_id

    result = core_command_service.process_command(
        db=db,
        raw_input=request.input,
        user=current_user,
        context=context,
    )
    return result


@router.get("/recent-actions")
def get_recent_actions(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's most recent command bar actions."""
    return core_command_service.get_recent_actions(db, current_user.id, limit=limit)


@router.post("/log-action")
def log_action(
    request: LogActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a command bar action execution."""
    action = core_command_service.log_action(
        db=db,
        user_id=current_user.id,
        company_id=current_user.company_id,
        action_id=request.action_id,
        raw_input=request.raw_input,
        result_title=request.result_title,
        result_type=request.result_type,
        action_data=request.action_data or {},
        input_method=request.input_method,
    )
    return {"id": action.id, "status": "logged"}
