/**
 * MoC Planning section (r123) — the personal build-backlog on the maps.
 *
 * The map shows what's NEEDED, not just what exists. PERSONAL-SCOPED: the
 * backend returns only the authenticated user's items for this map's tier —
 * the section is the current user's lens. Grouped by KIND (the operator's
 * sections: Features / Workflows to create / Focuses to create / Documents
 * to create) with a modest kind icon per group header; status as an inline
 * pick (the 2b vocabulary-picker interaction); DONE items collapse into a
 * muted per-group disclosure (visible history, not clutter). Add via the
 * panel pattern; title/description click-to-edit inline (the 2b hybrid).
 */

import * as React from "react"
import { toast } from "sonner"
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Focus,
  Lightbulb,
  NotebookPen,
  Plus,
  Trash2,
  Workflow,
  type LucideIcon,
} from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  createPlanning,
  deletePlanning,
  listPlanning,
  patchPlanning,
  type PlanningItem,
  type PlanningKind,
  type PlanningStatus,
} from "@/bridgeable-admin/services/moc-service"

const KIND_ORDER: PlanningKind[] = ["feature", "workflow", "focus", "document"]

const KIND_META: Record<PlanningKind, { title: string; icon: LucideIcon }> = {
  feature: { title: "Features", icon: Lightbulb },
  workflow: { title: "Workflows to create", icon: Workflow },
  focus: { title: "Focuses to create", icon: Focus },
  document: { title: "Documents to create", icon: FileText },
}

const STATUS_META: Record<PlanningStatus, { label: string; cls: string }> = {
  planned: {
    label: "Planned",
    cls: "bg-surface-sunken text-content-muted",
  },
  in_progress: {
    label: "In progress",
    cls: "bg-accent-subtle text-accent",
  },
  done: {
    label: "Done",
    cls: "bg-status-success-muted text-status-success",
  },
}

export interface MoCPlanningSectionProps {
  scope: "platform_default" | "vertical_default"
  vertical?: string | null
  /** For the empty-state copy ("…for Manufacturing"). */
  contextLabel: string
  "data-testid"?: string
}

export function MoCPlanningSection({
  scope,
  vertical,
  contextLabel,
  "data-testid": testId,
}: MoCPlanningSectionProps) {
  const [items, setItems] = React.useState<PlanningItem[]>([])
  const [addOpen, setAddOpen] = React.useState(false)

  const reload = React.useCallback(async () => {
    try {
      setItems(
        await listPlanning({
          scope,
          vertical: scope === "vertical_default" ? vertical ?? undefined : undefined,
        }),
      )
    } catch {
      setItems([]) // quiet — the section renders its deliberate empty
    }
  }, [scope, vertical])

  React.useEffect(() => {
    void reload()
  }, [reload])

  const byKind = new Map<PlanningKind, PlanningItem[]>()
  for (const item of items) {
    const list = byKind.get(item.kind)
    if (list) list.push(item)
    else byKind.set(item.kind, [item])
  }

  return (
    <section className="space-y-2" data-testid={testId ?? "moc-planning"}>
      <div className="flex items-center gap-3">
        <h2 className="flex items-center gap-1.5 text-h4 font-semibold text-content-strong">
          <NotebookPen size={16} className="text-content-muted" /> Planning
        </h2>
        <span className="text-caption text-content-subtle">
          your build backlog — only you see this
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setAddOpen(true)}
          data-testid="planning-add"
        >
          <Plus size={14} /> Add item
        </Button>
      </div>

      {items.length === 0 ? (
        <p
          className="rounded-lg border border-dashed border-border-base bg-surface-elevated px-4 py-6 text-body-sm text-content-subtle"
          data-testid="planning-empty"
        >
          Your planning space for {contextLabel} — features to build, and the
          workflows, focuses, and documents it still needs.
        </p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {KIND_ORDER.filter((k) => byKind.has(k)).map((kind) => (
            <KindGroup
              key={kind}
              kind={kind}
              items={byKind.get(kind) ?? []}
              onChanged={() => void reload()}
            />
          ))}
        </div>
      )}

      {addOpen ? (
        <AddPlanningDialog
          scope={scope}
          vertical={vertical ?? null}
          contextLabel={contextLabel}
          onClose={() => setAddOpen(false)}
          onCreated={() => {
            setAddOpen(false)
            void reload()
          }}
        />
      ) : null}
    </section>
  )
}

