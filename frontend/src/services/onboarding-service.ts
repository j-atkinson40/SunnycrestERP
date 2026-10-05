import apiClient from "@/lib/api-client";
import type {
  OnboardingChecklist,
  OnboardingScenario,
  DataImport,
  IntegrationSetup,
  ProductTemplate,
  ProductImportItem,
  ImportPreview,
  OnboardingAnalytics,
} from "@/types/onboarding";

// --- Checklist ---

export async function getChecklist(): Promise<OnboardingChecklist> {
  const { data } = await apiClient.get("/tenant-onboarding/checklist");
  return data;
}

export async function initializeChecklist(): Promise<OnboardingChecklist> {
  const { data } = await apiClient.post("/tenant-onboarding/checklist/initialize");
  return data;
}

export async function updateChecklistItem(
  itemKey: string,
  update: { status?: string; skipped?: boolean }
): Promise<void> {
  await apiClient.patch(`/tenant-onboarding/checklist/items/${itemKey}`, update);
}

export async function completeChecklistItem(itemKey: string): Promise<void> {
  await apiClient.post(`/tenant-onboarding/checklist/items/${itemKey}/complete`);
}

// --- Scenarios ---

export async function getScenarios(): Promise<OnboardingScenario[]> {
  const { data } = await apiClient.get("/tenant-onboarding/scenarios");
  return data;
}

export async function getScenario(scenarioKey: string): Promise<OnboardingScenario> {
  const { data } = await apiClient.get(`/tenant-onboarding/scenarios/${scenarioKey}`);
  return data;
}

export async function startScenario(scenarioKey: string): Promise<OnboardingScenario> {
  const { data } = await apiClient.post(`/tenant-onboarding/scenarios/${scenarioKey}/start`);
  return data;
}

// ⚠️ WRONG PREFIX ON PURPOSE, UNTIL THE ROUTE BEHIND IT WORKS.
// Posts to `/onboarding/...`; the route is at `/tenant-onboarding/...`, so this
// 404s. Correcting the prefix would reach a route that raises 500
// unconditionally — a worse diagnostic, since "no such route" is informative and
// an AttributeError/TypeError traceback is not. Fix the prefix when the route is
// repaired, not before.
// Measured 2026-10-05 — docs/investigations/2026-10-03-e8e86328-route-sweep.md
// would hit: POST .../scenarios/{key}/advance -> 500 TypeError, and
//            `step_key` (a string) would bind to `step_number: int`
export async function advanceScenario(
  scenarioKey: string,
  stepNumber: number,
  triggerKey?: string
): Promise<OnboardingScenario> {
  const { data } = await apiClient.post(`/onboarding/scenarios/${scenarioKey}/advance`, {
    step_number: stepNumber,
    trigger_key: triggerKey,
  });
  return data;
}

// --- Product Library ---

export async function getProductLibrary(params?: {
  form?: string;
}): Promise<ProductTemplate[]> {
  const { data } = await apiClient.get("/tenant-onboarding/product-library", { params });
  return data;
}

export async function importProductTemplates(
  templateIds: string[],
  products: ProductImportItem[]
): Promise<{ imported_count: number }> {
  const { data } = await apiClient.post("/tenant-onboarding/product-library/import", {
    template_ids: templateIds,
    products,
  });
  return data;
}

// --- Data Imports ---

export async function createDataImport(
  importType: string,
  sourceFormat: string
): Promise<DataImport> {
  const { data } = await apiClient.post("/tenant-onboarding/imports", {
    import_type: importType,
    source_format: sourceFormat,
  });
  return data;
}

export async function listDataImports(): Promise<DataImport[]> {
  const { data } = await apiClient.get("/tenant-onboarding/imports");
  return data;
}

// ⚠️ WRONG PREFIX ON PURPOSE, UNTIL THE ROUTE BEHIND IT WORKS.
// This posts to `/onboarding/...`; the route lives at `/tenant-onboarding/...`,
// so it 404s. Correcting the prefix would make it reach a route that raises 500
// unconditionally (see the verdict on the line below), which is a WORSE
// diagnostic: "no such route" tells you something, an AttributeError traceback
// does not. Fix the prefix when the route is repaired, not before.
// Measured 2026-10-05 — docs/investigations/2026-10-03-e8e86328-route-sweep.md
// would hit: GET /tenant-onboarding/imports/{id} -> 500, no get_import
export async function getDataImport(importId: string): Promise<DataImport> {
  const { data } = await apiClient.get(`/onboarding/imports/${importId}`);
  return data;
}

