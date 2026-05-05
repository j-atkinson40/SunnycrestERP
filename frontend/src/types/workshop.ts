/**
 * Workshop primitive frontend types — Phase 1D pattern-establisher.
 *
 * Per BRIDGEABLE_MASTER §3.26.14 Workshop primitive canon: mirrors
 * backend ``app.services.workshop.registry`` + ``tenant_config`` shapes.
 *
 * Pattern-establisher discipline: Step 2 + future Generation Focus
 * templates extend the same TemplateType union + tune-mode types via
 * registry registrations at backend; frontend types remain stable.
 */

import type { CanonicalOptionType } from "@/types/personalization-studio"

/** Workshop template-type discriminator. Phase 1D registers
 *  ``burial_vault_personalization_studio``; Step 2 extends with
 *  ``urn_vault_personalization_studio``; future templates extend
 *  identically. */
export type WorkshopTemplateType = "burial_vault_personalization_studio"

/** Workshop template-type registry entry mirror. */
export interface TemplateTypeDescriptor {
  template_type: WorkshopTemplateType
  display_name: string
  description: string
  applicable_verticals: string[]
  applicable_authoring_contexts: string[]
  empty_canvas_state_factory_key: string
  tune_mode_dimensions: TuneModeDimension[]
  sort_order: number
}

/** Tune mode dimension keys per Phase 1D + §3.26.11.12.19.2 canonical
 *  4-options vocabulary scope freeze. Tune mode operations are
 *  parameter overrides within these dimensions; cannot add new
 *  dimensions outside the registered set. */
export type TuneModeDimension =
  | "display_labels"
  | "emblem_catalog"
  | "font_catalog"
  | "legacy_print_catalog"

/** Per-tenant Tune mode configuration response.
 *
 *  Mirrors backend ``get_tenant_personalization_config`` shape —
 *  resolved values (tenant override OR canonical default) surface
 *  alongside ``defaults`` so chrome can show "currently customized
 *  vs default" without secondary fetch.
 */
export interface TenantPersonalizationConfig {
  template_type: WorkshopTemplateType
  display_labels: Record<CanonicalOptionType, string>
  emblem_catalog: string[]
  font_catalog: string[]
  legacy_print_catalog: string[]
  defaults: {
    display_labels: Record<CanonicalOptionType, string>
    emblem_catalog: string[]
    font_catalog: string[]
    legacy_print_catalog: string[]
  }
  vinyl_symbols: string[]
}

/** Per-tenant Tune mode configuration update request — partial-update
 *  semantics. Only present dimensions are written; absent dimensions
 *  remain at their existing tenant override (or canonical default).
 *
 *  Tune mode boundary discipline enforced at backend service layer;
 *  violations return HTTP 422.
 */
export interface TenantPersonalizationConfigUpdate {
  display_labels?: Partial<Record<CanonicalOptionType, string>>
  emblem_catalog?: string[]
  font_catalog?: string[]
  legacy_print_catalog?: string[]
}
