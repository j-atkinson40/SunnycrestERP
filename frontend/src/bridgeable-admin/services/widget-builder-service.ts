/**
 * widget-builder-service — DEPRECATED RE-EXPORT SHIM (WB-cycle-followup-2).
 *
 * Prior to WB-cycle-followup-2, this module owned the Widget Builder
 * API client and consumed the tenant `apiClient`, calling
 * `/api/v1/widget-definitions/*`. On the admin subdomain
 * (`admin.getbridgeable.com`) the tenant apiClient has no tenant token,
 * which produced a 403 on every Widget Builder operation
 * (the operator-validation gap from WB-cycle-followup-1).
 *
 * WB-cycle-followup-2 relocates the API client to
 * `visual-editor-widgets-service.ts` which consumes `adminApi` against
 * `/api/platform/admin/visual-editor/widgets/*`. This file remains as
 * a thin re-export shim so existing consumers + test `vi.mock(...)`
 * paths continue working without churn.
 *
 * New code SHOULD import from
 * `@/bridgeable-admin/services/visual-editor-widgets-service` directly.
 * The shim is preserved indefinitely for stability (low cost; one
 * file, no logic).
 */
export {
  WidgetBuilderApiError,
  visualEditorWidgetsService as widgetBuilderService,
} from "./visual-editor-widgets-service"

export type {
  WidgetBuilderRecord,
  CreateWidgetPayload,
  SaveDraftPayload,
  PublishValidationError,
  ComposedWidgetDefinitionDTO,
} from "./visual-editor-widgets-service"
