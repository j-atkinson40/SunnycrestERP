/**
 * Phase R-6.2b — file-upload field primitive.
 *
 * Single component, dual UX via CSS @media query for capability
 * detection:
 *
 *   - Devices with hover + fine pointer (desktop with mouse, iPad with
 *     keyboard) see the drag-and-drop affordance.
 *   - Touch-only devices (phones, iPad without keyboard) see ONLY the
 *     file picker button.
 *
 * Both paths produce the same `selectedFiles` state — upstream
 * orchestrator handles the presign + R2 PUT + complete chain.
 *
 * Architectural pattern locked (CLAUDE.md §4): CSS-only capability
 * detection avoids SSR/hydration mismatch + iPad-with-keyboard edge
 * case that JS-based detection trips on.
 *
 * Note: client-side validation (size cap, content-type allowlist) is
 * UX-only. Backend `file_adapter.complete_file_upload` is canonical
 * source of truth for upload acceptance.
 */

import { Upload, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { IntakeFileConfig } from "@/types/intake";

import {
  FieldError,
  FieldHelpText,
  FieldLabel,
  FieldWrapper,
  type IntakeFieldProps,
} from "./_shared";

interface FileUploadFieldProps extends IntakeFieldProps {
  uploadConfig: Pick<
    IntakeFileConfig,
    "allowed_content_types" | "max_file_size_bytes" | "max_file_count"
  >;
  /** When set, shows an aggregate progress bar (0..1). */
  uploadProgress?: number | null;
  /** True while presign/PUT/complete chain is firing. */
  isUploading?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(
  file: File,
  config: Pick<
    IntakeFileConfig,
    "allowed_content_types" | "max_file_size_bytes"
  >,
): string | null {
  if (file.size > config.max_file_size_bytes) {
    return `File exceeds max size (${formatBytes(
      config.max_file_size_bytes,
    )}).`;
  }
  const allowed = config.allowed_content_types ?? [];
  if (
    allowed.length > 0 &&
    !allowed.includes(file.type) &&
    !allowed.includes("*/*")
  ) {
    return `File type "${file.type}" is not allowed.`;
  }
  return null;
}

export function FileUploadField({
  config,
  value,
  onChange,
  error,
  inputId,
  uploadConfig,
  uploadProgress,
  isUploading,
}: FileUploadFieldProps) {
  const id = inputId ?? `intake-${config.id}`;
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const selected = Array.isArray(value) ? (value as File[]) : [];

  const acceptAttr = (uploadConfig.allowed_content_types ?? []).join(",");
  const maxCount = uploadConfig.max_file_count ?? 1;
  const allowMultiple = maxCount > 1;

  function addFiles(files: FileList | File[]) {
    setLocalError(null);
    const incoming = Array.from(files);
    const validated: File[] = [];
    for (const file of incoming) {
      const validationError = validateFile(file, uploadConfig);
      if (validationError) {
        setLocalError(validationError);
        return;
      }
      validated.push(file);
    }
    const combined = [...selected, ...validated].slice(0, maxCount);
    onChange(combined);
  }

  function removeFile(index: number) {
    const next = selected.filter((_, i) => i !== index);
    onChange(next);
  }

  function onPickerChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files) return;
    addFiles(e.target.files);
    // Reset native input so re-selecting the same file fires onChange.
    if (inputRef.current) inputRef.current.value = "";
  }

  function onDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(true);
  }
  function onDragLeave() {
    setIsDragging(false);
  }
  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    if (!e.dataTransfer.files) return;
    addFiles(e.dataTransfer.files);
  }

  const displayError = error ?? localError ?? undefined;

  return (
    <FieldWrapper config={config}>
      <FieldLabel config={config} htmlFor={id} />

      {/*
        Drop zone — visible on devices with hover + fine pointer per
        @media query. CSS class `intake-file-upload-drop-zone` is used
        by tests to assert presence; capability gate is applied via
        inline `@media (hover: hover) and (pointer: fine)` in the
        className arbitrary variant.
       */}
      <div
        className={`intake-file-upload-drop-zone hidden [@media(hover:hover)and(pointer:fine)]:block rounded border-2 border-dashed transition-colors ${
          isDragging
            ? "border-accent bg-accent-subtle"
            : "border-border-base bg-surface-sunken"
        } p-6 text-center`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        data-testid={`intake-dropzone-${config.id}`}
        data-dragging={isDragging ? "true" : "false"}
      >
        <Upload
          className="mx-auto mb-2 h-8 w-8 text-content-muted"
          aria-hidden="true"
        />
        <p className="mb-2 text-body-sm text-content-base">
          Drag and drop a file here
        </p>
        <p className="mb-3 text-caption text-content-muted">or</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={isUploading || selected.length >= maxCount}
          data-testid={`intake-file-picker-button-desktop-${config.id}`}
        >
          Choose file{allowMultiple ? "s" : ""}
        </Button>
      </div>

      {/* Touch-friendly path — visible when hover/pointer NOT fine. */}
      <div
        className="[@media(hover:hover)and(pointer:fine)]:hidden"
        data-testid={`intake-file-picker-touch-${config.id}`}
      >
        <Button
          type="button"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={isUploading || selected.length >= maxCount}
          className="w-full min-h-11"
        >
          <Upload className="mr-2 h-4 w-4" />
          Choose file{allowMultiple ? "s" : ""}
        </Button>
      </div>

      {/* Hidden file input — always present, both UX paths invoke it. */}
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={acceptAttr || undefined}
        multiple={allowMultiple}
        onChange={onPickerChange}
        className="sr-only"
        data-testid={`intake-file-input-${config.id}`}
      />

      {/* Selected files list. */}
      {selected.length > 0 ? (
        <ul
          className="mt-3 space-y-2"
          data-testid={`intake-selected-files-${config.id}`}
        >
          {selected.map((file, i) => (
            <li
              key={`${file.name}-${i}`}
              className="flex items-center justify-between gap-3 rounded border border-border-subtle bg-surface-elevated px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-body-sm text-content-strong">
                  {file.name}
                </p>
                <p className="text-caption text-content-muted">
                  {formatBytes(file.size)}
                </p>
              </div>
              {!isUploading ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => removeFile(i)}
                  aria-label={`Remove ${file.name}`}
                  data-testid={`intake-remove-file-${config.id}-${i}`}
                >
                  <X className="h-4 w-4" />
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {/* Aggregate progress bar during upload. */}
      {isUploading && typeof uploadProgress === "number" ? (
        <div
          className="mt-3"
          data-testid={`intake-upload-progress-${config.id}`}
        >
          <div className="h-2 w-full overflow-hidden rounded bg-surface-sunken">
            <div
              className="h-2 bg-accent transition-all duration-quick"
              style={{ width: `${Math.round(uploadProgress * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-caption text-content-muted">
            Uploading… {Math.round(uploadProgress * 100)}%
          </p>
        </div>
      ) : null}

      <p className="mt-2 text-caption text-content-muted">
        Max {formatBytes(uploadConfig.max_file_size_bytes)}
        {maxCount > 1 ? ` · up to ${maxCount} files` : ""}
        {uploadConfig.allowed_content_types?.length
          ? ` · ${uploadConfig.allowed_content_types.join(", ")}`
          : ""}
      </p>

      <FieldHelpText config={config} />
      <FieldError fieldId={config.id} error={displayError} />
    </FieldWrapper>
  );
}
