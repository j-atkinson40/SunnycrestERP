/**
 * workflow-node-palette — family vocabulary for the Workflow Builder
 * right-rail action palette (2026-05-29).
 *
 * Mirrors `widget-palette.ts`'s shape (order tuple + label map + a
 * grouping helper) so the Workflow Builder palette groups the 32 node
 * types into the 6 node families. The family taxonomy itself lives in
 * `node-families.ts` (NODE_FAMILY / resolveNodeFamily — also the A3
 * card-render source of truth); this module is the PALETTE-facing view:
 * a stable display order + plain-language labels + a family→types
 * grouping built from NODE_FAMILY (the reverse map node-families doesn't
 * expose). Keeping it here keeps node-families focused on card render.
 */
import {
  NODE_FAMILY,
  resolveNodeFamily,
  type NodeFamily,
} from "@/bridgeable-admin/components/visual-editor/workflow-canvas/node-families"

/** Display order of the 6 families in the palette (top → bottom). */
export const NODE_FAMILY_ORDER: readonly NodeFamily[] = [
  "lifecycle",
  "flow-control",
  "action-data",
  "ai-generation",
  "communication",
  "cross-tenant",
]

/** Plain-language family section headers. */
export const NODE_FAMILY_LABELS: Record<NodeFamily, string> = {
  lifecycle: "Lifecycle",
  "flow-control": "Flow control",
  "action-data": "Action & data",
  "ai-generation": "AI & generation",
  communication: "Communication",
  "cross-tenant": "Cross-tenant",
}

/** A type belonging to a family (palette-facing). */
export interface FamilyTypeEntry {
  name: string
  displayName: string
}

/** A family section with its member types (palette-facing). */
export interface FamilyGroup {
  family: NodeFamily
  label: string
  types: FamilyTypeEntry[]
}

export function nodeFamilyLabel(family: NodeFamily): string {
  return NODE_FAMILY_LABELS[family] ?? family
}

/**
 * Group an arbitrary list of node types into the 6 families, in
 * NODE_FAMILY_ORDER. Built from NODE_FAMILY via resolveNodeFamily (the
 * reverse of node-families' type→family map). A type with no family
 * (resolveNodeFamily → null) is bucketed defensively under the last
 * family so it never silently disappears from the palette. Empty
 * families are omitted (the palette renders only non-empty sections).
 */
export function nodeTypesByFamily(
  types: readonly FamilyTypeEntry[],
): FamilyGroup[] {
  const buckets = new Map<NodeFamily, FamilyTypeEntry[]>()
  for (const family of NODE_FAMILY_ORDER) buckets.set(family, [])
  const fallback = NODE_FAMILY_ORDER[NODE_FAMILY_ORDER.length - 1]
  for (const t of types) {
    const family = resolveNodeFamily(t.name) ?? fallback
    buckets.get(family)!.push(t)
  }
  return NODE_FAMILY_ORDER.map((family) => ({
    family,
    label: nodeFamilyLabel(family),
    types: buckets.get(family)!,
  })).filter((g) => g.types.length > 0)
}

/** All node-type names known to the family taxonomy (for completeness). */
export function allFamilyTaxonomyTypes(): string[] {
  return Object.keys(NODE_FAMILY)
}
