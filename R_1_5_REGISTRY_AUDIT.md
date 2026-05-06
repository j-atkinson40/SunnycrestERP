# R-1.5 Registry Contract Audit

**Date**: 2026-06-06
**Trigger**: Phase R-1's `registerComponent` HOC change wraps every registered
component in a `display: contents` div carrying `data-component-name`,
`data-component-type`, `data-component-version`. The `RegistryEntry.component`
field now points at the wrapped boundary component, NOT the original component
reference. Existing tests asserting `entry.component === Cmp` would silently
fail.

## Audit scope

Every callsite (outside the registry package itself) that imports any of the
following registry exports:

- `getByName`, `getAllRegistered`, `getByType`, `getByVertical`
- `getCanvasPlaceableComponents`, `getCanvasMetadata`, `isCanvasPlaceable`
- `getEffectiveComponentClasses`, `getComponentsInClass`
- `getTokensConsumedBy`, `getComponentsConsumingToken`
- `getKnownTokens`, `getCountByType`, `getCoverageByVertical`, `getTotalCount`
- `getRegistrationVersion`, `getAcceptedChildrenForSlot`
- `RegistryEntry` type

Plus a structural grep for any `entry.component`, `reg.component`,
`registration.component` access patterns.

## Total callsites

**63** registry-export imports + reads across `frontend/src/` (outside the
registry package).

## Per-callsite analysis

| File | Function | Uses .component as ref? | Map key? | useMemo dep? | === check? | Remediation |
|---|---|---|---|---|---|---|
| `lib/visual-editor/components/PropControls.tsx` | iterates `getAllRegistered()` for tokenReference picker | No — reads `metadata.name` | No | No (deps are token-id strings) | No | None |
| `lib/visual-editor/components/component-config.test.ts` | iterates `getAllRegistered()` for backfill validation | No — reads `metadata.configurableProps` | No | n/a (test) | No | None |
| `lib/visual-editor/components/config-resolver.ts:70` | `getByName(kind, name)` to read `metadata.configurableProps` | No — reads metadata only | No | No | No | None |
| `lib/visual-editor/compositions/CompositionRenderer.test.tsx` | `getCanvasPlaceableComponents` + `getAllRegistered` for filter assertion | No — counts entries, doesn't render | No | n/a (test) | No | None |
| `lib/runtime-host/inspector/ClassTab.tsx:46` | `getEffectiveComponentClasses(entry)` | n/a — returns string[] | No | No | No | None |
| `lib/runtime-host/inspector/InspectorPanel.tsx:69` | `getByName(k, selectedComponentName)` to look up entry by selected name | No — passes the entry to tab children for metadata reads | No | No (deps are `selectedComponentName` string) | No | None |
| `lib/runtime-host/inspector/PropsTab.tsx` | reads `entry.metadata.type`, `entry.metadata.name`, `entry.metadata.configurableProps` | No | No | No | No | None |
| `bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas.tsx:190,192` | `getByName(...)` + `getCanvasMetadata(entry)` | No — `getCanvasMetadata` reads `metadata.canvasMetadata` | No | No | No | None |
| `bridgeable-admin/pages/visual-editor/ComponentEditorPage.tsx:154,180` | `getAllRegistered()` for component browser; `getByName(...)` for selected entry | No — renders preview by metadata name + invokes `preview-renderers` lookup table keyed on metadata name | No | `useMemo(..., [])` empty-deps — runs once on mount | No | None |
| `bridgeable-admin/pages/visual-editor/CompositionEditorPage.tsx:248,408,454` | `getCanvasPlaceableComponents()` for palette; `getCanvasMetadata(entry)` for placement bounds | No | No | `useMemo(..., [])` empty-deps | No | None |
| `bridgeable-admin/pages/visual-editor/RegistryDebugPage.tsx:75-78,111` | `getAllRegistered`, `getCountByType`, `getCoverageByVertical`, `getKnownTokens`, `getComponentsConsumingToken` for inspector UI | No — reads metadata | No | `useMemo(..., [])` empty-deps | No | None |
| `bridgeable-admin/pages/visual-editor/VisualEditorIndex.tsx:32,33` | `getAllRegistered()` + `getKnownTokens()` for landing-page stats | No — counts only | No | `useMemo(..., [])` empty-deps | No | None |
| `bridgeable-admin/pages/visual-editor/ClassEditorPage.tsx:305,462` | `getComponentsInClass(className)` for class-membership panel | No — reads metadata.name for display | No | `useMemo(..., [selectedClass])` — depends on string | No | None |
| `bridgeable-admin/pages/visual-editor/FocusEditorPage.tsx:302,338,957,1020` | `getAllRegistered()` + `getByName("focus-template", id)` + `getCanvasPlaceableComponents()` + `getCanvasMetadata(entry)` for focus editor + composition canvas | No — reads metadata | No | useMemo deps are template id strings, not entry refs | No | None |
| `bridgeable-admin/pages/visual-editor/WidgetEditorPage.tsx:169,202,671,992` | `getComponentsInClass("widget")` + `getByName("widget", selectedName)` for widget browser + per-widget editor | No — reads metadata | No | useMemo deps are `selectedName` string | No | None |
| `bridgeable-admin/pages/visual-editor/themes/PreviewCanvas.tsx:62,88,102` | `getAllRegistered()` for stand-in catalog; `registryKey(entry)` builds `${type}:${name}` string key; `Map<ComponentKind, RegistryEntry[]>` groups by kind | No — Map key is `ComponentKind`, not entry ref | No (entries grouped by kind, not stored by ref) | useMemo deps are `filterVertical` + `effectiveTokens` strings | No | None |
| `bridgeable-admin/pages/visual-editor/themes/TokenEditorPane.tsx:115,263` | `getTokensConsumedBy(type, name)` + `getComponentsConsumingToken(token)` | n/a — returns string arrays + entry arrays for read-only display | No | No (deps are token name strings) | No | None |

