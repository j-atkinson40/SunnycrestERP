from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    """Request to change own password (requires current password)."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class ResetPasswordRequest(BaseModel):
    """Admin request to reset another user's password."""

    new_password: str = Field(..., min_length=8)
