/**
 * ActionPreviewCard — WB-7 Area 4 Lock 4b.
 *
 * NON-DISPATCHING preview card. Computes "Clicking will: <description>"
 * text only; does NOT call the R-4 dispatcher. Source-shape-gated to
 * be distinguishable from WB-6's BindingPreviewTooltip — different
 * visual treatment + different test id, even though they share the
 * inspector real-estate pattern.
 */
import type { ActionRef } from "@/lib/widget-builder/types/composition-blob"

import { computeActionPreviewText } from "./useActionPreview"


export interface ActionPreviewCardProps {
  action: ActionRef | null
  testId?: string
}


export function ActionPreviewCard({
  action,
  testId,
}: ActionPreviewCardProps) {
  const preview = computeActionPreviewText(action)
  return (
    <div
      data-testid={testId ?? "action-preview-card"}
      data-preview-kind={action?.action_kind ?? "none"}
      // Visually distinct from BindingPreviewTooltip — uses raised
      // surface + accent left-border to read as an "action" preview
      // (vs. binding's sunken-flat treatment).
      className="rounded-md border-l-2 border-l-[color:var(--accent)] bg-surface-raised px-2.5 py-1.5 text-body-sm text-content-base"
    >
      <span className="text-caption uppercase tracking-wide text-content-muted">
        Clicking will:
      </span>
      <div data-testid={`${testId ?? "action-preview-card"}-text`}>
        {preview}
      </div>
    </div>
  )
}
