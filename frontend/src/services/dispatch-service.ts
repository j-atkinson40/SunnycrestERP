/**
 * Dispatch schedule + delivery monitor API client — Phase B Session 1.
 *
 * Mirrors `backend/app/api/routes/dispatch.py` + delivery + driver
 * reads needed by the Monitor view. Plain axios per codebase
 * convention (no TanStack).
 *
 * Endpoints covered:
 *   /api/v1/dispatch/schedule/{date}              — read state
 *   /api/v1/dispatch/schedule/range               — 3-day Monitor
 *   /api/v1/dispatch/schedule/{date}/ensure       — lazy create
 *   /api/v1/dispatch/schedule/{date}/finalize     — explicit
 *   /api/v1/dispatch/schedule/{date}/revert       — explicit
 *   /api/v1/dispatch/delivery/{id}/hole-dug       — quick-edit
 *
 * Delivery list + driver list use existing delivery-service endpoints.
 */

import apiClient from "@/lib/api-client"


export type ScheduleState = "draft" | "finalized" | "not_created"

/**
 * Three-state hole-dug, NOT nullable as of migration r50.
 * - unknown: default; dispatcher hasn't confirmed yet
 * - yes:     hole is dug
 * - no:      hole is NOT dug (follow-up flag)
 */
export type HoleDugStatus = "unknown" | "yes" | "no"


export interface ScheduleStateDTO {
  id: string | null
  company_id: string | null
  schedule_date: string           // ISO date "YYYY-MM-DD"
  state: ScheduleState
  finalized_at: string | null
  finalized_by_user_id: string | null
  auto_finalized: boolean
  last_reverted_at: string | null
  last_revert_reason: string | null
  created_at: string | null
  updated_at: string | null
}


export interface ScheduleRangeDTO {
  start_date: string
  end_date: string
  schedules: ScheduleStateDTO[]
}


export interface HoleDugResponseDTO {
  delivery_id: string
  hole_dug_status: HoleDugStatus
  schedule_reverted: boolean
  schedule_date: string | null
}


export interface DeliveryDTO {
  id: string
  company_id: string
  order_id: string | null
  customer_id: string | null
  delivery_type: string
  status: string
  priority: string
  requested_date: string | null   // ISO date
  scheduled_at: string | null     // ISO datetime
  completed_at: string | null
  scheduling_type: "kanban" | "ancillary" | "direct_ship" | null
  ancillary_fulfillment_status: string | null
  direct_ship_status: string | null
  // Phase 4.3.2 (r56) — renamed from `assigned_driver_id`; the field
  // now holds a `users.id` value (was `drivers.id`). Compare against
  // `DriverDTO.user_id`, not `DriverDTO.id`, when grouping cards by
  // assignee. Portal-only drivers have null `user_id` and cannot be
  // drag-assigned via kanban until the post-September follow-up.
  primary_assignee_id: string | null
  // Phase 4.3.2 — optional second person. Shown as icon+tooltip in
  // the card status row (Phase 4.3.4 UI).
  helper_user_id: string | null
  // Phase 4.3.2 — self-referential FK for the ancillary three-state
  // model. NULL + primary_assignee_id null = pool;
  // NULL + primary_assignee_id set = standalone;
  // set = attached (parent is another kanban delivery).
  attached_to_delivery_id: string | null
  // Phase 4.3.2 — per-delivery start-of-day target for the primary
  // assignee. Not the ETA; a scheduling hint for route planning.
  driver_start_time: string | null  // "HH:MM:SS"
  hole_dug_status: HoleDugStatus
  type_config: DeliveryTypeConfig | null
  special_instructions: string | null
}


