export interface CompanyHierarchyNode {
  id: string;
  name: string;
  slug: string;
  hierarchy_level: string | null;
  hierarchy_path: string | null;
  parent_company_id: string | null;
  is_active: boolean;
  children: CompanyHierarchyNode[];
}

export interface HierarchyResponse {
  tree: CompanyHierarchyNode[];
  total_companies: number;
}

export interface CompanyChildItem {
  id: string;
  name: string;
  slug: string;
  hierarchy_level: string | null;
  is_active: boolean;
  children_count: number;
}

export interface SetParentRequest {
  parent_company_id: string | null;
  hierarchy_level: string | null;
}
