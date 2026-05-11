/** Phase R-6.2b — phone field primitive (loose validation; mobile keyboard hint). */
import { Input } from "@/components/ui/input";

import {
  FieldError,
  FieldHelpText,
  FieldLabel,
  FieldWrapper,
  type IntakeFieldProps,
} from "./_shared";

export function PhoneField({
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
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        value={stringValue}
        onChange={(e) => onChange(e.target.value)}
        placeholder={config.placeholder ?? "(555) 555-5555"}
        required={config.required}
        aria-invalid={error ? "true" : "false"}
        data-testid={`intake-input-${config.id}`}
      />
      <FieldHelpText config={config} />
      <FieldError fieldId={config.id} error={error} />
    </FieldWrapper>
  );
}
