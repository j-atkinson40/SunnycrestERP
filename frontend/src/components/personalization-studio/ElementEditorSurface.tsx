/**
 * ElementEditorSurface — canonical per-element-type editing UI surface
 * per Phase 1B canvas implementation + DESIGN_LANGUAGE §14.14.4
 * canonical parametric controls visual canon.
 *
 * **Canonical edit-finish boundary discipline**: editor surfaces commit
 * canonical edit-finish updates to canvas state via canonical
 * `applyElementUpdate` helper. Per Phase A Session 3.8.3 canonical
 * compositor pattern: edit-in-progress is React-component-substrate
 * ephemeral; canvas state mutation happens at canonical edit-finish
 * boundary (canonical operator-decision boundary per §3.26.11.12.16
 * Anti-pattern 1).
 *
 * **Canonical anti-pattern guards explicit**:
 * - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
 *   rejected): editor surface state is React-component-substrate
 *   ephemeral; canonical canvas state at canonical Document substrate
 *   not coupled to canonical editor-surface state
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
 *   rejected): editor commits at canonical Save click; close-without-
 *   save discards draft per canonical operator agency
 */

import { useCallback, useEffect, useState } from "react"
import type { ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import type {
  CanvasElement as CanvasElementType,
} from "@/types/personalization-studio"

import { usePersonalizationCanvasState } from "./canvas-state-context"
import { usePersonalizationStudioTenantConfig } from "./tenant-config-context"

/** Canonical default font catalog — surfaces canonical Phase 1B
 *  canonical-pattern-establisher fallback when canonical Phase 1G
 *  tenant config provider is absent (canonical Storybook / test
 *  scope canonical-fallback). Phase 1G canonical runtime path
 *  context-resolves canonical per-tenant font catalog from canonical
 *  TenantPersonalizationConfig.font_catalog. */
const CANONICAL_FONT_CATALOG = [
  { key: "serif", label: "Serif (Plex Serif)" },
  { key: "sans", label: "Sans (Plex Sans)" },
  { key: "italic", label: "Italic" },
  { key: "uppercase", label: "Uppercase" },
] as const

/** Canonical default font key→label mapping for canonical Phase 1G
 *  context-driven catalog entries (canonical TenantPersonalizationConfig
 *  exposes catalog as canonical key list; canonical labels resolve
 *  via canonical fallback mapping). */
const FONT_LABEL_BY_KEY: Record<string, string> = {
  serif: "Serif (Plex Serif)",
  sans: "Sans (Plex Sans)",
  italic: "Italic",
  uppercase: "Uppercase",
}

/** Canonical default emblem catalog — surfaces canonical Phase 1B
 *  canonical-pattern-establisher fallback when canonical Phase 1G
 *  tenant config provider is absent. */
const CANONICAL_EMBLEM_CATALOG = [
  { key: "rose", label: "Rose" },
  { key: "cross", label: "Cross" },
  { key: "praying_hands", label: "Praying hands" },
  { key: "dove", label: "Dove" },
  { key: "wreath", label: "Wreath" },
] as const

/** Canonical default emblem key→label mapping for canonical Phase 1G
 *  context-driven catalog entries (canonical TenantPersonalizationConfig
 *  exposes catalog as canonical key list; canonical labels resolve via
 *  canonical fallback mapping). Canonical extended catalog beyond
 *  CANONICAL_EMBLEM_CATALOG for canonical Phase 1G context catalog
 *  resolution (canonical default catalog at canonical workshop service
 *  includes canonical star_of_david + canonical masonic + canonical
 *  patriotic_flag canonical-default keys). */
const EMBLEM_LABEL_BY_KEY: Record<string, string> = {
  rose: "Rose",
  cross: "Cross",
  praying_hands: "Praying hands",
  dove: "Dove",
  wreath: "Wreath",
  star_of_david: "Star of David",
  masonic: "Masonic",
  patriotic_flag: "Patriotic flag",
}

export function ElementEditorSurface() {
  const { editing, setEditing, canvasState, applyElementUpdate } =
    usePersonalizationCanvasState()

  if (editing === null) return null

  const element = canvasState.canvas_layout.elements.find(
    (el) => el.id === editing.elementId,
  )
  if (!element) {
    // Defensive: editing element no longer in canvas state — close
    // editor surface canonically.
    setEditing(null)
    return null
  }

  return (
    <div
      data-slot="element-editor-surface"
      data-editor-type={editing.editorType}
      className={cn(
        "rounded-md border border-border-subtle bg-surface-raised p-4 shadow-level-1",
        "flex flex-col gap-3",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="text-caption font-medium uppercase tracking-wider text-content-muted">
          Edit {editorTypeLabel(editing.editorType)}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setEditing(null)}
        >
          Close
        </Button>
      </div>

      {editing.editorType === "font" && (
        <FontEditor element={element} onApply={applyElementUpdate} />
      )}
      {editing.editorType === "emblem" && (
        <EmblemEditor element={element} onApply={applyElementUpdate} />
      )}
      {editing.editorType === "date" && (
        <DateEditor element={element} onApply={applyElementUpdate} />
      )}
      {editing.editorType === "nameplate_text" && (
        <NameplateTextEditor element={element} onApply={applyElementUpdate} />
      )}
    </div>
  )
}

function editorTypeLabel(t: "font" | "emblem" | "date" | "nameplate_text"): string {
  switch (t) {
    case "font":
      return "name + font"
    case "emblem":
      return "emblem"
    case "date":
      return "dates"
    case "nameplate_text":
      return "nameplate text"
  }
}

// ─────────────────────────────────────────────────────────────────────
// Per-canonical-editor-type editor components
// ─────────────────────────────────────────────────────────────────────

interface EditorProps {
  element: CanvasElementType
  onApply: (
    elementId: string,
    update: Partial<CanvasElementType>,
  ) => void
}

function FontEditor({ element, onApply }: EditorProps) {
  const config = (element.config ?? {}) as {
    name_display?: string
    font?: string
  }
  const [name, setName] = useState(config.name_display ?? "")
  const [font, setFont] = useState(config.font ?? "serif")

  useEffect(() => {
    setName(config.name_display ?? "")
    setFont(config.font ?? "serif")
  }, [config.name_display, config.font])

  const handleSave = useCallback(() => {
    onApply(element.id, {
      config: { ...config, name_display: name, font },
    })
  }, [config, element.id, font, name, onApply])

  // Phase 1G — canonical chrome-canvas runtime wiring. Context-resolved
  // per-tenant font catalog canonical-flows from canonical
  // PersonalizationStudioTenantConfigProvider when canonical provider
  // is present. Canonical fallback to canonical CANONICAL_FONT_CATALOG
  // at canonical Storybook / test scope canonical-bypass.
  const tenantConfig = usePersonalizationStudioTenantConfig()
  const fontCatalog = tenantConfig?.config?.font_catalog
  const resolvedFontCatalog = fontCatalog
    ? fontCatalog.map((key) => ({
        key,
        label: FONT_LABEL_BY_KEY[key] ?? key,
      }))
    : CANONICAL_FONT_CATALOG

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Name</span>
        <Input
          value={name}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
          placeholder="Decedent name"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Font</span>
        <select
          value={font}
          onChange={(e) => setFont(e.target.value)}
          data-testid="font-editor-select"
          className="rounded-md border border-border-base bg-surface-base px-3 py-2 text-body-sm"
        >
          {resolvedFontCatalog.map((f) => (
            <option key={f.key} value={f.key}>
              {f.label}
            </option>
          ))}
        </select>
      </label>
      <div className="flex justify-end">
        <Button type="button" onClick={handleSave}>
          Save
        </Button>
      </div>
    </div>
  )
}

function EmblemEditor({ element, onApply }: EditorProps) {
  const config = (element.config ?? {}) as { emblem_key?: string }
  const [emblemKey, setEmblemKey] = useState(config.emblem_key ?? "")

  useEffect(() => {
    setEmblemKey(config.emblem_key ?? "")
  }, [config.emblem_key])

  const handleSave = useCallback(() => {
    onApply(element.id, { config: { ...config, emblem_key: emblemKey } })
  }, [config, element.id, emblemKey, onApply])

  // Phase 1G — canonical chrome-canvas runtime wiring. Context-resolved
  // per-tenant emblem catalog canonical-flows from canonical
  // PersonalizationStudioTenantConfigProvider when canonical provider is
  // present. Canonical fallback to canonical CANONICAL_EMBLEM_CATALOG at
  // canonical Storybook / test scope canonical-bypass.
  const tenantConfig = usePersonalizationStudioTenantConfig()
  const emblemCatalog = tenantConfig?.config?.emblem_catalog
  const resolvedEmblemCatalog = emblemCatalog
    ? emblemCatalog.map((key) => ({
        key,
        label: EMBLEM_LABEL_BY_KEY[key] ?? key,
      }))
    : CANONICAL_EMBLEM_CATALOG

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2" data-testid="emblem-editor-grid">
        {resolvedEmblemCatalog.map((emblem) => {
          const active = emblem.key === emblemKey
          return (
            <button
              key={emblem.key}
              type="button"
              data-emblem-key={emblem.key}
              data-active={active ? "true" : "false"}
              onClick={() => setEmblemKey(emblem.key)}
              className={cn(
                "rounded-md border p-3 text-caption text-content-strong",
                active
                  ? "border-accent bg-accent-subtle/30"
                  : "border-border-base bg-surface-base hover:bg-surface-elevated",
              )}
            >
              {emblem.label}
            </button>
          )
        })}
      </div>
      <div className="flex justify-end">
        <Button type="button" onClick={handleSave}>
          Save
        </Button>
      </div>
    </div>
  )
}

