/**
 * R-5.1 — ButtonPicker modal.
 *
 * Lists every R-4 button in the visual-editor registry that is
 * applicable to the caller's tenant vertical, lets them add one to
 * the active edge panel page. Filtering rules:
 *   - Empty / missing `verticals` → universal (shown to every tenant)
 *   - Otherwise → shown when entry.metadata.verticals contains the
 *     tenant vertical OR contains all four canonical verticals (a
 *     proxy for "universal" applied via explicit tagging).
 *
 * Per-button row preview is a stylized stand-in (Button primitive
 * with the registration's defaultVariant + iconName + displayName)
 * rather than a live `RegisteredButton` to avoid firing real action
 * dispatchers from within the picker modal.
 */
import { useMemo } from "react"
import {
  AlertTriangle,
  CalendarPlus,
  Home,
  Workflow,
  type LucideIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { getByType } from "@/lib/visual-editor/registry"


type ButtonVariant =
  | "default"
  | "secondary"
  | "outline"
  | "ghost"
  | "destructive"
  | "link"


// Mirrors RegisteredButton's icon map — keeps the picker's stylized
// preview chrome consistent with the runtime button.
const ICON_MAP: Record<string, LucideIcon> = {
  AlertTriangle,
  CalendarPlus,
  Home,
  Workflow,
}


/** All four canonical verticals — `["manufacturing","funeral_home",
 *  "cemetery","crematory"]`. A button declaring all four is treated
 *  as universal applicability. */
const ALL_VERTICALS = [
  "manufacturing",
  "funeral_home",
  "cemetery",
  "crematory",
] as const


function isApplicable(
  verticals: readonly string[] | undefined,
  tenantVertical: string,
): boolean {
  if (!verticals || verticals.length === 0) return true
  if (verticals.includes(tenantVertical)) return true
  // Proxy for "universal": explicitly tagged with all four verticals.
  if (
    ALL_VERTICALS.every((v) => verticals.includes(v as string))
  ) {
    return true
  }
  return false
}


export interface ButtonPickerProps {
  open: boolean
  onClose: () => void
  /** Called when the user picks a button. Caller materializes it
   *  into a Placement (assigning placement_id, starting_column,
   *  column_span, etc.). */
  onSelect: (slug: string, defaults: Record<string, unknown>) => void
  tenantVertical: string
}


export function ButtonPicker({
  open,
  onClose,
  onSelect,
  tenantVertical,
}: ButtonPickerProps) {
  const candidates = useMemo(() => {
    return getByType("button").filter((entry) =>
      isApplicable(
        entry.metadata.verticals as readonly string[] | undefined,
        tenantVertical,
      ),
    )
  }, [tenantVertical])

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="edge-panel-settings-button-picker"
      >
        <DialogHeader>
          <DialogTitle>Add a button to your edge panel</DialogTitle>
          <DialogDescription>
            Choose a button to add to this page. You can edit its label
            after adding.
          </DialogDescription>
        </DialogHeader>

        <ul className="flex flex-col gap-2">
          {candidates.length === 0 && (
            <li
              className="text-content-muted text-body-sm"
              data-testid="edge-panel-settings-button-picker-empty"
            >
              No buttons are available for your vertical.
            </li>
          )}
          {candidates.map((entry) => {
            const meta = entry.metadata
            const props = (meta.configurableProps ?? {}) as Record<
              string,
              { default?: unknown }
            >
            const defaults: Record<string, unknown> = {}
            for (const [key, schema] of Object.entries(props)) {
              if (schema && "default" in schema) {
                defaults[key] = schema.default
              }
            }
            const label = (defaults.label as string) ?? meta.displayName
            const variant =
              ((defaults.variant as ButtonVariant) ?? "default") as ButtonVariant
            const iconName = (defaults.iconName as string) ?? ""
            const Icon = iconName ? ICON_MAP[iconName] : null

            return (
              <li
                key={meta.name}
                data-testid={`edge-panel-settings-button-picker-row-${meta.name}`}
                className="flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-surface-elevated p-3"
              >
                <div className="flex flex-col gap-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Button variant={variant} size="sm" disabled type="button">
                      {Icon !== null && <Icon className="h-4 w-4" />}
                      {label}
                    </Button>
                  </div>
                  <span className="text-caption text-content-muted">
                    {meta.displayName}
                  </span>
                  {meta.description && (
                    <span className="text-caption text-content-subtle line-clamp-2">
                      {meta.description}
                    </span>
                  )}
                </div>
                <Button
                  size="sm"
                  type="button"
                  onClick={() => {
                    onSelect(meta.name, defaults)
                    onClose()
                  }}
                  data-testid={`edge-panel-settings-button-picker-add-${meta.name}`}
                >
                  Add
                </Button>
              </li>
            )
          })}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