### Special: `frontend/src/services/vault-hub-registry.ts:115`

This is a **different registry** — the Vault widget hub registry, unrelated to
the visual editor registry. Its `reg.component` field stores a widget-renderer
React component the hub uses to render Vault Overview pieces. Not affected by
the visual editor `registerComponent` HOC change.

## Conclusion

**No callsites depend on the old contract.**

- 0 callsites compare `entry.component` via `===` / `!==`.
- 0 callsites use a registered component reference as a Map key (only Vault
  Hub Registry, which has its own component field unrelated to the visual
  editor HOC).
- 0 callsites pass a registered component reference to `useMemo` /
  `useCallback` deps.
- 0 callsites render `<entry.component />` directly anywhere — every consumer
  reads `metadata` fields (name, type, configurableProps, canvasMetadata,
  verticals) for routing or rendering decisions, then renders via dedicated
  per-kind preview components or stand-ins.

The HOC change is structurally non-breaking for the existing codebase. The
only asserter that broke was `registry.test.ts`, which was updated in R-1
to assert the new wrapped-component contract (Wrapped !== Cmp + the new
`Registered(displayName)` displayName pattern).

## Remediations applied during R-1.5

**None required.** Audit confirmed the contract change is invisible to all
existing consumers.

## What this audit doesn't cover

- **Production runtime** behavior — only static analysis. The fact that the
  `display: contents` wrapper preserves layout is verified by R-1 visual
  smoke + the lazy chunk split confirming the wrapper renders correctly.
- **Future callers** — any new code that compares `entry.component` via
  ref-identity or stores the component reference as a Map key would silently
  break. R-1.5 does not add a runtime guard or lint rule against this; the
  audit document is the contract record.

## Future-proofing recommendation (deferred — not R-1.5 scope)

If a future phase introduces ref-identity dependence on registered components,
add a `RegistryEntry.originalComponent` field exposing the un-wrapped reference
for callers that need it. The HOC already has access to the original component
parameter; storing it alongside the wrapped boundary is a 1-line registry
change. Tracking as a future consideration for R-2+ but not warranted today.
