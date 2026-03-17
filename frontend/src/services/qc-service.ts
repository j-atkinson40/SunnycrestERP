import apiClient from "@/lib/api-client";
import type {
  QCTemplate,
  QCStep,
  QCInspection,
  QCDefectType,
  PaginatedInspections,
  QCDashboardStats,
  QCSummaryReport,
  InspectionCreate,
  StepResultUpdate,
  DispositionCreate,
  ReworkCreate,
  QCMedia,
} from "@/types/qc";

export const qcService = {
  // -----------------------------------------------------------------------
  // Templates
  // -----------------------------------------------------------------------

  async listTemplates(productCategory?: string): Promise<QCTemplate[]> {
    const params = new URLSearchParams();
    if (productCategory) params.set("product_category", productCategory);
    const response = await apiClient.get<QCTemplate[]>(
      `/qc/templates?${params.toString()}`,
    );
    return response.data;
  },

  async getTemplateSteps(templateId: string): Promise<QCStep[]> {
    const response = await apiClient.get<QCStep[]>(
      `/qc/templates/${templateId}/steps`,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Inspections
  // -----------------------------------------------------------------------

  async createInspection(data: InspectionCreate): Promise<QCInspection> {
    const response = await apiClient.post<QCInspection>(
      "/qc/inspections",
      data,
    );
    return response.data;
  },

  async getInspection(id: string): Promise<QCInspection> {
    const response = await apiClient.get<QCInspection>(
      `/qc/inspections/${id}`,
    );
    return response.data;
  },

  async listInspections(
    page = 1,
    perPage = 20,
    status?: string,
    productCategory?: string,
    search?: string,
  ): Promise<PaginatedInspections> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (status) params.set("status", status);
    if (productCategory) params.set("product_category", productCategory);
    if (search) params.set("search", search);
    const response = await apiClient.get<PaginatedInspections>(
      `/qc/inspections?${params.toString()}`,
    );
    return response.data;
  },

  async updateStepResult(
    inspectionId: string,
    stepId: string,
    data: StepResultUpdate,
  ): Promise<QCInspection> {
    const response = await apiClient.patch<QCInspection>(
      `/qc/inspections/${inspectionId}/steps/${stepId}`,
      data,
    );
    return response.data;
  },

  async completeInspection(
    inspectionId: string,
    notes?: string,
  ): Promise<QCInspection> {
    const response = await apiClient.post<QCInspection>(
      `/qc/inspections/${inspectionId}/complete`,
      { overall_notes: notes },
    );
    return response.data;
  },

  async createDisposition(
    inspectionId: string,
    data: DispositionCreate,
  ): Promise<QCInspection> {
    const response = await apiClient.post<QCInspection>(
      `/qc/inspections/${inspectionId}/dispositions`,
      data,
    );
    return response.data;
  },

  async createRework(
    inspectionId: string,
    data: ReworkCreate,
  ): Promise<QCInspection> {
    const response = await apiClient.post<QCInspection>(
      `/qc/inspections/${inspectionId}/rework`,
      data,
    );
    return response.data;
  },

  async completeRework(
    inspectionId: string,
    reworkId: string,
    resultNotes?: string,
  ): Promise<QCInspection> {
    const response = await apiClient.post<QCInspection>(
      `/qc/inspections/${inspectionId}/rework/${reworkId}/complete`,
      { result_notes: resultNotes },
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Defect Types
  // -----------------------------------------------------------------------

  async listDefectTypes(productCategory?: string): Promise<QCDefectType[]> {
    const params = new URLSearchParams();
    if (productCategory) params.set("product_category", productCategory);
    const response = await apiClient.get<QCDefectType[]>(
      `/qc/defect-types?${params.toString()}`,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Reports / Stats
  // -----------------------------------------------------------------------

  async getDashboardStats(): Promise<QCDashboardStats> {
    const response = await apiClient.get<QCDashboardStats>(
      "/qc/stats/dashboard",
    );
    return response.data;
  },

  async getSummaryReport(
    dateFrom?: string,
    dateTo?: string,
  ): Promise<QCSummaryReport> {
    const params = new URLSearchParams();
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    const response = await apiClient.get<QCSummaryReport>(
      `/qc/reports/summary?${params.toString()}`,
    );
    return response.data;
  },

  async getItemHistory(inventoryItemId: string): Promise<QCInspection[]> {
    const response = await apiClient.get<QCInspection[]>(
      `/qc/items/${inventoryItemId}/history`,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Media
  // -----------------------------------------------------------------------

  async uploadMedia(
    inspectionId: string,
    stepResultId: string,
    file: File,
  ): Promise<QCMedia> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<QCMedia>(
      `/qc/inspections/${inspectionId}/steps/${stepResultId}/media`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  },

  async exportPdf(inspectionId: string): Promise<Blob> {
    const response = await apiClient.get(
      `/qc/inspections/${inspectionId}/export-pdf`,
      { responseType: "blob" },
    );
    return response.data;
  },
};
