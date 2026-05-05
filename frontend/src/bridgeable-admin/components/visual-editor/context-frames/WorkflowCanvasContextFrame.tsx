/**
 * WorkflowCanvasContextFrame — renders a small workflow canvas
 * snippet (3 nodes connected) with the node being edited as the
 * selected one in the middle.
 *
 * Upstream and downstream node placeholders are inferred from the
 * node type — `generation-focus-invocation` typically follows a
 * trigger and feeds a communication; `send-communication` is the
 * common downstream of many node types. The canvas chrome (subtle
 * grid, soft background) makes the context legible.
 */
import type { ReactNode } from "react"


interface Props {
  children: ReactNode
  /** The node-type name being edited; drives upstream/downstream labels. */
  nodeType?: string
  /** When true, renders three canvases with varied node states. */
  showAllInstances?: boolean
  renderInstance?: (variant: "default" | "branching" | "joining") => ReactNode
}


type Adjacency = { upstream: string; downstream: string }


function adjacencyFor(nodeType: string): Adjacency {
  switch (nodeType) {
    case "generation-focus-invocation":
      return { upstream: "trigger", downstream: "send-communication" }
    case "send-communication":
      return { upstream: "decision", downstream: "log" }
    default:
      return { upstream: "trigger", downstream: "next" }
  }
}


function PlaceholderNode({ label }: { label: string }) {
  return (
    <div
      className="flex h-16 w-32 flex-col items-center justify-center rounded-md border border-border-subtle bg-surface-elevated px-3 py-2 opacity-60"
      data-testid="workflow-placeholder-node"
    >
      <div className="text-micro uppercase tracking-wider text-content-muted">
        node
      </div>
      <div className="text-caption font-medium text-content-strong">
        {label}
      </div>
    </div>
  )
}


function ConnectionArrow() {
  return (
    <div
      className="flex items-center"
      data-testid="workflow-connection-arrow"
      aria-hidden="true"
    >
      <div className="h-px w-12 bg-border-base" />
      <div
        className="h-0 w-0"
        style={{
          borderTop: "5px solid transparent",
          borderBottom: "5px solid transparent",
          borderLeft: "8px solid var(--border-base)",
        }}
      />
    </div>
  )
}


function CanvasChrome({ children }: { children: ReactNode }) {
  return (
    <div
      className="relative flex h-full w-full items-center justify-center overflow-auto rounded-md bg-surface-base"
      style={{
        backgroundImage:
          "radial-gradient(circle, var(--border-subtle) 1px, transparent 1px)",
        backgroundSize: "16px 16px",
      }}
      data-testid="workflow-canvas-chrome"
    >
      {children}
    </div>
  )
}


export function WorkflowCanvasContextFrame({
  children,
  nodeType = "default",
  showAllInstances = false,
  renderInstance,
}: Props) {
  const { upstream, downstream } = adjacencyFor(nodeType)

  if (showAllInstances && renderInstance) {
    return (
      <div
        className="flex h-full flex-col gap-3 overflow-auto p-4"
        data-testid="show-all-instances"
      >
        {(["default", "branching", "joining"] as const).map((v) => (
          <div key={v} className="min-h-[140px]" data-testid={`instance-${v}`}>
            <CanvasChrome>
              <div className="flex items-center gap-3 p-6">
                <PlaceholderNode label={upstream} />
                <ConnectionArrow />
                <div
                  className="overflow-hidden rounded-md ring-2 ring-accent ring-offset-2 ring-offset-surface-base"
                  data-testid={`workflow-context-target-${v}`}
                >
                  {renderInstance(v)}
                </div>
                <ConnectionArrow />
                <PlaceholderNode label={downstream} />
              </div>
            </CanvasChrome>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="h-full p-4" data-testid="workflow-canvas-context-frame">
      <CanvasChrome>
        <div className="flex items-center gap-3 p-6">
          <PlaceholderNode label={upstream} />
          <ConnectionArrow />
          <div
            className="overflow-hidden rounded-md ring-2 ring-accent ring-offset-2 ring-offset-surface-base"
            data-testid="workflow-context-target"
          >
            {children}
          </div>
          <ConnectionArrow />
          <PlaceholderNode label={downstream} />
        </div>
      </CanvasChrome>
    </div>
  )
}