// ⚠️ WRONG PREFIX ON PURPOSE, UNTIL THE ROUTE BEHIND IT WORKS.
// This posts to `/onboarding/...`; the route lives at `/tenant-onboarding/...`,
// so it 404s. Correcting the prefix would make it reach a route that raises 500
// unconditionally (see the verdict on the line below), which is a WORSE
// diagnostic: "no such route" tells you something, an AttributeError traceback
// does not. Fix the prefix when the route is repaired, not before.
// Measured 2026-10-05 — docs/investigations/2026-10-03-e8e86328-route-sweep.md
// would hit: PATCH /tenant-onboarding/imports/{id} -> 500, no update_import
export async function updateDataImport(
  importId: string,
  update: { status?: string; field_mapping?: Record<string, string>; file_url?: string }
): Promise<DataImport> {
  const { data } = await apiClient.patch(`/onboarding/imports/${importId}`, update);
  return data;
}

// ⚠️ WRONG PREFIX ON PURPOSE, UNTIL THE ROUTE BEHIND IT WORKS.
// This posts to `/onboarding/...`; the route lives at `/tenant-onboarding/...`,
// so it 404s. Correcting the prefix would make it reach a route that raises 500
// unconditionally (see the verdict on the line below), which is a WORSE
// diagnostic: "no such route" tells you something, an AttributeError traceback
// does not. Fix the prefix when the route is repaired, not before.
// Measured 2026-10-05 — docs/investigations/2026-10-03-e8e86328-route-sweep.md
// would hit: POST .../imports/{id}/preview -> 500, no preview_import
export async function previewImport(importId: string): Promise<ImportPreview> {
  const { data } = await apiClient.post(`/onboarding/imports/${importId}/preview`);
  return data;
}

// ⚠️ WRONG PREFIX ON PURPOSE, UNTIL THE ROUTE BEHIND IT WORKS.
// This posts to `/onboarding/...`; the route lives at `/tenant-onboarding/...`,
// so it 404s. Correcting the prefix would make it reach a route that raises 500
// unconditionally (see the verdict on the line below), which is a WORSE
// diagnostic: "no such route" tells you something, an AttributeError traceback
// does not. Fix the prefix when the route is repaired, not before.
// Measured 2026-10-05 — docs/investigations/2026-10-03-e8e86328-route-sweep.md
// would hit: POST .../imports/{id}/execute -> 500, no execute_import
export async function executeImport(importId: string): Promise<DataImport> {
  const { data } = await apiClient.post(`/onboarding/imports/${importId}/execute`);
  return data;
}

export async function requestWhiteGlove(request: {
  import_type: string;
  description: string;
  contact_email: string;
}): Promise<DataImport> {
  const { data } = await apiClient.post("/tenant-onboarding/imports/white-glove", request);
  return data;
}

// --- Integration Setup ---

export async function listIntegrations(): Promise<IntegrationSetup[]> {
  const { data } = await apiClient.get("/tenant-onboarding/integrations");
  return data;
}

export async function createIntegration(
  integrationType: string
): Promise<IntegrationSetup> {
  const { data } = await apiClient.post("/tenant-onboarding/integrations", {
    integration_type: integrationType,
  });
  return data;
}

// ⚠️ WRONG PREFIX ON PURPOSE, UNTIL THE ROUTE BEHIND IT WORKS.
// Posts to `/onboarding/...`; the route is at `/tenant-onboarding/...`, so this
// 404s. Correcting the prefix would reach a route that raises 500
// unconditionally — a worse diagnostic, since "no such route" is informative and
// an AttributeError/TypeError traceback is not. Fix the prefix when the route is
// repaired, not before.
// Measured 2026-10-05 — docs/investigations/2026-10-03-e8e86328-route-sweep.md
// would hit: PATCH .../integrations/{id} -> 500 TypeError, and the
//            handler's tenant_id/integration_id are TRANSPOSED
export async function updateIntegration(
  integrationId: string,
  update: { status?: string; briefing_acknowledged?: boolean; sandbox_approved?: boolean }
): Promise<IntegrationSetup> {
  const { data } = await apiClient.patch(
    `/onboarding/integrations/${integrationId}`,
    update
  );
  return data;
}

// --- Help ---

export async function dismissHelp(helpKey: string): Promise<void> {
  await apiClient.post("/tenant-onboarding/help/dismiss", { help_key: helpKey });
}

export async function getDismissedHelp(): Promise<string[]> {
  const { data } = await apiClient.get("/tenant-onboarding/help/dismissed");
  return data;
}

// --- Check-in Call ---

export async function scheduleCheckInCall(scheduled: boolean): Promise<void> {
  await apiClient.post("/tenant-onboarding/check-in-call", { scheduled });
}

// --- Admin Analytics ---

export async function getOnboardingAnalytics(): Promise<OnboardingAnalytics> {
  const { data } = await apiClient.get("/admin/tenant-onboarding/analytics");
  return data;
}

export async function listWhiteGloveImports(status?: string): Promise<DataImport[]> {
  const { data } = await apiClient.get("/admin/tenant-onboarding/imports", {
    params: status ? { status } : undefined,
  });
  return data;
}
