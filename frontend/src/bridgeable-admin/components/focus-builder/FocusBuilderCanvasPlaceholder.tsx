/**
 * FocusBuilderCanvasPlaceholder — read-only canvas surface for F-1.
 *
 * Loads the selected subject (core or template) via service GETs and
 * renders a minimal preview card with identity metadata. Real canvas
 * composition (substrate / chrome / placements / widgets / live
 * preview) lands in F-2 + F-3 atop the same selection contract.
 */
import * as React from "react"

import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"
import {
  focusTemplatesService,
  type TemplateRecord,
} from "@/bridgeable-admin/services/focus-templates-service"

import type { FocusBuilderSubject } from "./FocusBuilderTree"


export interface FocusBuilderCanvasPlaceholderProps {
  subject: FocusBuilderSubject | null
}


export function FocusBuilderCanvasPlaceholder({
  subject,
}: FocusBuilderCanvasPlaceholderProps) {
  const [core, setCore] = React.useState<CoreRecord | null>(null)
  const [template, setTemplate] = React.useState<TemplateRecord | null>(null)
  const [inheritedCore, setInheritedCore] = React.useState<CoreRecord | null>(
    null,
  )
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    setError(null)
    if (!subject) {
      setCore(null)
      setTemplate(null)
      setInheritedCore(null)
      return
    }
    let cancelled = false
    setLoading(true)
    const promise: Promise<void> =
      subject.kind === "core"
        ? focusCoresService.get(subject.id).then((c) => {
            if (cancelled) return
            setCore(c)
            setTemplate(null)
            setInheritedCore(null)
          })
        : focusTemplatesService.get(subject.id).then(async (t) => {
            if (cancelled) return
            setTemplate(t)
            setCore(null)
            try {
              const ic = await focusCoresService.get(t.inherits_from_core_id)
              if (cancelled) return
              setInheritedCore(ic)
            } catch {
              if (cancelled) return
              setInheritedCore(null)
            }
          })

    promise
      .catch((e: unknown) => {
        if (cancelled) return
        const msg = e instanceof Error ? e.message : "Failed to load subject."
        setError(msg)
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [subject])

  if (!subject) {
    return (
      <div
        className="grid h-full place-items-center text-[13px] text-content-muted"
        data-testid="focus-builder-canvas-empty"
      >
        Select a focus from the tree to preview.
      </div>
    )
  }

  if (loading) {
    return (
      <div
        className="grid h-full place-items-center text-[13px] text-content-muted"
        data-testid="focus-builder-canvas-loading"
      >
        Loading preview…
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="grid h-full place-items-center text-[13px] text-status-error"
        data-testid="focus-builder-canvas-error"
      >
        {error}
      </div>
    )
  }

  if (subject.kind === "core" && core) {
    return (
      <div
        className="grid h-full place-items-center px-8 py-8"
        data-testid="focus-builder-canvas-core"
      >
        <div className="max-w-md rounded-xl bg-surface-elevated p-6 shadow-[var(--shadow-level-1)]">
          <div className="mb-1 text-[11px] uppercase tracking-wider text-content-muted">
            Canonical core
          </div>
          <div className="mb-2 text-[20px] font-medium text-content-strong">
            {core.display_name}
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12px]">
            <dt className="text-content-muted">Slug</dt>
            <dd className="font-plex-mono">{core.core_slug}</dd>
            <dt className="text-content-muted">Version</dt>
            <dd className="font-plex-mono">v{core.version}</dd>
            <dt className="text-content-muted">Chrome preset</dt>
            <dd className="font-plex-mono">
              {(core.chrome?.preset as string) ?? "—"}
            </dd>
          </dl>
        </div>
      </div>
    )
  }

  if (subject.kind === "template" && template) {
    return (
      <div
        className="grid h-full place-items-center px-8 py-8"
        data-testid="focus-builder-canvas-template"
      >
        <div className="max-w-md rounded-xl bg-surface-elevated p-6 shadow-[var(--shadow-level-1)]">
          <div className="mb-1 text-[11px] uppercase tracking-wider text-content-muted">
            Variant of {inheritedCore?.display_name ?? "core"}
          </div>
          <div className="mb-2 text-[20px] font-medium text-content-strong">
            {template.display_name}
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12px]">
            <dt className="text-content-muted">Slug</dt>
            <dd className="font-plex-mono">{template.template_slug}</dd>
            <dt className="text-content-muted">Scope</dt>
            <dd className="font-plex-mono">
              {template.scope}
              {template.vertical ? ` · ${template.vertical}` : ""}
            </dd>
            <dt className="text-content-muted">Version</dt>
            <dd className="font-plex-mono">v{template.version}</dd>
            <dt className="text-content-muted">Inherits from</dt>
            <dd className="font-plex-mono">
              {inheritedCore?.core_slug ?? template.inherits_from_core_id} (v
              {template.inherits_from_core_version})
            </dd>
          </dl>
        </div>
      </div>
    )
  }

  return null
}

export default FocusBuilderCanvasPlaceholder
