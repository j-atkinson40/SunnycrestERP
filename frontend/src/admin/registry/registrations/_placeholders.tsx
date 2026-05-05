/**
 * Placeholder shim components for registrations whose subjects
 * aren't single React components today.
 *
 * Phase 1 registers Focus types, Focus templates, document
 * blocks, and workflow node types as registry entries — each
 * eventually carries a real component (Phase 2+ when the editor
 * needs to render previews). The placeholder lets us seed the
 * registry with full metadata in Phase 1 without inventing
 * speculative implementations now.
 *
 * Keep these placeholders minimal and clearly labeled so any
 * accidental render in production is obvious.
 */

import type { ComponentType } from "react"


/** Generic placeholder component. Renders a labeled box;
 * never used in production paths today. The label makes
 * accidental mounts trivially identifiable. */
export function makePlaceholder(label: string): ComponentType<unknown> {
  function Placeholder() {
    return (
      <div
        data-placeholder-label={label}
        style={{
          border: "1px dashed var(--border-subtle)",
          padding: "var(--space-3, 12px)",
          color: "var(--content-muted)",
          fontSize: "var(--text-body-sm)",
          background: "var(--surface-sunken)",
          borderRadius: "var(--radius-md)",
        }}
      >
        Placeholder: {label}
      </div>
    )
  }
  Placeholder.displayName = `RegistryPlaceholder(${label})`
  return Placeholder
}
