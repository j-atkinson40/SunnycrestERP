/**
 * NL Creation — frontend type mirrors.
 *
 * Shadow `backend/app/services/nl_creation/types.py` + the API
 * schemas in `backend/app/api/routes/nl_creation.py`. Keep literal
 * sets + field names in lockstep.
 */

export type NLEntityType = "case" | "event" | "contact" | "task";

export type ExtractionSource =
  | "structured_parser"
  | "entity_resolver"
  | "ai_extraction"
  | "space_default";

export type NLFieldType =
  | "text"
  | "name"
  | "date"
  | "time"
  | "datetime"
  | "phone"
  | "email"
  | "entity"
  | "enum"
  | "currency"
  | "quantity"
  | "boolean";

export interface FieldExtraction {
  field_key: string;
  field_label: string;
  extracted_value: unknown;
  display_value: string;
  confidence: number;
  source: ExtractionSource;
  resolved_entity_id: string | null;
  resolved_entity_type: string | null;
}

export interface ExtractionResult {
  entity_type: NLEntityType;
  extractions: FieldExtraction[];
  missing_required: string[];
  raw_input: string;
  extraction_ms: number;
  ai_execution_id: string | null;
  ai_latency_ms: number | null;
  space_default_fields: string[];
}

export interface ExtractRequest {
  entity_type: NLEntityType;
  natural_language: string;
  active_space_id?: string | null;
  prior_extractions?: FieldExtraction[];
}

export interface CreateRequest {
  entity_type: NLEntityType;
  extractions: FieldExtraction[];
  raw_input: string;
}

export interface CreateResponse {
  entity_id: string;
  entity_type: string;
  navigate_url: string;
}

export interface FieldSchema {
  field_key: string;
  field_label: string;
  field_type: NLFieldType;
  required: boolean;
  enum_values: string[] | null;
  has_structured_parser: boolean;
  has_entity_resolver: boolean;
  ai_hint: string | null;
}

export interface NLEntityTypeInfo {
  entity_type: NLEntityType;
  display_name: string;
  ai_prompt_key: string;
  navigate_url_template: string;
  required_permission: string | null;
  fields: FieldSchema[];
  space_defaults: Record<string, Record<string, unknown>>;
}