function DateEditor({ element, onApply }: EditorProps) {
  const config = (element.config ?? {}) as {
    birth_date_display?: string
    death_date_display?: string
  }
  const [birth, setBirth] = useState(config.birth_date_display ?? "")
  const [death, setDeath] = useState(config.death_date_display ?? "")

  useEffect(() => {
    setBirth(config.birth_date_display ?? "")
    setDeath(config.death_date_display ?? "")
  }, [config.birth_date_display, config.death_date_display])

  const handleSave = useCallback(() => {
    onApply(element.id, {
      config: {
        ...config,
        birth_date_display: birth,
        death_date_display: death,
      },
    })
  }, [birth, config, death, element.id, onApply])

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Birth date</span>
        <Input
          value={birth}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setBirth(e.target.value)}
          placeholder="MM/DD/YYYY"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Death date</span>
        <Input
          value={death}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setDeath(e.target.value)}
          placeholder="MM/DD/YYYY"
        />
      </label>
      <div className="flex justify-end">
        <Button type="button" onClick={handleSave}>
          Save
        </Button>
      </div>
    </div>
  )
}

function NameplateTextEditor({ element, onApply }: EditorProps) {
  const config = (element.config ?? {}) as { nameplate_text?: string }
  const [text, setText] = useState(config.nameplate_text ?? "")

  useEffect(() => {
    setText(config.nameplate_text ?? "")
  }, [config.nameplate_text])

  const handleSave = useCallback(() => {
    onApply(element.id, { config: { ...config, nameplate_text: text } })
  }, [config, element.id, onApply, text])

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">Nameplate text</span>
        <Input
          value={text}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setText(e.target.value)}
          placeholder="Text engraved on nameplate"
        />
      </label>
      <div className="flex justify-end">
        <Button type="button" onClick={handleSave}>
          Save
        </Button>
      </div>
    </div>
  )
}
