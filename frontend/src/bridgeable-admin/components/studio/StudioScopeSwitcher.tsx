/**
 * StudioScopeSwitcher — top-bar scope picker.
 *
 * Lists "Platform" + every published vertical from
 * `/api/platform/admin/verticals/`. Active scope is derived from the
 * Studio shell's parsed URL. Clicking a scope navigates to either the
 * Platform overview (`/studio`), a vertical overview
 * (`/studio/:vertical`), or — if currently inside an editor — the
 * same editor at the new scope (`/studio/:vertical/:editor`), modulo
 * Platform-only editors which always stay at Platform scope.
 *
 * Studio 1a-i.A1 substrate. Renders inside StudioTopBar.
 */
import { useEffect, useState } from "react"
import { ChevronDown, Globe } from "lucide-react"
import { useNavigate } from "react-router-dom"
import {
  verticalsService,
  type Vertical,
} from "@/bridgeable-admin/services/verticals-service"
import {
  PLATFORM_ONLY_EDITORS,
  studioPath,
  writeLastVertical,
  type StudioEditorKey,
} from "@/bridgeable-admin/lib/studio-routes"


export interface StudioScopeSwitcherProps {
  /** Currently active vertical slug. null = Platform scope. */
  activeVertical: string | null
  /** Currently active editor key (drives "preserve editor on scope change"). */
  activeEditor: StudioEditorKey | null
  /** If true, render disabled (e.g. Live mode locks scope to tenant's vertical). */
  disabled?: boolean
  /**
   * Studio 1a-i.A2 — when true, render as a static read-only readout
   * rather than a dropdown. Used in Live mode where scope is determined
   * by the impersonated tenant's `Company.vertical`, not authored.
   */
  readOnly?: boolean
  /**
   * Studio 1a-i.A2 — supplemental description rendered in read-only
   * mode (e.g. "Vertical: manufacturing — via tenant testco"). When
   * omitted in readOnly mode, falls back to the activeLabel alone.
   */
  liveModeDescription?: string | null
}


export function StudioScopeSwitcher({
  activeVertical,
  activeEditor,
  disabled = false,
  readOnly = false,
  liveModeDescription = null,
}: StudioScopeSwitcherProps) {
  const [verticals, setVerticals] = useState<Vertical[]>([])
  const [open, setOpen] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    verticalsService
      .list()
      .then((rows) => {
        if (cancelled) return
        setVerticals(rows.filter((r) => r.status !== "archived"))
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err?.message ?? "Failed to load verticals")
      })
    return () => {
      cancelled = true
    }
  }, [])

  const switchTo = (slug: string | null) => {
    setOpen(false)
    writeLastVertical(slug)
    // Preserve editor across scope change unless it's platform-only.
    const editor =
      activeEditor &&
      !(slug && PLATFORM_ONLY_EDITORS.has(activeEditor))
        ? activeEditor
        : null
    // If platform-only editor + switching to vertical: keep editor +
    // drop vertical (studioPath will drop the vertical anyway).
    navigate(studioPath({ vertical: slug, editor }))
  }

  const activeLabel =
    activeVertical === null
      ? "Platform"
      : verticals.find((v) => v.slug === activeVertical)?.display_name ??
        activeVertical

  if (readOnly) {
    const display = liveModeDescription
      ? liveModeDescription
      : activeVertical === null
        ? "(pick a tenant)"
        : `Vertical: ${activeLabel}`
    return (
      <div
        data-testid="studio-scope-switcher"
        data-active-vertical={activeVertical ?? "platform"}
        data-read-only="true"
        className="flex items-center gap-1.5 rounded-sm bg-surface-sunken px-3 py-1.5 text-body-sm text-content-muted"
      >
        <Globe size={14} className="text-content-subtle" />
        <span>{display}</span>
      </div>
    )
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        data-testid="studio-scope-switcher"
        data-active-vertical={activeVertical ?? "platform"}
        className={
          disabled
            ? "flex items-center gap-1.5 rounded-sm bg-surface-sunken px-3 py-1.5 text-body-sm text-content-muted opacity-60"
            : "flex items-center gap-1.5 rounded-sm border border-border-subtle bg-surface-elevated px-3 py-1.5 text-body-sm text-content-strong hover:border-accent"
        }
      >
        <Globe size={14} className="text-accent" />
        <span>{activeLabel}</span>
        <ChevronDown size={14} className="text-content-muted" />
      </button>
      {open && !disabled && (
        <div
          className="absolute left-0 top-full z-40 mt-1 min-w-[200px] rounded-sm border border-border-subtle bg-surface-elevated shadow-level-2"
          data-testid="studio-scope-switcher-menu"
        >
          <ScopeItem
            label="Platform"
            sublabel="Cross-vertical defaults"
            active={activeVertical === null}
            onClick={() => switchTo(null)}
            testId="studio-scope-item-platform"
          />
          {verticals.length === 0 && !loadError && (
            <div className="px-3 py-2 text-caption text-content-muted">
              Loading verticals…
            </div>
          )}
          {loadError && (
            <div className="px-3 py-2 text-caption text-status-error">
              {loadError}
            </div>
          )}
          {verticals.map((v) => (
            <ScopeItem
              key={v.slug}
              label={v.display_name}
              sublabel={v.slug}
              active={activeVertical === v.slug}
              onClick={() => switchTo(v.slug)}
              testId={`studio-scope-item-${v.slug}`}
            />
          ))}
        </div>
      )}
    </div>
  )
}


interface ScopeItemProps {
  label: string
  sublabel: string
  active: boolean
  onClick: () => void
  testId: string
}


function ScopeItem({ label, sublabel, active, onClick, testId }: ScopeItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      data-active={active ? "true" : "false"}
      className={
        active
          ? "flex w-full flex-col items-start gap-0 bg-accent-subtle px-3 py-2 text-left text-body-sm text-accent"
          : "flex w-full flex-col items-start gap-0 px-3 py-2 text-left text-body-sm text-content-strong hover:bg-accent-subtle/40"
      }
    >
      <span className="font-medium">{label}</span>
      <span className="text-caption text-content-muted font-plex-mono">
        {sublabel}
      </span>
    </button>
  )
}
