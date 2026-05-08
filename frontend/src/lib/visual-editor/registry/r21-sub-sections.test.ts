/**
 * R-2.1 — entity-card sub-section substrate tests.
 *
 * Exercises:
 *   - getByName resolves all 10 sub-section registrations
 *   - extensions.entityCardSection shape is canonical for each
 *   - getSubSectionsFor returns the parent → children mapping
 *   - Path 1 wrapping: each sub-section's component is a wrapper
 *     (Registered(*) displayName) emitting data-component-name
 *   - Slug convention: dot-separated, parent in segment-zero
 */

import { afterEach, beforeAll, describe, expect, it } from "vitest"

import {
  _internal_clear,
} from "@/lib/visual-editor/registry/registry"
import {
  getAllRegistered,
  getByName,
  getByType,
  getSubSectionsFor,
} from "@/lib/visual-editor/registry"
import type { EntityCardSectionExtension } from "@/lib/visual-editor/registry"


const EXPECTED_SUB_SECTIONS: ReadonlyArray<{
  slug: string
  parentName: string
  sectionRole: EntityCardSectionExtension["sectionRole"]
  optional: boolean
}> = [
  // delivery-card (4)
  { slug: "delivery-card.header", parentName: "delivery-card", sectionRole: "header", optional: false },
  { slug: "delivery-card.body", parentName: "delivery-card", sectionRole: "body", optional: false },
  { slug: "delivery-card.actions", parentName: "delivery-card", sectionRole: "actions", optional: false },
  { slug: "delivery-card.hole-dug-badge", parentName: "delivery-card", sectionRole: "custom", optional: false },
  // ancillary-card (3)
  { slug: "ancillary-card.header", parentName: "ancillary-card", sectionRole: "header", optional: false },
  { slug: "ancillary-card.body", parentName: "ancillary-card", sectionRole: "body", optional: false },
  { slug: "ancillary-card.actions", parentName: "ancillary-card", sectionRole: "actions", optional: true },
  // order-card (3)
  { slug: "order-card.header", parentName: "order-card", sectionRole: "header", optional: false },
  { slug: "order-card.body", parentName: "order-card", sectionRole: "body", optional: false },
  { slug: "order-card.actions", parentName: "order-card", sectionRole: "actions", optional: true },
]


