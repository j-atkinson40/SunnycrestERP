/**
 * Mock data harness for the Funeral Scheduling Focus editor preview.
 *
 * Supplies representative Hopkins-FH-shape data — realistic deceased
 * names, family details, service times, dispositions — but obviously
 * not real tenant data (named with the "Sample" prefix where the
 * pattern allows; clearly fictional + disclaimed in the harness
 * docstring). The shape exactly matches the production DTOs from
 * `services/dispatch-service.ts` so the preview renders through the
 * real DeliveryCard / DateBox / AncillaryCard components without
 * type adjustments.
 *
 * Pattern parallels Phase 2's preview-data harness for the theme
 * editor (`lib/visual-editor/themes/preview-data.tsx`) which uses
 * structurally-faithful stand-ins fed by mock data rather than
 * mounting the full production components inside the editor.
 *
 * Three sample scenarios available — Default (mid-week, normal volume),
 * High-Volume (busier kanban with more cases), and Empty (verifies
 * the empty kanban appearance).
 */
import type {
  DeliveryDTO,
  DeliveryTypeConfig,
  DriverDTO,
  ScheduleStateDTO,
  TenantTimeDTO,
} from "@/services/dispatch-service"


export type SampleScenario = "default" | "high-volume" | "empty"


// ─── Tenant time + schedule baseline ─────────────────────────


/** Stable preview "today" — June 5, 2026 (mid-week Friday). Deliveries
 *  are scheduled for "today" so the preview renders at the canonical
 *  default day-cursor without browser-clock drift. */
const PREVIEW_TODAY = "2026-06-05"
const PREVIEW_TIMEZONE = "America/New_York"


export function makeMockTenantTime(): TenantTimeDTO {
  return {
    tenant_timezone: PREVIEW_TIMEZONE,
    local_iso: "2026-06-05T10:30:00-04:00",
    local_date: PREVIEW_TODAY,
    local_hour: 10,
    local_minute: 30,
  }
}


export function makeMockSchedule(scenario: SampleScenario): ScheduleStateDTO {
  return {
    id: scenario === "empty" ? null : "preview-schedule-001",
    company_id: "preview-tenant",
    schedule_date: PREVIEW_TODAY,
    state: scenario === "empty" ? "not_created" : "draft",
    finalized_at: null,
    finalized_by_user_id: null,
    auto_finalized: false,
    last_reverted_at: null,
    last_revert_reason: null,
    created_at: "2026-06-05T07:00:00-04:00",
    updated_at: "2026-06-05T10:15:00-04:00",
  }
}


// ─── Drivers ─────────────────────────────────────────────────


export function makeMockDrivers(scenario: SampleScenario): DriverDTO[] {
  const base: DriverDTO[] = [
    {
      id: "preview-driver-1",
      user_id: "user-driver-1",
      license_number: "CDL-1234",
      license_class: "B",
      active: true,
      display_name: "Tom Reilly",
    },
    {
      id: "preview-driver-2",
      user_id: "user-driver-2",
      license_number: "CDL-5678",
      license_class: "B",
      active: true,
      display_name: "Sandra Mills",
    },
    {
      id: "preview-driver-3",
      user_id: "user-driver-3",
      license_number: "CDL-9012",
      license_class: "B",
      active: true,
      display_name: "Marcus Chen",
    },
  ]
  if (scenario === "high-volume") {
    base.push({
      id: "preview-driver-4",
      user_id: "user-driver-4",
      license_number: "CDL-3456",
      license_class: "B",
      active: true,
      display_name: "Diane Park",
    })
    base.push({
      id: "preview-driver-5",
      user_id: "user-driver-5",
      license_number: "CDL-7890",
      license_class: "B",
      active: true,
      display_name: "Felipe Ortiz",
    })
  }
  return base
}


// ─── Deliveries ──────────────────────────────────────────────


function _typeConfig(over: Partial<DeliveryTypeConfig> = {}): DeliveryTypeConfig {
  return {
    family_name: "Sample Family",
    cemetery_name: "Riverside Memorial Cemetery",
    cemetery_city: "Riverside",
    cemetery_section: "Sec 12, Lot 8",
    funeral_home_name: "Hopkins Funeral Home",
    service_time: "11:00 AM",
    service_type: "graveside",
    vault_type: "Continental Bronze",
    equipment_type: "Full Equipment",
    eta: null,
    driver_note: null,
    chat_activity_count: null,
    ...over,
  }
}


