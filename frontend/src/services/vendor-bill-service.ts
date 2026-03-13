import apiClient from "@/lib/api-client";
import type {
  PaginatedVendorBills,
  VendorBill,
  VendorBillCreate,
  VendorBillListItem,
  VendorBillUpdate,
} from "@/types/vendor-bill";

export const vendorBillService = {
  async getAll(
    page = 1,
    perPage = 20,
    search?: string,
    status?: string,
    vendorId?: string,
    dueFrom?: string,
    dueTo?: string,
  ): Promise<PaginatedVendorBills> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (vendorId) params.set("vendor_id", vendorId);
    if (dueFrom) params.set("due_from", dueFrom);
    if (dueTo) params.set("due_to", dueTo);
    return (
      await apiClient.get<PaginatedVendorBills>(
        `/vendor-bills?${params.toString()}`,
      )
    ).data;
  },

  async get(id: string): Promise<VendorBill> {
    return (await apiClient.get<VendorBill>(`/vendor-bills/${id}`)).data;
  },

  async create(data: VendorBillCreate): Promise<VendorBill> {
    return (await apiClient.post<VendorBill>("/vendor-bills", data)).data;
  },

  async update(id: string, data: VendorBillUpdate): Promise<VendorBill> {
    return (await apiClient.put<VendorBill>(`/vendor-bills/${id}`, data)).data;
  },

  async approve(id: string): Promise<VendorBill> {
    return (
      await apiClient.post<VendorBill>(`/vendor-bills/${id}/approve`)
    ).data;
  },

  async void(id: string): Promise<VendorBill> {
    return (await apiClient.post<VendorBill>(`/vendor-bills/${id}/void`)).data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/vendor-bills/${id}`);
  },

  async getDue(days = 30): Promise<VendorBillListItem[]> {
    return (
      await apiClient.get<VendorBillListItem[]>(
        `/vendor-bills/due?days=${days}`,
      )
    ).data;
  },

  async getOverdue(): Promise<VendorBillListItem[]> {
    return (
      await apiClient.get<VendorBillListItem[]>("/vendor-bills/overdue")
    ).data;
  },
};
