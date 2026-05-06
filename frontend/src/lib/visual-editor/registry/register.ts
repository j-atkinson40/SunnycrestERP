/**
 * Bridgeable Admin Visual Editor — `registerComponent` HOC.
 *
 * Wraps a React component with registry metadata at module
 * import time. Runtime behavior of the component is unchanged:
 * the HOC returns the original component reference plus a
 * side-effect registration into the singleton registry.
 *
 * Usage:
 * ```tsx
 * import { registerComponent } from "@/lib/visual-editor/registry/register"
 *
 * export const CaseFileWidget = registerComponent({
 *   type: "widget",
 *   name: "case-file-summary",
 *   displayName: "Case File Summary",
 *   verticals: ["funeral_home"],
 *   userParadigms: ["owner-operator", "operator-power-user"],
 *   consumedTokens: ["surface-elevated", "border-base", ...],
 *   configurableProps: { showDeceased: { type: "boolean", default: true } },
 *   schemaVersion: 1,
 *   componentVersion: 1,
 * })(({ caseFile, showDeceased }) => { ... })
 * ```
 *
 * Type ergonomics: when a component declares `configurableProps`,
 * the HOC narrows the wrapped component's props so that those
 * keys arrive at their declared types. Other props (entity data,
 * callbacks) remain free-form.
 */

import { createElement, type ComponentType } from "react"

import {
  _internal_register,
  _internal_getEntry,
} from "./registry"
import type {
  ComponentKind,
  ConfigPropSchema,
  RegistrationMetadata,
  RegistryEntry,
} from "./types"
import { REGISTRY_SCHEMA_VERSION } from "./types"


/** Validate the metadata payload at registration time. Throws
 * on irrecoverable shape errors (missing `type` / `name`),
 * console-warns on softer concerns (schemaVersion mismatch,
 * empty `verticals`). */
function _validateMetadata(meta: RegistrationMetadata): void {
  if (!meta.type) {
    throw new Error("[admin-registry] registration missing `type`")
  }
  if (!meta.name || typeof meta.name !== "string") {
    throw new Error(
      `[admin-registry] registration missing string \`name\` for type=${meta.type}`,
    )
  }
  if (!meta.displayName) {
    throw new Error(
      `[admin-registry] registration missing \`displayName\` for ${meta.type}:${meta.name}`,
    )
  }
  if (!Array.isArray(meta.verticals) || meta.verticals.length === 0) {
    throw new Error(
      `[admin-registry] \`verticals\` must be a non-empty array for ${meta.type}:${meta.name} (use ["all"] for cross-vertical components)`,
    )
  }
  if (!Array.isArray(meta.userParadigms) || meta.userParadigms.length === 0) {
    throw new Error(
      `[admin-registry] \`userParadigms\` must be a non-empty array for ${meta.type}:${meta.name}`,
    )
  }
  if (!Array.isArray(meta.consumedTokens)) {
    throw new Error(
      `[admin-registry] \`consumedTokens\` must be an array for ${meta.type}:${meta.name}`,
    )
  }
  if (typeof meta.schemaVersion !== "number") {
    throw new Error(
      `[admin-registry] \`schemaVersion\` must be a number for ${meta.type}:${meta.name}`,
    )
  }
  if (typeof meta.componentVersion !== "number") {
    throw new Error(
      `[admin-registry] \`componentVersion\` must be a number for ${meta.type}:${meta.name}`,
    )
  }

  // Soft warnings — log but do not throw.
  if (meta.schemaVersion !== REGISTRY_SCHEMA_VERSION) {
    // eslint-disable-next-line no-console
    console.warn(
      `[admin-registry] ${meta.type}:${meta.name} schemaVersion=${meta.schemaVersion}, current REGISTRY_SCHEMA_VERSION=${REGISTRY_SCHEMA_VERSION}`,
    )
  }
}


/** Deep-freeze a metadata payload + its nested arrays/objects so
 * consumers of the introspection API can't mutate the registry.
 * Best-effort — `Object.freeze` is shallow; we recurse over known
 * nested structures (slots, variants, configurableProps). */
