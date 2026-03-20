// ---------------------------------------------------------------------------
// Vehicles
// ---------------------------------------------------------------------------

export interface Vehicle {
  id: string;
  company_id: string;
  name: string;
  license_plate: string | null;
  vehicle_type: string;
  max_weight_lbs: string | null;
  max_stops: number | null;
  active: boolean;
  notes: string | null;
  created_at: string;
  modified_at: string | null;
}

export interface VehicleCreate {
  name: string;
  license_plate?: string | null;
  vehicle_type?: string;
  max_weight_lbs?: string | null;
  max_stops?: number | null;
  notes?: string | null;
}

export interface VehicleUpdate {
  name?: string;
  license_plate?: string | null;
  vehicle_type?: string;
  max_weight_lbs?: string | null;
  max_stops?: number | null;
  active?: boolean;
  notes?: string | null;
}

export interface PaginatedVehicles {
  items: Vehicle[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Drivers
// ---------------------------------------------------------------------------

export interface Driver {
  id: string;
  company_id: string;
  employee_id: string;
  employee_name: string | null;
  license_number: string | null;
  license_class: string | null;
  license_expiry: string | null;
  active: boolean;
  preferred_vehicle_id: string | null;
  notes: string | null;
  created_at: string;
  modified_at: string | null;
}

export interface DriverCreate {
  employee_id: string;
  license_number?: string | null;
  license_class?: string | null;
  license_expiry?: string | null;
  preferred_vehicle_id?: string | null;
  notes?: string | null;
}

export interface DriverUpdate {
  license_number?: string | null;
  license_class?: string | null;
  license_expiry?: string | null;
  preferred_vehicle_id?: string | null;
  active?: boolean;
  notes?: string | null;
}

export interface PaginatedDrivers {
  items: Driver[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Carriers
// ---------------------------------------------------------------------------

export interface Carrier {
  id: string;
  company_id: string;
  name: string;
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  carrier_type: string;
  active: boolean;
  notes: string | null;
  created_at: string;
  modified_at: string | null;
}

export interface CarrierCreate {
  name: string;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  carrier_type?: string;
  notes?: string | null;
}

export interface CarrierUpdate {
  name?: string;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  carrier_type?: string;
  active?: boolean;
  notes?: string | null;
}

export interface PaginatedCarriers {
  items: Carrier[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Delivery Settings
// ---------------------------------------------------------------------------

export interface DeliverySettings {
  id: string;
  company_id: string;
  preset: string;
  require_photo_on_delivery: boolean;
  require_signature: boolean;
  require_weight_ticket: boolean;
  require_setup_confirmation: boolean;
  require_departure_photo: boolean;
  require_mileage_entry: boolean;
  allow_partial_delivery: boolean;
  allow_driver_resequence: boolean;
  track_gps: boolean;
  notify_customer_on_dispatch: boolean;
  notify_customer_on_arrival: boolean;
  notify_customer_on_complete: boolean;
  notify_connected_tenant_on_arrival: boolean;
  notify_connected_tenant_on_setup: boolean;
  enable_driver_messaging: boolean;
  enable_delivery_portal: boolean;
  auto_create_delivery_from_order: boolean;
  auto_invoice_on_complete: boolean;
  sms_carrier_updates: boolean;
  carrier_portal: boolean;
  max_stops_per_route: number | null;
  default_delivery_window_minutes: number | null;
  created_at: string;
  modified_at: string | null;
}

export interface DeliverySettingsUpdate {
  preset?: string;
  require_photo_on_delivery?: boolean;
  require_signature?: boolean;
  require_weight_ticket?: boolean;
  require_setup_confirmation?: boolean;
  require_departure_photo?: boolean;
  require_mileage_entry?: boolean;
  allow_partial_delivery?: boolean;
  allow_driver_resequence?: boolean;
  track_gps?: boolean;
  notify_customer_on_dispatch?: boolean;
  notify_customer_on_arrival?: boolean;
  notify_customer_on_complete?: boolean;
  notify_connected_tenant_on_arrival?: boolean;
  notify_connected_tenant_on_setup?: boolean;
  enable_driver_messaging?: boolean;
  enable_delivery_portal?: boolean;
  auto_create_delivery_from_order?: boolean;
  auto_invoice_on_complete?: boolean;
  sms_carrier_updates?: boolean;
  carrier_portal?: boolean;
  max_stops_per_route?: number | null;
  default_delivery_window_minutes?: number | null;
}

// ---------------------------------------------------------------------------
// Deliveries
// ---------------------------------------------------------------------------

/** Delivery type key — configurable per tenant via delivery_type_definitions. */
export type DeliveryType = string;
export type DeliveryStatus =
  | "pending"
  | "scheduled"
  | "in_transit"
  | "arrived"
  | "setup"
  | "completed"
  | "cancelled"
  | "failed";
export type DeliveryPriority = "low" | "normal" | "high" | "urgent";

export interface DeliveryListItem {
  id: string;
  company_id: string;
  delivery_type: string;
  order_id: string | null;
  customer_id: string | null;
  customer_name: string | null;
  carrier_id: string | null;
  carrier_name: string | null;
  carrier_tracking_reference: string | null;
  delivery_address: string | null;
  requested_date: string | null;
  status: string;
  priority: string;
  weight_lbs: string | null;
  scheduled_at: string | null;
  created_at: string;
}

export interface Delivery extends DeliveryListItem {
  delivery_lat: string | null;
  delivery_lng: string | null;
  required_window_start: string | null;
  required_window_end: string | null;
  type_config: Record<string, unknown> | null;
  special_instructions: string | null;
  completed_at: string | null;
  created_by: string | null;
  modified_at: string | null;
}

export interface DeliveryCreate {
  delivery_type: string;
  order_id?: string | null;
  customer_id?: string | null;
  carrier_id?: string | null;
  carrier_tracking_reference?: string | null;
  delivery_address?: string | null;
  delivery_lat?: string | null;
  delivery_lng?: string | null;
  requested_date?: string | null;
  required_window_start?: string | null;
  required_window_end?: string | null;
  priority?: string;
  type_config?: Record<string, unknown> | null;
  special_instructions?: string | null;
  weight_lbs?: string | null;
}

export interface DeliveryUpdate {
  carrier_id?: string | null;
  carrier_tracking_reference?: string | null;
  delivery_address?: string | null;
  delivery_lat?: string | null;
  delivery_lng?: string | null;
  requested_date?: string | null;
  required_window_start?: string | null;
  required_window_end?: string | null;
  status?: string;
  priority?: string;
  type_config?: Record<string, unknown> | null;
  special_instructions?: string | null;
  weight_lbs?: string | null;
}

export interface PaginatedDeliveries {
  items: DeliveryListItem[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export type RouteStatus =
  | "draft"
  | "dispatched"
  | "in_progress"
  | "completed"
  | "cancelled";

export interface DeliveryStop {
  id: string;
  route_id: string;
  delivery_id: string;
  delivery: DeliveryListItem | null;
  sequence_number: number;
  estimated_arrival: string | null;
  estimated_departure: string | null;
  actual_arrival: string | null;
  actual_departure: string | null;
  status: string;
  driver_notes: string | null;
  created_at: string;
}

export interface DeliveryRoute {
  id: string;
  company_id: string;
  driver_id: string;
  driver_name: string | null;
  vehicle_id: string | null;
  vehicle_name: string | null;
  route_date: string;
  status: string;
  notes: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_mileage: string | null;
  total_stops: number;
  stops: DeliveryStop[];
  created_by: string | null;
  created_at: string;
  modified_at: string | null;
}

export interface RouteCreate {
  driver_id: string;
  vehicle_id?: string | null;
  route_date: string;
  notes?: string | null;
}

export interface RouteUpdate {
  driver_id?: string;
  vehicle_id?: string | null;
  status?: string;
  notes?: string | null;
  total_mileage?: string | null;
}

export interface PaginatedRoutes {
  items: DeliveryRoute[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

export type EventSource = "driver" | "dispatch_manual" | "carrier_sms" | "carrier_portal" | "system";

export interface DeliveryEvent {
  id: string;
  company_id: string;
  delivery_id: string;
  route_id: string | null;
  driver_id: string | null;
  event_type: string;
  source: string | null;
  lat: string | null;
  lng: string | null;
  notes: string | null;
  created_at: string;
}

export interface EventCreate {
  delivery_id: string;
  route_id?: string | null;
  event_type: string;
  source?: string;
  lat?: string | null;
  lng?: string | null;
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Media
// ---------------------------------------------------------------------------

export interface DeliveryMedia {
  id: string;
  company_id: string;
  delivery_id: string;
  event_id: string | null;
  media_type: string;
  file_url: string;
  captured_at: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

export interface DeliveryStats {
  total_deliveries: number;
  pending: number;
  scheduled: number;
  in_transit: number;
  completed_today: number;
  active_routes: number;
  available_drivers: number;
  available_vehicles: number;
}

// ---------------------------------------------------------------------------
// Funeral Kanban
// ---------------------------------------------------------------------------

export interface KanbanCard {
  delivery_id: string;
  family_name: string;
  cemetery_name: string;
  funeral_home_name: string;
  service_time: string;
  service_time_display: string;
  vault_type: string;
  vault_personalization: string;
  requested_date: string | null;
  required_window_start: string | null;
  required_window_end: string | null;
  hours_until_service: number | null;
  is_critical: boolean;
  is_warning: boolean;
  order_id: string | null;
  notes: string | null;
  status: string;
  delivery_address: string | null;
  scheduled_sequence?: number;
}

export interface KanbanDriverLane {
  driver_id: string;
  name: string;
  deliveries: KanbanCard[];
  delivery_count: number;
}

export interface KanbanConfig {
  default_view: string;
  saturday_default: string;
  sunday_default: string;
  show_driver_count_badge: boolean;
  warn_driver_count: number;
  card_show_cemetery: boolean;
  card_show_funeral_home: boolean;
  card_show_service_time: boolean;
  card_show_vault_type: boolean;
  card_show_family_name: boolean;
  critical_window_hours: number;
}

export interface KanbanScheduleResponse {
  date: string;
  config: KanbanConfig;
  unscheduled: KanbanCard[];
  drivers: KanbanDriverLane[];
}

export interface KanbanAssignRequest {
  delivery_id: string;
  driver_id: string | null;
  date: string;
  sequence?: number;
}

export interface KanbanAssignResponse {
  status: string;
  delivery_id: string;
  driver_id?: string;
  route_id?: string;
  sequence?: number;
}

// ---------------------------------------------------------------------------
// Ancillary Orders
// ---------------------------------------------------------------------------

export type AncillaryFulfillmentStatus =
  | "unassigned"
  | "awaiting_pickup"
  | "assigned_to_driver"
  | "completed";

export interface AncillaryCard {
  delivery_id: string;
  delivery_type: string;
  order_type_label: string;
  funeral_home_name: string;
  product_summary: string;
  deceased_name: string;
  status: string;
  ancillary_fulfillment_status: AncillaryFulfillmentStatus;
  assigned_driver_id: string | null;
  pickup_expected_by: string | null;
  pickup_confirmed_at: string | null;
  pickup_confirmed_by: string | null;
  requested_date: string | null;
  completed_at: string | null;
  special_instructions: string | null;
  created_at: string | null;
}

export interface AncillaryDriverGroup {
  driver_id: string;
  driver_name: string;
  items: AncillaryCard[];
  item_count: number;
}

export interface AncillaryAvailableDriver {
  driver_id: string;
  name: string;
}

export interface AncillaryOrdersResponse {
  date: string;
  needs_action: AncillaryCard[];
  awaiting_pickup: AncillaryCard[];
  assigned_groups: AncillaryDriverGroup[];
  completed: AncillaryCard[];
  available_drivers: AncillaryAvailableDriver[];
  stats: {
    total: number;
    needs_action: number;
    awaiting_pickup: number;
    assigned: number;
    completed: number;
    unresolved: number;
  };
}

// ---------------------------------------------------------------------------
// Direct Ship Orders
// ---------------------------------------------------------------------------

export type DirectShipStatus =
  | "pending"
  | "ordered_from_wilbert"
  | "shipped"
  | "done";

export interface DirectShipCard {
  delivery_id: string;
  delivery_type: string;
  funeral_home_name: string;
  product_summary: string;
  deceased_name: string;
  status: string;
  direct_ship_status: DirectShipStatus;
  wilbert_order_number: string | null;
  direct_ship_notes: string | null;
  needed_by: string | null;
  marked_shipped_at: string | null;
  marked_shipped_by: string | null;
  completed_at: string | null;
  special_instructions: string | null;
  created_at: string | null;
}

export interface DirectShipResponse {
  needs_ordering: DirectShipCard[];
  ordered: DirectShipCard[];
  shipped: DirectShipCard[];
  completed: DirectShipCard[];
  stats: {
    total: number;
    needs_ordering: number;
    ordered: number;
    shipped: number;
    completed: number;
    unresolved: number;
  };
}

export interface AncillaryConsoleItem {
  delivery_id: string;
  delivery_type: string;
  order_type_label: string;
  funeral_home_name: string;
  product_summary: string;
  deceased_name: string;
  ancillary_fulfillment_status: AncillaryFulfillmentStatus;
  special_instructions: string | null;
}
