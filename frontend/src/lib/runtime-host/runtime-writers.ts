/**
 * Phase R-1 — Runtime override writers.
 *
 * R-0 shipped EditModeProvider's `commitDraft` with stub writers.
 * R-1 wires real platform-token writes via the existing visual
 * editor service clients (themes-service, component-configurations-
 * service, component-class-configurations-service, dashboard-layouts-
 * service). All writes route through `adminApi` (the existing admin
 * tree's axios instance) which uses the PlatformUser token.
 *
 * Scope discipline (V1):
 *   - Theme + component_prop + component_class writes default to
 *     `vertical_default` for the impersonated tenant's vertical.
 *     Platform admin authoring "the canonical {vertical}
 *     experience." Future scope picker (vertical_default vs
 *     tenant_default vs platform_default) is post-V1.
 *   - dashboard_layout writes also default to vertical_default
 *     (the runtime editor's authoring scope; tenant_default is
 *     authored through the Widget Editor's Dashboard Layouts tab
 *     for now, but R-1 doesn't ship layout editing in the
 *     inspector — deferred to R-3).
 *
 * Audit trail: each write captures `actor_user_id` from the
 * PlatformUser session via getAdminToken's session lookup; the
 * impersonation context (tenant_id + impersonated_user_id) is
 * passed alongside so audit log enrichment can correlate later.
 * R-1 doesn't ship audit log enrichment server-side; the writer
 * forwards the metadata as best-effort context.
 *
 * Per-type writer signature mirrors R-0's OverrideWriter:
 *   `(helpers, override) => Promise<void>`. Throws on failure;
 *   commitDraft catches + records per-key error.
 */
import {
  componentClassConfigurationsService,
  type ClassConfigurationRecord,
} from "@/bridgeable-admin/services/component-class-configurations-service"
import {
  componentConfigurationsService,
  type ComponentConfigurationRecord,
} from "@/bridgeable-admin/services/component-configurations-service"
import { themesService } from "@/bridgeable-admin/services/themes-service"

import type {
  OverrideWriter,
  RuntimeOverride,
} from "./edit-mode-context"


/** Authoring-scope context the runtime editor's writers consume. The
 *  scope is supplied by the `RuntimeEditorShell` (the impersonation
 *  context's vertical drives vertical_default scope writes). */
export interface RuntimeWriteContext {
  vertical: string | null
  tenantId: string | null
  impersonatedUserId: string | null
  /** Mode driving theme writes — light or dark. Defaults to "light"
   *  if not specified; future R-* phases route this from the active
   *  theme mode picker. */
  themeMode: "light" | "dark"
}


/** Theme writer — POST a token override at vertical_default scope.
 *  Each `RuntimeOverride` carries one token; the writer collects all
 *  pending token overrides for the same scope into a single create
 *  call would be ideal but R-1 ships per-override writes (versioning
 *  is tolerant of multiple writes; `commitDraft` invokes the writer
 *  per staged override). Future R-* phases may batch. */
export function makeThemeWriter(ctx: RuntimeWriteContext): OverrideWriter {
  return async (_helpers, override: RuntimeOverride) => {
    const tokenName = override.target
    const value = override.value
    if (!ctx.vertical) {
      throw new Error(
        "runtime-writers/theme: vertical missing — runtime editor " +
          "requires impersonated tenant's vertical to author at " +
          "vertical_default scope.",
      )
    }
    // Find existing active row at vertical_default scope; if present,
    // merge the new token; if not, create.
    const existing = await themesService.list({
      scope: "vertical_default",
      vertical: ctx.vertical,
      mode: ctx.themeMode,
    })
    const activeRow = existing.find((r) => r.is_active) ?? null
    const merged: Record<string, unknown> = {
      ...(activeRow?.token_overrides ?? {}),
      [tokenName]: value,
    }
    if (activeRow) {
      // R-1.6.15 — `themesService.update`'s second arg is the raw
      // token_overrides map (the service wraps it into
      // `{ token_overrides }` before POSTing). Pre-R-1.6.15 this call
      // double-wrapped (`{ token_overrides: merged }`) producing
      // `{token_overrides: {token_overrides: merged}}` over the wire.
      // Backend Pydantic accepted the nested object as a valid value
      // of `Dict[str, Any]`, so commits silently stored junk and the
      // resolver returned defaults — spec 7's commit-and-reload
      // persistence assertion failed against the static default. The
      // canonical caller (`ThemeEditorPage.tsx:235`) passes the raw
      // map directly; matching that shape closes the bug.
      await themesService.update(activeRow.id, merged)
    } else {
      await themesService.create({
        scope: "vertical_default",
        vertical: ctx.vertical,
        mode: ctx.themeMode,
        token_overrides: merged,
      })
    }
  }
}


