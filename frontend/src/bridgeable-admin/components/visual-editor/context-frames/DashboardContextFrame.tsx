/**
 * DashboardContextFrame — wraps a widget preview in representative
 * dashboard chrome so the operator sees the widget alongside what
 * it would normally surround it.
 *
 * Uses Bridgeable warm tokens; not a real dashboard, just a 3-column
 * stand-in with placeholder cards. The actual widget being edited
 * occupies the center cell; surrounding cells are token-styled
 * placeholders that imply other widgets.
 */
import type { ReactNode } from "react"


interface Props {
  children: ReactNode
  /** When true, renders three instances of the widget side-by-side. */
  showAllInstances?: boolean
  /** When showAllInstances is true, this renders each instance. */
  renderInstance?: (variant: "default" | "compact" | "ultra") => ReactNode
}


function PlaceholderWidget({ label }: { label: string }) {
  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-elevated p-3 opacity-60"
      data-testid="dashboard-placeholder-widget"
    >
      <div className="flex items-center justify-between">
        <div className="text-caption font-medium text-content-muted">{label}</div>
        <div className="h-1.5 w-1.5 rounded-full bg-content-subtle" />
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="h-2 w-full rounded bg-surface-sunken" />
        <div className="h-2 w-3/4 rounded bg-surface-sunken" />
        <div className="h-2 w-2/3 rounded bg-surface-sunken" />
      </div>
      <div className="mt-auto flex items-center gap-1.5">
        <div className="h-1.5 flex-1 rounded bg-surface-sunken" />
        <div className="h-1.5 w-8 rounded bg-surface-sunken" />
      </div>
    </div>
  )
}


export function DashboardContextFrame({
  children,
  showAllInstances = false,
  renderInstance,
}: Props) {
  return (
    <div
      className="flex h-full w-full flex-col gap-3 rounded-md bg-surface-base p-4"
      data-testid="dashboard-context-frame"
    >
      {/* Mock dashboard header */}
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <div className="text-h4 font-plex-serif text-content-strong">
            Today
          </div>
          <div className="text-caption text-content-muted">
            Sample dashboard context
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 w-16 rounded bg-surface-sunken opacity-60" />
          <div className="h-6 w-16 rounded bg-surface-sunken opacity-60" />
        </div>
      </div>

      {/* 3-column grid; widget under edit lives in the center cell */}
      <div className="grid flex-1 grid-cols-3 gap-3">
        <PlaceholderWidget label="Recent activity" />

        {showAllInstances && renderInstance ? (
          <div className="col-span-3 grid grid-cols-3 gap-3" data-testid="show-all-instances">
            <div data-testid="instance-default">
              {renderInstance("default")}
            </div>
            <div data-testid="instance-compact">
              {renderInstance("compact")}
            </div>
            <div data-testid="instance-ultra">
              {renderInstance("ultra")}
            </div>
          </div>
        ) : (
          <>
            <div
              className="overflow-hidden rounded-md ring-2 ring-accent ring-offset-2 ring-offset-surface-base"
              data-testid="dashboard-context-target"
            >
              {children}
            </div>
            <PlaceholderWidget label="Anomalies" />
          </>
        )}

        <PlaceholderWidget label="Operator profile" />
        <PlaceholderWidget label="Vault schedule" />
        <PlaceholderWidget label="Line status" />
      </div>
    </div>
  )
}
