/**
 * Briefing item and announcement category registries.
 *
 * These define what can appear in employee briefings and what can be
 * individually disabled. The actual disabled state is stored in
 * assistant_profiles.disabled_briefing_items / disabled_announcement_categories.
 */

export interface BriefingItemDef {
  key: string;
  label: string;
  description: string;
}

export const BRIEFING_ITEM_REGISTRY: Record<string, BriefingItemDef[]> = {
  funeral_scheduling: [
    { key: "delivery_readiness", label: "Today's delivery readiness flags", description: "Unassigned drivers, vaults not in yard" },
    { key: "unscheduled_orders", label: "Unscheduled orders this week", description: "Orders with delivery dates but no driver assigned" },
    { key: "spring_burial_summary", label: "Spring burial activity", description: "Pending spring burials and cemetery opening dates" },
    { key: "ancillary_needs_action", label: "Ancillary orders needing action", description: "Drop-offs and pickups not yet assigned" },
    { key: "direct_ship_pending", label: "Direct ship orders pending", description: "Merchandise orders not yet ordered from Wilbert" },
  ],
  precast_scheduling: [
    { key: "precast_unscheduled", label: "Unscheduled precast orders", description: "Wastewater, Redi-Rock, or Rosetta orders needing scheduling" },
    { key: "open_quotes_aging", label: "Aging open quotes", description: "Quotes over 7 days old without response" },
    { key: "direct_ship_pending", label: "Direct ship orders pending", description: "Orders not yet placed with Wilbert" },
  ],
  invoicing_ar: [
    { key: "overdue_60_days", label: "Invoices over 60 days", description: "Accounts with balances past 60 days" },
    { key: "overdue_30_days", label: "Invoices over 30 days", description: "Accounts with balances past 30 days" },
    { key: "uninvoiced_orders", label: "Completed orders not invoiced", description: "Orders marked delivered with no invoice sent" },
    { key: "sync_errors", label: "Accounting sync errors", description: "QuickBooks or Sage sync failures" },
    { key: "payments_today", label: "Payments received today", description: "Summary of today's incoming payments" },
  ],
  safety_compliance: [
    { key: "overdue_inspections", label: "Overdue equipment inspections", description: "Equipment past inspection due date" },
    { key: "open_incidents", label: "Open safety incidents", description: "Incidents not yet closed or resolved" },
    { key: "compliance_score", label: "Compliance score alerts", description: "Score drop or specific gap warnings" },
    { key: "training_overdue", label: "Overdue training acknowledgments", description: "Employees who haven't acknowledged required safety notices" },
    { key: "npca_countdown", label: "NPCA audit countdown", description: "Days until next NPCA audit (if extension enabled)" },
    { key: "osha_300_unreviewed", label: "OSHA 300 entries pending review", description: "Auto-populated entries awaiting safety manager review" },
  ],
  full_admin: [
    { key: "revenue_trend", label: "Revenue this week vs last week", description: "Invoiced amount comparison" },
    { key: "ar_summary", label: "Outstanding AR summary", description: "Total AR and largest overdue account" },
    { key: "delivery_count", label: "Deliveries this week", description: "Completed delivery count" },
    { key: "compliance_scores", label: "Compliance scores", description: "NPCA and OSHA compliance score summary" },
    { key: "sync_status", label: "Accounting sync status", description: "Whether QuickBooks or Sage is syncing correctly" },
  ],
  driver: [
    { key: "assigned_deliveries", label: "Today's assigned deliveries", description: "All deliveries assigned to this driver today" },
    { key: "vault_readiness", label: "Vault readiness flags", description: "Vaults not confirmed in yard for their deliveries" },
    { key: "ancillary_dropoffs", label: "Ancillary drop-offs on route", description: "Non-burial drop-offs assigned to this driver" },
  ],
  production_staff: [
    { key: "missing_production_log", label: "Missing yesterday's production log", description: "Alert if no entries logged for yesterday" },
    { key: "pour_schedule", label: "Today's pour schedule", description: "Scheduled pours from work orders (if extension enabled)" },
    { key: "safety_alerts", label: "Critical safety alerts", description: "Any critical safety notices or overdue inspections" },
  ],
};

export interface AnnouncementCategoryDef {
  key: string;
  label: string;
  description: string;
  safetyOnly?: boolean;
}

export const ANNOUNCEMENT_CATEGORY_REGISTRY: AnnouncementCategoryDef[] = [
  { key: "procedure", label: "Safety procedures", description: "New or updated safety procedures", safetyOnly: true },
  { key: "equipment_alert", label: "Equipment alerts", description: "Equipment-specific safety alerts", safetyOnly: true },
  { key: "osha_reminder", label: "OSHA compliance reminders", description: "OSHA compliance reminders", safetyOnly: true },
  { key: "incident_followup", label: "Incident follow-up", description: "Follow-up notifications after safety incidents", safetyOnly: true },
  { key: "training_assignment", label: "Training assignments", description: "Monthly safety training notices", safetyOnly: true },
  { key: "toolbox_talk", label: "Toolbox talk topics", description: "Toolbox talk discussion topics", safetyOnly: true },
];

export const AREA_LABELS: Record<string, string> = {
  funeral_scheduling: "Funeral Scheduling",
  precast_scheduling: "Precast Scheduling",
  invoicing_ar: "Invoicing / AR",
  safety_compliance: "Safety & Compliance",
  production_log: "Production Log",
  customer_management: "Customer Management",
  full_admin: "Full Admin",
  driver: "Driver",
  production_staff: "Production Staff",
};
