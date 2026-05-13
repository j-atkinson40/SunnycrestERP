/**
 * Verticals admin page — Verticals-lite precursor arc.
 *
 * Lists the 4 canonical verticals seeded by migration
 * r95_verticals_table; lets a platform admin partial-update the
 * mutable columns (display_name, description, status, icon,
 * sort_order). Slug is immutable and renders as a read-only
 * <code> element in the edit modal.
 *
 * Mounted inside AdminLayout (operational chrome). Studio shell
 * arcs will provide a parallel `/studio/admin/verticals` surface
 * with Studio chrome; this page is the bridge until that ships.
 */

import { useEffect, useState } from "react"
import type { JSX } from "react"
import type {
  Vertical,
  VerticalStatus,
  VerticalUpdate,
} from "@/bridgeable-admin/services/verticals-service"
import { verticalsService } from "@/bridgeable-admin/services/verticals-service"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"


const STATUS_VALUES: VerticalStatus[] = ["draft", "published", "archived"]


function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—"
  try {
    const then = new Date(iso).getTime()
    const now = Date.now()
    const seconds = Math.floor((now - then) / 1000)
    if (seconds < 60) return `${seconds}s ago`
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 30) return `${days}d ago`
    return new Date(iso).toLocaleDateString()
  } catch {
    return iso
  }
}


function statusBadgeClass(status: VerticalStatus): string {
  switch (status) {
    case "published":
      return "bg-status-success-muted text-status-success"
    case "draft":
      return "bg-status-info-muted text-status-info"
    case "archived":
      return "bg-surface-sunken text-content-muted"
  }
}


export default function VerticalsAdminPage(): JSX.Element {
  const [rows, setRows] = useState<Vertical[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Vertical | null>(null)

  const load = () => {
    setLoading(true)
    setError(null)
    verticalsService
      .list({ include_archived: true })
      .then((r) => setRows(r))
      .catch((e: unknown) => {
        setError(
          e instanceof Error ? e.message : "Failed to load verticals",
        )
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="space-y-4" data-testid="verticals-admin-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            Verticals
          </h1>
          <p className="text-sm text-slate-500">
            Platform verticals registry. Slugs are immutable.
          </p>
        </div>
      </div>

      {error && (
        <div
          className="rounded border border-status-error bg-status-error-muted px-4 py-3 text-sm text-status-error"
          data-testid="verticals-admin-error"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div
          className="p-8 text-center text-slate-400"
          data-testid="verticals-admin-loading"
        >
          Loading…
        </div>
      ) : (
        <div
          className="overflow-hidden rounded border border-slate-200 bg-white"
          data-testid="verticals-admin-table"
        >
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-4 py-2 text-left">Slug</th>
                <th className="px-4 py-2 text-left">Display name</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Sort order</th>
                <th className="px-4 py-2 text-left">Updated</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.slug}
                  className="border-t border-slate-100"
                  data-testid={`verticals-row-${row.slug}`}
                >
                  <td className="px-4 py-2">
                    <code
                      className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700"
                      data-testid={`verticals-row-${row.slug}-slug`}
                    >
                      {row.slug}
                    </code>
                  </td>
                  <td className="px-4 py-2 font-medium text-slate-900">
                    {row.display_name}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(row.status)}`}
                    >
                      {row.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{row.sort_order}</td>
                  <td className="px-4 py-2 text-slate-500">
                    {formatRelativeTime(row.updated_at)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEditing(row)}
                      data-testid={`verticals-row-${row.slug}-edit`}
                    >
                      Edit
                    </Button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    className="px-4 py-8 text-center text-slate-400"
                    colSpan={6}
                  >
                    No verticals found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <EditVerticalDialog
          vertical={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            load()
          }}
        />
      )}
    </div>
  )
}


function EditVerticalDialog({
  vertical,
  onClose,
  onSaved,
}: {
  vertical: Vertical
  onClose: () => void
  onSaved: () => void
}): JSX.Element {
  const [displayName, setDisplayName] = useState(vertical.display_name)
  const [description, setDescription] = useState(vertical.description ?? "")
  const [status, setStatus] = useState<VerticalStatus>(vertical.status)
  const [icon, setIcon] = useState(vertical.icon ?? "")
  const [sortOrder, setSortOrder] = useState<number>(vertical.sort_order)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    const payload: VerticalUpdate = {
      display_name: displayName,
      description: description.length > 0 ? description : null,
      status,
      icon: icon.length > 0 ? icon : null,
      sort_order: sortOrder,
    }
    try {
      await verticalsService.update(vertical.slug, payload)
      onSaved()
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "Failed to save vertical",
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={true}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        className="max-w-md"
        data-testid="verticals-edit-dialog"
      >
        <DialogHeader>
          <DialogTitle>Edit vertical</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="vertical-slug-readonly">Slug</Label>
            <code
              id="vertical-slug-readonly"
              className="block rounded bg-slate-100 px-2 py-1.5 font-mono text-sm text-slate-700"
              data-testid="verticals-edit-slug"
            >
              {vertical.slug}
            </code>
            <p className="text-xs text-content-muted">
              Slug is immutable.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="vertical-display-name">Display name</Label>
            <Input
              id="vertical-display-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              data-testid="verticals-edit-display-name"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="vertical-description">Description</Label>
            <Textarea
              id="vertical-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              data-testid="verticals-edit-description"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="vertical-status">Status</Label>
            <Select
              value={status}
              onValueChange={(v) => {
                if (v && STATUS_VALUES.includes(v as VerticalStatus)) {
                  setStatus(v as VerticalStatus)
                }
              }}
            >
              <SelectTrigger
                id="vertical-status"
                data-testid="verticals-edit-status"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_VALUES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="vertical-icon">Icon</Label>
            <Input
              id="vertical-icon"
              value={icon}
              onChange={(e) => setIcon(e.target.value)}
              placeholder="e.g. factory"
              data-testid="verticals-edit-icon"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="vertical-sort-order">Sort order</Label>
            <Input
              id="vertical-sort-order"
              type="number"
              value={sortOrder}
              onChange={(e) =>
                setSortOrder(Number.parseInt(e.target.value, 10) || 0)
              }
              data-testid="verticals-edit-sort-order"
            />
          </div>

          {error && (
            <div
              className="rounded border border-status-error bg-status-error-muted px-3 py-2 text-sm text-status-error"
              data-testid="verticals-edit-error"
            >
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={saving}
            data-testid="verticals-edit-cancel"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            data-testid="verticals-edit-save"
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
