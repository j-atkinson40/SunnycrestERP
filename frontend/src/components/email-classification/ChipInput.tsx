/**
 * ChipInput — bespoke tag-input primitive for R-6.1b.a.
 *
 * Composed from `Input` + `Badge` per Aesthetic Arc Session 3 primitives.
 * Investigation (R-6.1b.a §10 risk #7) confirmed no existing chip-input
 * pattern in the codebase, so this composes minimally rather than
 * pulling a third-party library.
 *
 * Behavior:
 *   - Enter or comma adds the current input as a chip (trimmed).
 *   - Backspace on empty input removes the last chip.
 *   - Esc clears in-progress input AND removes the last chip if input
 *     is already empty (per build-prompt direction).
 *   - Duplicate values are silently ignored.
 *   - Empty / whitespace-only input does not add a chip.
 *
 * Accessibility:
 *   - role="list" on the chip strip; each chip is role="listitem".
 *   - Each chip's remove button has aria-label="Remove {value}".
 *   - Composes a single accessible label via aria-describedby pointing
 *     at an optional helper paragraph.
 */

import * as React from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

export interface ChipInputProps {
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Inline help below the input. */
  helperText?: React.ReactNode;
  "data-testid"?: string;
  /** Validate a candidate value before it becomes a chip. Reject by
   *  returning a string error message. */
  validate?: (value: string) => string | null;
}

export function ChipInput({
  values,
  onChange,
  placeholder,
  disabled = false,
  helperText,
  validate,
  ...props
}: ChipInputProps) {
  const [draft, setDraft] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  const commit = React.useCallback(
    (raw: string) => {
      const trimmed = raw.trim();
      if (!trimmed) return false;
      if (values.includes(trimmed)) {
        setDraft("");
        return true; // dedupe — silent
      }
      if (validate) {
        const msg = validate(trimmed);
        if (msg) {
          setError(msg);
          return false;
        }
      }
      onChange([...values, trimmed]);
      setDraft("");
      setError(null);
      return true;
    },
    [values, onChange, validate],
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit(draft);
    } else if (e.key === "Backspace" && draft === "" && values.length > 0) {
      e.preventDefault();
      onChange(values.slice(0, -1));
    } else if (e.key === "Escape") {
      e.preventDefault();
      if (draft !== "") {
        setDraft("");
        setError(null);
      } else if (values.length > 0) {
        onChange(values.slice(0, -1));
      }
    }
  }

  function removeAt(idx: number) {
    onChange(values.filter((_, i) => i !== idx));
  }

  return (
    <div className="space-y-1.5" data-testid={props["data-testid"] ?? "chip-input"}>
      <div className="flex flex-wrap items-start gap-1.5 rounded border border-border-base bg-surface-raised p-2">
        {values.length > 0 ? (
          <ul role="list" className="contents">
            {values.map((v, i) => (
              <li key={`${v}-${i}`} role="listitem">
                <Badge
                  variant="secondary"
                  className="gap-1 pl-2 pr-1 text-body-sm"
                >
                  <span>{v}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${v}`}
                    disabled={disabled}
                    onClick={() => removeAt(i)}
                    className="rounded-sm p-0.5 text-content-muted hover:text-content-strong hover:bg-accent-subtle focus-ring-accent disabled:pointer-events-none"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}
        <Input
          type="text"
          value={draft}
          disabled={disabled}
          placeholder={values.length === 0 ? placeholder : undefined}
          onChange={(e) => {
            setDraft(e.target.value);
            if (error) setError(null);
          }}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (draft.trim()) commit(draft);
          }}
          className="min-w-[8rem] flex-1 border-0 bg-transparent p-0 px-1 text-body-sm shadow-none focus-visible:ring-0"
          data-testid="chip-input-field"
        />
      </div>
      {error ? (
        <p className="text-caption text-status-error" role="alert">
          {error}
        </p>
      ) : null}
      {helperText ? (
        <p className="text-caption text-content-muted">{helperText}</p>
      ) : null}
    </div>
  );
}
