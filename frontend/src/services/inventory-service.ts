import apiClient from "@/lib/api-client";
import type {
  AdjustStockRequest,
  InventoryItem,
  InventorySettingsUpdate,
  PaginatedInventoryItems,
  PaginatedTransactions,
  ReceiveStockRequest,
} from "@/types/inventory";

export const inventoryService = {
  // -----------------------------------------------------------------------
  // Inventory items
  // -----------------------------------------------------------------------

  async getInventoryItems(
    page = 1,
    perPage = 20,
    search?: string,
    lowStockOnly = false,
  ): Promise<PaginatedInventoryItems> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (lowStockOnly) params.set("low_stock_only", "true");
    const response = await apiClient.get<PaginatedInventoryItems>(
      `/inventory?${params.toString()}`,
    );
    return response.data;
  },

  async getInventoryItem(productId: string): Promise<InventoryItem> {
    const response = await apiClient.get<InventoryItem>(
      `/inventory/${productId}`,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Stock operations
  // -----------------------------------------------------------------------

  async receiveStock(
    productId: string,
    data: ReceiveStockRequest,
  ): Promise<InventoryItem> {
    const response = await apiClient.post<InventoryItem>(
      `/inventory/${productId}/receive`,
      data,
    );
    return response.data;
  },

  async adjustStock(
    productId: string,
    data: AdjustStockRequest,
  ): Promise<InventoryItem> {
    const response = await apiClient.post<InventoryItem>(
      `/inventory/${productId}/adjust`,
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Settings
  // -----------------------------------------------------------------------

  async updateSettings(
    productId: string,
    data: InventorySettingsUpdate,
  ): Promise<InventoryItem> {
    const response = await apiClient.patch<InventoryItem>(
      `/inventory/${productId}/settings`,
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Transactions
  // -----------------------------------------------------------------------

  async getTransactions(
    productId: string,
    page = 1,
    perPage = 20,
  ): Promise<PaginatedTransactions> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    const response = await apiClient.get<PaginatedTransactions>(
      `/inventory/${productId}/transactions?${params.toString()}`,
    );
    return response.data;
  },

  async getAllTransactions(
    page = 1,
    perPage = 20,
  ): Promise<PaginatedTransactions> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    const response = await apiClient.get<PaginatedTransactions>(
      `/inventory/transactions?${params.toString()}`,
    );
    return response.data;
  },
};
