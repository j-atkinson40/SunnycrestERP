/**
 * Workshop frontend service — Phase 1D Tune mode operations.
 *
 * Per BRIDGEABLE_MASTER §3.26.14 Workshop primitive canon: mirrors
 * backend ``/api/v1/workshop/*`` endpoint set.
 */

import apiClient from "@/lib/api-client"
import type {
  TemplateTypeDescriptor,
  TenantPersonalizationConfig,
  TenantPersonalizationConfigUpdate,
  WorkshopTemplateType,
} from "@/types/workshop"

const BASE_PATH = "/workshop"

/** List Workshop template-types registered at canonical substrate.
 *
 *  Optional ``vertical`` filter narrows to template-types applicable
 *  to that vertical (or cross-vertical templates).
 */
export async function listTemplateTypes(
  vertical?: string,
): Promise<TemplateTypeDescriptor[]> {
  const params = vertical ? { vertical } : undefined
  const res = await apiClient.get<TemplateTypeDescriptor[]>(
    `${BASE_PATH}/template-types`,
    { params },
  )
  return res.data
}

/** Read per-tenant Tune mode configuration. Admin-gated server-side. */
export async function getTenantPersonalizationConfig(
  templateType: WorkshopTemplateType,
): Promise<TenantPersonalizationConfig> {
  const res = await apiClient.get<TenantPersonalizationConfig>(
    `${BASE_PATH}/personalization-studio/${templateType}/tenant-config`,
  )
  return res.data
}

/** Update per-tenant Tune mode configuration with partial-update
 *  semantics. Tune mode boundary violations return HTTP 422 from
 *  backend per §3.26.11.12.19.2. */
export async function updateTenantPersonalizationConfig(
  templateType: WorkshopTemplateType,
  body: TenantPersonalizationConfigUpdate,
): Promise<TenantPersonalizationConfig> {
  const res = await apiClient.patch<TenantPersonalizationConfig>(
    `${BASE_PATH}/personalization-studio/${templateType}/tenant-config`,
    body,
  )
  return res.data
}
