/**
 * NLOverlay — the Fantastical-style extraction panel.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────┐
 *   │ Create Case                                 │
 *   ├─────────────────────────────────────────────┤
 *   │ ✓ Deceased name        John Smith           │
 *   │ ✓ Date of death        Today (2026-04-20)   │
 *   │ ✓ Funeral home         [Hopkins FH]         │ ← pill
 *   │                                             │
 *   │ Missing:                                    │
 *   │ • Service time                              │
 *   ├─────────────────────────────────────────────┤
 *   │ [Enter] Create with current data            │
 *   │ [Tab]   Fill remaining fields               │
 *   │ [Esc]   Cancel                              │
 *   └─────────────────────────────────────────────┘
 *
 * Styling goals: subtle, readable, matches command bar aesthetic.
 * No modals, no dialogs — just a panel beneath the input.
 */

import { useMemo } from "react";
import { Loader2 } from "lucide-react";

import { MissingRow, NLField } from "./NLField";
import type {
  FieldExtraction,
  FieldSchema,
  NLEntityType,
  NLEntityTypeInfo,
} from "@/types/nl-creation";

export interface NLOverlayProps {
  entityType: NLEntityType;
  entityInfo: NLEntityTypeInfo | null;
  extractions: FieldExtraction[];
  missingRequired: string[];
  isExtracting: boolean;
  error: string | null;
  extractionMs: number | null;
}

export function NLOverlay({
  entityType,
  entityInfo,
  extractions,
  missingRequired,
  isExtracting,
  error,
  extractionMs,
}: NLOverlayProps) {
  const title = entityInfo?.display_name ?? `Create ${entityType}`;
  const fieldByKey: Record<string, FieldSchema> = useMemo(() => {
    const out: Record<string, FieldSchema> = {};
    for (const f of entityInfo?.fields ?? []) {
      out[f.field_key] = f;
    }
    return out;
  }, [entityInfo]);

  const missingLabels = useMemo(
    () =>
      missingRequired.map(
        (k) => fieldByKey[k]?.field_label ?? k.replaceAll("_", " "),
      ),
    [missingRequired, fieldByKey],
  );

  return (
    <div
      className="rounded-md border bg-card shadow-sm"
      data-testid="nl-overlay"
      data-entity-type={entityType}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{title}</span>
          {isExtracting && (
            <Loader2 className="size-3 animate-spin text-muted-foreground" />
          )}
        </div>
        {extractionMs != null && (
          <span className="text-[10px] tabular-nums text-muted-foreground/60">
            {extractionMs}ms
          </span>
        )}
      </div>

      {/* Body */}
      <div
        className="max-h-[50vh] overflow-y-auto px-1 py-2"
        role="region"
        aria-label="Natural language extraction results"
        aria-live="polite"
        aria-busy={isExtracting}
      >
        {error ? (
          <div
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {error}
            <div className="mt-1 text-xs opacity-80">
              AI extraction is temporarily unavailable. Press Tab to open the form directly.
            </div>
          </div>
        ) : (
          <>
            {extractions.length === 0 ? (
              <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                {isExtracting ? "Extracting…" : "Keep typing…"}
              </div>
            ) : (
              <div className="space-y-0.5" data-testid="nl-overlay-extractions">
                {extractions.map((e) => (
                  <NLField key={e.field_key} extraction={e} />
                ))}
              </div>
            )}

            {missingLabels.length > 0 && (
              <div className="mt-2 border-t pt-2" data-testid="nl-overlay-missing">
                <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                  Missing
                </div>
                {missingLabels.map((label) => (
                  <MissingRow key={label} fieldLabel={label} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer — keyboard hints */}
      <div className="flex items-center gap-4 border-t px-3 py-1.5 text-[11px] text-muted-foreground">
        <span>
          <kbd className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">
            Enter
          </kbd>{" "}
          Create
        </span>
        <span>
          <kbd className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">
            Tab
          </kbd>{" "}
          Open form
        </span>
        <span>
          <kbd className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">
            Esc
          </kbd>{" "}
          Cancel
        </span>
      </div>
    </div>
  );
}
