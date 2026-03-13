export interface InventoryItem {
  id: string;
  company_id: string;
  product_id: string;
  product_name: string | null;
  product_sku: string | null;
  category_name: string | null;
  quantity_on_hand: number;
  reorder_point: number | null;
  reorder_quantity: number | null;
  location: string | null;
  last_counted_at: string | null;
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaginatedInventoryItems {
  items: InventoryItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface ReceiveStockRequest {
  quantity: number;
  reference?: string;
  notes?: string;
}

export interface AdjustStockRequest {
  new_quantity: number;
  reference?: string;
  notes?: string;
}

export interface InventorySettingsUpdate {
  reorder_point?: number | null;
  reorder_quantity?: number | null;
  location?: string | null;
}

export interface ProductionEntryRequest {
  quantity: number;
  reference?: string;
  notes?: string;
}

export interface WriteOffRequest {
  quantity: number;
  reason: string;
  reference?: string;
  notes?: string;
}

export interface BatchProductionEntry {
  product_id: string;
  quantity: number;
  reference?: string;
  notes?: string;
}

export interface BatchProductionRequest {
  entries: BatchProductionEntry[];
  batch_reference?: string;
}

export interface BatchProductionResult {
  success_count: number;
  failure_count: number;
  results: Array<{
    product_id: string;
    success: boolean;
    error?: string;
  }>;
}

export interface InventoryTransaction {
  id: string;
  product_id: string;
  product_name: string | null;
  transaction_type: string;
  quantity_change: number;
  quantity_after: number;
  reference: string | null;
  notes: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface PaginatedTransactions {
  items: InventoryTransaction[];
  total: number;
  page: number;
  per_page: number;
}
