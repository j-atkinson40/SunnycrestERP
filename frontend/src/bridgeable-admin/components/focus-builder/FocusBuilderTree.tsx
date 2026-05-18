/**
 * FocusBuilderTree — Focus-specific consumer of VerticalGroupedTree.
 *
 * Sub-arc F-1 deliverable. Owns:
 *   - Fetching verticals + cores + templates.
 *   - Building the vertical → focus-type → core → template tree.
 *   - Orphan-handling (Q-7): cores with no templates fall into an
 *     "Other" focus-type sub-group under each vertical they would
 *     otherwise belong to; cores that cannot be assigned a vertical
 *     fall into a top-level "Unclassified" pseudo-vertical at the
 *     bottom of the rail.
 *   - Scope chip on template nodes (Q-8 LOCKED: flat list + chip).
 *   - localStorage expansion persistence under
 *     bridgeable.focus-builder.tree-expanded.
 *   - Q-5 default expansion: Studio active vertical (from
 *     readLastVertical() or `studioActiveVertical` prop) expanded;
 *     fallback alphabetical-first. Inside the expanded vertical,
 *     focus-types start expanded so cores are visible. Templates
 *     under cores stay collapsed.
 *
 * **Vertical-resolution per-core** — the focus_cores table has no
 * `vertical` field today (verified at F-1 dispatch). Vertical
 * association is derived from inheriting templates' `vertical` /
 * `scope`:
 *   - A core is shown under each vertical that has at least one
 *     vertical_default template inheriting from it.
 *   - A core whose only inheriting templates are platform_default
 *     (no vertical_default) is shown under EVERY published vertical
 *     (cross-vertical core).
 *   - A core with NO inheriting templates falls into "Unclassified".
 *
 * This is the F-1 read-only behavior; F-2+ can refine if core-level
 * `vertical` becomes a DB field.
 */
import * as React from "react"

import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"
import {
  focusTemplatesService,
  type TemplateRecord,
} from "@/bridgeable-admin/services/focus-templates-service"
import {
  verticalsService,
  type Vertical,
} from "@/bridgeable-admin/services/verticals-service"
import { readLastVertical } from "@/bridgeable-admin/lib/studio-routes"

import {
  VerticalGroupedTree,
  type TreeNode,
} from "@/bridgeable-admin/components/builder-primitives/VerticalGroupedTree"
import {
  focusTypeForCore,
  focusTypeLabel,
  FOCUS_TYPES,
  type FocusType,
} from "@/lib/visual-editor/focus-types"


const STORAGE_KEY = "bridgeable.focus-builder.tree-expanded"
const UNCLASSIFIED_VERTICAL = "__unclassified__"


export interface FocusBuilderSubject {
  kind: "core" | "template"
  id: string
}


export interface FocusBuilderTreeProps {
  /** Current selection (one of core:<id> / template:<id>). */
  selectedSubject: FocusBuilderSubject | null
  /** Fires when the operator clicks a core or template leaf. */
  onSelectSubject: (subject: FocusBuilderSubject) => void
  /** Optional Studio active vertical slug for default expansion. */
  studioActiveVertical?: string | null
}


export interface FocusBuilderTreeNodeMetadata {
  kind: "vertical" | "focus-type" | "core" | "template" | "new-template"
  /** For "core" + "template" — for use by selection. */
  subjectId?: string
  /** For "template" — surface scope as a chip. */
  scope?: "platform_default" | "vertical_default" | "tenant"
  /** For "new-template" — the parent core id. */
  parentCoreId?: string
}


function readExpandedFromStorage(): Set<string> {
  if (typeof window === "undefined") return new Set()
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw) as unknown
    if (Array.isArray(parsed)) {
      return new Set(parsed.filter((x): x is string => typeof x === "string"))
    }
  } catch {
    // ignore
  }
  return new Set()
}


