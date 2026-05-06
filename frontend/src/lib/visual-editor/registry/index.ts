/**
 * Bridgeable Admin Visual Editor — Phase 1 Component Registry.
 *
 * Public API surface. Phase 1 consumers:
 *   • `registerComponent` — HOC for tagging components
 *   • Introspection helpers — read-side queries for the admin
 *     debug page + future visual editor
 *   • Types — for downstream consumers building on the schema
 *
 * Side-effect import `auto-register` to populate the registry
 * with the 17 Phase 1 components before any reader mounts.
 */

export { registerComponent } from "./register"

export {
  getAllRegistered,
  getByType,
  getByVertical,
  getByName,
  getTokensConsumedBy,
  getComponentsConsumingToken,
  getAcceptedChildrenForSlot,
  getRegistrationVersion,
  getTotalCount,
  getCountByType,
  getCoverageByVertical,
  getKnownTokens,
  getEffectiveComponentClasses,
  getComponentsInClass,
  isCanvasPlaceable,
  getCanvasMetadata,
  getCanvasPlaceableComponents,
} from "./introspection"

export type {
  ComponentKind,
  ConfigPropSchema,
  ConfigPropType,
  RegistrationMetadata,
  RegistryEntry,
  RegistryKey,
  ResolveConfigPropValue,
  ResolveConfigurableProps,
  SlotDeclaration,
  TokenCategory,
  TokenOverrideMap,
  UserParadigm,
  VariantDeclaration,
  VerticalScope,
} from "./types"

export { REGISTRY_SCHEMA_VERSION } from "./types"

// ── Component class layer (May 2026) ─────────────────────────
export {
  CLASS_REGISTRATIONS,
  getAllClassNames,
  getClassRegistration,
  getClassProp,
} from "./class-registrations"
export type { ClassRegistration } from "./class-registrations"
