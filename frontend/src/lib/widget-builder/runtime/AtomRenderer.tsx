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
  RepeaterAtomRenderer,
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
    "Container atom; registered so the runtime editor can identify " +
    "the container via the data-component-name boundary div per " +
    "Area 6 dual-wrapping lock.",
  category: "widget-builder",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user", "focused-executor"],
  consumedTokens: [],
  configurableProps: {},
  schemaVersion: 1,
  componentVersion: 1,
})(ConditionalContainerRenderer)

// WB-3 — repeater_atom is the second container atom in Phase 1 and
// gets its own registerComponent wrap per Area 6 dual-wrapping lock.
// AtomRenderer applies the wrap at dispatch time (not in the atoms
// barrel) so the wrap stays scoped to the dispatch path.
const RepeaterAtomWrapped = registerComponent({
  type: "widget",
  name: "wb-repeater-atom",
  displayName: "Repeater (composed-widget atom)",
  description:
    "WB-3 runtime renderer for the repeater_atom atom_type. " +
    "Iteration primitive — renders children once per row of an " +
    "iterating BindingRef. Registered so the runtime editor can " +
    "identify the container via the data-component-name boundary " +
    "div per Area 6 dual-wrapping lock.",
  category: "widget-builder",
  verticals: ["all"],
  userParadigms: ["owner-operator", "operator-power-user", "focused-executor"],
  consumedTokens: [],
  configurableProps: {},
  schemaVersion: 1,
  componentVersion: 1,
})(RepeaterAtomRenderer)


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
  // leaf renderer doesn't have to reach back into atom_tree. Phase 1
  // post-WB-3: conditional_container + repeater_atom are container
  // atoms.
  let childRenders: ReactNode | undefined = undefined
  if (atom.atom_type === "conditional_container" && atom.children) {
    childRenders = atom.children.map((childId) => {
      const child = atomTree[childId]
      if (!child) return null
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
  } else if (atom.atom_type === "repeater_atom" && atom.children) {
    // WB-6 — repeater iteration substantiated. Real rows flow via
    // `dataContext.rows` (WB-5 canvas preview supplies this; embedded
    // widget renders supply this from saved-view fetch). When
    // `dataContext` is undefined OR rows is absent, render a single
    // mock row so the layout remains visible during authoring (the
    // canvas preview is WB-5's job — until then the canvas renders
    // one structural row so the operator can shape the row template).
    //
    // Per Area 4c lock: rowContext spreads the row dict INTO the
    // context. `__row` discriminator + `__index` position marker stay
    // alongside; the row's fields become directly accessible.
    let realRows: Record<string, unknown>[] | undefined = undefined
    if (
      typeof dataContext === "object" &&
      dataContext !== null &&
      Array.isArray((dataContext as { rows?: unknown }).rows)
    ) {
      realRows = (dataContext as { rows: Record<string, unknown>[] }).rows
    }

    const repeaterConfig = (atom.config as { empty_state?: string; max_rows?: number } | undefined) ?? {}

    // Empty array → render empty_state if configured. (RepeaterAtomRenderer
    // handles the empty-children render path; we surface empty rows via
    // an empty `rows` array passed as children below — but the renderer
    // looks at children.length, so we route to empty path by passing [].)
    if (realRows !== undefined && realRows.length === 0) {
      // Empty real rows — pass no children; renderer surfaces empty_state.
      childRenders = []
    } else {
      const iterRows: Array<Record<string, unknown> | null> =
        realRows !== undefined
          ? (repeaterConfig.max_rows
              ? realRows.slice(0, repeaterConfig.max_rows)
              : realRows)
          : [null] // WB-6 authoring fallback: 1 structural mock row
      const rows: ReactNode[] = []
      iterRows.forEach((rowData, i) => {
        const rowContext: Record<string, unknown> =
          rowData !== null
            ? { __row: true, __index: i, ...rowData }
            : { __row: true, __index: i }
        rows.push(
          <div
            key={`row-${i}`}
            data-row-index={i}
            className="flex flex-row items-center gap-2"
          >
            {atom.children!.map((childId) => {
              const child = atomTree[childId]
              if (!child) return null
              // Defensive: repeater inside repeater would have been
              // rejected at validation time. Throw at render time as
              // defense-in-depth.
              if (child.atom_type === "repeater_atom") {
                throw new Error(
                  `[AtomRenderer] repeater_atom ${atom.atom_id} may not contain another repeater_atom (${childId}) — Phase 1 cap`,
                )
              }
              return (
                <AtomRenderer
                  key={`${childId}-${i}`}
                  atom={child}
                  atomTree={atomTree}
                  bindingsCatalog={bindingsCatalog}
                  variantId={variantId}
                  dataContext={rowContext}
                />
              )
            })}
          </div>,
        )
      })
      childRenders = rows
    }
  }

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
    case "repeater_atom":
      return (
        <RepeaterAtomWrapped
          {...baseProps}
          config={
            atom.config as unknown as Parameters<
              typeof RepeaterAtomRenderer
            >[0]["config"]
          }
        >
          {childRenders}
        </RepeaterAtomWrapped>
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
