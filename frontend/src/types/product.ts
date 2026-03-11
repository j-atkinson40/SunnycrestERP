export interface ProductCategory {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
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
}

export interface CategoryUpdate {
  name?: string;
  description?: string;
  is_active?: boolean;
}