function writeExpandedToStorage(set: Set<string>) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(Array.from(set)),
    )
  } catch {
    // ignore
  }
}


function ScopeChip({
  scope,
}: {
  scope: "platform_default" | "vertical_default" | "tenant"
}) {
  const label =
    scope === "platform_default"
      ? "platform"
      : scope === "vertical_default"
        ? "vertical"
        : "tenant"
  return (
    <span
      className="rounded-sm bg-[color:var(--surface-sunken)] px-1 py-px font-plex-mono text-[9px] uppercase tracking-wider text-content-muted"
      data-testid={`scope-chip-${scope}`}
    >
      {label}
    </span>
  )
}


interface TreeData {
  verticals: Vertical[]
  cores: CoreRecord[]
  templates: TemplateRecord[]
}


/**
 * Build the vertical-grouped tree from raw data. Pure function —
 * unit-testable, deterministic.
 */
export function buildFocusBuilderTree(data: TreeData): TreeNode[] {
  const { verticals, cores, templates } = data

  const coreById = new Map<string, CoreRecord>()
  for (const c of cores) coreById.set(c.id, c)

  // For each core, collect which verticals it should appear under.
  // - vertical_default templates: append their vertical
  // - platform_default templates: signal "cross-vertical" → all
  // - no templates at all: → UNCLASSIFIED
  const verticalsByCore = new Map<string, Set<string>>()
  const templatesByCore = new Map<string, TemplateRecord[]>()
  for (const t of templates) {
    const list = templatesByCore.get(t.inherits_from_core_id) ?? []
    list.push(t)
    templatesByCore.set(t.inherits_from_core_id, list)
  }

  const publishedVerticalSlugs = verticals
    .filter((v) => v.status === "published")
    .map((v) => v.slug)

  for (const c of cores) {
    const tList = templatesByCore.get(c.id) ?? []
    if (tList.length === 0) {
      verticalsByCore.set(c.id, new Set([UNCLASSIFIED_VERTICAL]))
      continue
    }
    const set = new Set<string>()
    let hasPlatform = false
    for (const t of tList) {
      if (t.scope === "platform_default") hasPlatform = true
      else if (t.scope === "vertical_default" && t.vertical) set.add(t.vertical)
    }
    if (hasPlatform) {
      // Platform-default core is cross-vertical — show in every
      // published vertical.
      for (const v of publishedVerticalSlugs) set.add(v)
    }
    if (set.size === 0) {
      set.add(UNCLASSIFIED_VERTICAL)
    }
    verticalsByCore.set(c.id, set)
  }

  // Build vertical → focus-type → cores nesting.
  // verticalGroup id = `vertical:<slug>`
  // focusTypeGroup id = `vertical:<slug>::focus-type:<fid>`
  // core leaf id = `vertical:<slug>::focus-type:<fid>::core:<id>`
  // template leaf id = `...::core:<id>::template:<tid>`
  // +new pseudo id = `...::core:<id>::new`

  const verticalNodes: TreeNode[] = []

  // Iterate over published verticals in sort_order order (verticals
  // already arrive sorted from list endpoint), then append the
  // pseudo-Unclassified at the very end if any cores landed there.
  const allVerticalSlugs = [...publishedVerticalSlugs]
  const hasUnclassified = Array.from(verticalsByCore.values()).some((s) =>
    s.has(UNCLASSIFIED_VERTICAL),
  )

  for (const vSlug of allVerticalSlugs) {
    const v = verticals.find((vv) => vv.slug === vSlug)!
    const coresHere = cores.filter((c) =>
      (verticalsByCore.get(c.id) ?? new Set()).has(vSlug),
    )
    if (coresHere.length === 0) {
      // Vertical with no applicable cores — still render so operators
      // see their vertical exists, but without children. Skipping would
      // hide currently-empty verticals.
      verticalNodes.push({
        id: `vertical:${vSlug}`,
        label: v.display_name,
        iconName: "layers",
        children: [],
        metadata: { kind: "vertical" } satisfies FocusBuilderTreeNodeMetadata,
      })
      continue
    }

    // Group cores by focus-type.
    const coresByType = new Map<FocusType, CoreRecord[]>()
    for (const c of coresHere) {
      const ft = focusTypeForCore(c)
      const arr = coresByType.get(ft) ?? []
      arr.push(c)
      coresByType.set(ft, arr)
    }

    // Build focus-type children in canonical FOCUS_TYPES order.
    const focusTypeChildren: TreeNode[] = []
    for (const { id: ft } of FOCUS_TYPES) {
      const list = coresByType.get(ft)
      if (!list || list.length === 0) continue

      const coreChildren: TreeNode[] = list.map((c) => {
        const tList = (templatesByCore.get(c.id) ?? []).filter((t) => {
          if (t.scope === "platform_default") return true
          return t.scope === "vertical_default" && t.vertical === vSlug
        })

        const templateChildren: TreeNode[] = tList.map((t) => ({
          id: `vertical:${vSlug}::focus-type:${ft}::core:${c.id}::template:${t.id}`,
          label: t.display_name,
          iconName: "square-dashed",
          metadata: {
            kind: "template",
            subjectId: t.id,
            scope: t.scope,
          } satisfies FocusBuilderTreeNodeMetadata,
        }))

        // + New <CoreName>-based template pseudo-child.
        templateChildren.push({
          id: `vertical:${vSlug}::focus-type:${ft}::core:${c.id}::new`,
          label: `+ New ${c.display_name}-based template`,
          metadata: {
            kind: "new-template",
            parentCoreId: c.id,
          } satisfies FocusBuilderTreeNodeMetadata,
        })

        return {
          id: `vertical:${vSlug}::focus-type:${ft}::core:${c.id}`,
          label: c.display_name,
          iconName: "square",
          children: templateChildren,
          metadata: {
            kind: "core",
            subjectId: c.id,
          } satisfies FocusBuilderTreeNodeMetadata,
        }
      })

      focusTypeChildren.push({
        id: `vertical:${vSlug}::focus-type:${ft}`,
        label: focusTypeLabel(ft),
        children: coreChildren,
        metadata: { kind: "focus-type" } satisfies FocusBuilderTreeNodeMetadata,
      })
    }

    verticalNodes.push({
      id: `vertical:${vSlug}`,
      label: v.display_name,
      iconName: "layers",
      children: focusTypeChildren,
      metadata: { kind: "vertical" } satisfies FocusBuilderTreeNodeMetadata,
    })
  }

  if (hasUnclassified) {
    const orphanCores = cores.filter((c) =>
      (verticalsByCore.get(c.id) ?? new Set()).has(UNCLASSIFIED_VERTICAL),
    )
    verticalNodes.push({
      id: `vertical:${UNCLASSIFIED_VERTICAL}`,
      label: "Unclassified",
      iconName: "layers",
      children: orphanCores.map((c) => ({
        id: `vertical:${UNCLASSIFIED_VERTICAL}::focus-type:other::core:${c.id}`,
        label: c.display_name,
        iconName: "square",
        children: [
          {
            id: `vertical:${UNCLASSIFIED_VERTICAL}::focus-type:other::core:${c.id}::new`,
            label: `+ New ${c.display_name}-based template`,
            metadata: {
              kind: "new-template",
              parentCoreId: c.id,
            } satisfies FocusBuilderTreeNodeMetadata,
          },
        ],
        metadata: {
          kind: "core",
          subjectId: c.id,
        } satisfies FocusBuilderTreeNodeMetadata,
      })),
      metadata: { kind: "vertical" } satisfies FocusBuilderTreeNodeMetadata,
    })
  }

  return verticalNodes
}


