import apiClient from "@/lib/api-client";
import type {
  AdjustStockRequest,
  BatchProductionRequest,
  BatchProductionResult,
  InventoryItem,
  InventorySettingsUpdate,
  PaginatedInventoryItems,
  PaginatedTransactions,
  ProductionEntryRequest,
  ReceiveStockRequest,
  WriteOffRequest,
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

  async recordProduction(
    productId: string,
    data: ProductionEntryRequest,
  ): Promise<InventoryItem> {
    const response = await apiClient.post<InventoryItem>(
      `/inventory/${productId}/production`,
      data,
    );
    return response.data;
  },

  async writeOffStock(
    productId: string,
    data: WriteOffRequest,
  ): Promise<InventoryItem> {
    const response = await apiClient.post<InventoryItem>(
      `/inventory/${productId}/write-off`,
      data,
    );
    return response.data;
  },

  async batchRecordProduction(
    data: BatchProductionRequest,
  ): Promise<BatchProductionResult> {
    const response = await apiClient.post<BatchProductionResult>(
      "/inventory/batch-production",
      data,
    );
    return response.data;
  },

  async getWriteOffs(
    page = 1,
    perPage = 20,
  ): Promise<PaginatedTransactions> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    const response = await apiClient.get<PaginatedTransactions>(
      `/inventory/write-offs?${params.toString()}`,
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
