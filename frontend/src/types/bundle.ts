export interface BundleComponent {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string | null;
  product_price: number;
  quantity: number;
  sort_order: number;
}

export interface ProductBundle {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  sku: string | null;
  price: number | null;
  is_active: boolean;
  sort_order: number;
  source: string;
  components: BundleComponent[];
  component_count: number;
  à_la_carte_total: number;
  savings: number | null;
  // Conditional pricing
  has_conditional_pricing: boolean;
  standalone_price: number | null;
  with_vault_price: number | null;
  vault_qualifier_categories: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface BundleComponentInput {
  product_id: string;
  quantity?: number;
}

export interface BundleCreate {
  name: string;
  description?: string;
  sku?: string;
  price?: number;
  is_active?: boolean;
  sort_order?: number;
  components: BundleComponentInput[];
  has_conditional_pricing?: boolean;
  standalone_price?: number;
  with_vault_price?: number;
  vault_qualifier_categories?: string[];
}

export interface BundleUpdate {
  name?: string;
  description?: string;
  sku?: string;
  price?: number;
  is_active?: boolean;
  sort_order?: number;
  components?: BundleComponentInput[];
  has_conditional_pricing?: boolean;
  standalone_price?: number;
  with_vault_price?: number;
  vault_qualifier_categories?: string[];
}
