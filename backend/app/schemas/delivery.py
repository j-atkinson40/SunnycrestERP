"""Pydantic schemas for the Driver Scheduling & Delivery system."""

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------


class VehicleCreate(BaseModel):
    name: str
    license_plate: str | None = None
    vehicle_type: str = "truck"
    max_weight_lbs: Decimal | None = None
    max_stops: int | None = None
    notes: str | None = None


class VehicleUpdate(BaseModel):
    name: str | None = None
    license_plate: str | None = None
    vehicle_type: str | None = None
    max_weight_lbs: Decimal | None = None
    max_stops: int | None = None
    active: bool | None = None
    notes: str | None = None


class VehicleResponse(BaseModel):
    id: str
    company_id: str
    name: str
    license_plate: str | None = None
    vehicle_type: str
    max_weight_lbs: Decimal | None = None
    max_stops: int | None = None
    active: bool
    notes: str | None = None
    created_at: datetime
    modified_at: datetime | None = None

    class Config:
        from_attributes = True


class PaginatedVehicles(BaseModel):
    items: list[VehicleResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


# Phase 8e.2.1 — DriverCreate retained ONLY for schema-module
# backward compatibility with any remaining imports; POST /delivery/
# drivers endpoint removed. Fields kept with employee_id optional
# so the schema can construct but shouldn't be used for new writes.
# Actual removal lands in the latent-bug cleanup session.
class DriverCreate(BaseModel):
    employee_id: str | None = None  # retired — portal invite path instead
    license_number: str | None = None
    license_class: str | None = None
    license_expiry: date | None = None
    preferred_vehicle_id: str | None = None
    notes: str | None = None


class DriverUpdate(BaseModel):
    license_number: str | None = None
    license_class: str | None = None
    license_expiry: date | None = None
    preferred_vehicle_id: str | None = None
    active: bool | None = None
    notes: str | None = None


class DriverResponse(BaseModel):
    id: str
    company_id: str
    # Phase 8e.2.1 — employee_id nullable; portal_user_id is the
    # canonical identity for new drivers.
    employee_id: str | None = None
    employee_name: str | None = None
    portal_user_id: str | None = None
    portal_user_name: str | None = None
    license_number: str | None = None
    license_class: str | None = None
    license_expiry: date | None = None
    active: bool
    preferred_vehicle_id: str | None = None
    notes: str | None = None
    created_at: datetime
    modified_at: datetime | None = None

    class Config:
        from_attributes = True


class PaginatedDrivers(BaseModel):
    items: list[DriverResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Carriers
# ---------------------------------------------------------------------------


class CarrierCreate(BaseModel):
    name: str
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    carrier_type: str = "own_fleet"  # own_fleet, third_party
    notes: str | None = None


class CarrierUpdate(BaseModel):
    name: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    carrier_type: str | None = None
    active: bool | None = None
    notes: str | None = None


class CarrierResponse(BaseModel):
    id: str
    company_id: str
    name: str
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    carrier_type: str
    active: bool
    notes: str | None = None
    created_at: datetime
    modified_at: datetime | None = None

    class Config:
        from_attributes = True


class PaginatedCarriers(BaseModel):
    items: list[CarrierResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Delivery Settings
# ---------------------------------------------------------------------------


# Legacy presets — kept for backward compatibility.
# New tenants should configure delivery types via delivery_type_definitions table.
DELIVERY_PRESETS: dict[str, dict[str, bool | int | None]] = {
    "standard": {
        "require_photo_on_delivery": False,
        "require_signature": False,
        "require_weight_ticket": False,
        "require_setup_confirmation": False,
        "require_departure_photo": False,
        "require_mileage_entry": False,
        "allow_partial_delivery": False,
        "allow_driver_resequence": False,
        "track_gps": False,
        "notify_customer_on_dispatch": False,
        "notify_customer_on_arrival": False,
        "notify_customer_on_complete": False,
        "notify_connected_tenant_on_arrival": False,
        "notify_connected_tenant_on_setup": False,
        "enable_driver_messaging": False,
        "enable_delivery_portal": False,
        "auto_create_delivery_from_order": False,
        "auto_invoice_on_complete": False,
        "sms_carrier_updates": False,
        "carrier_portal": False,
    },
    "funeral_vault": {
        "require_photo_on_delivery": True,
        "require_signature": True,
        "require_weight_ticket": False,
        "require_setup_confirmation": True,
        "require_departure_photo": True,
        "require_mileage_entry": True,
        "allow_partial_delivery": False,
        "allow_driver_resequence": False,
        "track_gps": True,
        "notify_customer_on_dispatch": True,
        "notify_customer_on_arrival": True,
        "notify_customer_on_complete": True,
        "notify_connected_tenant_on_arrival": True,
        "notify_connected_tenant_on_setup": True,
        "enable_driver_messaging": True,
        "enable_delivery_portal": True,
        "auto_create_delivery_from_order": True,
        "auto_invoice_on_complete": True,
        "sms_carrier_updates": False,
        "carrier_portal": False,
    },
    "precast": {
        "require_photo_on_delivery": True,
        "require_signature": True,
        "require_weight_ticket": True,
        "require_setup_confirmation": False,
        "require_departure_photo": False,
        "require_mileage_entry": True,
        "allow_partial_delivery": True,
        "allow_driver_resequence": True,
        "track_gps": True,
        "notify_customer_on_dispatch": True,
        "notify_customer_on_arrival": False,
        "notify_customer_on_complete": True,
        "notify_connected_tenant_on_arrival": False,
        "notify_connected_tenant_on_setup": False,
        "enable_driver_messaging": True,
        "enable_delivery_portal": False,
        "auto_create_delivery_from_order": True,
        "auto_invoice_on_complete": False,
        "sms_carrier_updates": False,
        "carrier_portal": False,
    },
    "redi_rock": {
        "require_photo_on_delivery": True,
        "require_signature": True,
        "require_weight_ticket": True,
        "require_setup_confirmation": False,
        "require_departure_photo": False,
        "require_mileage_entry": True,
        "allow_partial_delivery": True,
        "allow_driver_resequence": True,
        "track_gps": True,
        "notify_customer_on_dispatch": True,
        "notify_customer_on_arrival": False,
        "notify_customer_on_complete": True,
        "notify_connected_tenant_on_arrival": False,
        "notify_connected_tenant_on_setup": False,
        "enable_driver_messaging": True,
        "enable_delivery_portal": False,
        "auto_create_delivery_from_order": True,
        "auto_invoice_on_complete": False,
        "sms_carrier_updates": True,
        "carrier_portal": True,
    },
}


class DeliverySettingsUpdate(BaseModel):
    preset: str | None = None
    require_photo_on_delivery: bool | None = None
    require_signature: bool | None = None
    require_weight_ticket: bool | None = None
    require_setup_confirmation: bool | None = None
    require_departure_photo: bool | None = None
    require_mileage_entry: bool | None = None
    allow_partial_delivery: bool | None = None
    allow_driver_resequence: bool | None = None
    track_gps: bool | None = None
    notify_customer_on_dispatch: bool | None = None
    notify_customer_on_arrival: bool | None = None
    notify_customer_on_complete: bool | None = None
    notify_connected_tenant_on_arrival: bool | None = None
    notify_connected_tenant_on_setup: bool | None = None
    enable_driver_messaging: bool | None = None
    enable_delivery_portal: bool | None = None
    auto_create_delivery_from_order: bool | None = None
    auto_invoice_on_complete: bool | None = None
    invoice_generation_mode: str | None = None
    require_driver_status_updates: bool | None = None
    show_en_route_button: bool | None = None
    show_exception_button: bool | None = None
    show_delivered_button: bool | None = None
    show_equipment_checklist: bool | None = None
    show_funeral_home_contact: bool | None = None
    show_cemetery_contact: bool | None = None
    show_get_directions: bool | None = None
    show_call_office_button: bool | None = None
    require_personalization_complete: bool | None = None
    sms_carrier_updates: bool | None = None
    carrier_portal: bool | None = None
    max_stops_per_route: int | None = None
    default_delivery_window_minutes: int | None = None


class DeliverySettingsResponse(BaseModel):
    id: str
    company_id: str
    preset: str
    require_photo_on_delivery: bool
    require_signature: bool
    require_weight_ticket: bool
    require_setup_confirmation: bool
    require_departure_photo: bool
    require_mileage_entry: bool
    allow_partial_delivery: bool
    allow_driver_resequence: bool
    track_gps: bool
    notify_customer_on_dispatch: bool
    notify_customer_on_arrival: bool
    notify_customer_on_complete: bool
    notify_connected_tenant_on_arrival: bool
    notify_connected_tenant_on_setup: bool
    enable_driver_messaging: bool
    enable_delivery_portal: bool
    auto_create_delivery_from_order: bool
    auto_invoice_on_complete: bool
    invoice_generation_mode: str = "end_of_day"
    require_driver_status_updates: bool = False
    show_en_route_button: bool = True
    show_exception_button: bool = True
    show_delivered_button: bool = True
    show_equipment_checklist: bool = False
    show_funeral_home_contact: bool = True
    show_cemetery_contact: bool = True
    show_get_directions: bool = True
    show_call_office_button: bool = True
    require_personalization_complete: bool = False
    sms_carrier_updates: bool
    carrier_portal: bool
    max_stops_per_route: int | None = None
    default_delivery_window_minutes: int | None = None
    created_at: datetime
    modified_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------


class DeliveryCreate(BaseModel):
    delivery_type: str
    order_id: str | None = None
    customer_id: str | None = None
    carrier_id: str | None = None
    carrier_tracking_reference: str | None = None
    delivery_address: str | None = None
    delivery_lat: Decimal | None = None
    delivery_lng: Decimal | None = None
    requested_date: date | None = None
    required_window_start: datetime | None = None
    required_window_end: datetime | None = None
    priority: str = "normal"
    type_config: dict | None = None
    special_instructions: str | None = None
    weight_lbs: Decimal | None = None
    # Ancillary fields
    scheduling_type: str | None = None  # 'kanban' | 'ancillary' | 'direct_ship'
    pickup_expected_by: datetime | None = None
    ancillary_is_floating: bool | None = None
    ancillary_soft_target_date: date | None = None
    # Direct ship fields
    direct_ship_status: str | None = None
    wilbert_order_number: str | None = None
    direct_ship_notes: str | None = None


class DeliveryUpdate(BaseModel):
    carrier_id: str | None = None
    carrier_tracking_reference: str | None = None
    delivery_address: str | None = None
    delivery_lat: Decimal | None = None
    delivery_lng: Decimal | None = None
    requested_date: date | None = None
    required_window_start: datetime | None = None
    required_window_end: datetime | None = None
    status: str | None = None
    priority: str | None = None
    type_config: dict | None = None
    special_instructions: str | None = None
    weight_lbs: Decimal | None = None
    # Ancillary fields
    scheduling_type: str | None = None
    ancillary_fulfillment_status: str | None = None
    # Phase 4.3 (r56) — renamed from assigned_driver_id; FK users.id.
    primary_assignee_id: str | None = None
    pickup_expected_by: datetime | None = None
    pickup_confirmed_by: str | None = None
    ancillary_is_floating: bool | None = None
    ancillary_soft_target_date: date | None = None
    # Phase 4.3 (r56) — helper + attach + start time.
    helper_user_id: str | None = None
    attached_to_delivery_id: str | None = None
    driver_start_time: time | None = None
    # Direct ship fields
    direct_ship_status: str | None = None
    wilbert_order_number: str | None = None
    direct_ship_notes: str | None = None


class DeliveryListItem(BaseModel):
    id: str
    company_id: str
    delivery_type: str
    order_id: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    carrier_id: str | None = None
    carrier_name: str | None = None
    carrier_tracking_reference: str | None = None
    delivery_address: str | None = None
    requested_date: date | None = None
    status: str
    priority: str
    weight_lbs: Decimal | None = None
    scheduled_at: datetime | None = None
    created_at: datetime
    # Ancillary fields
    scheduling_type: str | None = None
    ancillary_fulfillment_status: str | None = None
    # Phase 4.3 (r56) — renamed from assigned_driver_id.
    primary_assignee_id: str | None = None
    ancillary_is_floating: bool | None = None
    ancillary_soft_target_date: date | None = None
    # Phase 4.3 (r56) — helper + attach + start time.
    helper_user_id: str | None = None
    attached_to_delivery_id: str | None = None
    driver_start_time: time | None = None

    class Config:
        from_attributes = True


class DeliveryResponse(BaseModel):
    id: str
    company_id: str
    delivery_type: str
    order_id: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    carrier_id: str | None = None
    carrier_name: str | None = None
    carrier_tracking_reference: str | None = None
    delivery_address: str | None = None
    delivery_lat: Decimal | None = None
    delivery_lng: Decimal | None = None
    requested_date: date | None = None
    required_window_start: datetime | None = None
    required_window_end: datetime | None = None
    status: str
    priority: str
    type_config: dict | None = None
    special_instructions: str | None = None
    weight_lbs: Decimal | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    modified_at: datetime | None = None
    # Ancillary fields
    scheduling_type: str | None = None
    ancillary_fulfillment_status: str | None = None
    # Phase 4.3 (r56) — renamed from assigned_driver_id.
    primary_assignee_id: str | None = None
    pickup_expected_by: datetime | None = None
    pickup_confirmed_at: datetime | None = None
    pickup_confirmed_by: str | None = None
    ancillary_is_floating: bool | None = None
    ancillary_soft_target_date: date | None = None
    # Phase 4.3 (r56) — helper + attach + start time.
    helper_user_id: str | None = None
    attached_to_delivery_id: str | None = None
    driver_start_time: time | None = None
    # Direct ship fields
    direct_ship_status: str | None = None
    wilbert_order_number: str | None = None
    direct_ship_notes: str | None = None
    marked_shipped_at: datetime | None = None
    marked_shipped_by: str | None = None

    class Config:
        from_attributes = True


class PaginatedDeliveries(BaseModel):
    items: list[DeliveryListItem]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


class RouteCreate(BaseModel):
    driver_id: str
    vehicle_id: str | None = None
    route_date: date
    notes: str | None = None


class RouteUpdate(BaseModel):
    driver_id: str | None = None
    vehicle_id: str | None = None
    status: str | None = None
    notes: str | None = None
    total_mileage: Decimal | None = None


class StopCreate(BaseModel):
    delivery_id: str
    sequence_number: int


class StopResequence(BaseModel):
    stop_ids: list[str]


class StopResponse(BaseModel):
    id: str
    route_id: str
    delivery_id: str
    delivery: DeliveryListItem | None = None
    sequence_number: int
    estimated_arrival: datetime | None = None
    estimated_departure: datetime | None = None
    actual_arrival: datetime | None = None
    actual_departure: datetime | None = None
    status: str
    driver_notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class RouteResponse(BaseModel):
    id: str
    company_id: str
    driver_id: str
    driver_name: str | None = None
    vehicle_id: str | None = None
    vehicle_name: str | None = None
    route_date: date
    status: str
    notes: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_mileage: Decimal | None = None
    total_stops: int
    stops: list[StopResponse] = []
    created_by: str | None = None
    created_at: datetime
    modified_at: datetime | None = None

    class Config:
        from_attributes = True


class PaginatedRoutes(BaseModel):
    items: list[RouteResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    delivery_id: str
    route_id: str | None = None
    event_type: str
    source: str = "driver"  # driver, dispatch_manual, carrier_sms, system
    lat: Decimal | None = None
    lng: Decimal | None = None
    notes: str | None = None


class EventResponse(BaseModel):
    id: str
    company_id: str
    delivery_id: str
    route_id: str | None = None
    driver_id: str | None = None
    event_type: str
    source: str | None = None
    lat: Decimal | None = None
    lng: Decimal | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


class MediaResponse(BaseModel):
    id: str
    company_id: str
    delivery_id: str
    event_id: str | None = None
    media_type: str
    file_url: str
    captured_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class DeliveryStats(BaseModel):
    total_deliveries: int = 0
    pending: int = 0
    scheduled: int = 0
    in_transit: int = 0
    completed_today: int = 0
    active_routes: int = 0
    available_drivers: int = 0
    available_vehicles: int = 0
