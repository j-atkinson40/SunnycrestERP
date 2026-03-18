import apiClient from "@/lib/api-client";
import type {
  FHCase,
  FHCaseContact,
  FHServiceItem,
  FHVaultOrder,
  FHObituary,
  FHInvoice,
  FHPayment,
  FHPriceListItem,
  FHPriceListVersion,
  FHCaseActivity,
  FHManufacturerRelationship,
  FHVaultProduct,
  FHDashboardData,
  FTCComplianceReport,
  FHPortalData,
  FHDirector,
  CremationStatus,
} from "@/types/funeral-home";

export const funeralHomeService = {
  // ── Cases ───────────────────────────────────────────────────

  async listCases(params?: Record<string, string>): Promise<{ items: FHCase[]; total: number }> {
    const { data } = await apiClient.get("/funeral-home/cases", { params });
    return data;
  },

  async getBoard(): Promise<Record<string, FHCase[]>> {
    const { data } = await apiClient.get("/funeral-home/cases/board");
    return data;
  },

  async createCase(payload: Record<string, unknown>): Promise<FHCase> {
    const { data } = await apiClient.post("/funeral-home/cases", payload);
    return data;
  },

  async getCase(id: string): Promise<FHCase> {
    const { data } = await apiClient.get(`/funeral-home/cases/${id}`);
    return data;
  },

  async getCaseSummary(id: string): Promise<FHCase> {
    const { data } = await apiClient.get(`/funeral-home/cases/${id}/summary`);
    return data;
  },

  async updateCase(id: string, payload: Record<string, unknown>): Promise<FHCase> {
    const { data } = await apiClient.put(`/funeral-home/cases/${id}`, payload);
    return data;
  },

  async updateCaseStatus(id: string, status: string): Promise<FHCase> {
    const { data } = await apiClient.patch(`/funeral-home/cases/${id}/status`, { status });
    return data;
  },

  async getCaseActivity(id: string, params?: Record<string, string>): Promise<{ items: FHCaseActivity[]; total: number }> {
    const { data } = await apiClient.get(`/funeral-home/cases/${id}/activity`, { params });
    return data;
  },

  async updateCremationStatus(caseId: string, payload: Partial<CremationStatus>): Promise<void> {
    await apiClient.patch(`/funeral-home/cases/${caseId}/cremation`, payload);
  },

  // ── Contacts ────────────────────────────────────────────────

  async listContacts(caseId: string): Promise<FHCaseContact[]> {
    const { data } = await apiClient.get(`/funeral-home/cases/${caseId}/contacts`);
    return data;
  },

  async addContact(caseId: string, payload: Record<string, unknown>): Promise<FHCaseContact> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/contacts`, payload);
    return data;
  },

  async updateContact(caseId: string, contactId: string, payload: Record<string, unknown>): Promise<FHCaseContact> {
    const { data } = await apiClient.put(`/funeral-home/cases/${caseId}/contacts/${contactId}`, payload);
    return data;
  },

  async sendPortalInvite(caseId: string, contactId: string): Promise<{ message: string }> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/contacts/${contactId}/portal-invite`);
    return data;
  },

  // ── Services ────────────────────────────────────────────────

  async listServices(caseId: string): Promise<FHServiceItem[]> {
    const { data } = await apiClient.get(`/funeral-home/cases/${caseId}/services`);
    return data;
  },

  async addService(caseId: string, payload: Record<string, unknown>): Promise<FHServiceItem> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/services`, payload);
    return data;
  },

  async bulkAddServices(caseId: string, items: Record<string, unknown>[]): Promise<FHServiceItem[]> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/services/bulk`, { items });
    return data;
  },

  async updateService(caseId: string, serviceId: string, payload: Record<string, unknown>): Promise<FHServiceItem> {
    const { data } = await apiClient.put(`/funeral-home/cases/${caseId}/services/${serviceId}`, payload);
    return data;
  },

  async removeService(caseId: string, serviceId: string): Promise<void> {
    await apiClient.delete(`/funeral-home/cases/${caseId}/services/${serviceId}`);
  },

  // ── Vault Orders ────────────────────────────────────────────

  async getVaultOrder(caseId: string): Promise<FHVaultOrder | null> {
    const { data } = await apiClient.get(`/funeral-home/cases/${caseId}/vault-order`);
    return data;
  },

  async submitVaultOrder(caseId: string, payload: Record<string, unknown>): Promise<FHVaultOrder> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/vault-order`, payload);
    return data;
  },

  async syncVaultStatus(caseId: string): Promise<FHVaultOrder> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/vault-order/sync`);
    return data;
  },

  async getManufacturerCatalog(manufacturerId: string): Promise<FHVaultProduct[]> {
    const { data } = await apiClient.get(`/funeral-home/manufacturers/${manufacturerId}/catalog`);
    return data;
  },

  async getManufacturers(): Promise<FHManufacturerRelationship[]> {
    const { data } = await apiClient.get("/funeral-home/manufacturers");
    return data;
  },

  async linkManufacturer(payload: Record<string, unknown>): Promise<FHManufacturerRelationship> {
    const { data } = await apiClient.post("/funeral-home/manufacturers", payload);
    return data;
  },

  // ── Obituary ────────────────────────────────────────────────

  async getObituary(caseId: string): Promise<FHObituary | null> {
    const { data } = await apiClient.get(`/funeral-home/cases/${caseId}/obituary`);
    return data;
  },

  async generateObituary(caseId: string, payload: Record<string, unknown>): Promise<FHObituary> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/obituary/generate`, payload);
    return data;
  },

  async saveObituary(caseId: string, payload: Record<string, unknown>): Promise<FHObituary> {
    const { data } = await apiClient.put(`/funeral-home/cases/${caseId}/obituary`, payload);
    return data;
  },

  async sendObituaryForApproval(caseId: string): Promise<FHObituary> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/obituary/send-for-approval`);
    return data;
  },

  async markObituaryPublished(caseId: string, locations: string[]): Promise<FHObituary> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/obituary/publish`, { locations });
    return data;
  },

  // ── Invoices ────────────────────────────────────────────────

  async getInvoice(caseId: string): Promise<FHInvoice | null> {
    const { data } = await apiClient.get(`/funeral-home/cases/${caseId}/invoice`);
    return data;
  },

  async generateInvoice(caseId: string): Promise<FHInvoice> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/invoice/generate`);
    return data;
  },

  async sendInvoice(caseId: string, email: string): Promise<{ message: string }> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/invoice/send`, { email });
    return data;
  },

  async recordPayment(caseId: string, payload: Record<string, unknown>): Promise<FHPayment> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/invoice/payments`, payload);
    return data;
  },

  async voidInvoice(caseId: string): Promise<void> {
    await apiClient.post(`/funeral-home/cases/${caseId}/invoice/void`);
  },

  async getPayments(caseId: string): Promise<FHPayment[]> {
    const { data } = await apiClient.get(`/funeral-home/cases/${caseId}/invoice/payments`);
    return data;
  },

  // ── Documents ───────────────────────────────────────────────

  async uploadDocument(caseId: string, payload: Record<string, unknown>): Promise<{ message: string }> {
    const { data } = await apiClient.post(`/funeral-home/cases/${caseId}/documents`, payload);
    return data;
  },

  async listDocuments(caseId: string): Promise<{ id: string; document_type: string; document_name: string; file_url: string; created_at: string }[]> {
    const { data } = await apiClient.get(`/funeral-home/cases/${caseId}/documents`);
    return data;
  },

  // ── Price List / GPL ────────────────────────────────────────

  async listPriceList(): Promise<FHPriceListItem[]> {
    const { data } = await apiClient.get("/funeral-home/price-list");
    return data;
  },

  async createPriceListItem(payload: Record<string, unknown>): Promise<FHPriceListItem> {
    const { data } = await apiClient.post("/funeral-home/price-list", payload);
    return data;
  },

  async updatePriceListItem(id: string, payload: Record<string, unknown>): Promise<FHPriceListItem> {
    const { data } = await apiClient.put(`/funeral-home/price-list/${id}`, payload);
    return data;
  },

  async getGPLVersions(): Promise<FHPriceListVersion[]> {
    const { data } = await apiClient.get("/funeral-home/price-list/versions");
    return data;
  },

  async createGPLVersion(payload: Record<string, unknown>): Promise<FHPriceListVersion> {
    const { data } = await apiClient.post("/funeral-home/price-list/versions", payload);
    return data;
  },

  async seedFTCItems(): Promise<{ message: string }> {
    const { data } = await apiClient.post("/funeral-home/price-list/seed-ftc");
    return data;
  },

  // ── FTC Compliance ──────────────────────────────────────────

  async getCompliance(): Promise<FTCComplianceReport> {
    const { data } = await apiClient.get("/funeral-home/compliance");
    return data;
  },

  // ── Dashboard ───────────────────────────────────────────────

  async getDashboard(): Promise<FHDashboardData> {
    const { data } = await apiClient.get("/funeral-home/dashboard");
    return data;
  },

  // ── Directors ───────────────────────────────────────────────

  async getDirectors(): Promise<FHDirector[]> {
    const { data } = await apiClient.get("/funeral-home/directors");
    return data;
  },

  // ── Portal ──────────────────────────────────────────────────

  async getPortalData(token: string): Promise<FHPortalData> {
    const { data } = await apiClient.get(`/funeral-home/portal/${token}`);
    return data;
  },

  async approveObituary(token: string, notes?: string): Promise<{ message: string }> {
    const { data } = await apiClient.post(`/funeral-home/portal/${token}/obituary/approve`, { notes });
    return data;
  },

  async requestObituaryChanges(token: string, notes: string): Promise<{ message: string }> {
    const { data } = await apiClient.post(`/funeral-home/portal/${token}/obituary/request-changes`, { notes });
    return data;
  },

  async sendDirectorMessage(token: string, message: string): Promise<{ message: string }> {
    const { data } = await apiClient.post(`/funeral-home/portal/${token}/message`, { message });
    return data;
  },
};
