export interface ProductCategory {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  parent_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface PriceTier {
  id: string;
  product_id: string;
  min_quantity: number;
  price: number;
  label: string | null;
}

export interface PriceTierCreate {
  min_quantity: number;
  price: number;
  label?: string;
}

export interface Product {
  id: string;
  company_id: string;
  category_id: string | null;
  category_name: string | null;
  name: string;
  sku: string | null;
  description: string | null;
  price: number | null;
  cost_price: number | null;
  unit_of_measure: string | null;
  image_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  price_tiers: PriceTier[];
}

export interface ProductCreate {
  name: string;
  sku?: string;
  description?: string;
  category_id?: string;
  price?: number;
  cost_price?: number;
  unit_of_measure?: string;
  image_url?: string;
}

export interface ProductUpdate {
  name?: string;
  sku?: string;
  description?: string;
  category_id?: string | null;
  price?: number | null;
  cost_price?: number | null;
  unit_of_measure?: string;
  image_url?: string;
  is_active?: boolean;
}

export interface PaginatedProducts {
  items: Product[];
  total: number;
  page: number;
  per_page: number;
}

export interface CategoryCreate {
  name: string;
  description?: string;
  parent_id?: string;
}

export interface CategoryUpdate {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export interface ImportResult {
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
}
