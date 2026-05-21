/**
 * AtomErrorIndicator — WB-4b composition-wrapper that renders a
 * 2px red outline + tooltip when an atom has validation errors.
 *
 * Composed as a wrapper around canvas atom nodes — sibling to the
 * existing selection outline. Renders ONLY when the wrapped atom has
 * at least one error in `errorsByAtom[atomId]`. The outline uses
 * `--status-error` per DESIGN_LANGUAGE.md status palette.
 *
 * The error tooltip is rendered via `title=` for Phase 1 (fast +
 * universally supported). A richer tooltip is post-arc polish.
 */
import { cn } from "@/lib/utils"


export function AtomErrorIndicator({
  atomId,
  errors,
  children,
}: {
  atomId: string
  errors: string[] | undefined
  children: React.ReactNode
}) {
  const hasErrors = errors && errors.length > 0
  if (!hasErrors) {
    return <>{children}</>
  }
  return (
    <div
      data-testid={`widget-builder-canvas-atom-error-${atomId}`}
      data-atom-id={atomId}
      data-has-errors="true"
      title={errors!.join("\n")}
      className={cn(
        "rounded-sm outline outline-2 outline-status-error/70",
        "outline-offset-1",
      )}
    >
      {children}
    </div>
  )
}