/**
 * Compute the default expansion set for a freshly-loaded tree.
 * Per Q-5 LOCKED (c):
 *   - Studio active vertical expanded.
 *   - Inside it, all focus-types expanded so cores are visible.
 *   - Templates inside cores stay collapsed.
 *   - Fallback to alphabetical-first vertical if no Studio scope.
 */
export function defaultExpansionForTree(
  groups: TreeNode[],
  studioVertical: string | null,
): Set<string> {
  const expanded = new Set<string>()
  if (groups.length === 0) return expanded

  // Determine the vertical to start expanded.
  let target: TreeNode | undefined
  if (studioVertical) {
    target = groups.find((g) => g.id === `vertical:${studioVertical}`)
  }
  if (!target) {
    // Alphabetical-first (excluding Unclassified pseudo if any).
    const candidates = groups
      .filter((g) => g.id !== `vertical:${UNCLASSIFIED_VERTICAL}`)
      .slice()
      .sort((a, b) => a.label.localeCompare(b.label))
    target = candidates[0]
  }
  if (!target) return expanded

  expanded.add(target.id)
  for (const focusType of target.children ?? []) {
    expanded.add(focusType.id)
    // cores stay collapsed.
  }
  return expanded
}


/**
 * Find the tree-path ids for a given subject id (core / template),
 * for URL-driven auto-expansion on load.
 */
