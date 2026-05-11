/**
 * Phase R-6.2b — Shared chrome for intake field primitives.
 *
 * Every field renders the same label-row + help-text-row + error-row
 * pattern. Extracted to avoid duplication across 7 primitives.
 */

import { Label } from "@/components/ui/label";
import type { IntakeFieldConfig } from "@/types/intake";

export interface IntakeFieldProps {
  config: IntakeFieldConfig;
  value: unknown;
  onChange: (next: unknown) => void;
  error?: string;
  /** ID prefix for `<label htmlFor>` wiring. */
  inputId?: string;
}

export function FieldLabel({
  config,
  htmlFor,
}: {
  config: IntakeFieldConfig;
  htmlFor: string;
}) {
  return (
    <Label htmlFor={htmlFor} className="mb-1.5">
      {config.label}
      {config.required ? (
        <span
          className="text-status-error ml-1"
          aria-label="required"
          data-testid={`intake-field-required-${config.id}`}
        >
          *
        </span>
      ) : null}
    </Label>
  );
}

export function FieldHelpText({
  config,
}: {
  config: IntakeFieldConfig;
}) {
  if (!config.help_text) return null;
  return (
    <p
      className="mt-1 text-caption text-content-muted"
      data-testid={`intake-field-help-${config.id}`}
    >
      {config.help_text}
    </p>
  );
}

export function FieldError({
  fieldId,
  error,
}: {
  fieldId: string;
  error?: string;
}) {
  if (!error) return null;
  return (
    <p
      className="mt-1 text-caption text-status-error"
      role="alert"
      data-testid={`intake-field-error-${fieldId}`}
    >
      {error}
    </p>
  );
}

export function FieldWrapper({
  config,
  children,
}: {
  config: IntakeFieldConfig;
  children: React.ReactNode;
}) {
  return (
    <div
      className="mb-4"
      data-testid={`intake-field-${config.id}`}
      data-field-type={config.type}
    >
      {children}
    </div>
  );
}
