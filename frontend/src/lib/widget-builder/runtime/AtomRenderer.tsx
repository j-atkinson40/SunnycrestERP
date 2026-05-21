/**
 * AtomRenderer — WB-2 recursive atom dispatcher.
 *
 * Renders a single AtomNode by:
 *   1. Checking variant visibility (visible_in_variants filter when
 *      variantId is set). When variantId is undefined, all atoms render.
 *   2. Resolving binding refs via the WB-2 resolveBinding placeholder
 *      (WB-6 swaps to real saved-view data without API change).
 *   3. Dispatching on atom_type to the corresponding atom renderer.
 *   4. For conditional_container, recursively building child renders
 *      from atom_tree before invoking the leaf renderer.
 *
 * Per investigation Area 6 dual-wrapping lock:
 *   - conditional_container is the only Phase 1 atom that gets its
 *     own `registerComponent` wrap (it's a container — the editor
 *     needs to identify it for click-to-select).
 *   - Other 7 leaf atoms render inside ComposedWidget's hit-testable
 *     inner-div per Area 6; no per-atom registerComponent.
 *
 * Per Area 1 8-atom enumeration. Per WB-1 schema integrity (codec
 * validates structurally; this dispatcher trusts shape).
 *
 * Phase 1 2-level nesting cap (Q-5) is trusted from WB-1's backend
 * validator — no runtime guard here; deeper trees will not crash,
 * but authoring should already have rejected.
 */

import { type ReactNode } from "react"

import type {
  AtomNode,
  BindingRef,
  VariantId,
} from "../types/composition-blob"
import { registerComponent } from "@/lib/visual-editor/registry/register"

import {
  ButtonRenderer,
  ConditionalContainerRenderer,
  DividerRenderer,
  IconRenderer,
  ImageRenderer,
  StatusBadgeRenderer,
  TextLabelRenderer,
  ValueDisplayRenderer,
} from "./atoms"
import { resolveBinding } from "./resolveBinding"


// Wrap ConditionalContainerRenderer with registerComponent so its
// rendered DOM carries the `data-component-name` boundary the runtime
// editor walks up the DOM to identify a clicked container. Leaf atoms
// stay un-wrapped; ComposedWidget's inner-div is the single hit-test
// surface for them per Area 6.
const ConditionalContainerWrapped = registerComponent({
  type: "widget",
  name: "wb-conditional-container-atom",
  displayName: "Conditional Container (composed-widget atom)",
  description:
    "WB-2 runtime renderer for the conditional_container atom_type. " +
    "The only Phase 1 atom_type that may have children. Registered " +
    "so the runtime editor can identify the container via the " +
    "data-component-name boundary div per Area 6 dual-wrapping lock.",
  category: "widget-builder",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user", "focused-executor"],
  consumedTokens: [],
  configurableProps: {},
  schemaVersion: 1,
  componentVersion: 1,
})(ConditionalContainerRenderer)


export interface AtomRendererProps {
  atom: AtomNode
  atomTree: Record<string, AtomNode>
  bindingsCatalog: Record<string, BindingRef>
  variantId?: VariantId
  dataContext?: unknown
}


/** Determine whether this atom is visible given the current variantId.
 *  Rules:
 *   - variantId === undefined → render all atoms (catalog-preview /
 *     unscoped render).
 *   - variantId set AND atom.visible_in_variants is null/undefined →
 *     atom renders in every variant (per WB-1 schema doc-comment).
 *   - variantId set AND atom.visible_in_variants is set → atom renders
 *     only if variantId ∈ the list. */
function isAtomVisibleInVariant(
  atom: AtomNode,
  variantId: VariantId | undefined,
): boolean {
  if (variantId === undefined) return true
  if (!atom.visible_in_variants) return true
  return atom.visible_in_variants.includes(variantId)
}


/** Build the resolvedBindings record keyed by config field name.
 *  Each entry in atom.binding_refs maps `configFieldName → binding_id`;
 *  we look up the BindingRef in the catalog and resolve. */
