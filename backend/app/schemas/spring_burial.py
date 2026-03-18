"""Spring burial Pydantic schemas."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MarkSpringBurialRequest(BaseModel):
    notes: str | None = None


class ScheduleSpringBurialRequest(BaseModel):
    delivery_date: date
    time_preference: str | None = None
    driver_id: str | None = None
    instructions: str | None = None


class BulkScheduleItem(BaseModel):
    order_id: str
    delivery_date: date
    time_preference: str | None = None
    driver_id: str | None = None
    instructions: str | None = None


class BulkScheduleRequest(BaseModel):
    orders: list[BulkScheduleItem]


class SpringBurialOrderResponse(BaseModel):
    id: str
    order_number: str
    deceased_name: str | None = None
    funeral_home_id: str
    funeral_home_name: str
    cemetery_name: str | None = None
    vault_product: str | None = None
    spring_burial_added_at: datetime | None = None
    spring_burial_notes: str | None = None
    typical_opening_date: str | None = None
    days_until_opening: int | None = None
    model_config = ConfigDict(from_attributes=True)


class SpringBurialGroupResponse(BaseModel):
    group_key: str
    group_name: str
    order_count: int
    earliest_opening: str | None = None
    orders: list[SpringBurialOrderResponse]


class SpringBurialStatsResponse(BaseModel):
    total_count: int
    funeral_home_count: int
    soonest_cemetery: str | None = None
    soonest_opening_date: str | None = None
    days_until_soonest: int | None = None
