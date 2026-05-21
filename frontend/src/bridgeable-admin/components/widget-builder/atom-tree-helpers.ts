/**
 * atom-tree-helpers — pure functions for manipulating a
 * CompositionBlob's atom_tree during WB-4a authoring.
 *
 * The canvas is structurally a flex stack of children of the root
 * container atom; container atoms recursively flex-stack. Operators
 * insert / reorder / remove via drag-to-canvas.
 *
 * All helpers are pure (no React, no state). The page-level
 * orchestrator imports them, runs them against a draft snapshot, and
 * passes the next snapshot to useWidgetAutoSave.setDraft.
 */
import type {
  AtomNode,
  AtomType,
  CompositionBlob,
} from "@/lib/widget-builder/types/composition-blob"
import { CONTAINER_ATOM_TYPES } from "@/lib/widget-builder/types/composition-blob"


function generateAtomId(): string {
  const c =
    typeof globalThis !== "undefined"
      ? (globalThis as { crypto?: { randomUUID?: () => string } }).crypto
      : undefined
  if (c?.randomUUID) {
    return c.randomUUID()
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    const v = ch === "x" ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}


/** Build a default AtomNode of the given type. */
export function makeDefaultAtomNode(atom_type: AtomType): AtomNode {
  const atom_id = generateAtomId()
  switch (atom_type) {
    case "text_label":
      return { atom_id, atom_type, config: { align: "left" } }
    case "value_display":
      return {
        atom_id,
        atom_type,
        config: { format: "number", format_config: {}, align: "left" },
      }
    case "icon":
      return { atom_id, atom_type, config: { icon_name: "Star", size_token: "md" } }
    case "status_badge":
      return { atom_id, atom_type, config: { status_map: {}, show_icon: true } }
    case "divider":
      return {
        atom_id,
        atom_type,
        config: { orientation: "horizontal", spacing_token: "sm" },
      }
    case "image":
      return {
        atom_id,
        atom_type,
        config: { source_kind: "url", fit: "cover" },
      }
    case "button":
      return {
        atom_id,
        atom_type,
        config: {
          action_kind: "navigate",
          action_config: {},
          variant: "secondary",
        },
      }
    case "conditional_container":
      return {
        atom_id,
        atom_type,
        config: { direction: "column", gap_token: "sm" },
        children: [],
      }
    case "repeater_atom":
      return {
        atom_id,
        atom_type,
        config: {
          binding_id: "",
          children: [],
          direction: "column",
          spacing: "normal",
        },
        children: [],
      }
    default: {
      // Exhaustiveness check.
      const _exhaustive: never = atom_type
      void _exhaustive
      throw new Error(`Unknown atom_type: ${atom_type as string}`)
    }
  }
}


export function isContainerAtom(node: AtomNode): boolean {
  return CONTAINER_ATOM_TYPES.has(node.atom_type)
}


/** Find the parent atom_id of `childId` (or null if it's the root). */
export function findParentId(
  tree: Record<string, AtomNode>,
  childId: string,
): string | null {
  for (const [parentId, node] of Object.entries(tree)) {
    if (node.children && node.children.includes(childId)) {
      return parentId
    }
  }
  return null
}


/** Insert a new atom as a child of `parentId` at `index`.
 *
 *  Returns the next CompositionBlob + the new atom's id. */
export function insertAtomAt(
  blob: CompositionBlob,
  parentId: string,
  index: number,
  newNode: AtomNode,
): { next: CompositionBlob; newAtomId: string } {
  const parent = blob.atom_tree[parentId]
  if (!parent) {
    throw new Error(`Parent atom_id not found: ${parentId}`)
  }
  if (!isContainerAtom(parent)) {
    throw new Error(`Cannot insert into non-container atom: ${parent.atom_type}`)
  }
  const oldChildren = parent.children ?? []
  const safeIndex = Math.max(0, Math.min(index, oldChildren.length))
  const newChildren = [
    ...oldChildren.slice(0, safeIndex),
    newNode.atom_id,
    ...oldChildren.slice(safeIndex),
  ]
  // repeater_atom carries duplicate children in config — keep mirror.
  const updatedParent: AtomNode = {
    ...parent,
    children: newChildren,
    config:
      parent.atom_type === "repeater_atom"
        ? { ...parent.config, children: newChildren }
        : parent.config,
  }
  const next: CompositionBlob = {
    ...blob,
    atom_tree: {
      ...blob.atom_tree,
      [parentId]: updatedParent,
      [newNode.atom_id]: newNode,
    },
  }
  return { next, newAtomId: newNode.atom_id }
}


/** Move an existing atom from its current position to a new index
 *  under the same OR a different parent.
 *
 *  No-op if the atom's parent is unchanged AND the index equals its
 *  current position. */
export function moveAtomTo(
  blob: CompositionBlob,
  atomId: string,
  newParentId: string,
  newIndex: number,
): CompositionBlob {
  const oldParentId = findParentId(blob.atom_tree, atomId)
  if (oldParentId === null) {
    // Can't move root.
    return blob
  }
  // Detach.
  let nextTree: Record<string, AtomNode> = { ...blob.atom_tree }
  const oldParent = nextTree[oldParentId]
  if (!oldParent || !oldParent.children) return blob
  const filtered = oldParent.children.filter((c) => c !== atomId)
  nextTree[oldParentId] = {
    ...oldParent,
    children: filtered,
    config:
      oldParent.atom_type === "repeater_atom"
        ? { ...oldParent.config, children: filtered }
        : oldParent.config,
  }
  // Attach.
  const newParent = nextTree[newParentId]
  if (!newParent || !isContainerAtom(newParent)) {
    return blob
  }
  const targetChildren = nextTree[newParentId].children ?? []
  const safeIndex = Math.max(0, Math.min(newIndex, targetChildren.length))
  const newChildren = [
    ...targetChildren.slice(0, safeIndex),
    atomId,
    ...targetChildren.slice(safeIndex),
  ]
  nextTree[newParentId] = {
    ...nextTree[newParentId],
    children: newChildren,
    config:
      nextTree[newParentId].atom_type === "repeater_atom"
        ? { ...nextTree[newParentId].config, children: newChildren }
        : nextTree[newParentId].config,
  }
  return { ...blob, atom_tree: nextTree }
}


/** Remove an atom + its descendants from the tree. */
export function removeAtom(
  blob: CompositionBlob,
  atomId: string,
): CompositionBlob {
  if (atomId === blob.root_atom_id) {
    // Don't remove root.
    return blob
  }
  const parentId = findParentId(blob.atom_tree, atomId)
  const nextTree: Record<string, AtomNode> = { ...blob.atom_tree }
  // Collect descendants for removal.
  const toRemove: Set<string> = new Set()
  const stack: string[] = [atomId]
  while (stack.length > 0) {
    const id = stack.pop()
    if (id === undefined) break
    toRemove.add(id)
    const node = nextTree[id]
    if (node?.children) {
      for (const c of node.children) stack.push(c)
    }
  }
  for (const id of toRemove) {
    delete nextTree[id]
  }
  if (parentId !== null) {
    const parent = nextTree[parentId]
    if (parent?.children) {
      const newChildren = parent.children.filter((c) => !toRemove.has(c))
      nextTree[parentId] = {
        ...parent,
        children: newChildren,
        config:
          parent.atom_type === "repeater_atom"
            ? { ...parent.config, children: newChildren }
            : parent.config,
      }
    }
  }
  return { ...blob, atom_tree: nextTree }
}


/** Mutate canvas root container's `direction` / `gap_token` config. */
export function setRootDirection(
  blob: CompositionBlob,
  direction: "row" | "column",
): CompositionBlob {
  const root = blob.atom_tree[blob.root_atom_id]
  if (!root || root.atom_type !== "conditional_container") return blob
  return {
    ...blob,
    atom_tree: {
      ...blob.atom_tree,
      [blob.root_atom_id]: {
        ...root,
        config: { ...root.config, direction },
      },
    },
  }
}


export function setRootGap(
  blob: CompositionBlob,
  gap_token: "sm" | "md" | "lg",
): CompositionBlob {
  const root = blob.atom_tree[blob.root_atom_id]
  if (!root || root.atom_type !== "conditional_container") return blob
  return {
    ...blob,
    atom_tree: {
      ...blob.atom_tree,
      [blob.root_atom_id]: {
        ...root,
        config: { ...root.config, gap_token },
      },
    },
  }
}
