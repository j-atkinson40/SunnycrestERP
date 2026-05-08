/**
 * R-4.0 — RegisteredButton.
 *
 * Click target for placement-mounted buttons. Reads its registration
 * metadata from the visual-editor registry via the slug provided as
 * `componentName`. Resolves parameter bindings at click-time via
 * React hooks. Optionally opens a confirmation Dialog before
 * dispatching. Routes the dispatch result through the per-button
 * `successBehavior` (stay / navigate / toast).
 *
 * Three example registrations live at
 * `lib/visual-editor/registry/registrations/buttons.ts`. Each
 * declares an R-4 contract under `extensions.r4`.
 *
 * Render contract:
 *   - The wrapped Button primitive carries variant/size from
 *     `prop_overrides` (with registration defaults as fallback).
 *   - Label text from `prop_overrides.label` (with registration
 *     default).
 *   - Icon position from registration class metadata (R-2.0 class-
 *     configuration phase already authored these for the button
 *     class). R-4.0 reads the per-button `iconName` if set.
 *
 * Composition renderer dispatch:
 *   - `CompositionRenderer.tsx::renderRuntimePlacement` extended in
 *     R-4.0 to dispatch `component_kind: "button"` placements to
 *     this component (per the renderer-dispatch probe finding —
 *     /tmp/r4_0_renderer_dispatch_probe.md). Single-registry path
 *     extended; no parallel button-renderers map needed.
 */

import { useCallback, useState } from "react"
import {
  AlertTriangle,
  CalendarPlus,
  Home,
  Workflow,
  type LucideIcon,
} from "lucide-react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useAuth } from "@/contexts/auth-context"
import { useFocus } from "@/contexts/focus-context"
import { useEdgePanelOptional } from "@/lib/edge-panel/EdgePanelProvider"
import { getByName } from "@/lib/visual-editor/registry"

import { dispatchAction } from "./action-dispatch"
import {
  resolveBindings,
  type BindingContext,
} from "./parameter-resolver"
import type { R4ButtonContract } from "./types"


export interface RegisteredButtonProps {
  /** Slug — e.g. "open-funeral-scheduling-focus". Looked up against
   *  the `entity-card`-shaped registry; missing slugs surface a
   *  graceful error state rather than crashing. */
  componentName: string
  /** Per-placement prop overrides. Composition placement carries
   *  these from the visual editor's authoring surface. Common keys:
   *  `label`, `variant`, `size`, `iconName`, `disabled`. */
  propOverrides?: Record<string, unknown>
}


// Curated icon map — keeps lucide-react tree-shaking working. Adding
// a new iconName to a button registration requires adding the named
// import + map entry here. Keeps the bundle delta bounded.
const ICON_MAP: Record<string, LucideIcon> = {
  AlertTriangle,
  CalendarPlus,
  Home,
  Workflow,
}

function resolveIcon(name: string | undefined): LucideIcon | null {
  if (!name) return null
  return ICON_MAP[name] ?? null
}


