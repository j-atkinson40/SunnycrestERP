export interface SageExportConfig {
  id: string;
  company_id: string;
  warehouse_code: string;
  export_directory: string | null;
  column_mapping: string | null;
  is_active: boolean;
  last_export_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SageExportConfigUpdate {
  warehouse_code?: string;
  export_directory?: string;
}

export interface SageExportRequest {
  date_from: string;
  date_to: string;
}

export interface SageExportResponse {
  csv_data: string;
  record_count: number;
  sync_log_id: string;
}

export interface SyncLogEntry {
  id: string;
  company_id: string;
  sync_type: string;
  source: string;
  destination: string;
  status: string;
  records_processed: number;
  records_failed: number;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface PaginatedSyncLogs {
  items: SyncLogEntry[];
  total: number;
  page: number;
  per_page: number;
}
