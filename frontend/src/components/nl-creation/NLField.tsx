/**
 * NLField — one row in the NL overlay.
 *
 * Visual states:
 *   - captured (confidence >= 0.9)        → check icon, normal text
 *   - low-confidence (0.5 <= c < 0.9)     → alert icon, amber left border
 *   - unavailable (wrapped in MissingRow) → muted, no icon
 *
 * Resolved entity pills render with a distinctive style + icon so
 * the user knows the system connected the reference to a real vault
 * record (e.g. "Hopkins FH" → pill linking to the CRM entry).
 */

import { Check, CircleAlert, Link2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { FieldExtraction } from "@/types/nl-creation";

export interface NLFieldProps {
  extraction: FieldExtraction;
  onRemove?: () => void;
  onEdit?: () => void;
}

export function NLField({ extraction }: NLFieldProps) {
  const conf = extraction.confidence;
  const isLowConfidence = conf < 0.9;
  const isResolvedEntity =
    extraction.source === "entity_resolver" &&
    extraction.resolved_entity_id !== null;
  const isSpaceDefault = extraction.source === "space_default";

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-md px-2 py-1.5 text-sm",
        "border-l-2 transition-colors",
        // Phase 7 micro-interaction — subtle entrance when a field
        // first appears during extraction. motion-safe: honors the
        // user's reduced-motion preference.
        "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1 motion-safe:duration-200",
        isLowConfidence
          ? "border-amber-400 bg-amber-50/60"
          : "border-transparent",
      )}
      data-testid={`nl-field-${extraction.field_key}`}
      data-confidence={conf.toFixed(2)}
      data-source={extraction.source}
    >
      <div className="mt-0.5 shrink-0">
        {isLowConfidence ? (
          <CircleAlert className="size-4 text-amber-600" />
        ) : (
          <Check className="size-4 text-emerald-600" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {extraction.field_label}
          </span>
          {isSpaceDefault && (
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground/60">
              from space
            </span>
          )}
        </div>
        {isResolvedEntity ? (
          <EntityPill extraction={extraction} />
        ) : (
          <div className="mt-0.5 truncate">{extraction.display_value}</div>
        )}
      </div>
    </div>
  );
}

function EntityPill({ extraction }: { extraction: FieldExtraction }) {
  return (
    <div
      className={cn(
        "mt-1 inline-flex items-center gap-1.5 rounded-full",
        "border border-primary/30 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary",
      )}
      data-testid="nl-entity-pill"
      data-entity-id={extraction.resolved_entity_id}
    >
      <Link2 className="size-3" />
      {extraction.display_value}
    </div>
  );
}

export interface MissingRowProps {
  fieldLabel: string;
}

export function MissingRow({ fieldLabel }: MissingRowProps) {
  return (
    <div
      className="flex items-center gap-2 px-2 py-1 text-sm text-muted-foreground"
      data-testid="nl-missing-field"
      data-field-label={fieldLabel}
    >
      <div className="size-1.5 rounded-full bg-muted-foreground/40" />
      {fieldLabel}
    </div>
  );
}
