export interface CompanySummary {
  id: string;
  name: string;
  slug: string;
}

export interface NetworkRelationship {
  id: string;
  requesting_company_id: string;
  target_company_id: string;
  relationship_type: string;
  status: string;
  permissions: string | null;
  notes: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  requesting_company: CompanySummary | null;
  target_company: CompanySummary | null;
}

export interface NetworkRelationshipCreate {
  target_company_id: string;
  relationship_type: string;
  permissions?: string;
  notes?: string;
}

export interface NetworkRelationshipUpdate {
  relationship_type?: string;
  status?: string;
  permissions?: string;
  notes?: string;
}

export interface PaginatedRelationships {
  items: NetworkRelationship[];
  total: number;
  page: number;
  per_page: number;
}

export interface NetworkTransaction {
  id: string;
  relationship_id: string;
  source_company_id: string;
  target_company_id: string;
  transaction_type: string;
  source_record_type: string | null;
  source_record_id: string | null;
  target_record_type: string | null;
  target_record_id: string | null;
  payload: string | null;
  status: string;
  error_message: string | null;
  created_by: string | null;
  created_at: string;
}

export interface NetworkTransactionCreate {
  relationship_id: string;
  target_company_id: string;
  transaction_type: string;
  source_record_type?: string;
  source_record_id?: string;
  target_record_type?: string;
  target_record_id?: string;
  payload?: string;
}

export interface PaginatedTransactions {
  items: NetworkTransaction[];
  total: number;
  page: number;
  per_page: number;
}

export interface NetworkStats {
  total_relationships: number;
  active_relationships: number;
  pending_relationships: number;
  total_transactions: number;
  transactions_30d: number;
}
