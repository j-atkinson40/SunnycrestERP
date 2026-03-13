import apiClient from "@/lib/api-client";
import type {
  PaginatedPurchaseOrders,
  POStats,
  PurchaseOrder,
  PurchaseOrderCreate,
  PurchaseOrderUpdate,
  ReceiveLineItem,
} from "@/types/purchase-order";

export const purchaseOrderService = {
  async getAll(
    page = 1,
    perPage = 20,
    search?: string,
    status?: string,
    vendorId?: string,
    dateFrom?: string,
    dateTo?: string,
  ): Promise<PaginatedPurchaseOrders> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (vendorId) params.set("vendor_id", vendorId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return (
      await apiClient.get<PaginatedPurchaseOrders>(
        `/purchase-orders?${params.toString()}`,
      )
    ).data;
  },

  async get(id: string): Promise<PurchaseOrder> {
    return (await apiClient.get<PurchaseOrder>(`/purchase-orders/${id}`)).data;
  },

  async create(data: PurchaseOrderCreate): Promise<PurchaseOrder> {
    return (await apiClient.post<PurchaseOrder>("/purchase-orders", data)).data;
  },

  async update(
    id: string,
    data: PurchaseOrderUpdate,
  ): Promise<PurchaseOrder> {
    return (await apiClient.put<PurchaseOrder>(`/purchase-orders/${id}`, data))
      .data;
  },

  async send(id: string): Promise<PurchaseOrder> {
    return (
      await apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/send`)
    ).data;
  },

  async receive(
    id: string,
    lines: ReceiveLineItem[],
  ): Promise<PurchaseOrder> {
    return (
      await apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/receive`, {
        lines,
      })
    ).data;
  },

  async cancel(id: string): Promise<PurchaseOrder> {
    return (
      await apiClient.post<PurchaseOrder>(`/purchase-orders/${id}/cancel`)
    ).data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/purchase-orders/${id}`);
  },

  async getStats(): Promise<POStats> {
    return (await apiClient.get<POStats>("/purchase-orders/stats")).data;
  },
};
