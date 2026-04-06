// Widget component map for the Operations Board page context

import type { WidgetComponentMap } from "../types"

import TodaysServicesWidget from "./TodaysServicesWidget"
import LegacyQueueWidget from "./LegacyQueueWidget"
import DriverStatusWidget from "./DriverStatusWidget"
import ProductionStatusWidget from "./ProductionStatusWidget"
import OpenOrdersWidget from "./OpenOrdersWidget"
import InventoryWidget from "./InventoryWidget"
import BriefingSummaryWidget from "./BriefingSummaryWidget"
import ActivityFeedWidget from "./ActivityFeedWidget"
import AtRiskAccountsWidget from "./AtRiskAccountsWidget"
import QCStatusWidget from "./QCStatusWidget"
import TimeClockWidget from "./TimeClockWidget"
import SafetyWidget from "./SafetyWidget"

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
}
