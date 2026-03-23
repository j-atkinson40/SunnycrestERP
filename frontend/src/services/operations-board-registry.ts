/**
 * OperationsBoardRegistry — singleton that manages board contributors.
 *
 * Contributors register on app initialization. The board reads the registry
 * at render time. Core features register as permanent contributors.
 * Extensions register themselves when installed.
 */

import type {
  BoardContributor,
  ButtonDefinition,
  EODSectionDefinition,
  OperationsBoardSettings,
  OverviewPanelDefinition,
  ProductionLogColumnDefinition,
  SettingsItemDefinition,
} from "@/types/operations-board"

class OperationsBoardRegistryClass {
  private contributors: Map<string, BoardContributor> = new Map()

  register(contributor: BoardContributor): void {
    if (this.contributors.has(contributor.contributor_key)) {
      console.warn(
        `BoardContributor ${contributor.contributor_key} already registered — skipping`
      )
      return
    }
    this.contributors.set(contributor.contributor_key, contributor)
  }

  getActiveContributors(activeExtensions: string[]): BoardContributor[] {
    return Array.from(this.contributors.values())
      .filter(
        (c) =>
          c.requires_extension === null ||
          activeExtensions.includes(c.requires_extension)
      )
      .sort((a, b) => a.sort_order - b.sort_order)
  }

  getButtons(
    activeExtensions: string[],
    settings: OperationsBoardSettings
  ): ButtonDefinition[] {
    return this.getActiveContributors(activeExtensions)
      .filter((c) => c.quick_action_button)
      .map((c) => c.quick_action_button!)
      .filter((b) => settings[`button_${b.key}`] !== false)
      .sort((a, b) => a.sort_order - b.sort_order)
  }

  getOverviewPanels(
    activeExtensions: string[],
    settings: OperationsBoardSettings
  ): OverviewPanelDefinition[] {
    return this.getActiveContributors(activeExtensions)
      .filter((c) => c.overview_panel)
      .map((c) => c.overview_panel!)
      .filter((p) => settings[`zone_${p.key}_visible`] !== false)
      .sort((a, b) => a.sort_order - b.sort_order)
  }

  getEODSections(activeExtensions: string[]): EODSectionDefinition[] {
    const active = this.getActiveContributors(activeExtensions)

    // Deduplicate by key — extension contributors override core contributors
    const deduped = new Map<string, EODSectionDefinition & { isExtension: boolean }>()

    // Add core sections first
    active
      .filter((c) => c.requires_extension === null && c.eod_summary_section)
      .forEach((c) =>
        deduped.set(c.eod_summary_section!.key, {
          ...c.eod_summary_section!,
          isExtension: false,
        })
      )

    // Extension sections override core sections with same key
    active
      .filter((c) => c.requires_extension !== null && c.eod_summary_section)
      .forEach((c) =>
        deduped.set(c.eod_summary_section!.key, {
          ...c.eod_summary_section!,
          isExtension: true,
        })
      )

    return Array.from(deduped.values()).sort((a, b) => a.sort_order - b.sort_order)
  }

  getProductionLogColumns(
    activeExtensions: string[]
  ): ProductionLogColumnDefinition[] {
    const baseColumns: ProductionLogColumnDefinition[] = [
      { key: "time", label: "Time", width: 1 },
      { key: "product", label: "Product", width: 3 },
      { key: "quantity", label: "Qty", width: 1 },
      { key: "qc_status", label: "QC", width: 1 },
      { key: "actions", label: "", width: 1 },
    ]

    const contributorColumns = this.getActiveContributors(activeExtensions).flatMap(
      (c) => c.production_log_columns || []
    )

    // Insert contributor columns before the actions column
    return [
      ...baseColumns.slice(0, -1),
      ...contributorColumns,
      baseColumns[baseColumns.length - 1],
    ]
  }

  getAllSettingsItems(
    activeExtensions: string[]
  ): Record<string, SettingsItemDefinition[]> {
    const result: Record<string, SettingsItemDefinition[]> = {}
    this.getActiveContributors(activeExtensions).forEach((c) => {
      if (c.settings_items?.length) {
        result[c.contributor_key] = c.settings_items
      }
    })
    return result
  }

  getSettingsItemsByGroup(
    activeExtensions: string[]
  ): Record<string, SettingsItemDefinition[]> {
    const allItems = this.getActiveContributors(activeExtensions).flatMap(
      (c) => c.settings_items || []
    )
    const grouped: Record<string, SettingsItemDefinition[]> = {
      sections: [],
      buttons: [],
      behavior: [],
    }
    for (const item of allItems) {
      if (!grouped[item.group]) grouped[item.group] = []
      grouped[item.group].push(item)
    }
    return grouped
  }
}

const OperationsBoardRegistry = new OperationsBoardRegistryClass()
export default OperationsBoardRegistry