function expansionIdsForSubject(
  groups: TreeNode[],
  subject: FocusBuilderSubject,
): string[] {
  const out: string[] = []
  function walk(nodes: TreeNode[], trail: string[]) {
    for (const n of nodes) {
      const md = n.metadata as FocusBuilderTreeNodeMetadata | undefined
      const isMatch =
        (subject.kind === "core" &&
          md?.kind === "core" &&
          md.subjectId === subject.id) ||
        (subject.kind === "template" &&
          md?.kind === "template" &&
          md.subjectId === subject.id)
      if (isMatch) {
        out.push(...trail)
        return
      }
      if (n.children && n.children.length > 0) {
        walk(n.children, [...trail, n.id])
      }
    }
  }
  walk(groups, [])
  return out
}


export function FocusBuilderTree({
  selectedSubject,
  onSelectSubject,
  studioActiveVertical,
}: FocusBuilderTreeProps) {
  const [data, setData] = React.useState<TreeData | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [expandedIds, setExpandedIds] = React.useState<Set<string>>(() =>
    readExpandedFromStorage(),
  )
  const initializedDefaults = React.useRef(false)

  // Fetch all three sources in parallel.
  React.useEffect(() => {
    let cancelled = false
    Promise.all([
      verticalsService.list(),
      focusCoresService.list(),
      focusTemplatesService.list(),
    ])
      .then(([verticals, cores, templates]) => {
        if (cancelled) return
        setData({ verticals, cores, templates })
      })
      .catch((e: unknown) => {
        if (cancelled) return
        const msg = e instanceof Error ? e.message : "Failed to load tree."
        setError(msg)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const groups = React.useMemo<TreeNode[]>(() => {
    if (!data) return []
    return buildFocusBuilderTree(data)
  }, [data])

  // First-load default expansion. Only fires once after groups arrive
  // AND localStorage was empty (operator has saved state → respect).
  React.useEffect(() => {
    if (initializedDefaults.current) return
    if (groups.length === 0) return
    initializedDefaults.current = true

    const stored = readExpandedFromStorage()
    if (stored.size > 0) {
      setExpandedIds(stored)
      return
    }
    const studioVertical =
      studioActiveVertical ??
      (typeof window !== "undefined" ? readLastVertical() : null)
    const defaults = defaultExpansionForTree(groups, studioVertical)
    setExpandedIds(defaults)
    writeExpandedToStorage(defaults)
  }, [groups, studioActiveVertical])

  // If a subject is selected and its trail isn't expanded, expand it.
  React.useEffect(() => {
    if (!selectedSubject) return
    if (groups.length === 0) return
    const trail = expansionIdsForSubject(groups, selectedSubject)
    if (trail.length === 0) return
    setExpandedIds((prev) => {
      const next = new Set(prev)
      let changed = false
      for (const id of trail) {
        if (!next.has(id)) {
          next.add(id)
          changed = true
        }
      }
      if (!changed) return prev
      writeExpandedToStorage(next)
      return next
    })
  }, [selectedSubject, groups])

  const selectedTreeId = React.useMemo<string | null>(() => {
    if (!selectedSubject) return null
    const trail = expansionIdsForSubject(groups, selectedSubject)
    // The leaf id is not in the trail (trail is parents only); find it.
    let found: string | null = null
    function walk(nodes: TreeNode[]) {
      for (const n of nodes) {
        const md = n.metadata as FocusBuilderTreeNodeMetadata | undefined
        if (
          (selectedSubject.kind === "core" &&
            md?.kind === "core" &&
            md.subjectId === selectedSubject.id) ||
          (selectedSubject.kind === "template" &&
            md?.kind === "template" &&
            md.subjectId === selectedSubject.id)
        ) {
          found = n.id
          return
        }
        if (n.children) walk(n.children)
      }
    }
    walk(groups)
    // Reference trail just to silence the unused-var lint if the
    // selected node hasn't been found yet — trail expansion still
    // happens via the effect above.
    void trail
    return found
  }, [selectedSubject, groups])

  const handleSelect = React.useCallback(
    (id: string, node: TreeNode) => {
      const md = node.metadata as FocusBuilderTreeNodeMetadata | undefined
      if (!md) return
      if (md.kind === "core" && md.subjectId) {
        onSelectSubject({ kind: "core", id: md.subjectId })
        return
      }
      if (md.kind === "template" && md.subjectId) {
        onSelectSubject({ kind: "template", id: md.subjectId })
        return
      }
      if (md.kind === "new-template") {
        // F-1 stub — F-3 wires this to a CreateTemplateFromCoreFlow modal.
        // eslint-disable-next-line no-console
        console.log(
          "[FocusBuilderTree] + New template clicked",
          md.parentCoreId,
        )
        // TODO(F-3): open CreateTemplateFromCoreFlow with
        // inherits_from_core_id = md.parentCoreId pre-filled.
        return
      }
      // Vertical / focus-type rows: toggle their own expansion as a
      // courtesy when the label area (not the chevron) is clicked.
      const isExpanded = expandedIds.has(id)
      handleExpandChange(id, !isExpanded)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onSelectSubject, expandedIds],
  )

  const handleExpandChange = React.useCallback(
    (id: string, expanded: boolean) => {
      setExpandedIds((prev) => {
        const next = new Set(prev)
        if (expanded) next.add(id)
        else next.delete(id)
        writeExpandedToStorage(next)
        return next
      })
    },
    [],
  )

  const renderAccessory = React.useCallback((node: TreeNode) => {
    const md = node.metadata as FocusBuilderTreeNodeMetadata | undefined
    if (md?.kind === "template" && md.scope) {
      return <ScopeChip scope={md.scope} />
    }
    return null
  }, [])

  if (error) {
    return (
      <div
        className="px-3 py-4 text-[12px] text-status-error"
        data-testid="focus-builder-tree-error"
      >
        {error}
      </div>
    )
  }

  if (!data) {
    return (
      <div
        className="px-3 py-4 text-[12px] text-content-muted"
        data-testid="focus-builder-tree-loading"
      >
        Loading focuses…
      </div>
    )
  }

  return (
    <VerticalGroupedTree
      groups={groups}
      selectedId={selectedTreeId}
      onSelect={handleSelect}
      expandedIds={expandedIds}
      onExpandChange={handleExpandChange}
      renderNodeAccessory={renderAccessory}
      data-testid="focus-builder-tree"
    />
  )
}

export default FocusBuilderTree
