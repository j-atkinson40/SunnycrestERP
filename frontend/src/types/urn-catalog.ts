export interface UrnProduct {
  id: string;
  name: string;
  wilbert_sku: string | null;
  wholesale_cost: number | null;
  price: number | null;
  markup_percent: number | null;
  category: string | null;
  source: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface UrnCatalogStats {
  active_count: number;
  inactive_count: number;
  imported_count: number;
  last_import_at: string | null;
}

export interface UrnImportItem {
  wilbert_sku: string;
  name: string;
  wholesale_cost: number;
  selling_price: number | null;
  category: string | null;
  size: string | null;
  selected: boolean; // frontend-only for selection UI
}

export interface ColumnMapping {
  sku: string | null;
  name: string | null;
  cost: string | null;
  category: string | null;
  size: string | null;
}
