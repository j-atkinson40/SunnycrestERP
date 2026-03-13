from datetime import date, datetime

from pydantic import BaseModel


class PerformanceNoteCreate(BaseModel):
    user_id: str
    type: str = "note"  # review, note, goal, warning
    title: str
    content: str | None = None
    review_date: date | None = None


class PerformanceNoteResponse(BaseModel):
    id: str
    company_id: str
    user_id: str
    author_id: str
    type: str
    title: str
    content: str | None = None
    review_date: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
