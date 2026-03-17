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
  const { data } = await apiClient.get("/onboarding/checklist");
  return data;
}

export async function initializeChecklist(): Promise<OnboardingChecklist> {
  const { data } = await apiClient.post("/onboarding/checklist/initialize");
  return data;
}

export async function updateChecklistItem(
  itemKey: string,
  update: { status?: string; skipped?: boolean }
): Promise<void> {
  await apiClient.patch(`/onboarding/checklist/items/${itemKey}`, update);
}

export async function completeChecklistItem(itemKey: string): Promise<void> {
  await apiClient.post(`/onboarding/checklist/items/${itemKey}/complete`);
}

// --- Scenarios ---

export async function getScenarios(): Promise<OnboardingScenario[]> {
  const { data } = await apiClient.get("/onboarding/scenarios");
  return data;
}

export async function getScenario(scenarioKey: string): Promise<OnboardingScenario> {
  const { data } = await apiClient.get(`/onboarding/scenarios/${scenarioKey}`);
  return data;
}

export async function startScenario(scenarioKey: string): Promise<OnboardingScenario> {
  const { data } = await apiClient.post(`/onboarding/scenarios/${scenarioKey}/start`);
  return data;
}

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
  preset?: string;
  category?: string;
}): Promise<ProductTemplate[]> {
  const { data } = await apiClient.get("/onboarding/product-library", { params });
  return data;
}

export async function importProductTemplates(
  templateIds: string[],
  products: ProductImportItem[]
): Promise<{ imported_count: number }> {
  const { data } = await apiClient.post("/onboarding/product-library/import", {
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
  const { data } = await apiClient.post("/onboarding/imports", {
    import_type: importType,
    source_format: sourceFormat,
  });
  return data;
}

export async function listDataImports(): Promise<DataImport[]> {
  const { data } = await apiClient.get("/onboarding/imports");
  return data;
}

export async function getDataImport(importId: string): Promise<DataImport> {
  const { data } = await apiClient.get(`/onboarding/imports/${importId}`);
  return data;
}

export async function updateDataImport(
  importId: string,
  update: { status?: string; field_mapping?: Record<string, string>; file_url?: string }
): Promise<DataImport> {
  const { data } = await apiClient.patch(`/onboarding/imports/${importId}`, update);
  return data;
}

export async function previewImport(importId: string): Promise<ImportPreview> {
  const { data } = await apiClient.post(`/onboarding/imports/${importId}/preview`);
  return data;
}

export async function executeImport(importId: string): Promise<DataImport> {
  const { data } = await apiClient.post(`/onboarding/imports/${importId}/execute`);
  return data;
}

export async function requestWhiteGlove(request: {
  import_type: string;
  description: string;
  contact_email: string;
}): Promise<DataImport> {
  const { data } = await apiClient.post("/onboarding/imports/white-glove", request);
  return data;
}

// --- Integration Setup ---

export async function listIntegrations(): Promise<IntegrationSetup[]> {
  const { data } = await apiClient.get("/onboarding/integrations");
  return data;
}

export async function createIntegration(
  integrationType: string
): Promise<IntegrationSetup> {
  const { data } = await apiClient.post("/onboarding/integrations", {
    integration_type: integrationType,
  });
  return data;
}

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
  await apiClient.post("/onboarding/help/dismiss", { help_key: helpKey });
}

export async function getDismissedHelp(): Promise<string[]> {
  const { data } = await apiClient.get("/onboarding/help/dismissed");
  return data;
}

// --- Check-in Call ---

export async function scheduleCheckInCall(scheduled: boolean): Promise<void> {
  await apiClient.post("/onboarding/check-in-call", { scheduled });
}

// --- Admin Analytics ---

export async function getOnboardingAnalytics(): Promise<OnboardingAnalytics> {
  const { data } = await apiClient.get("/admin/onboarding/analytics");
  return data;
}

export async function listWhiteGloveImports(status?: string): Promise<DataImport[]> {
  const { data } = await apiClient.get("/admin/onboarding/imports", {
    params: status ? { status } : undefined,
  });
  return data;
}