describe("R-2.1 — entity-card sub-section registrations", () => {
  beforeAll(async () => {
    _internal_clear()
    await import("@/lib/visual-editor/registry/auto-register")
  })

  afterEach(() => {
    /* keep registry populated across cases */
  })

  it("registers all 10 sub-sections via getByType", () => {
    const all = getByType("entity-card-section")
    expect(all.length).toBe(10)
  })

  it.each(EXPECTED_SUB_SECTIONS)(
    "registers sub-section $slug with canonical extension shape",
    ({ slug, parentName, sectionRole, optional }) => {
      const entry = getByName("entity-card-section", slug)
      expect(entry, `${slug} must be registered`).toBeDefined()
      const ext = entry!.metadata.extensions
        ?.entityCardSection as EntityCardSectionExtension | undefined
      expect(ext, `${slug} must carry extensions.entityCardSection`).toBeDefined()
      expect(ext!.parentKind).toBe("entity-card")
      expect(ext!.parentName).toBe(parentName)
      expect(ext!.sectionRole).toBe(sectionRole)
      expect(ext!.optional).toBe(optional)
    },
  )

  it("slug convention: every sub-section's slug parses parent via dot split", () => {
    const all = getByType("entity-card-section")
    for (const entry of all) {
      const slug = entry.metadata.name
      expect(slug).toContain(".")
      const ext = entry.metadata.extensions
        ?.entityCardSection as EntityCardSectionExtension | undefined
      expect(ext).toBeDefined()
      // Slug-string-segment-zero recovers the parent slug (convenience
      // path); registry-walker canonical path is via extension shape.
      const parentFromSlug = slug.split(".")[0]
      expect(parentFromSlug).toBe(ext!.parentName)
    }
  })

  it("slug convention: all sub-section names contain a dot, all parent names do not", () => {
    const subs = getByType("entity-card-section")
    for (const s of subs) {
      expect(s.metadata.name).toMatch(/\./)
    }
    const parents = getByType("entity-card")
    for (const p of parents) {
      expect(p.metadata.name).not.toMatch(/\./)
    }
  })

  it("Path 1 wrapping: each sub-section component has a Registered(*) displayName", () => {
    const all = getByType("entity-card-section")
    for (const entry of all) {
      const cmp = entry.component as unknown as { displayName?: string }
      expect(cmp.displayName, `${entry.metadata.name} should be wrapped`).toMatch(
        /^Registered\(/,
      )
    }
  })

  it("componentClasses defaults to entity-card-section for every sub-section", () => {
    const all = getByType("entity-card-section")
    for (const entry of all) {
      expect(entry.metadata.componentClasses).toContain(
        "entity-card-section",
      )
    }
  })

  it("each sub-section declares schemaVersion=1 and componentVersion>=1", () => {
    const all = getByType("entity-card-section")
    for (const entry of all) {
      expect(entry.metadata.schemaVersion).toBe(1)
      expect(entry.metadata.componentVersion).toBeGreaterThanOrEqual(1)
    }
  })
})


describe("R-2.1 — getSubSectionsFor introspection helper", () => {
  // Registry remains populated from the prior describe block's
  // beforeAll. _internal_clear + re-import the auto-register barrel
  // here would be a no-op (module-cache hit) and would leave the
  // registry empty. Module-cache discipline canonical for vitest
  // registry-touching tests per CLAUDE.md.

  it("returns 4 sub-sections for delivery-card", () => {
    const subs = getSubSectionsFor("entity-card", "delivery-card")
    expect(subs.length).toBe(4)
    const slugs = subs.map((s) => s.metadata.name).sort()
    expect(slugs).toEqual([
      "delivery-card.actions",
      "delivery-card.body",
      "delivery-card.header",
      "delivery-card.hole-dug-badge",
    ])
  })

  it("returns 3 sub-sections for ancillary-card", () => {
    const subs = getSubSectionsFor("entity-card", "ancillary-card")
    expect(subs.length).toBe(3)
  })

  it("returns 3 sub-sections for order-card", () => {
    const subs = getSubSectionsFor("entity-card", "order-card")
    expect(subs.length).toBe(3)
  })

  it("returns empty for an entity-card with no sub-sections", () => {
    const subs = getSubSectionsFor("entity-card", "nonexistent-card")
    expect(subs).toEqual([])
  })

  it("returns empty for unknown parentKind", () => {
    // widgets don't have entity-card-section sub-sections
    const subs = getSubSectionsFor("widget", "today")
    expect(subs).toEqual([])
  })

  it("uses extension shape, NOT slug-string parsing, to identify parent", () => {
    // Sanity: even if a hypothetical sub-section's slug had no dot,
    // the helper would still find it via the extension shape.
    // We test the inverse: dot-segment-zero matching is consistent
    // with extension-shape matching for the actual registrations.
    const all = getAllRegistered().filter(
      (e) => e.metadata.type === "entity-card-section",
    )
    for (const entry of all) {
      const slug = entry.metadata.name
      const ext = entry.metadata.extensions
        ?.entityCardSection as EntityCardSectionExtension | undefined
      const parentFromSlug = slug.split(".")[0]
      const subs = getSubSectionsFor("entity-card", ext!.parentName)
      expect(subs.map((s) => s.metadata.name)).toContain(slug)
      // If dot-string-parsing produced a different parent, the
      // helper would still resolve via extensions — but in practice
      // they agree.
      expect(parentFromSlug).toBe(ext!.parentName)
    }
  })
})
