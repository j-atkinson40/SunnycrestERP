/**
 * Studio overview inventory client — Studio 1a-ii.
 *
 * Wraps the canonical inventory endpoint:
 *   GET /api/platform/admin/studio/inventory          (platform-wide)
 *   GET /api/platform/admin/studio/inventory?vertical=<slug>
 *
 * Routes through adminApi (PlatformUser auth realm).
 *
 * Decision 6 — `editor_email` may be null (rendered as silently
 * omitted on the recent-edits row, no "by —" placeholder).
 * Decision 7 — `count` may be null (registry inspector + plugin
 * registry under vertical scope); card omits the count display.
 */

import { adminApi } from "@/bridgeable-admin/lib/admin-api"


export type InventoryScope = "platform" | "vertical"


export interface SectionInventoryEntry {
  key: string
  label: string
  count: number | null
}


export interface RecentEditEntry {
  section: string
  entity_name: string
  entity_id: string
  editor_email: string | null
  edited_at: string
  deep_link_path: string
}


export interface InventoryResponse {
  scope: InventoryScope
  vertical_slug: string | null
  sections: SectionInventoryEntry[]
  recent_edits: RecentEditEntry[]
}


export class StudioInventoryError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "StudioInventoryError"
    this.status = status
  }
}


/**
 * Fetch Studio overview inventory. Pass `null` for Platform scope,
 * a vertical slug otherwise. Unknown slug → throws with status=404.
 */
export async function getStudioInventory(
  verticalSlug: string | null,
): Promise<InventoryResponse> {
  try {
    const params: Record<string, string> = {}
    if (verticalSlug) {
      params.vertical = verticalSlug
    }
    const { data } = await adminApi.get<InventoryResponse>(
      "/api/platform/admin/studio/inventory",
      { params },
    )
    return data
  } catch (err) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const e = err as any
    const status = e?.response?.status ?? 0
    const detail = e?.response?.data?.detail ?? e?.message ?? "Network error"
    throw new StudioInventoryError(detail, status)
  }
}
