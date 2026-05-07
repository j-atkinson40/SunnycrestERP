/**
 * Phase R-1 — EditModeToggle.
 *
 * Floating fixed-position toggle in the top-right of the runtime
 * editor viewport. Reflects + drives `useEditMode().isEditing`.
 * URL parameter `?edit=1` mirrors state for shareability + page
 * reload preservation. Toggle-off with uncommitted drafts opens a
 * confirm dialog (discard / commit / cancel-toggle).
 *
 * Tenant operators don't see this — it lives inside the runtime
 * editor's mount point only.
 */
import { useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Pencil, Eye, AlertCircle } from "lucide-react"

import { useEditMode } from "./edit-mode-context"
import { usePageContext } from "./use-page-context"


export function EditModeToggle() {
  const editMode = useEditMode()
  const { pageContext, label, mapped } = usePageContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const [confirmOpen, setConfirmOpen] = useState(false)

  // Sync URL ?edit=1 ↔ editing state. URL is read on mount + each
  // route change; toggle clicks update both.
  useEffect(() => {
    const wantsEdit = searchParams.get("edit") === "1"
    if (wantsEdit !== editMode.isEditing) {
      editMode.setEditing(wantsEdit)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  // Update the EditMode context's pageContext when the route changes.
  useEffect(() => {
    editMode.setPageContext(pageContext)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageContext])

  const handleToggle = useCallback(() => {
    const next = !editMode.isEditing
    if (!next && editMode.draftOverrides.size > 0) {
      // Draft overrides exist — confirm before exiting edit mode.
      setConfirmOpen(true)
      return
    }
    const params = new URLSearchParams(searchParams)
    if (next) {
      params.set("edit", "1")
    } else {
      params.delete("edit")
    }
    setSearchParams(params, { replace: true })
  }, [editMode.isEditing, editMode.draftOverrides.size, searchParams, setSearchParams])

  const handleDiscardAndExit = useCallback(() => {
    editMode.discardDraft()
    const params = new URLSearchParams(searchParams)
    params.delete("edit")
    setSearchParams(params, { replace: true })
    setConfirmOpen(false)
  }, [editMode, searchParams, setSearchParams])

  const handleCommitAndExit = useCallback(async () => {
    const outcome = await editMode.commitDraft()
    if (outcome.failed === 0) {
      const params = new URLSearchParams(searchParams)
      params.delete("edit")
      setSearchParams(params, { replace: true })
      setConfirmOpen(false)
    }
    // Partial / full failure: leave dialog open so user sees the
    // error state. Inspector panel surfaces per-key errors.
  }, [editMode, searchParams, setSearchParams])

  const stagedCount = editMode.draftOverrides.size

  return (
    <>
      {/* Page-chrome edit indicator — subtle brass top-edge highlight
          when edit mode active. Doesn't shift layout (height: 2px). */}
      {editMode.isEditing && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed left-0 right-0 top-0 z-[var(--z-edit-mode,90)] h-0.5 bg-accent"
          style={{ zIndex: 90 }}
          data-testid="runtime-editor-edit-indicator"
        />
      )}

      {/* Toggle button — fixed top-right, brass when active.
       *
       *  R-1.6.13 — when the inspector panel is mounted (edit mode +
       *  selected component), the panel covers the right 380px of
       *  the viewport at z-95. Toggle at right-3 + z-91 sits inside
       *  that footprint and gets click-intercepted. Slide the toggle
       *  to right-[396px] (380px panel + 16px gap) so it stays
       *  reachable. Smooth `transition-[right]` makes the slide feel
       *  intentional.
       *
       *  Page label below also slides to keep visual co-location. */}
      <button
        type="button"
        onClick={handleToggle}
        className={`fixed top-2 z-[91] flex items-center gap-1.5 rounded-sm border px-3 py-1.5 text-caption font-medium shadow-level-1 transition-[right,colors] duration-arrive ease-settle ${
          editMode.selectedComponentName ? "right-[396px]" : "right-3"
        } ${
          editMode.isEditing
            ? "border-accent bg-accent text-content-on-accent hover:bg-accent-hover"
            : "border-border-base bg-surface-raised text-content-strong hover:bg-accent-subtle/40"
        }`}
        style={{ zIndex: 91 }}
        data-testid="runtime-editor-toggle"
        data-active={editMode.isEditing ? "true" : "false"}
        title={
          editMode.isEditing
            ? `Exit edit mode (${stagedCount} unsaved override${stagedCount === 1 ? "" : "s"})`
            : "Enter edit mode"
        }
      >
        {editMode.isEditing ? (
          <>
            <Pencil size={12} />
            Editing
            {stagedCount > 0 && (
              <span
                className="ml-1 rounded-full bg-content-on-accent px-1.5 py-0 text-[10px] font-bold text-accent"
                data-testid="runtime-editor-staged-count"
              >
                {stagedCount}
              </span>
            )}
          </>
        ) : (
          <>
            <Eye size={12} />
            View
          </>
        )}
      </button>

      {/* Page label — below toggle, brass-tinted in edit mode for
          contextual feedback. */}
      <div
        className={`fixed top-12 z-[91] rounded-sm bg-surface-raised/90 px-2 py-0.5 text-[10px] text-content-muted shadow-level-1 backdrop-blur transition-[right] duration-arrive ease-settle ${
          editMode.selectedComponentName ? "right-[396px]" : "right-3"
        }`}
        style={{ zIndex: 91 }}
        data-testid="runtime-editor-page-label"
      >
        Page: <code>{pageContext}</code>
        {!mapped && (
          <span
            className="ml-1 text-status-warning"
            title="Unmapped route — widget overrides disabled. Theme + class edits still work."
            data-testid="runtime-editor-unmapped-warning"
          >
            ⚠
          </span>
        )}
        <span className="ml-1 text-content-subtle">({label})</span>
      </div>

      {/* Confirm dialog on toggle-off with unsaved drafts. */}
      {confirmOpen && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40"
          style={{ zIndex: 200 }}
          data-testid="runtime-editor-confirm-dialog"
        >
          <div className="max-w-md rounded-md bg-surface-raised p-4 shadow-level-3">
            <div className="flex items-center gap-2 text-h4 font-plex-serif text-content-strong">
              <AlertCircle size={18} className="text-status-warning" />
              Unsaved overrides
            </div>
            <p className="mt-2 text-body-sm text-content-muted">
              You have {stagedCount} unsaved override
              {stagedCount === 1 ? "" : "s"}. Discard them or commit
              before exiting edit mode?
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                className="rounded-sm border border-border-base px-3 py-1 text-body-sm text-content-strong hover:bg-accent-subtle/40"
                data-testid="runtime-editor-confirm-cancel"
              >
                Stay in edit mode
              </button>
              <button
                type="button"
                onClick={handleDiscardAndExit}
                className="rounded-sm border border-status-error px-3 py-1 text-body-sm text-status-error hover:bg-status-error-muted"
                data-testid="runtime-editor-confirm-discard"
              >
                Discard {stagedCount}
              </button>
              <button
                type="button"
                onClick={() => void handleCommitAndExit()}
                disabled={editMode.isCommitting}
                className="rounded-sm bg-accent px-3 py-1 text-body-sm text-content-on-accent hover:bg-accent-hover disabled:opacity-50"
                data-testid="runtime-editor-confirm-commit"
              >
                {editMode.isCommitting ? "Committing…" : `Commit ${stagedCount}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
