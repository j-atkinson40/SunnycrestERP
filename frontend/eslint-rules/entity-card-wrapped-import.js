/**
 * Custom ESLint rule — entity card import discipline.
 *
 * R-2.0 — DeliveryCard / AncillaryCard / OrderCard each have two
 * exports per the Path 1 wrapping convention (per CLAUDE.md
 * R-1.6.12 + R-2.0):
 *
 *   - `*Raw` (e.g. `DeliveryCardRaw`) — the unwrapped React component.
 *     Used ONLY by the visual-editor registration shim
 *     (`lib/visual-editor/registry/registrations/entity-cards.ts`)
 *     which wraps it via `registerComponent(meta)(Raw)` so the
 *     wrapped version emits a `data-component-name` boundary div for
 *     runtime-editor click-to-edit.
 *
 *   - the wrapped reference (e.g. `DeliveryCard`) re-exported from the
 *     entity-cards barrel. Every render site MUST import this version.
 *
 * Direct imports of the `*Raw` export (or of the bare original name
 * before R-2.0's rename) bypass the wrapping. The runtime DOM ends up
 * with a card that has no `data-component-name`, breaking
 * SelectionOverlay's capture-phase walker. Click-to-edit silently no-
 * ops on those cards.
 *
 * This rule errors on:
 *   - `import { DeliveryCard } from ".../DeliveryCard"`
 *   - `import { AncillaryCard } from ".../AncillaryCard"`
 *   - `import { OrderCard } from ".../OrderCard"`
 * (since R-2.0 those names are no longer exported from the source
 *  files, so this catches stale code-gen + AI-suggested edits)
 *
 * It does NOT error on:
 *   - The registration shim itself
 *   - Test files importing `DeliveryCardRaw` etc. directly
 *   - Imports from the registrations barrel
 *
 * Allowed import path for runtime use:
 *   `import { DeliveryCard, AncillaryCard, OrderCard }
 *      from "@/lib/visual-editor/registry/registrations/entity-cards"`
 */

const FORBIDDEN_BARE_NAMES = new Set([
  "DeliveryCard",
  "AncillaryCard",
  "OrderCard",
])

const SOURCE_PATH_TAILS = [
  "components/dispatch/DeliveryCard",
  "components/dispatch/AncillaryCard",
  "components/delivery/OrderCard",
]

const ALLOW_FILE_TAILS = [
  // The registration shim itself imports the *Raw exports.
  "lib/visual-editor/registry/registrations/entity-cards.ts",
  // Tests are allowed to import the *Raw exports for direct unit
  // testing of the unwrapped component (avoids registry side effects).
  ".test.tsx",
  ".test.ts",
]

function fileExempt(filename) {
  return ALLOW_FILE_TAILS.some((tail) => filename.endsWith(tail))
}


/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Entity cards (DeliveryCard / AncillaryCard / OrderCard) must be imported from the visual-editor registrations barrel. Direct imports bypass runtime registration and break click-to-edit.",
      recommended: false,
    },
    schema: [],
    messages: {
      barePathImport:
        "Import wrapped {{name}} from '@/lib/visual-editor/registry/registrations/entity-cards'. Direct import of the raw component bypasses runtime registration and breaks click-to-edit. See R-1.6.12 / R-2.0 architectural pattern.",
    },
  },
  create(context) {
    const filename = context.getFilename ? context.getFilename() : context.filename
    if (filename && fileExempt(filename)) {
      return {}
    }
    return {
      ImportDeclaration(node) {
        const source = node.source.value
        if (typeof source !== "string") return
        const matchesEntityCardSource = SOURCE_PATH_TAILS.some((tail) =>
          source.endsWith(tail) || source.endsWith(tail + ".tsx") ||
          source.endsWith(tail + ".ts"),
        )
        if (!matchesEntityCardSource) return

        for (const spec of node.specifiers) {
          if (spec.type !== "ImportSpecifier") continue
          const importedName = spec.imported && spec.imported.name
          if (importedName && FORBIDDEN_BARE_NAMES.has(importedName)) {
            context.report({
              node: spec,
              messageId: "barePathImport",
              data: { name: importedName },
            })
          }
        }
      },
    }
  },
}
