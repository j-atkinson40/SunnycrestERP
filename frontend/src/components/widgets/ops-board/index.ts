// Widget component map for the Operations Board page context.
//
// Arc 4a.2a — every widget here now imports the WRAPPED version from
// `@/lib/visual-editor/registry/registrations/dashboard-widgets`. The
// wrapped versions carry the `data-component-name` boundary div from
// the `registerComponent` HOC at `register.ts:185` so the runtime
// editor's SelectionOverlay walks up the DOM and resolves clicks to
// the registered widget. Pre-Arc-4a.2a these widgets emitted no
// boundary div on the operations-board-desktop / home-dashboard /
// vault-overview surfaces; click-to-edit could not select them.
//
// Cast pattern (per R-1.6.12 + Arc 1 + foundation/manufacturing
// register.ts:54-60 convention): each wrapped component's TypeScript
// type carries its original prop shape (more specific than WidgetProps);
// `as unknown as ComponentType<WidgetProps>` widens it back to the
// WidgetComponentMap value type. Same runtime contract.

import type { ComponentType } from "react"

import type { WidgetComponentMap, WidgetProps } from "../types"

// Arc 4a.2a — wrapped versions emit data-component-name boundary div.
import {
  TodaysServicesWidget as TodaysServicesWidgetWrapped,
  LegacyQueueWidget as LegacyQueueWidgetWrapped,
  DriverStatusWidget as DriverStatusWidgetWrapped,
  ProductionStatusWidget as ProductionStatusWidgetWrapped,
  OpenOrdersWidget as OpenOrdersWidgetWrapped,
  InventoryWidget as InventoryWidgetWrapped,
  BriefingSummaryWidget as BriefingSummaryWidgetWrapped,
  ActivityFeedWidget as ActivityFeedWidgetWrapped,
  AtRiskAccountsWidget as AtRiskAccountsWidgetWrapped,
  QCStatusWidget as QCStatusWidgetWrapped,
  TimeClockWidget as TimeClockWidgetWrapped,
  SafetyWidget as SafetyWidgetWrapped,
  ComplianceUpcomingWidget as ComplianceUpcomingWidgetWrapped,
  TeamCertificationsWidget as TeamCertificationsWidgetWrapped,
  MyCertificationsWidget as MyCertificationsWidgetWrapped,
  MyTrainingWidget as MyTrainingWidgetWrapped,
  KbRecentWidget as KbRecentWidgetWrapped,
} from "@/lib/visual-editor/registry/registrations/dashboard-widgets"


const TodaysServicesWidget =
  TodaysServicesWidgetWrapped as unknown as ComponentType<WidgetProps>
const LegacyQueueWidget =
  LegacyQueueWidgetWrapped as unknown as ComponentType<WidgetProps>
const DriverStatusWidget =
  DriverStatusWidgetWrapped as unknown as ComponentType<WidgetProps>
const ProductionStatusWidget =
  ProductionStatusWidgetWrapped as unknown as ComponentType<WidgetProps>
const OpenOrdersWidget =
  OpenOrdersWidgetWrapped as unknown as ComponentType<WidgetProps>
const InventoryWidget =
  InventoryWidgetWrapped as unknown as ComponentType<WidgetProps>
const BriefingSummaryWidget =
  BriefingSummaryWidgetWrapped as unknown as ComponentType<WidgetProps>
const ActivityFeedWidget =
  ActivityFeedWidgetWrapped as unknown as ComponentType<WidgetProps>
const AtRiskAccountsWidget =
  AtRiskAccountsWidgetWrapped as unknown as ComponentType<WidgetProps>
const QCStatusWidget =
  QCStatusWidgetWrapped as unknown as ComponentType<WidgetProps>
const TimeClockWidget =
  TimeClockWidgetWrapped as unknown as ComponentType<WidgetProps>
const SafetyWidget =
  SafetyWidgetWrapped as unknown as ComponentType<WidgetProps>
const ComplianceUpcomingWidget =
  ComplianceUpcomingWidgetWrapped as unknown as ComponentType<WidgetProps>
const TeamCertificationsWidget =
  TeamCertificationsWidgetWrapped as unknown as ComponentType<WidgetProps>
const MyCertificationsWidget =
  MyCertificationsWidgetWrapped as unknown as ComponentType<WidgetProps>
const MyTrainingWidget =
  MyTrainingWidgetWrapped as unknown as ComponentType<WidgetProps>
const KbRecentWidget =
  KbRecentWidgetWrapped as unknown as ComponentType<WidgetProps>


export const OPS_BOARD_WIDGETS: WidgetComponentMap = {
  todays_services: TodaysServicesWidget,
  legacy_queue: LegacyQueueWidget,
  driver_status: DriverStatusWidget,
  production_status: ProductionStatusWidget,
  open_orders: OpenOrdersWidget,
  inventory_levels: InventoryWidget,
  briefing_summary: BriefingSummaryWidget,
  activity_feed: ActivityFeedWidget,
  at_risk_accounts: AtRiskAccountsWidget,
  qc_status: QCStatusWidget,
  time_clock: TimeClockWidget,
  safety_status: SafetyWidget,
  // Platform Polish additions (compliance, training, KB surfaces)
  compliance_upcoming: ComplianceUpcomingWidget,
  team_certifications: TeamCertificationsWidget,
  my_certifications: MyCertificationsWidget,
  my_training: MyTrainingWidget,
  kb_recent: KbRecentWidget,
}
