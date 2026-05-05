/**
 * DocumentContextFrame — renders sample document chrome around a
 * document block being edited.
 *
 * Header blocks render at the top of the page; signature blocks
 * render at the bottom. Other block types render inline. Mock
 * paragraphs frame the block being edited so the operator sees
 * how it sits in a real document.
 */
import type { ReactNode } from "react"


type BlockPosition = "top" | "inline" | "bottom"


interface Props {
  children: ReactNode
  /** Where in the document to anchor the block. */
  position?: BlockPosition
  /** When true, renders three document pages with varied content. */
  showAllInstances?: boolean
  renderInstance?: (variant: "letter" | "invoice" | "certificate") => ReactNode
}


function MockParagraph({ width = "100%" }: { width?: string }) {
  return (
    <div
      className="flex flex-col gap-1.5 opacity-60"
      style={{ width }}
    >
      <div className="h-2 w-full rounded bg-surface-sunken" />
      <div className="h-2 w-full rounded bg-surface-sunken" />
      <div className="h-2 w-3/4 rounded bg-surface-sunken" />
    </div>
  )
}


function DocumentPage({
  position,
  variant,
  children,
}: {
  position: BlockPosition
  variant: string
  children: ReactNode
}) {
  return (
    <div
      className="mx-auto flex h-full w-full max-w-[680px] flex-col gap-5 rounded-md bg-surface-elevated p-10 shadow-level-1"
      style={{ aspectRatio: "8.5 / 11" }}
      data-testid="document-page"
      data-document-variant={variant}
      data-block-position={position}
    >
      {/* Page header / corporate identity strip */}
      <div className="border-b border-border-subtle pb-3">
        <div className="text-h4 font-plex-serif text-content-strong">
          {variant === "invoice"
            ? "Hopkins Funeral Home — Invoice"
            : variant === "certificate"
              ? "Bridgeable — Compliance Certificate"
              : "Hopkins Funeral Home"}
        </div>
        <div className="text-caption text-content-muted">
          1234 Main Street · Auburn, NY · (555) 123-4567
        </div>
      </div>

      {position === "top" ? (
        <>
          <div
            className="overflow-hidden rounded-sm ring-2 ring-accent ring-offset-2 ring-offset-surface-elevated"
            data-testid="document-context-target"
          >
            {children}
          </div>
          <MockParagraph />
          <MockParagraph />
          <MockParagraph width="85%" />
        </>
      ) : position === "bottom" ? (
        <>
          <MockParagraph />
          <MockParagraph />
          <MockParagraph width="85%" />
          <MockParagraph width="60%" />
          <div className="mt-auto" />
          <div
            className="overflow-hidden rounded-sm ring-2 ring-accent ring-offset-2 ring-offset-surface-elevated"
            data-testid="document-context-target"
          >
            {children}
          </div>
        </>
      ) : (
        <>
          <MockParagraph />
          <div
            className="overflow-hidden rounded-sm ring-2 ring-accent ring-offset-2 ring-offset-surface-elevated"
            data-testid="document-context-target"
          >
            {children}
          </div>
          <MockParagraph />
          <MockParagraph width="85%" />
        </>
      )}
    </div>
  )
}


export function DocumentContextFrame({
  children,
  position = "inline",
  showAllInstances = false,
  renderInstance,
}: Props) {
  if (showAllInstances && renderInstance) {
    return (
      <div
        className="grid h-full grid-cols-1 gap-4 overflow-auto bg-surface-base p-4 lg:grid-cols-3"
        data-testid="show-all-instances"
      >
        {(["letter", "invoice", "certificate"] as const).map((v) => (
          <div key={v} data-testid={`instance-${v}`}>
            <DocumentPage position={position} variant={v}>
              {renderInstance(v)}
            </DocumentPage>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div
      className="flex h-full flex-col items-stretch overflow-auto bg-surface-base p-6"
      data-testid="document-context-frame"
    >
      <DocumentPage position={position} variant="letter">
        {children}
      </DocumentPage>
    </div>
  )
}