function buildResolvedBindings(
  atom: AtomNode,
  bindingsCatalog: Record<string, BindingRef>,
  dataContext: unknown,
): Record<string, unknown> {
  if (!atom.binding_refs) return {}
  const resolved: Record<string, unknown> = {}
  for (const [fieldName, bindingId] of Object.entries(atom.binding_refs)) {
    const ref = bindingsCatalog[bindingId]
    if (!ref) {
      // Defensive: WB-1 validator catches dangling binding_id refs
      // before persistence. If we hit one at runtime, surface a
      // placeholder rather than crash — production load must remain
      // resilient to slightly-broken compositions.
      resolved[fieldName] = `[unbound:${bindingId}]`
      continue
    }
    resolved[fieldName] = resolveBinding(ref, dataContext)
  }
  return resolved
}


export function AtomRenderer({
  atom,
  atomTree,
  bindingsCatalog,
  variantId,
  dataContext,
}: AtomRendererProps): ReactNode {
  if (!isAtomVisibleInVariant(atom, variantId)) return null

  const resolvedBindings = buildResolvedBindings(
    atom,
    bindingsCatalog,
    dataContext,
  )

  // Build child renders for container atoms BEFORE dispatch so the
  // leaf renderer doesn't have to reach back into atom_tree. Phase 1:
  // only conditional_container has children.
  const childRenders =
    atom.atom_type === "conditional_container" && atom.children
      ? atom.children.map((childId) => {
          const child = atomTree[childId]
          if (!child) {
            // Defensive: WB-1 validator catches dangling child refs;
            // skip gracefully at runtime.
            return null
          }
          return (
            <AtomRenderer
              key={childId}
              atom={child}
              atomTree={atomTree}
              bindingsCatalog={bindingsCatalog}
              variantId={variantId}
              dataContext={dataContext}
            />
          )
        })
      : undefined

  // Each leaf renderer types its own config narrowly; AtomRenderer
  // hands through atom.config (typed Record<string,unknown> per WB-1)
  // via a per-branch cast. The renderers read fields defensively
  // (optional chaining + fallbacks); placeholder Phase 1 UI doesn't
  // need strict config validation. WB-3 may layer per-atom-type
  // runtime config validation via the codec's atom-config schemas.
  const baseProps = {
    atom,
    resolvedBindings,
  }

  switch (atom.atom_type) {
    case "text_label":
      return (
        <TextLabelRenderer
          {...baseProps}
          config={atom.config as unknown as Parameters<typeof TextLabelRenderer>[0]["config"]}
        />
      )
    case "value_display":
      return (
        <ValueDisplayRenderer
          {...baseProps}
          config={atom.config as unknown as Parameters<typeof ValueDisplayRenderer>[0]["config"]}
        />
      )
    case "icon":
      return (
        <IconRenderer
          {...baseProps}
          config={atom.config as unknown as Parameters<typeof IconRenderer>[0]["config"]}
        />
      )
    case "status_badge":
      return (
        <StatusBadgeRenderer
          {...baseProps}
          config={atom.config as unknown as Parameters<typeof StatusBadgeRenderer>[0]["config"]}
        />
      )
    case "divider":
      return (
        <DividerRenderer
          {...baseProps}
          config={atom.config as unknown as Parameters<typeof DividerRenderer>[0]["config"]}
        />
      )
    case "button":
      return (
        <ButtonRenderer
          {...baseProps}
          config={atom.config as unknown as Parameters<typeof ButtonRenderer>[0]["config"]}
        />
      )
    case "image":
      return (
        <ImageRenderer
          {...baseProps}
          config={atom.config as unknown as Parameters<typeof ImageRenderer>[0]["config"]}
        />
      )
    case "conditional_container":
      return (
        <ConditionalContainerWrapped
          {...baseProps}
          config={
            atom.config as unknown as Parameters<
              typeof ConditionalContainerRenderer
            >[0]["config"]
          }
        >
          {childRenders}
        </ConditionalContainerWrapped>
      )
    default: {
      // Exhaustive guard — TypeScript flags missing atom_type cases.
      const _exhaustive: never = atom.atom_type
      throw new Error(
        `[AtomRenderer] unknown atom_type: ${String(_exhaustive)}`,
      )
    }
  }
}

export default AtomRenderer
