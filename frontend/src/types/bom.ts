export interface BOMLine {
  id: string;
  bom_id: string;
  component_product_id: string;
  component_product_name: string;
  component_sku: string | null;
  quantity: number;
  unit_of_measure: string | null;
  waste_percent: number;
  effective_quantity: number;
  unit_cost: number | null;
  line_cost: number | null;
  notes: string | null;
  sort_order: number;
}

export interface BOMLineCreate {
  component_product_id: string;
  quantity: number;
  unit_of_measure?: string;
  waste_percent?: number;
  notes?: string;
  sort_order?: number;
}

export interface BOMLineUpdate {
  component_product_id?: string;
  quantity?: number;
  unit_of_measure?: string;
  waste_percent?: number;
  notes?: string;
  sort_order?: number;
}

export type BOMStatus = "draft" | "active" | "archived";

export interface BOM {
  id: string;
  company_id: string;
  product_id: string;
  product_name: string;
  product_sku: string | null;
  version: number;
  status: BOMStatus;
  notes: string | null;
  cost_total: number | null;
  lines: BOMLine[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface BOMListItem {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string | null;
  version: number;
  status: BOMStatus;
  line_count: number;
  cost_total: number | null;
  created_at: string;
}

export interface BOMCreate {
  product_id: string;
  notes?: string;
  lines?: BOMLineCreate[];
}

export interface BOMUpdate {
  notes?: string;
}

export interface PaginatedBOMs {
  items: BOMListItem[];
  total: number;
  page: number;
  per_page: number;
}
