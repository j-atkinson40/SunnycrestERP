/**
 * Bridgeable Admin Visual Editor — auto-register barrel.
 *
 * Side-effect-on-import module. Imports every Phase 1
 * registration module so the singleton registry is populated
 * before any consumer (admin debug page, future visual editor)
 * mounts.
 *
 * Pattern mirrors existing platform conventions:
 *   • `@/components/widgets/foundation/register`
 *   • `@/components/widgets/manufacturing/register`
 *   • `@/components/dispatch/scheduling-focus/register`
 *
 * Future phases may switch to in-component
 * `registerComponent({...})(Component)` wrapping at each
 * component file. The introspection API doesn't care which
 * pattern the registration came through.
 */

import "./registrations/widgets"
import "./registrations/focus-types"
import "./registrations/focus-templates"
import "./registrations/document-blocks"
import "./registrations/workflow-nodes"
// R-2.0 — entity-card registrations (DeliveryCard / AncillaryCard /
// OrderCard). Path 1 wrapping per R-1.6.12 convention; render sites
// import wrapped versions from the registrations barrel, not from
// the underlying component files (eslint rule enforces).
import "./registrations/entity-cards"
// R-2.1 — entity-card-section registrations (10 sub-sections across
// the 3 entity cards). Each sub-section is its own Path-1-wrapped
// React component emitting `data-component-name="<parent>.<child>"`.
// MUST import after entity-cards (the parent registrations) so the
// inspector's outer-tabs lookup chain (parent → sub-sections) is
// populated in canonical order.
import "./registrations/entity-card-sections"
// R-4.0 — button registrations (3 example slugs covering 3 of the 5
// R-4 action types: open_focus, trigger_workflow, navigate). Other 8
// ActionKind values from services/actions/ deferred to R-4.x
// increments per Spec-Override Discipline. Buttons are registered as
// `button` ComponentKind; widget-shaped registration pattern (1 kind,
// N instances) — RegisteredButton looks up its own metadata at click-
// time via getByName("button", slug).
import "./registrations/buttons"
