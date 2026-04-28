/**
 * OperatorOnboardingFlow — Phase W-4a operator onboarding surface.
 *
 * Captures `work_areas` (multi-select cards) + `responsibilities_description`
 * (free-text textarea with debounced auto-save) per BRIDGEABLE_MASTER
 * §3.26.3 + DESIGN_LANGUAGE §13.6.
 *
 * Two save paths:
 *  • Auto-save: Textarea onChange flushes after 1s idle (debounced).
 *    Card click toggles save immediately.
 *  • Save-and-continue: explicit button stamps
 *    `preferences.onboarding_touches.operator_profile = true` so the
 *    PulseSurface first-login banner stops appearing.
 *
 * Visual contract per DESIGN_LANGUAGE §13.6:
 *  • Multi-select cards with brass border + filled background on
 *    selection
 *  • Multi-line textarea calibrated for 3-5 sentences
 *  • Subtle "saving" / "saved" indicator
 *  • "Skip for now" affordance — sets onboarding_completed without
 *    requiring at least one work area (vertical-default fallback
 *    handles the empty case)
 *
 * Page lives at `/onboarding/operator-profile`. Reachable via direct
 * URL today; PulseSurface (Phase W-4a Commit 5) will surface a banner
 * pointing here when `onboarding_completed === false`.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Check, Loader2, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { SkeletonLines } from "@/components/ui/skeleton"
import { InlineError } from "@/components/ui/inline-error"
import { cn } from "@/lib/utils"
import {
  getOperatorProfile,
  updateOperatorProfile,
} from "@/services/operator-profile-service"
import type { OperatorProfile } from "@/types/operator-profile"


const RESPONSIBILITIES_PLACEHOLDER =
  "Tell us about your day-to-day. What do you do, " +
  "what do you watch out for, what do you wish you " +
  "had better visibility into?"


type SaveState = "idle" | "saving" | "saved" | "error"


export default function OperatorOnboardingFlow() {
  const navigate = useNavigate()
  const [profile, setProfile] = useState<OperatorProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Form state — local, flushed to backend on auto-save / explicit
  // save. Initialized from server state on mount.
  const [selectedAreas, setSelectedAreas] = useState<string[]>([])
  const [responsibilities, setResponsibilities] = useState<string>("")
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const [saveError, setSaveError] = useState<string | null>(null)

  // Debounce ref for textarea auto-save — module-scoped timer would
  // create cross-mount cancellation issues; per-mount ref is correct.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedTextRef = useRef<string>("")
  const lastSavedAreasRef = useRef<string[]>([])

  // ── Load on mount ───────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false
    getOperatorProfile()
      .then((p) => {
        if (cancelled) return
        setProfile(p)
        setSelectedAreas(p.work_areas)
        setResponsibilities(p.responsibilities_description ?? "")
        lastSavedAreasRef.current = p.work_areas
        lastSavedTextRef.current = p.responsibilities_description ?? ""
        setLoading(false)
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(
          err instanceof Error
            ? err.message
            : "Failed to load profile.",
        )
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // ── Save helpers ────────────────────────────────────────────────

  const flushSave = useCallback(
    async ({
      areas,
      text,
      finalize,
    }: {
      areas?: string[]
      text?: string
      finalize?: boolean
    }) => {
      setSaveState("saving")
      setSaveError(null)
      try {
        const body: Parameters<typeof updateOperatorProfile>[0] = {}
        if (areas !== undefined) body.work_areas = areas
        if (text !== undefined)
          body.responsibilities_description = text === "" ? null : text
        if (finalize) body.mark_onboarding_complete = true
        const updated = await updateOperatorProfile(body)
        setProfile(updated)
        if (areas !== undefined) lastSavedAreasRef.current = areas
        if (text !== undefined) lastSavedTextRef.current = text
        setSaveState("saved")
        // Soft-decay the "saved" indicator after 2s.
        setTimeout(() => {
          setSaveState((s) => (s === "saved" ? "idle" : s))
        }, 2000)
      } catch (err) {
        setSaveState("error")
        setSaveError(
          err instanceof Error ? err.message : "Failed to save.",
        )
      }
    },
    [],
  )

  // ── Card click handler — immediate save ─────────────────────────

  const handleToggleArea = useCallback(
    (area: string) => {
      const next = selectedAreas.includes(area)
        ? selectedAreas.filter((a) => a !== area)
        : [...selectedAreas, area].sort()
      setSelectedAreas(next)
      // Cancel any in-flight textarea debounce (we're saving anyway).
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
      void flushSave({ areas: next })
    },
    [selectedAreas, flushSave],
  )

  // ── Textarea change — debounced save ────────────────────────────

  const handleResponsibilitiesChange = useCallback(
    (value: string) => {
      setResponsibilities(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        if (value !== lastSavedTextRef.current) {
          void flushSave({ text: value })
        }
      }, 1000)
    },
    [flushSave],
  )

  // Cleanup pending debounce on unmount.
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  // ── Save-and-continue + Skip handlers ───────────────────────────

  const handleSaveAndContinue = useCallback(async () => {
    // Flush pending changes + stamp the onboarding-complete touch.
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    const areasChanged =
      JSON.stringify(selectedAreas) !==
      JSON.stringify(lastSavedAreasRef.current)
    const textChanged = responsibilities !== lastSavedTextRef.current
    await flushSave({
      areas: areasChanged ? selectedAreas : undefined,
      text: textChanged ? responsibilities : undefined,
      finalize: true,
    })
    navigate("/")
  }, [selectedAreas, responsibilities, flushSave, navigate])

  const handleSkip = useCallback(async () => {
    // Stamp the onboarding-complete flag without requiring areas —
    // user explicitly chose to skip; vertical-default Pulse fallback
    // (D4) handles the empty-work_areas case.
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    await flushSave({ finalize: true })
    navigate("/")
  }, [flushSave, navigate])

  const remainingChars = useMemo(() => {
    return Math.max(0, 2000 - responsibilities.length)
  }, [responsibilities])

  // ── Render ──────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <SkeletonLines count={6} />
      </div>
    )
  }
  if (loadError || !profile) {
    return (
      <div className="mx-auto max-w-3xl p-8">
        <InlineError
          message="Couldn't load your profile."
          hint={loadError ?? undefined}
          onRetry={() => window.location.reload()}
        />
      </div>
    )
  }

  return (
    <div
      className="mx-auto max-w-3xl p-6 sm:p-8 space-y-8"
      data-slot="operator-onboarding-flow"
    >
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-accent">
          <Sparkles className="h-5 w-5" aria-hidden />
          <span className="text-caption font-sans uppercase tracking-wide">
            Personalize your Pulse
          </span>
        </div>
        <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
          Tell us what you do
        </h1>
        <p className="text-body text-content-muted font-sans max-w-prose">
          Bridgeable's Home Pulse composes intelligently around your
          work. Pick the areas you cover and share a few sentences about
          your day. We'll use this to surface what matters most.
        </p>
      </header>

      {/* Work areas multi-select */}
      <section className="space-y-3" data-slot="work-areas-section">
        <Label className="text-body-sm font-medium text-content-strong">
          Work areas
          <span className="ml-2 text-caption font-normal text-content-muted">
            select all that apply
          </span>
        </Label>
        <div
          role="group"
          aria-label="Work areas"
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2"
        >
          {profile.available_work_areas.map((area) => {
            const selected = selectedAreas.includes(area)
            return (
              <button
                key={area}
                type="button"
                role="checkbox"
                aria-checked={selected}
                onClick={() => handleToggleArea(area)}
                data-slot="work-area-card"
                data-area={area}
                data-selected={selected ? "true" : "false"}
                className={cn(
                  "flex items-center gap-2 px-3 py-3 rounded-md border text-left",
                  "text-body-sm font-sans text-content-base",
                  "transition-colors duration-quick ease-settle",
                  "focus-ring-accent outline-none",
                  selected
                    ? "border-accent bg-accent-subtle text-content-strong"
                    : "border-border-base bg-surface-elevated hover:border-accent/50 hover:bg-surface-muted",
                )}
              >
                <span
                  className={cn(
                    "flex h-4 w-4 items-center justify-center rounded-sm border flex-shrink-0",
                    selected
                      ? "border-accent bg-accent text-content-on-accent"
                      : "border-border-base bg-surface-base",
                  )}
                  aria-hidden
                >
                  {selected ? <Check className="h-3 w-3" /> : null}
                </span>
                <span className="flex-1">{area}</span>
              </button>
            )
          })}
        </div>
      </section>

      {/* Responsibilities textarea */}
      <section
        className="space-y-2"
        data-slot="responsibilities-section"
      >
        <Label
          htmlFor="responsibilities"
          className="text-body-sm font-medium text-content-strong"
        >
          Your day-to-day
          <span className="ml-2 text-caption font-normal text-content-muted">
            optional but recommended
          </span>
        </Label>
        <Textarea
          id="responsibilities"
          rows={5}
          maxLength={2000}
          placeholder={RESPONSIBILITIES_PLACEHOLDER}
          value={responsibilities}
          onChange={(e) =>
            handleResponsibilitiesChange(e.currentTarget.value)
          }
          data-slot="responsibilities-textarea"
        />
        <div className="flex items-center justify-between">
          <span
            className="text-caption font-sans text-content-muted"
            data-slot="save-state-indicator"
          >
            {saveState === "saving" ? (
              <span className="inline-flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                Saving…
              </span>
            ) : saveState === "saved" ? (
              <span className="inline-flex items-center gap-1 text-status-success">
                <Check className="h-3 w-3" aria-hidden />
                Saved
              </span>
            ) : saveState === "error" ? (
              <span className="text-status-error">
                Save failed. {saveError ?? "Try again."}
              </span>
            ) : (
              <span className="invisible">·</span>
            )}
          </span>
          <span
            className="text-caption font-plex-mono text-content-subtle"
            aria-label={`${remainingChars} characters remaining`}
          >
            {remainingChars}
          </span>
        </div>
      </section>

      {/* Footer actions */}
      <footer className="flex items-center justify-between pt-4 border-t border-border-subtle">
        <Button
          variant="ghost"
          onClick={handleSkip}
          disabled={saveState === "saving"}
          data-slot="skip-button"
        >
          Skip for now
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            render={<Link to="/" />}
            data-slot="cancel-button"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSaveAndContinue}
            disabled={saveState === "saving"}
            data-slot="save-continue-button"
          >
            Save and continue
          </Button>
        </div>
      </footer>
    </div>
  )
}
