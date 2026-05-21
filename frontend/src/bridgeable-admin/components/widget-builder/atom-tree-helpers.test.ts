/**
 * Unit tests for atom-tree-helpers (WB-4a).
 */
import { describe, expect, it } from "vitest"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import {
  findParentId,
  insertAtomAt,
  isContainerAtom,
  makeDefaultAtomNode,
  moveAtomTo,
  removeAtom,
  setRootDirection,
  setRootGap,
} from "./atom-tree-helpers"


function mkBlob(): CompositionBlob {
  return {
    schema_version: 1,
    root_atom_id: "root",
    atom_tree: {
      root: {
        atom_id: "root",
        atom_type: "conditional_container",
        config: { direction: "column", gap_token: "sm" },
        children: [],
      },
    },
    variants: [],
    bindings_catalog: {},
  }
}


describe("makeDefaultAtomNode", () => {
  it("returns a unique atom_id per call", () => {
    const a = makeDefaultAtomNode("text_label")
    const b = makeDefaultAtomNode("text_label")
    expect(a.atom_id).not.toBe(b.atom_id)
  })

  it("seeds container atoms with empty children", () => {
    const a = makeDefaultAtomNode("conditional_container")
    expect(a.children).toEqual([])
    const b = makeDefaultAtomNode("repeater_atom")
    expect(b.children).toEqual([])
  })

  it("ships sensible defaults per atom_type", () => {
    expect(makeDefaultAtomNode("text_label").config.align).toBe("left")
    expect(makeDefaultAtomNode("value_display").config.format).toBe("number")
    expect(makeDefaultAtomNode("button").config.action_kind).toBe("navigate")
  })
})


describe("isContainerAtom", () => {
  it("identifies the two container types", () => {
    expect(
      isContainerAtom(makeDefaultAtomNode("conditional_container")),
    ).toBe(true)
    expect(isContainerAtom(makeDefaultAtomNode("repeater_atom"))).toBe(true)
    expect(isContainerAtom(makeDefaultAtomNode("text_label"))).toBe(false)
  })
})


describe("insertAtomAt", () => {
  it("appends an atom to an empty root", () => {
    const blob = mkBlob()
    const node = makeDefaultAtomNode("text_label")
    const { next, newAtomId } = insertAtomAt(blob, "root", 0, node)
    expect(newAtomId).toBe(node.atom_id)
    expect(next.atom_tree.root.children).toEqual([node.atom_id])
    expect(next.atom_tree[node.atom_id]).toBeDefined()
  })

  it("inserts at a specific index", () => {
    let blob = mkBlob()
    const a = makeDefaultAtomNode("text_label")
    const b = makeDefaultAtomNode("icon")
    const c = makeDefaultAtomNode("divider")
    blob = insertAtomAt(blob, "root", 0, a).next
    blob = insertAtomAt(blob, "root", 1, b).next
    // Insert c between a and b at index 1.
    blob = insertAtomAt(blob, "root", 1, c).next
    expect(blob.atom_tree.root.children).toEqual([a.atom_id, c.atom_id, b.atom_id])
  })

  it("clamps out-of-range indices", () => {
    const blob = mkBlob()
    const a = makeDefaultAtomNode("text_label")
    const { next } = insertAtomAt(blob, "root", 99, a)
    expect(next.atom_tree.root.children).toEqual([a.atom_id])
  })

  it("rejects insert into non-container", () => {
    let blob = mkBlob()
    const leaf = makeDefaultAtomNode("text_label")
    blob = insertAtomAt(blob, "root", 0, leaf).next
    const child = makeDefaultAtomNode("icon")
    expect(() => insertAtomAt(blob, leaf.atom_id, 0, child)).toThrow()
  })

  it("mirrors children into repeater_atom config", () => {
    let blob = mkBlob()
    const r = makeDefaultAtomNode("repeater_atom")
    blob = insertAtomAt(blob, "root", 0, r).next
    const inner = makeDefaultAtomNode("text_label")
    blob = insertAtomAt(blob, r.atom_id, 0, inner).next
    const rUpdated = blob.atom_tree[r.atom_id]
    expect(rUpdated.children).toEqual([inner.atom_id])
    expect((rUpdated.config as { children: string[] }).children).toEqual([
      inner.atom_id,
    ])
  })
})


describe("findParentId", () => {
  it("returns null for the root", () => {
    expect(findParentId(mkBlob().atom_tree, "root")).toBeNull()
  })

  it("returns the parent of a child", () => {
    let blob = mkBlob()
    const a = makeDefaultAtomNode("text_label")
    blob = insertAtomAt(blob, "root", 0, a).next
    expect(findParentId(blob.atom_tree, a.atom_id)).toBe("root")
  })
})


describe("moveAtomTo", () => {
  it("reorders within the same parent", () => {
    let blob = mkBlob()
    const a = makeDefaultAtomNode("text_label")
    const b = makeDefaultAtomNode("icon")
    const c = makeDefaultAtomNode("divider")
    blob = insertAtomAt(blob, "root", 0, a).next
    blob = insertAtomAt(blob, "root", 1, b).next
    blob = insertAtomAt(blob, "root", 2, c).next
    // Move c to index 0.
    blob = moveAtomTo(blob, c.atom_id, "root", 0)
    expect(blob.atom_tree.root.children).toEqual([
      c.atom_id,
      a.atom_id,
      b.atom_id,
    ])
  })

  it("moves between parents (root → container)", () => {
    let blob = mkBlob()
    const cont = makeDefaultAtomNode("conditional_container")
    const leaf = makeDefaultAtomNode("text_label")
    blob = insertAtomAt(blob, "root", 0, cont).next
    blob = insertAtomAt(blob, "root", 1, leaf).next
    blob = moveAtomTo(blob, leaf.atom_id, cont.atom_id, 0)
    expect(blob.atom_tree[cont.atom_id].children).toEqual([leaf.atom_id])
    expect(blob.atom_tree.root.children).toEqual([cont.atom_id])
  })
})


describe("removeAtom", () => {
  it("removes an atom + descendants", () => {
    let blob = mkBlob()
    const cont = makeDefaultAtomNode("conditional_container")
    const inner = makeDefaultAtomNode("text_label")
    blob = insertAtomAt(blob, "root", 0, cont).next
    blob = insertAtomAt(blob, cont.atom_id, 0, inner).next
    expect(Object.keys(blob.atom_tree)).toHaveLength(3)
    blob = removeAtom(blob, cont.atom_id)
    expect(Object.keys(blob.atom_tree)).toHaveLength(1)
    expect(blob.atom_tree.root.children).toEqual([])
  })

  it("refuses to remove root", () => {
    const blob = mkBlob()
    const next = removeAtom(blob, "root")
    expect(next.atom_tree.root).toBeDefined()
  })
})


describe("setRootDirection / setRootGap", () => {
  it("updates root config", () => {
    const blob = mkBlob()
    const b2 = setRootDirection(blob, "row")
    expect(b2.atom_tree.root.config.direction).toBe("row")
    const b3 = setRootGap(b2, "lg")
    expect(b3.atom_tree.root.config.gap_token).toBe("lg")
  })
})