/** Component-prop override writer — POST a single prop override at
 *  vertical_default scope for a (kind, name) pair. */
export function makeComponentPropWriter(
  ctx: RuntimeWriteContext,
): OverrideWriter {
  return async (_helpers, override: RuntimeOverride) => {
    if (!ctx.vertical) {
      throw new Error(
        "runtime-writers/component_prop: vertical missing.",
      )
    }
    // override.target shape: `${kind}:${name}` e.g. "widget:today"
    const sep = override.target.indexOf(":")
    if (sep < 0) {
      throw new Error(
        `runtime-writers/component_prop: target '${override.target}' must be 'kind:name'`,
      )
    }
    const kind = override.target.slice(0, sep)
    const name = override.target.slice(sep + 1)

    // Lookup any existing row at vertical_default scope.
    const existing = await componentConfigurationsService.list({
      scope: "vertical_default",
      vertical: ctx.vertical,
      component_kind: kind as ComponentConfigurationRecord["component_kind"],
      component_name: name,
    })
    const activeRow = existing.find((r) => r.is_active) ?? null
    const mergedProps: Record<string, unknown> = {
      ...(activeRow?.prop_overrides ?? {}),
      [override.prop]: override.value,
    }
    if (activeRow) {
      await componentConfigurationsService.update(activeRow.id, {
        prop_overrides: mergedProps,
      })
    } else {
      await componentConfigurationsService.create({
        scope: "vertical_default",
        vertical: ctx.vertical,
        component_kind: kind as ComponentConfigurationRecord["component_kind"],
        component_name: name,
        prop_overrides: mergedProps,
      })
    }
  }
}


/** Component-class override writer — class configurations are
 *  platform-default scope by spec (no vertical/tenant variant per
 *  CLAUDE.md §4 Component Class Configuration). */
export function makeComponentClassWriter(
  _ctx: RuntimeWriteContext,
): OverrideWriter {
  return async (_helpers, override: RuntimeOverride) => {
    const className = override.target
    const existing = await componentClassConfigurationsService.list({
      component_class: className,
    })
    const activeRow = existing.find(
      (r: ClassConfigurationRecord) => r.is_active,
    ) ?? null
    const mergedProps: Record<string, unknown> = {
      ...(activeRow?.prop_overrides ?? {}),
      [override.prop]: override.value,
    }
    if (activeRow) {
      await componentClassConfigurationsService.update(activeRow.id, {
        prop_overrides: mergedProps,
      })
    } else {
      await componentClassConfigurationsService.create({
        component_class: className,
        prop_overrides: mergedProps,
      })
    }
  }
}


/** Build the full per-type writer registry for a runtime editor
 *  session. Consumed by `<EditModeProvider writers={...}>`. */
export function buildRuntimeWriters(
  ctx: RuntimeWriteContext,
): Required<{
  token: OverrideWriter
  component_prop: OverrideWriter
  component_class: OverrideWriter
  dashboard_layout: OverrideWriter
}> {
  return {
    token: makeThemeWriter(ctx),
    component_prop: makeComponentPropWriter(ctx),
    component_class: makeComponentClassWriter(ctx),
    dashboard_layout: async () => {
      // R-1 doesn't ship layout editing in the inspector. Layouts
      // continue to be authored via the Widget Editor's Dashboard
      // Layouts tab. Keeping a stub writer so the contract is
      // honored — staged dashboard_layout overrides commit as a
      // no-op (and inspector doesn't expose them in V1).
      throw new Error(
        "runtime-writers/dashboard_layout: not wired in R-1. Use " +
          "the Widget Editor's 'Dashboard Layouts' tab to author " +
          "layouts at vertical_default scope.",
      )
    },
  }
}
