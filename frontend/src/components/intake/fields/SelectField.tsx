/**
 * Phase R-6.2b — select field primitive.
 *
 * Uses native <select> for maximum mobile keyboard friendliness +
 * accessibility. shadcn <Select> is more visually polished but
 * routes through Base UI popovers which interact awkwardly with
 * touch keyboards. Native select gives the OS keyboard's wheel
 * picker on iOS + spinner on Android.
 */

import {
  FieldError,
  FieldHelpText,
  FieldLabel,
  FieldWrapper,
  type IntakeFieldProps,
} from "./_shared";

export function SelectField({
  config,
  value,
  onChange,
  error,
  inputId,
}: IntakeFieldProps) {
  const id = inputId ?? `intake-${config.id}`;
  const stringValue = typeof value === "string" ? value : "";
  const options = config.options ?? [];
  return (
    <FieldWrapper config={config}>
      <FieldLabel config={config} htmlFor={id} />
      <select
        id={id}
        value={stringValue}
        onChange={(e) => onChange(e.target.value)}
        required={config.required}
        aria-invalid={error ? "true" : "false"}
        data-testid={`intake-select-${config.id}`}
        className="flex h-11 w-full rounded border border-border-base bg-surface-raised px-4 py-2.5 font-sans text-body text-content-strong outline-none transition-colors duration-quick ease-settle hover:border-border-strong focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/30 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-content-subtle aria-invalid:border-status-error aria-invalid:ring-2 aria-invalid:ring-status-error/20 md:text-body-sm"
      >
        <option value="" disabled>
          {config.placeholder ?? "Select an option"}
        </option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <FieldHelpText config={config} />
      <FieldError fieldId={config.id} error={error} />
    </FieldWrapper>
  );
}
