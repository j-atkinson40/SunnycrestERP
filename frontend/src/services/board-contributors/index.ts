/**
 * Board contributor registrations.
 * Import this file once at app startup to register all contributors.
 */

import OperationsBoardRegistry from "@/services/operations-board-registry"

// ─── CORE CONTRIBUTORS (requires_extension: null) ───────────────────────────

OperationsBoardRegistry.register({
  contributor_key: "core_incident",
  requires_extension: null,
  sort_order: 1,
  quick_action_button: {
    key: "log_incident",
    label: "Log Incident",
    icon: "alert-triangle",
    route: "/console/operations/incident",
    sort_order: 1,
  },
  settings_items: [
    {
      key: "button_log_incident",
      label: "Log Incident button",
      type: "button_toggle",
      default_value: true,
      group: "buttons",
    },
  ],
})

OperationsBoardRegistry.register({
  contributor_key: "core_safety_observation",
  requires_extension: null,
  sort_order: 2,
  quick_action_button: {
    key: "safety_observation",
    label: "Safety Obs.",
    icon: "search",
    route: "/console/operations/observation",
    sort_order: 2,
  },
  overview_panel: {
    key: "safety_status",
    label: "Safety",
    component: "SafetyStatusPanel",
    sort_order: 3,
  },
  settings_items: [
    {
      key: "button_safety_observation",
      label: "Safety Observation button",
      type: "button_toggle",
      default_value: true,
      group: "buttons",
    },
    {
      key: "zone_safety_status_visible",
      label: "Safety Status panel",
      type: "zone_toggle",
      default_value: true,
      group: "sections",
    },
  ],
})

OperationsBoardRegistry.register({
  contributor_key: "core_qc",
  requires_extension: null,
  sort_order: 3,
  quick_action_button: {
    key: "qc_check",
    label: "QC Check",
    icon: "check-circle",
    route: "/console/operations/qc",
    sort_order: 3,
  },
  eod_summary_section: {
    key: "qc_summary",
    label: "QC Results",
    component: "QCEODSection",
    sort_order: 2,
  },
  settings_items: [
    {
      key: "button_qc_check",
      label: "QC Check button",
      type: "button_toggle",
      default_value: true,
      group: "buttons",
    },
  ],
})

OperationsBoardRegistry.register({
  contributor_key: "core_product_entry",
  requires_extension: null,
  sort_order: 4,
  quick_action_button: {
    key: "log_product",
    label: "Log Product",
    icon: "package",
    route: "/console/operations/product-entry",
    sort_order: 4,
  },
  eod_summary_section: {
    key: "production_summary",
    label: "Production Today",
    component: "ProductionEODSection",
    sort_order: 1,
  },
  production_log_columns: [],
  settings_items: [
    {
      key: "button_log_product",
      label: "Log Product Entry button",
      type: "button_toggle",
      default_value: true,
      group: "buttons",
    },
  ],
})

OperationsBoardRegistry.register({
  contributor_key: "core_end_of_day",
  requires_extension: null,
  sort_order: 5,
  quick_action_button: {
    key: "end_of_day",
    label: "End of Day",
    icon: "clipboard-list",
    route: "/console/operations/end-of-day",
    sort_order: 5,
  },
  settings_items: [
    {
      key: "button_end_of_day",
      label: "End of Day Summary button",
      type: "button_toggle",
      default_value: true,
      group: "buttons",
    },
    {
      key: "eod_reminder_enabled",
      label: "End of day reminder",
      type: "custom",
      default_value: true,
      group: "behavior",
      description: "Remind you to submit the daily summary",
    },
  ],
})

OperationsBoardRegistry.register({
  contributor_key: "core_inspection",
  requires_extension: null,
  sort_order: 6,
  quick_action_button: {
    key: "equipment_inspection",
    label: "Inspection",
    icon: "wrench",
    route: "/console/operations/inspection",
    sort_order: 6,
  },
  eod_summary_section: {
    key: "equipment_summary",
    label: "Equipment",
    component: "EquipmentEODSection",
    sort_order: 3,
  },
  settings_items: [
    {
      key: "button_equipment_inspection",
      label: "Equipment Inspection button",
      type: "button_toggle",
      default_value: true,
      group: "buttons",
    },
  ],
})

OperationsBoardRegistry.register({
  contributor_key: "core_driver_schedule",
  requires_extension: null,
  sort_order: 7,
  overview_panel: {
    key: "driver_schedule",
    label: "Today's Deliveries",
    component: "DriverSchedulePanel",
    sort_order: 2,
  },
  settings_items: [
    {
      key: "zone_driver_schedule_visible",
      label: "Driver Schedule panel",
      type: "zone_toggle",
      default_value: true,
      group: "sections",
    },
  ],
})

// ─── EXTENSION CONTRIBUTORS ──────────────────────────────────────────────────

OperationsBoardRegistry.register({
  contributor_key: "work_orders_extension",
  requires_extension: "work_orders",
  sort_order: 10,
  quick_action_button: {
    key: "work_order_step",
    label: "Work Order",
    icon: "check-square",
    route: "/console/operations/work-order-step",
    sort_order: 7,
  },
  overview_panel: {
    key: "work_orders",
    label: "Work Orders",
    component: "WorkOrdersOverviewPanel",
    sort_order: 1,
  },
  eod_summary_section: {
    key: "work_orders_summary",
    label: "Work Orders",
    component: "WorkOrdersEODSection",
    sort_order: 4,
  },
  settings_items: [
    {
      key: "zone_work_orders_visible",
      label: "Work Orders panel",
      type: "zone_toggle",
      default_value: true,
      group: "sections",
      description: "Requires Work Orders extension",
    },
    {
      key: "button_work_order_step",
      label: "Work Order Step button",
      type: "button_toggle",
      default_value: true,
      group: "buttons",
    },
    {
      key: "auto_show_work_order_button",
      label: "Auto-show when extension activates",
      type: "custom",
      default_value: true,
      group: "behavior",
    },
  ],
})

OperationsBoardRegistry.register({
  contributor_key: "advanced_qc_extension",
  requires_extension: "qc_module_full",
  sort_order: 11,
  // No new button — upgrades the existing QC Check button behavior
  // Replaces the core_qc eod section when active (same key)
  eod_summary_section: {
    key: "qc_summary", // same key as core_qc — intentional override
    label: "QC Results",
    component: "AdvancedQCEODSection",
    sort_order: 2,
  },
  settings_items: [
    {
      key: "auto_upgrade_qc_advanced",
      label: "Use advanced QC checklist",
      type: "custom",
      default_value: true,
      group: "behavior",
      description: "Replaces basic pass/fail with full QC checklist",
    },
  ],
})

// ─── VAULT PURCHASE MODE CONTRIBUTOR ────────────────────────────────────────
// Only active when company.vault_fulfillment_mode is 'purchase' or 'hybrid'.
// The operations-board page pushes "vault_purchase_mode" into activeExtensions
// when that condition is met — so this contributor behaves like a conditional
// feature without being a true extension.

OperationsBoardRegistry.register({
  contributor_key: "vault_replenishment",
  requires_extension: "vault_purchase_mode",
  sort_order: 0, // top of board, above all other panels
  overview_panel: {
    key: "vault_replenishment",
    label: "Vault Replenishment",
    component: "VaultReplenishmentWidget",
    sort_order: 0,
  },
  settings_items: [
    {
      key: "zone_vault_replenishment_visible",
      label: "Vault Replenishment panel",
      type: "zone_toggle",
      default_value: true,
      group: "sections",
    },
  ],
})
