export type ProductCategory = "burial_vault" | "columbarium" | "monument" | "redi_rock" | "precast_other";
export type InspectionStatus = "pending" | "in_progress" | "passed" | "failed" | "conditional_pass" | "rework_required";
export type StepResult = "pending" | "pass" | "fail" | "na";
export type DefectSeverity = "minor" | "major" | "critical";
export type DispositionType = "scrap" | "rework" | "conditional_pass" | "hold_pending_review";
export type InspectionType = "visual" | "pressure_test" | "dimensional" | "photo_required";

export interface QCTemplate {
  id: string;
  company_id: string;
  name: string;
  product_category: ProductCategory;
  description: string | null;
  is_active: boolean;
  steps: QCStep[];
  created_at: string;
  updated_at: string;
}

export interface QCStep {
  id: string;
  template_id: string;
  step_number: number;
  name: string;
  description: string | null;
  inspection_type: InspectionType;
  is_required: boolean;
  photo_required: boolean;
  sort_order: number;
}

export interface QCInspection {
  id: string;
  company_id: string;
  inspection_number: string;
  template_id: string;
  template_name: string;
  inventory_item_id: string | null;
  item_identifier: string;
  product_category: ProductCategory;
  status: InspectionStatus;
  inspector_id: string;
  inspector_name: string;
  started_at: string | null;
  completed_at: string | null;
  overall_notes: string | null;
  step_results: QCStepResult[];
  dispositions: QCDisposition[];
  rework_records: QCReworkRecord[];
  created_at: string;
  updated_at: string;
}

export interface QCStepResult {
  id: string;
  inspection_id: string;
  step_id: string;
  step_number: number;
  step_name: string;
  step_description: string | null;
  inspection_type: InspectionType;
  photo_required: boolean;
  result: StepResult;
  defect_type_id: string | null;
  defect_type_name: string | null;
  defect_severity: DefectSeverity | null;
  notes: string | null;
  media: QCMedia[];
}

export interface QCDefectType {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  product_category: ProductCategory | null;
  default_severity: DefectSeverity;
  is_active: boolean;
}

export interface QCDisposition {
  id: string;
  inspection_id: string;
  disposition_type: DispositionType;
  reason: string | null;
  rework_instructions: string | null;
  decided_by_id: string;
  decided_by_name: string;
  created_at: string;
}

export interface QCReworkRecord {
  id: string;
  inspection_id: string;
  disposition_id: string;
  assigned_to_id: string | null;
  assigned_to_name: string | null;
  instructions: string | null;
  status: "pending" | "in_progress" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  result_notes: string | null;
  created_at: string;
}

export interface QCMedia {
  id: string;
  step_result_id: string;
  file_url: string;
  file_name: string;
  content_type: string;
  created_at: string;
}

// Create / Update types

export interface InspectionCreate {
  item_identifier: string;
  product_category: ProductCategory;
  template_id?: string;
  inventory_item_id?: string;
}

export interface StepResultUpdate {
  result: StepResult;
  defect_type_id?: string;
  defect_severity?: DefectSeverity;
  notes?: string;
}

export interface DispositionCreate {
  disposition_type: DispositionType;
  reason?: string;
  rework_instructions?: string;
}

export interface ReworkCreate {
  disposition_id: string;
  assigned_to_id?: string;
  instructions?: string;
}

// Report types

export interface QCSummaryReport {
  pass_rate_by_category: Record<string, { total: number; passed: number; rate: number }>;
  defect_frequency: { defect_type: string; count: number; severity: DefectSeverity }[];
  inspector_stats: { inspector_name: string; total: number; pass_rate: number }[];
  rework_success_rate: number;
  avg_time_in_qc: Record<string, number>;
}

// List types

export interface QCInspectionListItem {
  id: string;
  inspection_number: string;
  item_identifier: string;
  product_category: ProductCategory;
  status: InspectionStatus;
  inspector_name: string;
  started_at: string | null;
  completed_at: string | null;
  step_count: number;
  pass_count: number;
  fail_count: number;
  created_at: string;
}

export interface PaginatedInspections {
  items: QCInspectionListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface QCDashboardStats {
  pending_count: number;
  in_rework_count: number;
  awaiting_disposition_count: number;
  completed_today_count: number;
}
