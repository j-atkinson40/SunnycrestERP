import apiClient from "@/lib/api-client";
import type {
  PaginatedVendorPayments,
  VendorPayment,
  VendorPaymentCreate,
} from "@/types/vendor-payment";

export const vendorPaymentService = {
  async getAll(
    page = 1,
    perPage = 20,
    vendorId?: string,
  ): Promise<PaginatedVendorPayments> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (vendorId) params.set("vendor_id", vendorId);
    return (
      await apiClient.get<PaginatedVendorPayments>(
        `/vendor-payments?${params.toString()}`,
      )
    ).data;
  },

  async get(id: string): Promise<VendorPayment> {
    return (await apiClient.get<VendorPayment>(`/vendor-payments/${id}`)).data;
  },

  async create(data: VendorPaymentCreate): Promise<VendorPayment> {
    return (await apiClient.post<VendorPayment>("/vendor-payments", data)).data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/vendor-payments/${id}`);
  },
};
