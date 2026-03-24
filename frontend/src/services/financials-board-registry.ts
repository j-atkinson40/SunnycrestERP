/**
 * FinancialsBoardRegistry — mirrors OperationsBoardRegistry pattern.
 * Each zone is a registered contributor. The board reads from the registry
 * at render time and builds itself from whatever contributors are registered.
 */

export interface FinancialsZoneDefinition {
  key: string
  label: string
  component: string
  sort_order: number
  layout: "full" | "half-left" | "half-right"
  refresh_interval_ms: number
  default_visible: boolean
}

export interface FinancialsSettingsItem {
  key: string
  label: string
  default_value: boolean
  group: "zones" | "behavior"
}

export interface FinancialsBoardContributor {
  contributor_key: string
  zone: FinancialsZoneDefinition
  settings_items?: FinancialsSettingsItem[]
}

class FinancialsBoardRegistryClass {
  private contributors: Map<string, FinancialsBoardContributor> = new Map()

  register(contributor: FinancialsBoardContributor): void {
    if (this.contributors.has(contributor.contributor_key)) return
    this.contributors.set(contributor.contributor_key, contributor)
  }

  getZones(settings: Record<string, boolean | string>): FinancialsZoneDefinition[] {
    return Array.from(this.contributors.values())
      .map((c) => c.zone)
      .filter((z) => settings[`zone_${z.key}_visible`] !== false)
      .sort((a, b) => a.sort_order - b.sort_order)
  }

  getAllSettingsItems(): FinancialsSettingsItem[] {
    return Array.from(this.contributors.values()).flatMap((c) => c.settings_items || [])
  }
}

const FinancialsBoardRegistry = new FinancialsBoardRegistryClass()

// ── Register core zones ──

FinancialsBoardRegistry.register({
  contributor_key: "daily_briefing",
  zone: {
    key: "briefing",
    label: "Daily Briefing",
    component: "DailyBriefingZone",
    sort_order: 1,
    layout: "full",
    refresh_interval_ms: 1800000, // 30 min
    default_visible: true,
  },
  settings_items: [
    { key: "zone_briefing_visible", label: "Daily Briefing", default_value: true, group: "zones" },
  ],
})

FinancialsBoardRegistry.register({
  contributor_key: "ar_command",
  zone: {
    key: "ar",
    label: "AR Command Center",
    component: "ARCommandZone",
    sort_order: 2,
    layout: "half-left",
    refresh_interval_ms: 300000, // 5 min
    default_visible: true,
  },
  settings_items: [
    { key: "zone_ar_visible", label: "AR Command Center", default_value: true, group: "zones" },
  ],
})

FinancialsBoardRegistry.register({
  contributor_key: "ap_command",
  zone: {
    key: "ap",
    label: "AP Command Center",
    component: "APCommandZone",
    sort_order: 3,
    layout: "half-right",
    refresh_interval_ms: 300000,
    default_visible: true,
  },
  settings_items: [
    { key: "zone_ap_visible", label: "AP Command Center", default_value: true, group: "zones" },
  ],
})

FinancialsBoardRegistry.register({
  contributor_key: "cash_flow",
  zone: {
    key: "cashflow",
    label: "Cash Flow",
    component: "CashFlowZone",
    sort_order: 4,
    layout: "full",
    refresh_interval_ms: 900000, // 15 min
    default_visible: true,
  },
  settings_items: [
    { key: "zone_cashflow_visible", label: "Cash Flow Strip", default_value: true, group: "zones" },
  ],
})

FinancialsBoardRegistry.register({
  contributor_key: "reconciliation",
  zone: {
    key: "reconciliation",
    label: "Reconciliation",
    component: "ReconciliationZone",
    sort_order: 4.5,
    layout: "full",
    refresh_interval_ms: 600000,
    default_visible: true,
  },
  settings_items: [
    { key: "zone_reconciliation_visible", label: "Reconciliation", default_value: true, group: "zones" },
  ],
})

FinancialsBoardRegistry.register({
  contributor_key: "agent_activity",
  zone: {
    key: "activity",
    label: "Agent Activity",
    component: "AgentActivityZone",
    sort_order: 5,
    layout: "full",
    refresh_interval_ms: 300000,
    default_visible: true,
  },
  settings_items: [
    { key: "zone_activity_visible", label: "Agent Activity Feed", default_value: true, group: "zones" },
  ],
})

export default FinancialsBoardRegistry
