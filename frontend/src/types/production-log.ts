export interface ProductionLogEntry {
  id: string;
  tenant_id: string;
  log_date: string;
  product_id: string;
  product_name: string;
  quantity_produced: number;
  mix_design_id: string | null;
  mix_design_name: string | null;
  batch_count: number | null;
  notes: string | null;
  entered_by: string;
  entry_method: 'manual' | 'ai_command_bar' | 'mobile';
  created_at: string;
  updated_at: string;
}

export interface ProductionLogEntryCreate {
  log_date?: string;
  product_id: string;
  quantity_produced: number;
  mix_design_id?: string;
  batch_count?: number;
  notes?: string;
  entry_method?: string;
}

export interface ProductionLogEntryUpdate {
  quantity_produced?: number;
  mix_design_id?: string;
  batch_count?: number;
  notes?: string;
}

export interface DailyTotal {
  date: string;
  total_units: number;
  entry_count: number;
  entries: ProductionLogEntry[];
}

export interface ProductionLogSummary {
  id: string;
  summary_date: string;
  total_units_produced: number;
  products_produced: Array<{
    product_id: string;
    product_name: string;
    quantity: number;
  }> | null;
}
