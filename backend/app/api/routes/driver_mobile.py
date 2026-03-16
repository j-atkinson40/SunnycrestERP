"""Driver mobile endpoints — today's route, events, media."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module
from app.database import get_db
from app.models.user import User
from app.schemas.delivery import EventCreate, EventResponse, MediaResponse, RouteResponse, StopResponse
from app.services import delivery_service, driver_mobile_service

router = APIRouter()

MODULE = "driver_delivery"


class StartRouteRequest(BaseModel):
    pass


class CompleteRouteRequest(BaseModel):
    total_mileage: Decimal | None = None


class UpdateStopStatusRequest(BaseModel):
    status: str
    driver_notes: str | None = None


@router.get("/route/today", response_model=RouteResponse | None)
def get_today_route(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found for this user")
    route = driver_mobile_service.get_today_route(db, driver.id, current_user.company_id)
    if not route:
        return None
    resp = RouteResponse.model_validate(route)
    if route.driver and route.driver.employee:
        resp.driver_name = f"{route.driver.employee.first_name} {route.driver.employee.last_name}"
    if route.vehicle:
        resp.vehicle_name = route.vehicle.name
    return resp


@router.post("/route/today/start", response_model=RouteResponse)
def start_route(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")
    route = driver_mobile_service.get_today_route(db, driver.id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="No route scheduled for today")
    return driver_mobile_service.start_route(db, route)


@router.post("/route/today/complete", response_model=RouteResponse)
def complete_route(
    data: CompleteRouteRequest,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")
    route = driver_mobile_service.get_today_route(db, driver.id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="No route scheduled for today")
    return driver_mobile_service.complete_route(
        db, route, total_mileage=float(data.total_mileage) if data.total_mileage else None
    )


@router.patch("/stops/{stop_id}/status", response_model=StopResponse)
def update_stop_status(
    stop_id: str,
    data: UpdateStopStatusRequest,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    from app.models.delivery_stop import DeliveryStop

    stop = db.query(DeliveryStop).filter(DeliveryStop.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    return delivery_service.update_stop_status(db, stop, data.status, data.driver_notes)


@router.post("/events", response_model=EventResponse)
def post_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")
    return driver_mobile_service.post_event(
        db,
        current_user.company_id,
        driver.id,
        data.model_dump(exclude_none=True),
    )


@router.post("/media", response_model=MediaResponse, status_code=201)
async def upload_media(
    delivery_id: str,
    media_type: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    # In production, upload to S3/GCS. For now, store locally.
    import os
    import uuid

    upload_dir = "/tmp/delivery_media"
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    file_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, file_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return delivery_service.create_media(
        db,
        current_user.company_id,
        delivery_id=delivery_id,
        media_type=media_type,
        file_url=f"/media/{file_name}",
    )
