/**
 * Phase R-6.2b — Intake adapter type mirrors.
 *
 * Type shapes mirror backend Pydantic models in
 * backend/app/api/routes/intake_adapters.py.
 *
 * Schema source of truth: r94_intake_adapter_configurations migration.
 */

export type IntakeFieldType =
  | "text"
  | "textarea"
  | "email"
  | "phone"
  | "date"
  | "select"
  | "file_upload";

export interface IntakeSelectOption {
  value: string;
  label: string;
}

export interface IntakeFieldConfig {
  id: string;
  type: IntakeFieldType;
  label: string;
  required?: boolean;
  help_text?: string;
  max_length?: number;
  placeholder?: string;
  options?: IntakeSelectOption[]; // select fields only
}

export interface IntakeFormSchema {
  version: string;
  fields: IntakeFieldConfig[];
  captcha_required?: boolean;
}

export interface IntakeFormConfig {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  form_schema: IntakeFormSchema;
  success_message: string | null;
}

export interface IntakeFormSubmitResponse {
  submission_id: string;
  success_message: string | null;
}

export interface IntakeFileConfig {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  allowed_content_types: string[];
  max_file_size_bytes: number;
  max_file_count: number;
  metadata_schema: IntakeFormSchema;
  success_message: string | null;
}

export interface IntakePresignedUpload {
  upload_id?: string;
  r2_key?: string;
  key?: string;
  url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_in?: number;
}

export interface IntakeFileCompleteResponse {
  upload_id: string;
  success_message: string | null;
}

/** Submission payload for /submit endpoint. */
export interface IntakeFormSubmitRequest {
  submitted_data: Record<string, unknown>;
  captcha_token: string | null;
}

/** Presign request payload for /presign endpoint. */
export interface IntakePresignRequest {
  original_filename: string;
  content_type: string;
  size_bytes: number;
  captcha_token: string | null;
}

/** Complete request payload for /complete endpoint. */
export interface IntakeCompleteRequest {
  r2_key: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  uploader_metadata: Record<string, unknown>;
  captcha_token: string | null;
}
