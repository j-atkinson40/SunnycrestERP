/**
 * ComponentThumbnail — stylized per-kind representation for the
 * left-rail component browser.
 *
 * NOT a real render — just enough visual signature to convey the
 * shape of the component (widget vs Focus vs document block vs
 * workflow node). All colors are design tokens; ~80×60 footprint.
 */
import type { ComponentKind } from "@/bridgeable-admin/services/component-configurations-service"


interface Props {
  kind: ComponentKind
  componentName: string
  /** Optional small badge dot when this component has overrides at the active scope. */
  hasOverrides?: boolean
}


function WidgetThumb({ name }: { name: string }) {
  // Different widget names suggest different shapes:
  //  - metric/stat-style → single big value
  //  - list-style → multiple stacked rows
  //  - kanban/schedule → grid lanes
  const shape = inferWidgetShape(name)
  return (
    <div
      className="flex h-full w-full flex-col gap-1 rounded-sm border border-border-subtle bg-surface-elevated p-1.5"
      data-testid={`thumb-widget-${shape}`}
    >
      <div className="h-1 w-2/3 rounded bg-content-muted opacity-50" />
      {shape === "metric" && (
        <div className="flex flex-1 items-center justify-center">
          <div className="h-3 w-12 rounded bg-accent opacity-80" />
        </div>
      )}
      {shape === "list" && (
        <div className="flex flex-col gap-0.5">
          <div className="h-1 w-full rounded bg-surface-sunken" />
          <div className="h-1 w-5/6 rounded bg-surface-sunken" />
          <div className="h-1 w-4/6 rounded bg-surface-sunken" />
          <div className="h-1 w-5/6 rounded bg-surface-sunken" />
        </div>
      )}
      {shape === "schedule" && (
        <div className="grid flex-1 grid-cols-3 gap-0.5">
          <div className="rounded bg-surface-sunken" />
          <div className="rounded bg-accent-subtle" />
          <div className="rounded bg-surface-sunken" />
          <div className="rounded bg-accent-subtle" />
          <div className="rounded bg-surface-sunken" />
          <div className="rounded bg-surface-sunken" />
        </div>
      )}
      {shape === "default" && (
        <div className="flex flex-1 flex-col gap-0.5">
          <div className="h-1 w-full rounded bg-surface-sunken" />
          <div className="h-1 w-3/4 rounded bg-surface-sunken" />
        </div>
      )}
      <div className="mt-auto h-0.5 w-1/3 rounded bg-content-muted opacity-30" />
    </div>
  )
}


function inferWidgetShape(
  name: string,
): "metric" | "list" | "schedule" | "default" {
  const n = name.toLowerCase()
  if (n.includes("vault") || n.includes("schedule") || n.includes("kanban")) return "schedule"
  if (n.includes("today") || n.includes("recent") || n.includes("anomalies")) return "list"
  if (n.includes("operator") || n.includes("status") || n.includes("metric")) return "metric"
  return "default"
}


function FocusThumb({ name, isTemplate }: { name: string; isTemplate: boolean }) {
  // Slightly different proportions per Focus type
  const heightHint = inferFocusHeight(name)
  return (
    <div
      className="relative flex h-full w-full flex-col rounded-sm border border-border-subtle bg-surface-elevated"
      data-testid={`thumb-focus-${heightHint}`}
    >
      {/* Header strip */}
      <div className="flex items-center gap-0.5 border-b border-border-subtle bg-surface-sunken px-1 py-1">
        <div className="h-1 w-8 rounded bg-content-muted opacity-50" />
        <div className="ml-auto h-1.5 w-1.5 rounded-full bg-content-muted opacity-30" />
      </div>
      {/* Content */}
      <div className="flex flex-1 flex-col justify-center gap-0.5 px-1.5 py-1">
        {Array.from({ length: heightHint === "tall" ? 5 : heightHint === "short" ? 2 : 3 }).map((_, i) => (
          <div
            key={i}
            className="h-0.5 rounded bg-surface-sunken"
            style={{ width: `${100 - i * 12}%` }}
          />
        ))}
      </div>
      {/* Action bar */}
      <div className="flex items-center justify-end gap-0.5 border-t border-border-subtle bg-surface-sunken px-1 py-1">
        <div className="h-1 w-3 rounded bg-content-muted opacity-30" />
        <div className="h-1 w-4 rounded bg-accent" />
      </div>
      {isTemplate && (
        <div
          className="absolute -right-1 -top-1 rounded-full bg-accent px-1 text-[8px] font-medium text-content-on-accent"
          data-testid="thumb-template-badge"
        >
          T
        </div>
      )}
    </div>
  )
}


