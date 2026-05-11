/** Phase R-6.2b — text field primitive. */
import { Input } from "@/components/ui/input";

import {
  FieldError,
  FieldHelpText,
  FieldLabel,
  FieldWrapper,
  type IntakeFieldProps,
} from "./_shared";

export function TextField({
  config,
  value,
  onChange,
  error,
  inputId,
}: IntakeFieldProps) {
  const id = inputId ?? `intake-${config.id}`;
  const stringValue = typeof value === "string" ? value : "";
  return (
    <FieldWrapper config={config}>
      <FieldLabel config={config} htmlFor={id} />
      <Input
        id={id}
        type="text"
        value={stringValue}
        onChange={(e) => onChange(e.target.value)}
        placeholder={config.placeholder}
        maxLength={config.max_length}
        required={config.required}
        aria-invalid={error ? "true" : "false"}
        aria-describedby={
          config.help_text ? `intake-help-${config.id}` : undefined
        }
        data-testid={`intake-input-${config.id}`}
      />
      <FieldHelpText config={config} />
      <FieldError fieldId={config.id} error={error} />
    </FieldWrapper>
  );
}
