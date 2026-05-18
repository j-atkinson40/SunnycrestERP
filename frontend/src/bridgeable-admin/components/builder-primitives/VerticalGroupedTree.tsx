/**
 * VerticalGroupedTree — reusable hierarchical tree primitive.
 *
 * Sub-arc F-1 deliverable. Consumer-opaque: knows nothing about
 * cores / templates / focus-types / scope chips. Renders a nested
 * tree of TreeNode rows with chevron-driven expansion + click-driven
 * selection. Designed so that Page Builder / Document Builder /
 * Workflow Builder can consume the same primitive with their own
 * group shapes.
 *
 * Contract per investigation 2026-05-18-focus-builder Q-38:
 *   - `groups` is the tree data (top level = groups, children = leaves).
 *   - `metadata` field on each node is OPAQUE to the primitive.
 *     Consumer stuffs whatever it needs there ({kind, slug, scope,...}).
 *   - Primitive does NOT fetch data, persist expansion, OR render
 *     consumer-specific affordances (chips, badges). The
 *     `renderNodeAccessory` slot is the consumer's hook for that.
 *   - Single-value `selectedId` — multi-select deliberately deferred.
 *   - Recursive children with depth-based indentation; no depth limit.
 */
import * as React from "react"
import { ChevronDown, ChevronRight, type LucideIcon } from "lucide-react"

import {
  Briefcase,
  Box,
  CheckSquare,
  ClipboardList,
  FileText,
  Layers,
  Square,
  SquareDashed,
  Users,
} from "lucide-react"


export interface TreeNode {
  id: string
  label: string
  /** Optional lucide icon name (mapped via ICON_MAP). */
  iconName?: string
  children?: TreeNode[]
  /** Opaque consumer data — primitive does not inspect. */
  metadata?: Record<string, unknown>
}


export interface VerticalGroupedTreeProps {
  groups: TreeNode[]
  selectedId: string | null
  onSelect: (id: string, node: TreeNode) => void
  expandedIds: Set<string>
  onExpandChange: (id: string, expanded: boolean) => void
  /** Optional per-node accessory (e.g. scope chip). */
  renderNodeAccessory?: (node: TreeNode) => React.ReactNode
  className?: string
  "data-testid"?: string
}


/**
 * Narrow lucide map for icons referenced by tree nodes. Unknown
 * iconName values render no icon (label only) — consumers should
 * surface their own warning if an icon is expected.
 */
const ICON_MAP: Record<string, LucideIcon> = {
  square: Square,
  "square-dashed": SquareDashed,
  layers: Layers,
  box: Box,
  "file-text": FileText,
  briefcase: Briefcase,
  users: Users,
  "check-square": CheckSquare,
  "clipboard-list": ClipboardList,
}


function NodeIcon({ name }: { name?: string }) {
  if (!name) return null
  const Icon = ICON_MAP[name]
  if (!Icon) return null
  return (
    <Icon
      aria-hidden="true"
      className="size-3.5 shrink-0 text-[color:var(--content-muted)]"
    />
  )
}


interface TreeNodeRowProps {
  node: TreeNode
  depth: number
  selectedId: string | null
  expandedIds: Set<string>
  onSelect: (id: string, node: TreeNode) => void
  onExpandChange: (id: string, expanded: boolean) => void
  renderNodeAccessory?: (node: TreeNode) => React.ReactNode
}


function TreeNodeRow({
  node,
  depth,
  selectedId,
  expandedIds,
  onSelect,
  onExpandChange,
  renderNodeAccessory,
}: TreeNodeRowProps) {
  const hasChildren = !!node.children && node.children.length > 0
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const paddingLeft = depth * 12 + 8

  return (
    <li role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className={[
          "group flex items-center gap-1.5 py-1 pr-2 text-[13px] leading-5",
          "cursor-pointer transition-colors",
          isSelected
            ? "bg-accent-subtle text-content-strong"
            : "hover:bg-[color:var(--surface-elevated)]/60 text-content-base",
        ].join(" ")}
        style={{ paddingLeft: `${paddingLeft}px` }}
        data-testid={`tree-node-${node.id}`}
        data-selected={isSelected ? "true" : "false"}
        data-depth={depth}
        onClick={() => onSelect(node.id, node)}
      >
        {hasChildren ? (
          <button
            type="button"
            aria-label={isExpanded ? "Collapse" : "Expand"}
            data-testid={`tree-chevron-${node.id}`}
            className="-ml-1 grid size-4 shrink-0 place-items-center rounded text-content-muted hover:bg-[color:var(--surface-sunken)]"
            onClick={(e) => {
              e.stopPropagation()
              onExpandChange(node.id, !isExpanded)
            }}
          >
            {isExpanded ? (
              <ChevronDown className="size-3.5" />
            ) : (
              <ChevronRight className="size-3.5" />
            )}
          </button>
        ) : (
          <span className="size-4 shrink-0" aria-hidden="true" />
        )}

        <NodeIcon name={node.iconName} />

        <span className="min-w-0 flex-1 truncate">{node.label}</span>

        {renderNodeAccessory ? (
          <span
            className="shrink-0"
            data-testid={`tree-accessory-${node.id}`}
            onClick={(e) => e.stopPropagation()}
          >
            {renderNodeAccessory(node)}
          </span>
        ) : null}
      </div>

      {hasChildren && isExpanded ? (
        <ul role="group" className="m-0 list-none p-0">
          {node.children!.map((child) => (
            <TreeNodeRow
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              expandedIds={expandedIds}
              onSelect={onSelect}
              onExpandChange={onExpandChange}
              renderNodeAccessory={renderNodeAccessory}
            />
          ))}
        </ul>
      ) : null}
    </li>
  )
}


export function VerticalGroupedTree({
  groups,
  selectedId,
  onSelect,
  expandedIds,
  onExpandChange,
  renderNodeAccessory,
  className,
  "data-testid": dataTestid,
}: VerticalGroupedTreeProps) {
  return (
    <ul
      role="tree"
      className={[
        "m-0 list-none p-0 text-content-base",
        className ?? "",
      ].join(" ")}
      data-testid={dataTestid ?? "vertical-grouped-tree"}
    >
      {groups.length === 0 ? (
        <li
          className="px-3 py-4 text-[12px] text-content-muted"
          data-testid="vertical-grouped-tree-empty"
        >
          No groups to display.
        </li>
      ) : (
        groups.map((group) => (
          <TreeNodeRow
            key={group.id}
            node={group}
            depth={0}
            selectedId={selectedId}
            expandedIds={expandedIds}
            onSelect={onSelect}
            onExpandChange={onExpandChange}
            renderNodeAccessory={renderNodeAccessory}
          />
        ))
      )}
    </ul>
  )
}

export default VerticalGroupedTree
