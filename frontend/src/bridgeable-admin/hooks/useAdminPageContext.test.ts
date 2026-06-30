/**
 * useAdminPageContext.derive — route → page context (Authoring Assistant Shell-1).
 * The shell investigation established context is fully route-derivable; this
 * locks the derivation per surface type.
 */
import { describe, it, expect } from "vitest"

import { derive } from "./useAdminPageContext"

describe("derive — admin page context", () => {
  it("MoC vertical page → moc + vertical + armed", () => {
    const c = derive("/maps/manufacturing")
    expect(c.surface).toBe("moc")
    expect(c.vertical).toBe("manufacturing")
    expect(c.canAuthor).toBe(true)
    expect(c.label).toContain("manufacturing")
  })

  it("tolerates the /bridgeable-admin prefix", () => {
    expect(derive("/bridgeable-admin/maps/funeral_home").vertical).toBe("funeral_home")
  })

  it("Studio vertical+editor route → studio + vertical + editorKind + armed", () => {
    const c = derive("/studio/manufacturing/workflows")
    expect(c.surface).toBe("studio")
    expect(c.vertical).toBe("manufacturing")
    expect(c.editorKind).toBe("workflows")
    expect(c.canAuthor).toBe(true)
    expect(c.label).toMatch(/workflow editor/i)
  })

  it("Studio platform-scope editor → studio + editorKind, no vertical", () => {
    const c = derive("/studio/workflows")
    expect(c.surface).toBe("studio")
    expect(c.editorKind).toBe("workflows")
    expect(c.vertical).toBeNull()
    expect(c.canAuthor).toBe(true)
  })

  it("Studio overview (no editor) → studio, not armed", () => {
    const c = derive("/studio/manufacturing")
    expect(c.surface).toBe("studio")
    expect(c.editorKind).toBeNull()
    expect(c.canAuthor).toBe(false)
  })

  it("Studio live → studio, not armed", () => {
    const c = derive("/studio/live/manufacturing")
    expect(c.surface).toBe("studio")
    expect(c.canAuthor).toBe(false)
  })

  it("operational route → operational, not armed", () => {
    const c = derive("/health")
    expect(c.surface).toBe("operational")
    expect(c.canAuthor).toBe(false)
    expect(c.label).toBe("Operational")
  })

  it("MoC home (admin root) → moc, not armed", () => {
    expect(derive("/").surface).toBe("moc")
    expect(derive("/").canAuthor).toBe(false)
  })

  it("login → none (the bar hides)", () => {
    expect(derive("/login").surface).toBe("none")
    expect(derive("/bridgeable-admin/login").surface).toBe("none")
  })
})
