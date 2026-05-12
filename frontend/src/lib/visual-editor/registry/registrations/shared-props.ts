/**
 * Shared configurable-prop schemas reused across multiple registration
 * sites. Living-in-its-own-file prevents circular imports between
 * `class-registrations.ts` (class layer) and `entity-card-sections.ts`
 * (sub-section registrations) — both consume `BUTTON_SLUGS_PROP`
 * without depending on each other.
 *
 * R-2.1 introduced the original constant inside `entity-card-sections.ts`.
 * Arc 4a.1 needed it at class scope (Focus action bar substrate via
 * class-level buttonSlugs); lifting it here removes the import cycle
 * that would otherwise load `entity-card-sections.ts` before the
 * auto-register barrel's side-effect order.
 */
import type { ConfigPropSchema } from "../types"


/** Shared `buttonSlugs` prop schema — R-2.1 button composition Path A.
 *
 *  Array of componentReference items filtered to `button`
 *  ComponentKind. The receiving runtime maps each slug to a
 *  `<RegisteredButton componentName={slug} />`.
 *
 *  Canonical consumers (today + Arc 4a.1):
 *    - entity-card-section actions (R-2.1) — delivery / ancillary /
 *      order card per-section action bars
 *    - focus class (Arc 4a.1) — class-level Focus action bar
 *    - focus-template class (Arc 4a.1) — per-template override slot
 *
 *  Future class-level button composition reuses this constant
 *  verbatim — do not re-declare. */
export const BUTTON_SLUGS_PROP: ConfigPropSchema<string[]> = {
  type: "array",
  default: [],
  bounds: { maxLength: 6 },
  displayLabel: "Action buttons",
  description:
    "Array of registered button slugs to render in this section. Each slug fires its R-4 contract on click. Buttons must be registered via `registry/registrations/buttons.ts` first.",
  itemSchema: {
    type: "componentReference",
    default: "",
    componentTypes: ["button"],
    displayLabel: "Button",
    description: "Pick a registered button by slug.",
  },
}
