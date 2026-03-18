"""Funeral Home Case schemas."""

from datetime import date

from pydantic import BaseModel


class CremationStatusUpdate(BaseModel):
    cremation_authorization_status: str | None = None
    cremation_authorization_signed_by: str | None = None
    cremation_scheduled_date: date | None = None
    cremation_completed_date: date | None = None
    remains_disposition: str | None = None
    remains_released_to: str | None = None
    cremation_provider: str | None = None
    cremation_provider_case_number: str | None = None