function _freezeMetadata(meta: RegistrationMetadata): Readonly<RegistrationMetadata> {
  const frozen: RegistrationMetadata = {
    ...meta,
    verticals: Object.freeze([...meta.verticals]) as RegistrationMetadata["verticals"],
    userParadigms: Object.freeze([
      ...meta.userParadigms,
    ]) as RegistrationMetadata["userParadigms"],
    consumedTokens: Object.freeze([
      ...meta.consumedTokens,
    ]) as readonly string[] as string[],
    productLines: meta.productLines
      ? (Object.freeze([...meta.productLines]) as readonly string[] as string[])
      : undefined,
  }
  if (frozen.slots) {
    frozen.slots = Object.freeze(
      frozen.slots.map((s) => Object.freeze({ ...s })),
    ) as typeof frozen.slots
  }
  if (frozen.variants) {
    frozen.variants = Object.freeze(
      frozen.variants.map((v) => Object.freeze({ ...v })),
    ) as typeof frozen.variants
  }
  if (frozen.configurableProps) {
    const props: Record<string, ConfigPropSchema> = {}
    for (const [key, schema] of Object.entries(frozen.configurableProps)) {
      props[key] = Object.freeze({ ...schema })
    }
    frozen.configurableProps = Object.freeze(props) as typeof frozen.configurableProps
  }
  if (frozen.tokenOverrides) {
    frozen.tokenOverrides = Object.freeze({
      ...frozen.tokenOverrides,
    }) as typeof frozen.tokenOverrides
  }
  if (frozen.extensions) {
    frozen.extensions = Object.freeze({ ...frozen.extensions }) as Record<string, unknown>
  }
  return Object.freeze(frozen)
}


/**
 * Register a component. Returns a HOC that takes the React
 * component as its argument and yields the same component
 * reference back (registration is purely a side effect).
 *
 * **Phase 1 typing decision (deliberate):** the HOC accepts any
 * `ComponentType<P>` rather than narrowing to
 * `ResolveConfigurableProps<M["configurableProps"]>`. The reason:
 * registrations describe the metadata the EDITOR consumes — what
 * the visual editor knows it can configure, what tokens the
 * component reads from, etc. The actual React component props
 * may be a superset, subset, or disjoint set of `configurableProps`
 * during Phase 1, because most Phase 1 components were built
 * before the registry existed and haven't been refactored to
 * accept their configurableProps yet.
 *
 * For NEW components designed configuration-first, you can opt
 * into strict typing by declaring your component's props with
 * `ResolveConfigurableProps<typeof MyMeta["configurableProps"]>`
 * in the component definition itself — the exported helper type
 * lets you do that without the HOC enforcing it.
 *
 * Phase 2+ (when the editor injects configurableProps at render
 * time) is when strict alignment matters; that's tracked
 * separately and may add a `registerComponentStrict` variant.
 */
export function registerComponent<M extends RegistrationMetadata>(
  metadata: M,
): <P>(Component: ComponentType<P>) => ComponentType<P> {
  _validateMetadata(metadata)

  // Freeze before capture so the HOC always hands back the same
  // immutable payload regardless of what the caller does to its
  // local reference.
  const frozenMeta = _freezeMetadata(metadata)

  return <P>(Component: ComponentType<P>): ComponentType<P> => {
    // Phase R-1 — wrap with a `data-component-name` boundary so the
    // runtime editor's click-to-edit gesture can walk up the DOM
    // from any pointer event and resolve the nearest registered
    // component. The wrapper uses `display: contents` so it does
    // NOT participate in layout — child elements appear to the
    // parent's box-formation as if the wrapper weren't there. The
    // attributes are queryable via
    // `document.querySelectorAll('[data-component-name]')` from the
    // editor's selection overlay.
    //
    // Tenant operators see these attributes too; they're harmless
    // metadata. This avoids the "edit mode injects different
    // markup" anti-pattern that would create rendering inconsistency
    // between view + edit contexts.
    //
    // Display name + componentVersion preserved so React DevTools
    // shows a meaningful component name; the wrapper's displayName
    // is `Registered(<original>)`.
    const Wrapped: ComponentType<P> = (props: P) =>
      createElement(
        "div",
        {
          "data-component-name": frozenMeta.name,
          "data-component-type": frozenMeta.type,
          "data-component-version": frozenMeta.componentVersion,
          // `display: contents` removes this box from the visual
          // formatting context, so the wrapped child renders as
          // if the wrapper weren't here. WCAG: modern browsers
          // (Chromium, Firefox 63+, Safari 11.1+) properly
          // expose accessibility info for `display: contents`.
          style: { display: "contents" },
        },
        createElement(Component as ComponentType<unknown>, props as unknown as object),
      )

    Wrapped.displayName = `Registered(${
      (Component as { displayName?: string }).displayName ||
      (Component as { name?: string }).name ||
      frozenMeta.name
    })`

    const entry: RegistryEntry = {
      metadata: frozenMeta,
      // Store the WRAPPED component so introspection consumers
      // (preview canvas, editor) see the same DOM the runtime
      // does. Drift between runtime + editor would defeat the
      // purpose of the wrapper.
      component: Wrapped as ComponentType<unknown>,
      registeredAt: Date.now(),
    }
    _internal_register(entry)
    return Wrapped
  }
}


/** Lookup helper for tests + the auto-register barrel. Returns
 * the frozen entry or undefined. */
export function _testing_getEntry(
  type: ComponentKind,
  name: string,
): RegistryEntry | undefined {
  return _internal_getEntry(type, name)
}
