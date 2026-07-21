/**
 * FinancialsBoardRegistry — the board's SETTINGS registry.
 *
 * Honest role (Suite Session 2): the board renders its zones directly in
 * financials-board.tsx (explicit JSX per zone, gated by settings flags);
 * it never consumed the registry's render half, so the dead getZones()
 * was deleted rather than left to decorate. What IS load-bearing is
 * getAllSettingsItems() — every registered contributor's settings item
 * appears in the board's settings panel. A new zone registers here to
 * gain its visibility toggle, and renders explicitly in the page.
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
  contributor_key: "audit_readiness",
  zone: {
    key: "audit",
    label: "Audit Readiness",
    component: "AuditReadinessZone",
    sort_order: 4.7,
    layout: "full",
    refresh_interval_ms: 1800000,
    default_visible: true,
  },
  settings_items: [
    { key: "zone_audit_visible", label: "Audit Readiness", default_value: true, group: "zones" },
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
