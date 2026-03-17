// Safety Management types

export interface SafetyProgram {
  id: string;
  company_id: string;
  program_name: string;
  osha_standard: string | null;
  osha_standard_code: string | null;
  description: string | null;
  content: string | null;
  version: number;
  status: "draft" | "active" | "under_review" | "archived";
  last_reviewed_at: string | null;
  next_review_due_at: string | null;
  reviewed_by: string | null;
  applicable_job_roles: string[] | null;
  created_at: string;
  updated_at: string | null;
}

export interface SafetyProgramCreate {
  program_name: string;
  osha_standard?: string;
  osha_standard_code?: string;
  description?: string;
  content?: string;
  status?: string;
  applicable_job_roles?: string[];
}

export interface SafetyProgramUpdate {
  program_name?: string;
  osha_standard?: string;
  osha_standard_code?: string;
  description?: string;
  content?: string;
  status?: string;
  applicable_job_roles?: string[];
}

export interface TrainingRequirement {
  id: string;
  company_id: string;
  training_topic: string;
  osha_standard_code: string | null;
  applicable_roles: string[] | null;
  initial_training_required: boolean;
  refresher_frequency_months: number | null;
  new_hire_deadline_days: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface TrainingRequirementCreate {
  training_topic: string;
  osha_standard_code?: string;
  applicable_roles?: string[];
  initial_training_required?: boolean;
  refresher_frequency_months?: number;
  new_hire_deadline_days?: number;
}

export interface TrainingEvent {
  id: string;
  company_id: string;
  training_topic: string;
  osha_standard_code: string | null;
  training_type: string;
  trainer_name: string;
  trainer_type: string;
  training_date: string;
  duration_minutes: number;
  content_summary: string | null;
  training_materials_url: string | null;
  created_by: string | null;
  created_at: string;
  attendee_count?: number;
}

export interface TrainingEventCreate {
  training_topic: string;
  osha_standard_code?: string;
  training_type: string;
  trainer_name: string;
  trainer_type: string;
  training_date: string;
  duration_minutes: number;
  content_summary?: string;
  training_materials_url?: string;
}

export interface TrainingRecord {
  id: string;
  company_id: string;
  employee_id: string;
  training_event_id: string;
  completion_status: string;
  test_score: number | null;
  expiry_date: string | null;
  certificate_url: string | null;
  notes: string | null;
  created_at: string;
  employee_name?: string;
  training_topic?: string;
}

export interface TrainingGap {
  employee_id: string;
  employee_name: string;
  job_role: string | null;
  required_training: string;
  osha_standard_code: string | null;
  status: "missing" | "expired" | "expiring_soon";
  expiry_date: string | null;
  days_overdue: number | null;
}

export interface InspectionTemplate {
  id: string;
  company_id: string;
  template_name: string;
  inspection_type: string;
  equipment_type: string | null;
  frequency_days: number | null;
  description: string | null;
  active: boolean;
  items: InspectionItem[];
  created_at: string;
  updated_at: string | null;
}

export interface InspectionItem {
  id: string;
  template_id: string;
  item_order: number;
  item_text: string;
  response_type: "pass_fail" | "yes_no" | "numeric" | "text";
  required: boolean;
  failure_action: string | null;
  osha_reference: string | null;
}

export interface InspectionItemCreate {
  item_order: number;
  item_text: string;
  response_type?: string;
  required?: boolean;
  failure_action?: string;
  osha_reference?: string;
}

export interface InspectionTemplateCreate {
  template_name: string;
  inspection_type: string;
  equipment_type?: string;
  frequency_days?: number;
  description?: string;
  items?: InspectionItemCreate[];
}

export interface SafetyInspection {
  id: string;
  company_id: string;
  template_id: string;
  template_name: string | null;
  equipment_id: string | null;
  equipment_identifier: string | null;
  inspector_id: string;
  inspector_name: string | null;
  inspection_date: string;
  status: string;
  overall_result: string | null;
  notes: string | null;
  results: InspectionResult[];
  created_at: string;
  completed_at: string | null;
}

export interface InspectionResult {
  id: string;
  inspection_id: string;
  item_id: string;
  result: string | null;
  finding_notes: string | null;
  corrective_action_required: boolean;
  corrective_action_description: string | null;
  corrective_action_due_date: string | null;
  corrective_action_completed_at: string | null;
  corrective_action_completed_by: string | null;
  photo_urls: string[] | null;
  created_at: string;
  item_text?: string;
  item_order?: number;
  response_type?: string;
  required?: boolean;
}

export interface InspectionResultUpdate {
  result?: string;
  finding_notes?: string;
  corrective_action_required?: boolean;
  corrective_action_description?: string;
  corrective_action_due_date?: string;
  photo_urls?: string[];
}

export interface InspectionCreate {
  template_id: string;
  equipment_id?: string;
  equipment_identifier?: string;
  inspection_date: string;
  notes?: string;
}

export interface OverdueInspection {
  template_id: string;
  template_name: string;
  equipment_type: string | null;
  frequency_days: number;
  last_inspection_date: string | null;
  days_overdue: number;
}

export interface SafetyChemical {
  id: string;
  company_id: string;
  chemical_name: string;
  manufacturer: string | null;
  product_number: string | null;
  cas_number: string | null;
  location: string | null;
  quantity_on_hand: number | null;
  unit_of_measure: string | null;
  hazard_class: string[] | null;
  ppe_required: string[] | null;
  sds_url: string | null;
  sds_date: string | null;
  sds_review_due_at: string | null;
  active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface ChemicalCreate {
  chemical_name: string;
  manufacturer?: string;
  product_number?: string;
  cas_number?: string;
  location?: string;
  quantity_on_hand?: number;
  unit_of_measure?: string;
  hazard_class?: string[];
  ppe_required?: string[];
  sds_url?: string;
  sds_date?: string;
}

export interface ChemicalUpdate extends Partial<ChemicalCreate> {
  active?: boolean;
}

export interface SafetyIncident {
  id: string;
  company_id: string;
  incident_type: string;
  incident_date: string;
  incident_time: string | null;
  location: string;
  involved_employee_id: string | null;
  involved_employee_name: string | null;
  witnesses: string | null;
  description: string;
  immediate_cause: string | null;
  root_cause: string | null;
  body_part_affected: string | null;
  injury_type: string | null;
  medical_treatment: string;
  days_away_from_work: number;
  days_on_restricted_duty: number;
  osha_recordable: boolean;
  osha_300_case_number: number | null;
  reported_by: string | null;
  investigated_by: string | null;
  corrective_actions: string | null;
  status: string;
  created_at: string;
  updated_at: string | null;
}

export interface IncidentCreate {
  incident_type: string;
  incident_date: string;
  incident_time?: string;
  location: string;
  involved_employee_id?: string;
  witnesses?: string;
  description: string;
  immediate_cause?: string;
  body_part_affected?: string;
  injury_type?: string;
  medical_treatment?: string;
}

export interface IncidentUpdate {
  incident_type?: string;
  location?: string;
  involved_employee_id?: string;
  witnesses?: string;
  description?: string;
  immediate_cause?: string;
  root_cause?: string;
  body_part_affected?: string;
  injury_type?: string;
  medical_treatment?: string;
  days_away_from_work?: number;
  days_on_restricted_duty?: number;
  investigated_by?: string;
  corrective_actions?: string;
}

export interface OSHA300Entry {
  case_number: number;
  employee_name: string;
  job_title: string | null;
  incident_date: string;
  location: string;
  description: string;
  injury_type: string | null;
  days_away_from_work: number;
  days_on_restricted_duty: number;
  medical_treatment: string;
  incident_type: string;
}

export interface OSHA300ASummary {
  year: number;
  total_cases: number;
  total_deaths: number;
  total_days_away: number;
  total_days_restricted: number;
  total_other_recordable: number;
  injury_count: number;
  skin_disorder_count: number;
  respiratory_count: number;
  poisoning_count: number;
  hearing_loss_count: number;
  other_illness_count: number;
}

export interface EnergySource {
  type: string;
  location?: string;
  magnitude?: string;
  isolation_device?: string;
  isolation_location?: string;
  verification_method?: string;
}

export interface LOTOStep {
  step_number: number;
  action: string;
  photo_url?: string;
}

export interface LOTOProcedure {
  id: string;
  company_id: string;
  machine_name: string;
  machine_location: string | null;
  machine_id: string | null;
  procedure_number: string;
  energy_sources: EnergySource[];
  ppe_required: string[] | null;
  steps: LOTOStep[];
  estimated_time_minutes: number | null;
  authorized_employees: string[] | null;
  affected_employees: string[] | null;
  last_reviewed_at: string | null;
  next_review_due_at: string | null;
  active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface LOTOCreate {
  machine_name: string;
  machine_location?: string;
  machine_id?: string;
  procedure_number: string;
  energy_sources: EnergySource[];
  ppe_required?: string[];
  steps: LOTOStep[];
  estimated_time_minutes?: number;
  authorized_employees?: string[];
  affected_employees?: string[];
}

export interface LOTOUpdate extends Partial<LOTOCreate> {
  active?: boolean;
}

export interface SafetyAlert {
  id: string;
  company_id: string;
  alert_type: string;
  severity: "info" | "warning" | "critical";
  reference_id: string | null;
  reference_type: string | null;
  message: string;
  due_date: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ComplianceCategory {
  category: string;
  weight: number;
  score: number;
  max_score: number;
  items_total: number;
  items_compliant: number;
  gaps: string[];
}

export interface ComplianceScore {
  overall_score: number;
  categories: ComplianceCategory[];
  generated_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
}
