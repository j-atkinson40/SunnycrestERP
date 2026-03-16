"""Driver-facing service — today's route, event posting, media upload."""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.delivery_route import DeliveryRoute
from app.services import delivery_service


def get_today_route(db: Session, driver_id: str, company_id: str) -> DeliveryRoute | None:
    """Return the driver's route for today, if any."""
    return (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.driver_id == driver_id,
            DeliveryRoute.company_id == company_id,
            DeliveryRoute.route_date == date.today(),
        )
        .first()
    )


def start_route(db: Session, route: DeliveryRoute) -> DeliveryRoute:
    """Mark a route as started."""
    route.status = "in_progress"
    route.started_at = datetime.now(timezone.utc)
    route.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(route)
    return route


def complete_route(db: Session, route: DeliveryRoute, total_mileage: float | None = None) -> DeliveryRoute:
    """Mark a route as completed."""
    route.status = "completed"
    route.completed_at = datetime.now(timezone.utc)
    if total_mileage is not None:
        route.total_mileage = total_mileage
    route.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(route)
    return route


def post_event(
    db: Session,
    company_id: str,
    driver_id: str,
    event_data: dict,
) -> dict:
    """Create a delivery event from a driver action.

    Validates against tenant settings (e.g., required photo, signature).
    """
    from app.services import delivery_notification_service, delivery_settings_service

    event = delivery_service.create_event(
        db, company_id, event_data, driver_id=driver_id
    )

    # Trigger notifications based on event type
    delivery = delivery_service.get_delivery(db, event_data["delivery_id"], company_id)
    if delivery:
        event_type = event_data.get("event_type")
        if event_type == "arrived":
            delivery_notification_service.on_driver_arrived(db, delivery)
        elif event_type == "setup_complete":
            delivery_notification_service.on_setup_complete(db, delivery)
        elif event_type == "departed":
            delivery_notification_service.on_driver_departed(db, delivery)
        elif event_type == "completed":
            delivery_notification_service.on_delivery_complete(db, delivery)

    return event
