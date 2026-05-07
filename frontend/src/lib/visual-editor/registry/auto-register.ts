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
