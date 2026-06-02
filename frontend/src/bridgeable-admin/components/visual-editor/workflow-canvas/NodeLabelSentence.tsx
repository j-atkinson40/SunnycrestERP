/**
 * NodeLabelSentence — renders a workflow node's natural-language label
 * sentence. P1 shipped read-only token spans; P2a (2026-05-29) made the
 * SIMPLE-type tokens (string/enum/number/boolean) clickable → a popover
 * anchored to the token → PropControlDispatcher (the bare controlled
 * per-type control) → edit → onEditParam → handleUpdateNode({config}).
 *
 * P2b (2026-05-29) extends the SAME path to the COMPLEX types
 * (object/array/componentReference) via a gate-flip — the dispatcher
 * already renders ObjectControl/ArrayControl/ComponentReferenceControl as
 * controlled components, so widening the editable set makes them clickable
 * with no per-type branching here. The gate is `isTokenInlineEditable`,
 * which ALSO excludes the two bespoke-namespace types
 * (invoke_generation_focus / invoke_review_focus) whose `{focusTemplateName}`
 * token maps to a key their authoring path never writes — those tokens
 * stay read-only (a phantom-key guard; see workflow-node-templates.ts).
 *
 * When `onEditParam` is absent (e.g. detail views, or P1 callers) ALL
 * tokens render read-only — the clickable path is purely additive.
 *
 * Token styling uses existing DESIGN_LANGUAGE tokens only — no new tokens.
 * Falls back to plain text when the type has no template.
 */
import {
  renderModelFor,
  isTokenInlineEditable,
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

/** A clickable token: a popover editor anchored to the token. Reuses
 *  PropControlDispatcher (which dispatches by schema.type — simple OR
 *  complex; P2b), so the right control renders with no per-type branching
 *  here. Persists via onEditParam. stopPropagation guards (onClick +
 *  onPointerDown) mirror the trash button so a token click neither selects
 *  the node nor starts a dnd-kit drag. */
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
        // Roomier than P2a's w-56 — complex controls (ObjectControl's
        // rows=5 textarea, ArrayControl's row list) need the width. The
        // control scrolls within its own borders; max-w-(--available-width)
        // caps the popover at the viewport.
        className="w-80 p-3"
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
        // P2a+P2b: an editable-type token (simple or complex) on a
        // non-bespoke type + an editor callback → clickable popover.
        if (onEditParam && isTokenInlineEditable(nodeType, seg)) {
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
        // Read-only token: no editor callback, a non-editable propType,
        // or a bespoke-namespace type (phantom-key guard).
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
