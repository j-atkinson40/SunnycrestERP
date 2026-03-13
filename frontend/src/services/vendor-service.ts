import apiClient from "@/lib/api-client";
import type {
  Vendor,
  VendorContact,
  VendorContactCreate,
  VendorContactUpdate,
  VendorCreate,
  VendorImportResult,
  VendorNote,
  VendorNoteCreate,
  VendorStats,
  VendorUpdate,
  PaginatedVendors,
} from "@/types/vendor";

export const vendorService = {
  // -----------------------------------------------------------------------
  // Vendors
  // -----------------------------------------------------------------------

  async getVendors(
    page = 1,
    perPage = 20,
    search?: string,
    vendorStatus?: string,
    includeInactive = false,
  ): Promise<PaginatedVendors> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (vendorStatus) params.set("vendor_status", vendorStatus);
    if (includeInactive) params.set("include_inactive", "true");
    const response = await apiClient.get<PaginatedVendors>(
      `/vendors?${params.toString()}`,
    );
    return response.data;
  },

  async getVendor(id: string): Promise<Vendor> {
    const response = await apiClient.get<Vendor>(`/vendors/${id}`);
    return response.data;
  },

  async createVendor(data: VendorCreate): Promise<Vendor> {
    const response = await apiClient.post<Vendor>("/vendors", data);
    return response.data;
  },

  async updateVendor(id: string, data: VendorUpdate): Promise<Vendor> {
    const response = await apiClient.patch<Vendor>(`/vendors/${id}`, data);
    return response.data;
  },

  async deleteVendor(id: string): Promise<void> {
    await apiClient.delete(`/vendors/${id}`);
  },

  async getStats(): Promise<VendorStats> {
    const response = await apiClient.get<VendorStats>("/vendors/stats");
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Contacts
  // -----------------------------------------------------------------------

  async getContacts(vendorId: string): Promise<VendorContact[]> {
    const response = await apiClient.get<VendorContact[]>(
      `/vendors/${vendorId}/contacts`,
    );
    return response.data;
  },

  async createContact(
    vendorId: string,
    data: VendorContactCreate,
  ): Promise<VendorContact> {
    const response = await apiClient.post<VendorContact>(
      `/vendors/${vendorId}/contacts`,
      data,
    );
    return response.data;
  },

  async updateContact(
    vendorId: string,
    contactId: string,
    data: VendorContactUpdate,
  ): Promise<VendorContact> {
    const response = await apiClient.patch<VendorContact>(
      `/vendors/${vendorId}/contacts/${contactId}`,
      data,
    );
    return response.data;
  },

  async deleteContact(vendorId: string, contactId: string): Promise<void> {
    await apiClient.delete(`/vendors/${vendorId}/contacts/${contactId}`);
  },

  // -----------------------------------------------------------------------
  // Notes
  // -----------------------------------------------------------------------

  async getNotes(
    vendorId: string,
    page = 1,
    perPage = 20,
  ): Promise<{ items: VendorNote[]; total: number }> {
    const response = await apiClient.get(
      `/vendors/${vendorId}/notes?page=${page}&per_page=${perPage}`,
    );
    return response.data;
  },

  async createNote(
    vendorId: string,
    data: VendorNoteCreate,
  ): Promise<VendorNote> {
    const response = await apiClient.post<VendorNote>(
      `/vendors/${vendorId}/notes`,
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // CSV Import
  // -----------------------------------------------------------------------

  async importVendors(file: File): Promise<VendorImportResult> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<VendorImportResult>(
      "/vendors/import",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  },
};
