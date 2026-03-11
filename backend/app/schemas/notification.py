from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    company_id: str
    user_id: str
    title: str
    message: str
    type: str
    category: str | None = None
    link: str | None = None
    is_read: bool
    actor_id: str | None = None
    actor_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    per_page: int
    unread_count: int