/**
 * Display-field bag rendered on the Monitor card. Populated by the
 * seed / scheduling board's serializer; null-safe everywhere.
 *
 * Field meanings (Phase 3.2.1 clarification per user feedback):
 *   - service_type:   where the service HAPPENS — graveside / church
 *                     / funeral_home / ancillary_* / direct_ship.
 *                     Drives the service-time line label ("11:00
 *                     Church · ETA 12:00"). NOT an equipment cue.
 *   - vault_type:     product name (Monticello, Cameo Rose, Continental
 *                     Bronze, Triune Copper, Standard, Monarch,
 *                     Graveliner, Salute, etc). First half of the
 *                     product+equipment line.
 *   - equipment_type: equipment bundle name (Full Equipment, Full w/
 *                     Placer, Device, etc). Second half of the
 *                     product+equipment line. Distinct field from
 *                     vault_type; do not conflate with service_type.
 *
 * Phase 3.1+3.2 additions for icon+tooltip compaction:
 *   - cemetery_section: MapPin icon tooltip (e.g., "Sec 14, Lot 42B")
 *   - driver_note: StickyNote icon tooltip (distinct from
 *     Delivery.special_instructions which is order-level)
 *   - chat_activity_count: MessageCircle icon with unread-count badge
 *   - eta: inline "ETA 12:00" in the primary service-time line for
 *     church/funeral_home services (see DeliveryCard primary text).
 */
export interface DeliveryTypeConfig {
  family_name?: string | null
  cemetery_name?: string | null
  cemetery_city?: string | null
  cemetery_section?: string | null
  funeral_home_name?: string | null
  service_time?: string | null
  service_type?: string | null        // SERVICE LOCATION: 'graveside' | 'church' | 'funeral_home' | 'ancillary_pickup' | ...
  vault_type?: string | null          // PRODUCT: vault product name
  equipment_type?: string | null      // EQUIPMENT BUNDLE: 'Full Equipment' | 'Full w/ Placer' | 'Device' | ...
  eta?: string | null
  driver_note?: string | null
  chat_activity_count?: number | null
  [k: string]: unknown
}


// ── Tenant time (for Smart Stack single-day default) ─────────────────


/** Tenant-local wall clock — server authoritative (dispatchers on
 *  skewed laptops don't need their personal clock dictating the default
 *  day). The Monitor polls once on page-open + on window-focus to set
 *  the single-day Smart Stack primary (before/after 1pm local). */
export interface TenantTimeDTO {
  tenant_timezone: string             // IANA TZ name (e.g. "America/New_York")
  local_iso: string                   // ISO-8601 with tenant-local offset
  local_date: string                  // YYYY-MM-DD in tenant-local calendar
  local_hour: number                  // 0–23
  local_minute: number                // 0–59
}


export interface DriverDTO {
  id: string
  /** Phase 4.3.2 (r56) — the canonical assignee identity. Equal to
   *  `drivers.employee_id` on the backend (FK `users.id`). Compare
   *  this against `DeliveryDTO.primary_assignee_id` when grouping
   *  cards by driver. NULL for portal-only drivers; they appear in
   *  the roster but cannot be drag-assigned until the post-September
   *  follow-up lifts the limitation. `id` remains the `drivers.id`
   *  primary key for record identity. */
  user_id: string | null
  license_number: string | null
  license_class: string | null
  active: boolean
  display_name?: string | null        // computed client-side when available
}


// ── Schedule read + mutations ────────────────────────────────────────


export async function fetchSchedule(dateStr: string): Promise<ScheduleStateDTO> {
  const r = await apiClient.get<ScheduleStateDTO>(
    `/dispatch/schedule/${dateStr}`,
  )
  return r.data
}


export async function fetchScheduleRange(
  start: string,
  end: string,
): Promise<ScheduleRangeDTO> {
  const r = await apiClient.get<ScheduleRangeDTO>(
    `/dispatch/schedule/range`,
    { params: { start, end } },
  )
  return r.data
}


export async function ensureSchedule(dateStr: string): Promise<ScheduleStateDTO> {
  const r = await apiClient.post<ScheduleStateDTO>(
    `/dispatch/schedule/${dateStr}/ensure`,
  )
  return r.data
}