function KindGroup({
  kind,
  items,
  onChanged,
}: {
  kind: PlanningKind
  items: PlanningItem[]
  onChanged: () => void
}) {
  const meta = KIND_META[kind]
  const active = items.filter((i) => i.status !== "done")
  const done = items.filter((i) => i.status === "done")
  const [doneOpen, setDoneOpen] = React.useState(false)

  return (
    <div
      className="rounded-lg border border-border-subtle bg-surface-elevated p-3 shadow-level-1"
      data-testid={`planning-group-${kind}`}
    >
      <div className="mb-2 flex items-center gap-2 border-b border-border-subtle pb-2">
        <meta.icon size={15} className="text-content-muted" aria-hidden />
        <h3 className="text-body-sm font-medium text-content-base">
          {meta.title}
        </h3>
        <span className="text-caption text-content-subtle">{active.length}</span>
      </div>
      <ul className="space-y-2">
        {active.map((item) => (
          <PlanningRow key={item.id} item={item} onChanged={onChanged} />
        ))}
        {active.length === 0 ? (
          <li className="py-1 text-caption text-content-subtle">
            Nothing in flight.
          </li>
        ) : null}
      </ul>
      {done.length > 0 ? (
        <div className="mt-2 border-t border-border-subtle pt-1.5">
          <button
            type="button"
            onClick={() => setDoneOpen((o) => !o)}
            className="flex items-center gap-1 text-caption text-content-subtle hover:text-content-muted"
            data-testid={`planning-done-toggle-${kind}`}
          >
            {doneOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            Done ({done.length})
          </button>
          {doneOpen ? (
            <ul className="mt-1.5 space-y-1.5 opacity-60">
              {done.map((item) => (
                <PlanningRow key={item.id} item={item} onChanged={onChanged} />
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function PlanningRow({
  item,
  onChanged,
}: {
  item: PlanningItem
  onChanged: () => void
}) {
  const [editingTitle, setEditingTitle] = React.useState(false)
  const [editingDesc, setEditingDesc] = React.useState(false)
  const [draft, setDraft] = React.useState("")

  async function save(patch: Parameters<typeof patchPlanning>[1]) {
    try {
      await patchPlanning(item.id, patch)
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed")
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${item.title}"? This can't be undone.`)) return
    try {
      await deletePlanning(item.id)
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed")
    }
  }

  const status = STATUS_META[item.status]

  return (
    <li className="group/prow" data-testid={`planning-item-${item.id}`}>
      <div className="flex items-start gap-2">
        {/* Status — the 2b inline quick-pick. */}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <button
                type="button"
                className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-caption ${status.cls}`}
                data-testid={`planning-status-${item.id}`}
              >
                {status.label}
              </button>
            }
          />
          <DropdownMenuContent align="start">
            {(Object.keys(STATUS_META) as PlanningStatus[]).map((s) => (
              <DropdownMenuItem
                key={s}
                onClick={() => void save({ status: s })}
                data-testid={`planning-status-pick-${s}-${item.id}`}
              >
                {STATUS_META[s].label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="min-w-0 flex-1">
          {editingTitle ? (
            <Input
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={() => {
                setEditingTitle(false)
                if (draft.trim() && draft.trim() !== item.title)
                  void save({ title: draft.trim() })
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur()
                if (e.key === "Escape") setEditingTitle(false)
              }}
              className="h-7 text-body-sm"
            />
          ) : (
            <button
              type="button"
              onClick={() => {
                setDraft(item.title)
                setEditingTitle(true)
              }}
              className="block w-full truncate text-left text-body-sm text-content-base hover:text-accent"
              title="Click to edit"
            >
              {item.title}
            </button>
          )}
          {editingDesc ? (
            <Textarea
              autoFocus
              value={draft}
              rows={3}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={() => {
                setEditingDesc(false)
                if (draft.trim() !== (item.description ?? ""))
                  void save({ description: draft.trim() || null })
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") setEditingDesc(false)
              }}
              className="mt-1 text-caption"
            />
          ) : (
            <button
              type="button"
              onClick={() => {
                setDraft(item.description ?? "")
                setEditingDesc(true)
              }}
              className="mt-0.5 block w-full text-left text-caption text-content-subtle hover:text-content-muted"
              title="Click to edit the design note"
            >
              {item.description ? (
                <span className="line-clamp-3 whitespace-pre-wrap">
                  {item.description}
                </span>
              ) : (
                <span className="italic">Add a how-it-works note…</span>
              )}
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={() => void remove()}
          className="mt-0.5 shrink-0 text-content-subtle opacity-0 transition-opacity hover:text-status-error group-hover/prow:opacity-100"
          title="Delete"
          data-testid={`planning-delete-${item.id}`}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </li>
  )
}

function AddPlanningDialog({
  scope,
  vertical,
  contextLabel,
  onClose,
  onCreated,
}: {
  scope: "platform_default" | "vertical_default"
  vertical: string | null
  contextLabel: string
  onClose: () => void
  onCreated: () => void
}) {
  const [kind, setKind] = React.useState<PlanningKind>("feature")
  const [title, setTitle] = React.useState("")
  const [description, setDescription] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  async function submit() {
    setSaving(true)
    try {
      await createPlanning({
        scope,
        vertical: scope === "vertical_default" ? vertical : null,
        kind,
        title: title.trim(),
        description: description.trim() || null,
      })
      onCreated()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Create failed")
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-lg" data-testid="planning-add-dialog">
        <DialogHeader>
          <DialogTitle>Plan something for {contextLabel}</DialogTitle>
          <DialogDescription>
            A feature to build — or a workflow, focus, or document it still
            needs. Only you see your planning items.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Kind</Label>
            <div className="grid grid-cols-2 gap-1.5">
              {KIND_ORDER.map((k) => {
                const Meta = KIND_META[k]
                return (
                  <label
                    key={k}
                    className="flex cursor-pointer items-center gap-2 rounded-md border border-border-subtle bg-surface-elevated px-2.5 py-1.5 text-body-sm text-content-base has-[:checked]:border-accent"
                  >
                    <input
                      type="radio"
                      name="planning-kind"
                      checked={kind === k}
                      onChange={() => setKind(k)}
                      data-testid={`planning-kind-${k}`}
                    />
                    <Meta.icon size={14} className="text-content-muted" />
                    {Meta.title}
                  </label>
                )
              })}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="planning-title">Title</Label>
            <Input
              id="planning-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Delivery-day weather advisory"
              data-testid="planning-title-input"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="planning-desc">How it's going to work</Label>
            <Textarea
              id="planning-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder="The design note — flow, surfaces, who sees what."
              data-testid="planning-desc-input"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={() => void submit()}
            disabled={!title.trim() || saving}
            data-testid="planning-create-button"
          >
            {saving ? "Adding…" : "Add to plan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
