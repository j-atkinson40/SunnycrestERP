export interface AuditLogEntry {
  id: string;
  company_id: string;
  user_id: string | null;
  user_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  changes: Record<string, { old: unknown; new: unknown }> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface PaginatedAuditLogs {
  items: AuditLogEntry[];
  total: number;
  page: number;
  per_page: number;
}

export interface AuditLogFilters {
  user_id?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  date_from?: string;
  date_to?: string;
}