export function RegisteredButton({
  componentName,
  propOverrides,
}: RegisteredButtonProps) {
  const entry = getByName("button", componentName)
  const navigate = useNavigate()
  const focus = useFocus()
  const { user, company } = useAuth()
  const routeParams = useParams()
  const [searchParams] = useSearchParams()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pending, setPending] = useState(false)
  // R-5.0 — when this button is rendered inside the EdgePanel, auto-
  // close the panel after a successful dispatch (per close-on-fire
  // pattern). useEdgePanelOptional returns null outside the provider
  // tree, which is the canonical "not in an edge panel" case.
  const edgePanel = useEdgePanelOptional()

  // Pull the R-4 contract off the registration. Missing slug or
  // registration without an R-4 contract surfaces visibly rather
  // than rendering a no-op button.
  const contract = entry?.metadata.extensions?.r4 as
    | R4ButtonContract
    | undefined

  // Compose render-time props from registration defaults overlaid
  // by per-placement overrides. Both layers are optional; per-
  // placement always wins where set.
  const overrides = propOverrides ?? {}
  const defaults = (entry?.metadata.configurableProps ?? {}) as Record<
    string,
    { default?: unknown }
  >
  const propValue = (key: string): unknown =>
    key in overrides ? overrides[key] : defaults[key]?.default

  const label =
    (propValue("label") as string | undefined) ??
    entry?.metadata.displayName ??
    componentName
  const variantRaw = propValue("variant")
  const variant =
    typeof variantRaw === "string"
      ? (variantRaw as
          | "default"
          | "secondary"
          | "outline"
          | "ghost"
          | "destructive"
          | "link")
      : "default"
  const sizeRaw = propValue("size")
  const size =
    typeof sizeRaw === "string"
      ? (sizeRaw as
          | "default"
          | "xs"
          | "sm"
          | "lg"
          | "icon"
          | "icon-xs"
          | "icon-sm"
          | "icon-lg")
      : "default"
  const iconName = propValue("iconName") as string | undefined
  const Icon = resolveIcon(iconName)
  const disabled = propValue("disabled") === true

  const handleFire = useCallback(async () => {
    if (!contract) return
    setPending(true)
    try {
      const ctx: BindingContext = {
        user: user
          ? {
              id: user.id,
              email: user.email,
              // Codebase uses `role_slug` on the User type; we expose
              // it as `role` in the binding context for clarity at the
              // configuration surface (admins author bindings with
              // `userField: "role"`).
              role: user.role_slug ?? null,
            }
          : null,
        tenant: company
          ? {
              id: company.id,
              slug: company.slug ?? null,
              vertical: company.vertical ?? null,
            }
          : null,
        nowMs: Date.now(),
        routeParams,
        queryParams: searchParams,
        currentFocusId: focus.currentFocus?.id ?? null,
      }
      const resolved = resolveBindings(contract.parameterBindings ?? [], ctx)
      const result = await dispatchAction(
        contract.actionType,
        contract.actionConfig,
        resolved,
        { navigate, openFocus: focus.open },
      )
      if (result.status === "error") {
        toast.error(result.errorMessage ?? "Action failed.")
        return
      }
      // Success behavior dispatch.
      const beh = contract.successBehavior ?? "stay"
      if (beh === "toast") {
        toast.success(contract.successToastMessage ?? `${label}: done.`)
      } else if (beh === "navigate" && contract.successNavigateRoute) {
        navigate(contract.successNavigateRoute)
      }
      // "stay" → no side effect.
      // R-5.0 — close the edge panel when this button fired from
      // within it. Per-button override available via
      // R4ButtonContract.closePanelAfterFire (defaults true).
      if (
        edgePanel !== null &&
        contract.closePanelAfterFire !== false
      ) {
        edgePanel.closePanel()
      }
    } finally {
      setPending(false)
    }
  }, [
    contract,
    user,
    company,
    edgePanel,
    routeParams,
    searchParams,
    focus,
    navigate,
    label,
  ])

  const handleClick = useCallback(() => {
    if (!contract) return
    if (contract.confirmBeforeFire) {
      setConfirmOpen(true)
      return
    }
    void handleFire()
  }, [contract, handleFire])

  // Missing registration / missing R-4 contract → render a visible
  // error state rather than a silent broken button. data-testid
  // makes specs assert on this branch deliberately if they want.
  if (!entry || !contract) {
    return (
      <div
        data-testid="r4-button-missing-registration"
        data-component-slug={componentName}
        className="inline-flex items-center gap-1 rounded border border-status-warning/30 bg-status-warning-muted px-2 py-1 text-caption text-status-warning"
      >
        <AlertTriangle size={12} />
        <span>Button registration not found: {componentName}</span>
      </div>
    )
  }

  return (
    <>
      <Button
        type="button"
        variant={variant}
        size={size}
        disabled={disabled || pending}
        onClick={handleClick}
        data-testid={`r4-button-${componentName}`}
        data-component-slug={componentName}
        data-action-type={contract.actionType}
      >
        {Icon && <Icon size={16} />}
        <span>{label}</span>
      </Button>
      {contract.confirmBeforeFire && (
        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{label}</DialogTitle>
              <DialogDescription>
                {contract.confirmCopy ?? `Confirm: ${label}?`}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setConfirmOpen(false)}
                data-testid="r4-button-confirm-cancel"
              >
                Cancel
              </Button>
              <Button
                variant="default"
                onClick={async () => {
                  setConfirmOpen(false)
                  await handleFire()
                }}
                data-testid="r4-button-confirm-fire"
              >
                Confirm
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}
