/**
 * Operations Board Registry Types
 *
 * The registry architecture allows core features and extensions to register
 * themselves as board contributors. The board reads from the registry at
 * render time and builds itself dynamically.
 */

import type { ComponentType } from "react"

// ── Button Definition ──

export type ButtonDefinition = {
  key: string
  label: string
  icon: string
  route: string
  sort_order: number
}

// ── Overview Panel Definition ──

export type OverviewPanelDefinition = {
  key: string
  label: string
  component: string // React component key in PANEL_COMPONENTS map
  sort_order: number
}

// ── Settings Item Definition ──

export type SettingsItemDefinition = {
  key: string // must match a column in operations_board_settings or contributor_settings JSONB
  label: string
  type: "zone_toggle" | "button_toggle" | "custom"
  default_value: boolean
  group: "sections" | "buttons" | "behavior"
  description?: string
}

// ── EOD Section Definition ──

export type EODSectionDefinition = {
  key: string
  label: string
  component: string // React component key in EOD_SECTION_COMPONENTS map
  sort_order: number
}

// ── Production Log Column Definition ──

export type ProductionLogColumnDefinition = {
  key: string
  label: string
  width: number // relative column width
  render_component?: string
}

// ── Board Contributor ──

export type BoardContributor = {
  contributor_key: string
  requires_extension: string | null // null = always active
  sort_order: number

  // What this contributor adds — all optional
  quick_action_button?: ButtonDefinition
  overview_panel?: OverviewPanelDefinition
  settings_items?: SettingsItemDefinition[]
  eod_summary_section?: EODSectionDefinition
  production_log_columns?: ProductionLogColumnDefinition[]
}

// ── Board Settings (flat dict from backend) ──

export type OperationsBoardSettings = Record<string, boolean | string>