function inferFocusHeight(name: string): "tall" | "short" | "medium" {
  const n = name.toLowerCase()
  if (n.includes("generation")) return "tall"
  if (n.includes("execution") || n.includes("decision")) return "short"
  return "medium"
}


function DocumentBlockThumb({ name }: { name: string }) {
  const isHeader = name.toLowerCase().includes("header")
  const isSignature = name.toLowerCase().includes("signature")
  return (
    <div
      className="flex h-full w-full flex-col gap-0.5 rounded-sm border border-border-subtle bg-surface-elevated p-1"
      data-testid={`thumb-doc-${isHeader ? "header" : isSignature ? "signature" : "block"}`}
    >
      {isHeader && (
        <>
          <div className="h-2 w-3/4 rounded bg-accent opacity-70" />
          <div className="h-0.5 w-1/2 rounded bg-content-muted opacity-40" />
          <div className="h-px w-full bg-border-subtle" />
        </>
      )}
      {!isHeader && !isSignature && (
        <>
          <div className="h-px w-full bg-border-subtle" />
          <div className="h-1 w-full rounded bg-surface-sunken" />
          <div className="h-1 w-5/6 rounded bg-surface-sunken" />
          <div className="h-1 w-3/4 rounded bg-surface-sunken" />
        </>
      )}
      {/* Spacer pushes signatures to the bottom */}
      <div className="flex-1" />
      {!isHeader && (
        <>
          <div className="h-1 w-1/2 rounded bg-surface-sunken" />
          {isSignature && (
            <>
              <div className="h-px w-3/4 rounded bg-content-muted opacity-50" />
              <div className="h-0.5 w-1/3 rounded bg-content-muted opacity-30" />
            </>
          )}
        </>
      )}
    </div>
  )
}


function WorkflowNodeThumb({ name }: { name: string }) {
  const isCommunication = name.toLowerCase().includes("communication")
  return (
    <div
      className="flex h-full w-full items-center justify-center"
      data-testid={`thumb-workflow-${isCommunication ? "communication" : "node"}`}
    >
      <div
        className="relative flex h-12 w-20 items-center justify-center rounded-md border border-accent bg-surface-elevated"
      >
        {/* Input indicator */}
        <div className="absolute -left-1.5 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-content-muted opacity-70" />
        {/* Output indicator */}
        <div className="absolute -right-1.5 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-accent" />
        <div className="text-[8px] font-medium text-content-strong">
          {isCommunication ? "send" : "node"}
        </div>
      </div>
    </div>
  )
}


export function ComponentThumbnail({ kind, componentName, hasOverrides }: Props) {
  return (
    <div
      className="relative h-[60px] w-[80px] flex-shrink-0 overflow-hidden"
      data-testid="component-thumbnail"
      data-thumbnail-kind={kind}
    >
      {kind === "widget" && <WidgetThumb name={componentName} />}
      {(kind === "focus" || kind === "focus-template") && (
        <FocusThumb name={componentName} isTemplate={kind === "focus-template"} />
      )}
      {kind === "document-block" && <DocumentBlockThumb name={componentName} />}
      {kind === "workflow-node" && <WorkflowNodeThumb name={componentName} />}
      {hasOverrides && (
        <div
          className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-accent"
          data-testid="thumb-override-dot"
          title="Has overrides at this scope"
        />
      )}
    </div>
  )
}
