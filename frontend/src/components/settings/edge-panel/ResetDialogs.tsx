/**
 * R-5.1 — confirmation dialogs for destructive override-clearing
 * actions on the `/settings/edge-panel` settings page.
 *
 * Three flavors:
 *   - PanelLevelReset: clears every customization for a panel_key
 *   - PageReset: clears per-placement overrides for a single tenant
 *     page (rows escape-hatch, hidden_placement_ids,
 *     additional_placements, placement_order)
 *   - PersonalPageDelete: removes a user-authored personal page
 *
 * Each is a Dialog primitive with a Cancel / Confirm pair. Confirm
 * triggers `onConfirm()`; Cancel + outside-click close without
 * mutating state. Per CLAUDE.md §12, no `asChild` anywhere.
 */
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"


interface PanelLevelResetProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
}

export function PanelLevelReset({
  open,
  onClose,
  onConfirm,
}: PanelLevelResetProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="edge-panel-reset-dialog-panel">
        <DialogHeader>
          <DialogTitle>Reset edge panel to default?</DialogTitle>
          <DialogDescription>
            This removes every customization you've made — hidden
            placements, personal pages, reorderings — and restores
            the admin-default panel exactly. This action cannot be
            undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            data-testid="edge-panel-reset-dialog-panel-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onConfirm}
            data-testid="edge-panel-reset-dialog-panel-confirm"
          >
            Reset everything
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}


interface PageResetProps {
  open: boolean
  pageName: string
  onClose: () => void
  onConfirm: () => void
}

export function PageReset({
  open,
  pageName,
  onClose,
  onConfirm,
}: PageResetProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="edge-panel-reset-dialog-page">
        <DialogHeader>
          <DialogTitle>Reset “{pageName}” to default?</DialogTitle>
          <DialogDescription>
            This removes your customizations to this page only —
            hidden placements you re-added, placements you added,
            reorderings. Other pages are unaffected. This action
            cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            data-testid="edge-panel-reset-dialog-page-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onConfirm}
            data-testid="edge-panel-reset-dialog-page-confirm"
          >
            Reset this page
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}


interface PersonalPageDeleteProps {
  open: boolean
  pageName: string
  onClose: () => void
  onConfirm: () => void
}

export function PersonalPageDelete({
  open,
  pageName,
  onClose,
  onConfirm,
}: PersonalPageDeleteProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="edge-panel-reset-dialog-personal-page-delete">
        <DialogHeader>
          <DialogTitle>Delete personal page “{pageName}”?</DialogTitle>
          <DialogDescription>
            This removes the personal page and every placement on
            it. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            data-testid="edge-panel-reset-dialog-personal-page-delete-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onConfirm}
            data-testid="edge-panel-reset-dialog-personal-page-delete-confirm"
          >
            Delete page
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
