/** Phase R-6.2b — email field primitive. */
import { Input } from "@/components/ui/input";

import {
  FieldError,
  FieldHelpText,
  FieldLabel,
  FieldWrapper,
  type IntakeFieldProps,
} from "./_shared";

export function EmailField({
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
        type="email"
        inputMode="email"
        autoComplete="email"
        value={stringValue}
        onChange={(e) => onChange(e.target.value)}
        placeholder={config.placeholder ?? "you@example.com"}
        required={config.required}
        aria-invalid={error ? "true" : "false"}
        data-testid={`intake-input-${config.id}`}
      />
      <FieldHelpText config={config} />
      <FieldError fieldId={config.id} error={error} />
    </FieldWrapper>
  );
}
