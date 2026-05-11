/** Phase R-6.2b — textarea field primitive (with optional char counter). */
import { Textarea } from "@/components/ui/textarea";

import {
  FieldError,
  FieldHelpText,
  FieldLabel,
  FieldWrapper,
  type IntakeFieldProps,
} from "./_shared";

export function TextareaField({
  config,
  value,
  onChange,
  error,
  inputId,
}: IntakeFieldProps) {
  const id = inputId ?? `intake-${config.id}`;
  const stringValue = typeof value === "string" ? value : "";
  const showCounter =
    typeof config.max_length === "number" && config.max_length > 0;
  return (
    <FieldWrapper config={config}>
      <FieldLabel config={config} htmlFor={id} />
      <Textarea
        id={id}
        value={stringValue}
        onChange={(e) => onChange(e.target.value)}
        placeholder={config.placeholder}
        maxLength={config.max_length}
        required={config.required}
        aria-invalid={error ? "true" : "false"}
        data-testid={`intake-textarea-${config.id}`}
      />
      <div className="mt-1 flex items-start justify-between gap-2">
        <FieldHelpText config={config} />
        {showCounter ? (
          <span
            className="shrink-0 text-caption text-content-muted"
            data-testid={`intake-counter-${config.id}`}
          >
            {stringValue.length} / {config.max_length}
          </span>
        ) : null}
      </div>
      <FieldError fieldId={config.id} error={error} />
    </FieldWrapper>
  );
}
