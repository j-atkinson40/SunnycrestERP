/**
 * NodeLabelSentence — renders a workflow node's natural-language label
 * sentence. P1 shipped read-only token spans; P2a (2026-05-29) makes the
 * SIMPLE-type tokens (string/enum/number/boolean) clickable → a popover
 * anchored to the token → PropControlDispatcher (the bare controlled
 * per-type control) → edit → onEditParam → handleUpdateNode({config}).
 *
 * COMPLEX tokens (object/array/componentReference) stay read-only in P2a
 * (P2b makes them clickable). When `onEditParam` is absent (e.g. detail
 * views, or P1 callers) ALL tokens render read-only — the clickable path
 * is purely additive.
 *
 * Token styling uses existing DESIGN_LANGUAGE tokens only — no new tokens.
 * Falls back to plain text when the type has no template.
 */
import {
  renderModelFor,
  isEditableToken,
  nodeConfigProps,
  type RenderedSegment,
  type RenderedToken,
} from "@/lib/visual-editor/workflow-node-templates"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { PropControlDispatcher } from "@/lib/visual-editor/components/PropControls"

export interface NodeLabelSentenceProps {
  nodeId: string
  nodeType: string
  config: Record<string, unknown>
  /** Fallback text when the type has no template (raw node label). */
  fallback?: string
  /**
   * P2a: edit a config param inline. When provided, simple-type tokens
   * become clickable popover editors. Absent → all tokens read-only.
   */
  onEditParam?: (param: string, value: unknown) => void
}

/** Read-only token span (P1 styling): accent chip for values, dashed
 *  dimmed chip for unset placeholders. */
function readOnlyTokenClass(token: RenderedToken): string {
  return token.placeholder
    ? "mx-0.5 rounded-sm border border-dashed border-border-base px-1 text-content-muted"
    : "mx-0.5 rounded-sm border border-accent/30 bg-accent-subtle px-1 text-content-strong"
}

/** A clickable simple-type token: a popover editor anchored to the token.
 *  Reuses PropControlDispatcher; persists via onEditParam. stopPropagation
 *  guards (onClick + onPointerDown) mirror the trash button so a token
 *  click neither selects the node nor starts a dnd-kit drag. */
function EditableToken({
  nodeId,
  nodeType,
  config,
  token,
  onEditParam,
}: {
  nodeId: string
  nodeType: string
  config: Record<string, unknown>
  token: RenderedToken
  onEditParam: (param: string, value: unknown) => void
}) {
  const schema = nodeConfigProps(nodeType)[token.param]
  // Seed unset params from the schema default so the editor opens with a
  // sensible initial (not undefined). Edit → merge ADDS the key.
  const current =
    token.param in config ? config[token.param] : schema?.default

  const stop = (ev: { stopPropagation: () => void }) => ev.stopPropagation()

  return (
    <Popover>
      <PopoverTrigger
        render={
          <span
            role="button"
            tabIndex={0}
            data-testid={`node-token-${nodeId}-${token.param}`}
            data-token-param={token.param}
            data-token-placeholder={token.placeholder ? "true" : "false"}
            data-token-editable="true"
            onClick={stop}
            onPointerDown={stop}
            className={
              token.placeholder
                ? "mx-0.5 cursor-pointer rounded-sm border border-dashed border-border-base px-1 text-content-muted hover:border-accent hover:text-content-strong"
                : "mx-0.5 cursor-pointer rounded-sm border border-accent/30 bg-accent-subtle px-1 text-content-strong hover:border-accent"
            }
          >
            {token.text}
          </span>
        }
      />
      <PopoverContent
        className="w-56 p-3"
        // Keep the popover's own interactions from bubbling to the canvas.
        onClick={stop}
        onPointerDown={stop}
      >
        {schema && (
          <PropControlDispatcher
            schema={schema}
            value={current}
            onChange={(next) => onEditParam(token.param, next)}
            data-testid={`node-token-editor-${nodeId}-${token.param}`}
          />
        )}
      </PopoverContent>
    </Popover>
  )
}

export function NodeLabelSentence({
  nodeId,
  nodeType,
  config,
  fallback,
  onEditParam,
}: NodeLabelSentenceProps) {
  const model = renderModelFor(nodeType, config)

  // No template for this type → plain fallback text (raw label / type).
  if (model === null) {
    return (
      <span
        data-testid={`node-sentence-${nodeId}`}
        className="text-caption text-content-strong"
      >
        {fallback ?? nodeType}
      </span>
    )
  }

  return (
    <span
      data-testid={`node-sentence-${nodeId}`}
      className="text-caption leading-relaxed text-content-strong"
    >
      {model.map((seg: RenderedSegment, i) => {
        if (seg.kind === "literal") return <span key={i}>{seg.text}</span>
        // P2a: simple-type token + an editor callback → clickable popover.
        if (onEditParam && isEditableToken(seg)) {
          return (
            <EditableToken
              key={i}
              nodeId={nodeId}
              nodeType={nodeType}
              config={config}
              token={seg}
              onEditParam={onEditParam}
            />
          )
        }
        // Read-only token (complex types, or no editor callback).
        return (
          <span
            key={i}
            data-testid={`node-token-${nodeId}-${seg.param}`}
            data-token-param={seg.param}
            data-token-placeholder={seg.placeholder ? "true" : "false"}
            data-token-editable="false"
            className={readOnlyTokenClass(seg)}
          >
            {seg.text}
          </span>
        )
      })}
    </span>
  )
}