function _delivery(
  id: string,
  primary_assignee_id: string | null,
  type_config: DeliveryTypeConfig,
  scheduling_type: DeliveryDTO["scheduling_type"] = "kanban",
  hole_dug: DeliveryDTO["hole_dug_status"] = "unknown",
): DeliveryDTO {
  return {
    id,
    company_id: "preview-tenant",
    order_id: `preview-order-${id}`,
    customer_id: "preview-fh-hopkins",
    delivery_type: "graveside",
    status: "scheduled",
    priority: "normal",
    requested_date: PREVIEW_TODAY,
    scheduled_at: `${PREVIEW_TODAY}T10:00:00-04:00`,
    completed_at: null,
    scheduling_type,
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    primary_assignee_id,
    helper_user_id: null,
    attached_to_delivery_id: null,
    driver_start_time: "08:00:00",
    hole_dug_status: hole_dug,
    type_config,
    special_instructions: null,
    helper_user_name: null,
    attached_to_family_name: null,
  }
}


export function makeMockDeliveries(scenario: SampleScenario): DeliveryDTO[] {
  if (scenario === "empty") return []

  // Default scenario: 6 kanban deliveries spread across 3 drivers + 1
  // unassigned. Realistic mix of dispositions, cemeteries, vault types.
  const base: DeliveryDTO[] = [
    _delivery(
      "preview-d-1",
      "user-driver-1",
      _typeConfig({
        family_name: "Sample Anderson",
        cemetery_name: "Riverside Memorial Cemetery",
        cemetery_section: "Sec 14, Lot 42",
        service_time: "10:00 AM",
        service_type: "graveside",
        vault_type: "Continental Bronze",
        equipment_type: "Full Equipment",
      }),
      "kanban",
      "yes",
    ),
    _delivery(
      "preview-d-2",
      "user-driver-1",
      _typeConfig({
        family_name: "Sample Brennan",
        cemetery_name: "Sacred Heart Cemetery",
        cemetery_section: "Sec 3, Lot 18",
        service_time: "11:30 AM",
        service_type: "church",
        vault_type: "Monticello",
        equipment_type: "Full w/ Placer",
        eta: "12:30 PM",
      }),
    ),
    _delivery(
      "preview-d-3",
      "user-driver-2",
      _typeConfig({
        family_name: "Sample Castellanos",
        cemetery_name: "Riverside Memorial Cemetery",
        cemetery_section: "Sec 7, Lot 91",
        service_time: "1:00 PM",
        service_type: "graveside",
        vault_type: "Cameo Rose",
        equipment_type: "Full Equipment",
      }),
      "kanban",
      "yes",
    ),
    _delivery(
      "preview-d-4",
      "user-driver-2",
      _typeConfig({
        family_name: "Sample Donovan",
        cemetery_name: "Greenlawn Cemetery",
        cemetery_section: "Sec 22, Lot 7",
        service_time: "2:30 PM",
        service_type: "funeral_home",
        funeral_home_name: "Hopkins Funeral Home",
        vault_type: "Triune Copper",
        equipment_type: "Device",
        eta: "3:30 PM",
      }),
    ),
    _delivery(
      "preview-d-5",
      "user-driver-3",
      _typeConfig({
        family_name: "Sample Eriksen",
        cemetery_name: "Riverside Memorial Cemetery",
        cemetery_section: "Sec 14, Lot 56",
        service_time: "11:00 AM",
        service_type: "graveside",
        vault_type: "Standard",
        equipment_type: "Full Equipment",
      }),
      "kanban",
      "no",
    ),
    _delivery(
      "preview-d-6",
      null, // unassigned — appears in Unassigned lane
      _typeConfig({
        family_name: "Sample Foster",
        cemetery_name: "Maple Grove Cemetery",
        cemetery_section: "Sec 5, Lot 33",
        service_time: "3:00 PM",
        service_type: "graveside",
        vault_type: "Salute",
        equipment_type: "Full Equipment",
      }),
    ),
  ]

  if (scenario === "high-volume") {
    base.push(
      _delivery(
        "preview-d-7",
        "user-driver-4",
        _typeConfig({
          family_name: "Sample Gallego",
          cemetery_name: "Riverside Memorial Cemetery",
          cemetery_section: "Sec 18, Lot 4",
          service_time: "9:30 AM",
          service_type: "graveside",
          vault_type: "Monarch",
          equipment_type: "Full Equipment",
        }),
        "kanban",
        "yes",
      ),
      _delivery(
        "preview-d-8",
        "user-driver-4",
        _typeConfig({
          family_name: "Sample Hernandez",
          cemetery_name: "Sacred Heart Cemetery",
          cemetery_section: "Sec 11, Lot 27",
          service_time: "12:00 PM",
          service_type: "church",
          vault_type: "Continental Bronze",
          equipment_type: "Full Equipment",
          eta: "1:30 PM",
        }),
      ),
      _delivery(
        "preview-d-9",
        "user-driver-5",
        _typeConfig({
          family_name: "Sample Iverson",
          cemetery_name: "Greenlawn Cemetery",
          cemetery_section: "Sec 9, Lot 65",
          service_time: "2:00 PM",
          service_type: "graveside",
          vault_type: "Triune Copper",
          equipment_type: "Full w/ Placer",
        }),
      ),
      _delivery(
        "preview-d-10",
        null,
        _typeConfig({
          family_name: "Sample Johnson",
          cemetery_name: "Riverside Memorial Cemetery",
          cemetery_section: "Sec 6, Lot 14",
          service_time: "4:00 PM",
          service_type: "graveside",
          vault_type: "Standard",
          equipment_type: "Device",
        }),
      ),
    )
  }

  return base
}


