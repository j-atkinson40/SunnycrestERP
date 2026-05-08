/**
 * R-5.2 — EdgePanelEditor PageMetadataEditor.
 *
 * Inline at the top of the canvas area. Page name editor + set-as-
 * default + delete-page controls. Pure presentational; emit-only
 * handlers.
 *
 * data-testid attributes preserved from R-5.0 inline shape so spec
 * 28 stays green:
 *   - edge-panel-editor-page-name
 *   - edge-panel-editor-set-default
 *   - edge-panel-editor-delete-page
 */
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { EdgePanelPage } from "@/lib/edge-panel/types"


export interface PageMetadataEditorProps {
  page: EdgePanelPage
  isDefault: boolean
  isOnlyPage: boolean
  onRenamePage: (newName: string) => void
  onSetDefault: () => void
  onDeletePage: () => void
}


export function PageMetadataEditor({
  page,
  isDefault,
  isOnlyPage,
  onRenamePage,
  onSetDefault,
  onDeletePage,
}: PageMetadataEditorProps) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <Label htmlFor="ep-page-name">Page name</Label>
        <Input
          id="ep-page-name"
          data-testid="edge-panel-editor-page-name"
          value={page.name}
          onChange={(e) => onRenamePage(e.target.value)}
        />
      </div>
      <div className="flex items-end gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onSetDefault}
          disabled={isDefault}
          data-testid="edge-panel-editor-set-default"
        >
          {isDefault ? "Default page" : "Set as default page"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          onClick={onDeletePage}
          data-testid="edge-panel-editor-delete-page"
          disabled={isOnlyPage}
        >
          Delete page
        </Button>
      </div>
    </div>
  )
}
