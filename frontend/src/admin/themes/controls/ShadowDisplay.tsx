/**
 * ShadowDisplay — read-only display for shadow-composition tokens.
 *
 * Phase 2 doesn't ship a structured shadow editor — Tier-4
 * measurements showed that shadow compositions reference upstream
 * `--shadow-color-*` tokens, so the right way to "edit a shadow"
 * is to override the upstream color tokens, not to rewrite the
 * composition. We display the composition so the operator
 * understands what they're inheriting + flag the upstream tokens
 * they should edit instead.
 *
 * Phase 3+ may add a structured editor (offset-x / offset-y /
 * blur / spread / color picker) but per DESIGN_LANGUAGE.md §6 the
 * canonical compositions should rarely be touched directly.
 */

import { Badge } from "@/components/ui/badge"


export interface ShadowDisplayProps {
  value: string
  derivedFrom?: string[]
  "data-testid"?: string
}


export function ShadowDisplay({
  value,
  derivedFrom,
  "data-testid": testid = "shadow-display",
}: ShadowDisplayProps) {
  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-sunken p-2"
      data-testid={testid}
    >
      <div className="flex items-center gap-2">
        <Badge variant="outline">read-only composition</Badge>
      </div>
      <pre
        className="whitespace-pre-wrap break-words rounded-sm border border-border-base bg-surface-raised p-2 font-plex-mono text-caption text-content-base"
        data-testid={`${testid}-value`}
      >
        {value}
      </pre>
      {derivedFrom && derivedFrom.length > 0 && (
        <p className="text-caption text-content-muted">
          Composes upstream tokens —{" "}
          <span className="font-plex-mono text-content-base">
            {derivedFrom.join(", ")}
          </span>
          . Override those instead of the composition.
        </p>
      )}
    </div>
  )
}