export async function finalizeSchedule(
  dateStr: string,
  notes?: string,
): Promise<ScheduleStateDTO> {
  const r = await apiClient.post<ScheduleStateDTO>(
    `/dispatch/schedule/${dateStr}/finalize`,
    { notes: notes ?? null },
  )
  return r.data
}


export async function revertSchedule(
  dateStr: string,
  reason: string,
): Promise<ScheduleStateDTO> {
  const r = await apiClient.post<ScheduleStateDTO>(
    `/dispatch/schedule/${dateStr}/revert`,
    { reason },
  )
  return r.data
}


export async function updateHoleDug(
  deliveryId: string,
  status: HoleDugStatus,
): Promise<HoleDugResponseDTO> {
  const r = await apiClient.patch<HoleDugResponseDTO>(
    `/dispatch/delivery/${deliveryId}/hole-dug`,
    { status },
  )
  return r.data
}


// ── Deliveries + drivers for the Monitor ─────────────────────────────


/** Fetch deliveries in a date range for the Monitor. Targets the
 *  dispatch-router `/deliveries` endpoint which carries the
 *  type_config + hole_dug_status fields the card renders. */
export async function fetchDeliveriesForRange(params: {
  start: string
  end: string
  schedulingType?: "kanban" | "ancillary" | "direct_ship"
}): Promise<DeliveryDTO[]> {
  const r = await apiClient.get<DeliveryDTO[]>(
    `/dispatch/deliveries`,
    {
      params: {
        start: params.start,
        end: params.end,
        scheduling_type: params.schedulingType,
      },
    },
  )
  return r.data
}


export async function fetchDrivers(): Promise<DriverDTO[]> {
  const r = await apiClient.get<DriverDTO[]>(
    `/dispatch/drivers`,
    { params: { active_only: true } },
  )
  return r.data
}


/** Read tenant-local wall clock. Used by the Monitor's Smart Stack to
 *  pick the single-day default (before 1pm tenant-local → Today
 *  primary; after 1pm → Tomorrow primary). */
export async function fetchTenantTime(): Promise<TenantTimeDTO> {
  const r = await apiClient.get<TenantTimeDTO>(`/dispatch/tenant-time`)
  return r.data
}


/** Convenience — partial-update a delivery. Used by the Monitor's
 *  quick-edit modal for time/driver/note. Schedule revert is handled
 *  server-side by the revert hook in delivery_service.update_delivery.
 *
 *  Uses the legacy `/delivery/deliveries/{id}` endpoint (the canonical
 *  update path); the dispatch router's Monitor reads are new but the
 *  delivery-write surface is shared with the rest of the platform. */
export async function updateDelivery(
  deliveryId: string,
  patch: {
    scheduled_at?: string | null
    /** Phase 4.3.2 (r56) — renamed from `assigned_driver_id`. The
     *  backend accepts either a `users.id` or (transitionally) a
     *  `drivers.id` value; the `resolve_primary_assignee_id` helper
     *  translates via `Driver.employee_id`. Going forward, frontend
     *  should pass `DriverDTO.user_id` directly. */
    primary_assignee_id?: string | null
    /** Phase 4.3.2 — optional second person (FK users.id). */
    helper_user_id?: string | null
    /** Phase 4.3.2 — self-referential FK for ancillary three-state
     *  model. */
    attached_to_delivery_id?: string | null
    /** Phase 4.3.2 — per-delivery start-of-day target. */
    driver_start_time?: string | null
    special_instructions?: string | null
    priority?: string
    status?: string
    type_config?: DeliveryTypeConfig | null
  },
): Promise<DeliveryDTO> {
  const r = await apiClient.patch<DeliveryDTO>(
    `/delivery/deliveries/${deliveryId}`,
    patch,
  )
  return r.data
}
