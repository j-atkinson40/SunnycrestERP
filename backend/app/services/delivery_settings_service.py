"""Delivery settings service with Redis cache.

Settings are per-tenant and cached with a 5-minute TTL.
Falls back to DB on Redis unavailability.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.models.delivery_settings import DeliverySettings

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes
_CACHE_PREFIX = "delivery_settings:"


def _cache_key(tenant_id: str) -> str:
    return f"{_CACHE_PREFIX}{tenant_id}"


def _invalidate_cache(tenant_id: str) -> None:
    r = get_redis()
    if r:
        try:
            r.delete(_cache_key(tenant_id))
        except Exception:
            pass


def _get_cached(tenant_id: str) -> DeliverySettings | None:
    """Try to get settings from Redis cache. Returns None on miss."""
    r = get_redis()
    if not r:
        return None
    try:
        raw = r.get(_cache_key(tenant_id))
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def _set_cached(tenant_id: str, data: dict) -> None:
    r = get_redis()
    if not r:
        return
    try:
        r.setex(_cache_key(tenant_id), _CACHE_TTL, json.dumps(data, default=str))
    except Exception:
        pass


def _settings_to_dict(settings: DeliverySettings) -> dict:
    return {
        "id": settings.id,
        "company_id": settings.company_id,
        "preset": settings.preset,
        "require_photo_on_delivery": settings.require_photo_on_delivery,
        "require_signature": settings.require_signature,
        "require_weight_ticket": settings.require_weight_ticket,
        "require_setup_confirmation": settings.require_setup_confirmation,
        "require_departure_photo": settings.require_departure_photo,
        "require_mileage_entry": settings.require_mileage_entry,
        "allow_partial_delivery": settings.allow_partial_delivery,
        "allow_driver_resequence": settings.allow_driver_resequence,
        "track_gps": settings.track_gps,
        "notify_customer_on_dispatch": settings.notify_customer_on_dispatch,
        "notify_customer_on_arrival": settings.notify_customer_on_arrival,
        "notify_customer_on_complete": settings.notify_customer_on_complete,
        "notify_connected_tenant_on_arrival": settings.notify_connected_tenant_on_arrival,
        "notify_connected_tenant_on_setup": settings.notify_connected_tenant_on_setup,
        "enable_driver_messaging": settings.enable_driver_messaging,
        "enable_delivery_portal": settings.enable_delivery_portal,
        "auto_create_delivery_from_order": settings.auto_create_delivery_from_order,
        "auto_invoice_on_complete": settings.auto_invoice_on_complete,
        "sms_carrier_updates": settings.sms_carrier_updates,
        "carrier_portal": settings.carrier_portal,
        "max_stops_per_route": settings.max_stops_per_route,
        "default_delivery_window_minutes": settings.default_delivery_window_minutes,
    }


def get_settings(db: Session, tenant_id: str) -> DeliverySettings:
    """Get or create delivery settings for a tenant."""
    settings = (
        db.query(DeliverySettings)
        .filter(DeliverySettings.company_id == tenant_id)
        .first()
    )
    if not settings:
        settings = DeliverySettings(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, tenant_id: str, data: dict) -> DeliverySettings:
    """Update delivery settings and invalidate cache."""
    settings = get_settings(db, tenant_id)
    for k, v in data.items():
        if v is not None and hasattr(settings, k):
            setattr(settings, k, v)
    settings.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settings)
    _invalidate_cache(tenant_id)
    return settings


def apply_preset(db: Session, tenant_id: str, preset_name: str) -> DeliverySettings:
    """Apply a named preset to tenant settings."""
    from app.schemas.delivery import DELIVERY_PRESETS

    if preset_name not in DELIVERY_PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}")

    preset_values = DELIVERY_PRESETS[preset_name]
    settings = get_settings(db, tenant_id)
    settings.preset = preset_name
    for k, v in preset_values.items():
        if hasattr(settings, k):
            setattr(settings, k, v)
    settings.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settings)
    _invalidate_cache(tenant_id)
    return settings


# ---------------------------------------------------------------------------
# Helper methods for checking specific settings
# ---------------------------------------------------------------------------


def requires_photo(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).require_photo_on_delivery


def requires_signature(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).require_signature


def requires_weight_ticket(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).require_weight_ticket


def requires_setup_confirmation(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).require_setup_confirmation


def requires_mileage_entry(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).require_mileage_entry


def allows_partial_delivery(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).allow_partial_delivery


def allows_driver_resequence(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).allow_driver_resequence


def should_notify_customer_on_dispatch(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).notify_customer_on_dispatch


def should_notify_customer_on_arrival(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).notify_customer_on_arrival


def is_sms_carrier_updates_enabled(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).sms_carrier_updates


def is_carrier_portal_enabled(db: Session, tenant_id: str) -> bool:
    return get_settings(db, tenant_id).carrier_portal