// ─── Ancillary pool items ────────────────────────────────────


/** Pool items shape mirrors what AncillaryPoolPin reads from
 *  SchedulingFocusContext (delivery rows with scheduling_type=
 *  "ancillary" + primary_assignee_id null + attached_to_delivery_id
 *  null). */
export function makeMockPoolItems(scenario: SampleScenario): DeliveryDTO[] {
  if (scenario === "empty") return []

  return [
    _delivery(
      "preview-pool-1",
      null,
      _typeConfig({
        family_name: "Sample Krause",
        service_type: "ancillary_pickup",
        vault_type: "Greenwood Urn Vault",
      }),
      "ancillary",
    ),
    _delivery(
      "preview-pool-2",
      null,
      _typeConfig({
        family_name: "Sample Larson",
        service_type: "ancillary_pickup",
        vault_type: "Bronze Memorial Urn Vault",
      }),
      "ancillary",
    ),
  ]
}


// ─── Aggregate helper ──────────────────────────────────────


export interface FuneralSchedulingMockBundle {
  scenario: SampleScenario
  tenant_time: TenantTimeDTO
  schedule: ScheduleStateDTO
  drivers: DriverDTO[]
  deliveries: DeliveryDTO[]
  pool_items: DeliveryDTO[]
  target_date: string
}


export function buildMockBundle(
  scenario: SampleScenario = "default",
): FuneralSchedulingMockBundle {
  return {
    scenario,
    tenant_time: makeMockTenantTime(),
    schedule: makeMockSchedule(scenario),
    drivers: makeMockDrivers(scenario),
    deliveries: makeMockDeliveries(scenario),
    pool_items: makeMockPoolItems(scenario),
    target_date: PREVIEW_TODAY,
  }
}


export const SAMPLE_SCENARIO_OPTIONS: ReadonlyArray<{
  id: SampleScenario
  label: string
  description: string
}> = [
  {
    id: "default",
    label: "Default sample",
    description:
      "Mid-week Friday, 6 deliveries across 3 drivers + 1 unassigned. Representative Hopkins-FH-shape day.",
  },
  {
    id: "high-volume",
    label: "High-volume day",
    description:
      "10 deliveries across 5 drivers — busier kanban; useful for verifying lane-density appearance.",
  },
  {
    id: "empty",
    label: "Empty state",
    description:
      "No cases scheduled — verifies the kanban's empty-state appearance.",
  },
]
