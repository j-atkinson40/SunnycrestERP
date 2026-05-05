/**
 * FocusContextFrame — renders the Focus shell (header + content
 * area + action bar) around the Focus type or template being edited.
 *
 * The action bar adapts to the Focus type so the shell's footer
 * affordances suit the kind of decision/coordination/etc the
 * Focus represents. Decision shows Decline/Approve; Generation
 * shows Save Draft/Commit; Coordination shows Close; Execution
 * shows Mark Complete; Review shows Reject/Approve.
 */
import type { ReactNode } from "react"
import { X } from "lucide-react"


type FocusType =
  | "decision"
  | "coordination"
  | "execution"
  | "review"
  | "generation"
  | "unknown"


interface Props {
  children: ReactNode
  /** Inferred from registry metadata — drives action-bar shape. */
  focusType?: FocusType
  /** Display name shown in the header. */
  title?: string
  /** When true, renders three Focus shells with varied content. */
  showAllInstances?: boolean
  renderInstance?: (variant: "draft" | "active" | "complete") => ReactNode
}


function actionsFor(focusType: FocusType): Array<{ label: string; intent: "primary" | "secondary" | "destructive" }> {
  switch (focusType) {
    case "decision":
      return [
        { label: "Decline", intent: "destructive" },
        { label: "Approve", intent: "primary" },
      ]
    case "generation":
      return [
        { label: "Save draft", intent: "secondary" },
        { label: "Commit", intent: "primary" },
      ]
    case "coordination":
      return [{ label: "Close", intent: "secondary" }]
    case "execution":
      return [{ label: "Mark complete", intent: "primary" }]
    case "review":
      return [
        { label: "Reject", intent: "destructive" },
        { label: "Approve", intent: "primary" },
      ]
    default:
      return [{ label: "Close", intent: "secondary" }]
  }
}


function ActionButton({
  label,
  intent,
}: {
  label: string
  intent: "primary" | "secondary" | "destructive"
}) {
  const cls =
    intent === "primary"
      ? "bg-accent text-content-on-accent hover:bg-accent-hover"
      : intent === "destructive"
        ? "border border-status-error/40 text-status-error hover:bg-status-error-muted/40"
        : "border border-border-base text-content-strong hover:bg-accent-subtle/40"
  return (
    <button
      type="button"
      className={`rounded-sm px-3 py-1.5 text-body-sm font-medium ${cls}`}
      data-testid={`focus-action-${intent}`}
    >
      {label}
    </button>
  )
}


function FocusShell({
  focusType,
  title,
  children,
}: {
  focusType: FocusType
  title: string
  children: ReactNode
}) {
  return (
    <div
      className="flex h-full flex-col rounded-md border border-border-subtle bg-surface-elevated shadow-level-2"
      data-testid="focus-shell"
      data-focus-type={focusType}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle px-5 py-3">
        <div className="flex flex-col gap-0.5">
          <div className="text-caption text-content-muted">
            Sample · Focus preview
          </div>
          <div className="text-h4 font-plex-serif text-content-strong">
            {title}
          </div>
        </div>
        <button
          type="button"
          aria-label="Close"
          className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40"
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-5 py-4" data-testid="focus-content">
        {children}
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-end gap-2 border-t border-border-subtle bg-surface-sunken px-5 py-3">
        {actionsFor(focusType).map((a) => (
          <ActionButton key={a.label} label={a.label} intent={a.intent} />
        ))}
      </div>
    </div>
  )
}


export function FocusContextFrame({
  children,
  focusType = "unknown",
  title = "Sample Focus",
  showAllInstances = false,
  renderInstance,
}: Props) {
  if (showAllInstances && renderInstance) {
    return (
      <div
        className="grid h-full grid-cols-1 gap-4 overflow-auto p-4 lg:grid-cols-3"
        data-testid="show-all-instances"
      >
        {(["draft", "active", "complete"] as const).map((v) => (
          <div key={v} className="min-h-[400px]" data-testid={`instance-${v}`}>
            <FocusShell
              focusType={focusType}
              title={`${title} — ${v}`}
            >
              {renderInstance(v)}
            </FocusShell>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div
      className="flex h-full flex-col p-4"
      data-testid="focus-context-frame"
    >
      <FocusShell focusType={focusType} title={title}>
        {children}
      </FocusShell>
    </div>
  )
}
