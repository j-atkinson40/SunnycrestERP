/**
 * TaskSections — the tenant map's body: collapsible sections derived from
 * the vocabulary types-with-tasks, cards inside (The Sunnycrest Workshop).
 *
 * DERIVED, NEVER CONFIGURED: a section materializes because tasks of that
 * type exist (Accounting appears because accounting tasks exist); empty
 * types are hidden — the tab-derivation engine re-clothed. Untyped tasks
 * gather under "General". Sections ARE the overflow management: the
 * 40-task tenant lays out calm because each type folds.
 *
 * Section headers are TYPOGRAPHY-LED (DL §6 — no boxed-in chrome; the
 * CARDS are the material). Collapse state is per-user, localStorage-class,
 * default expanded.
 *
 * DELIBERATE ROOM: the section model accepts non-task card kinds later
 * (capability cards — the vision's layer). The grid renders whatever cards
 * a section carries; today that's tasks.
 */
import { useCallback, useEffect, useMemo, useState } from "react"
import { ChevronDown, Plus } from "lucide-react"

import { TaskCard } from "./TaskCard"
import type { MapTask } from "@/services/moc-map-service"

const UNTYPED = "General"
const STORAGE_KEY = "bridgeable-map-collapsed-sections"

function loadCollapsed(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return new Set(raw ? (JSON.parse(raw) as string[]) : [])
  } catch {
    return new Set()
  }
}

/** Section derivation — exported for the vitest pins. */
export function deriveSections(tasks: MapTask[]): Array<{
  type: string
  tasks: MapTask[]
}> {
  const by = new Map<string, MapTask[]>()
  for (const t of tasks) {
    const key = t.task_type || UNTYPED
    const arr = by.get(key)
    if (arr) arr.push(t)
    else by.set(key, [t])
  }
  // Typed sections alphabetically; General (untyped) last — the named
  // types are the map's vocabulary, the gather-all trails.
  return [...by.entries()]
    .sort((a, b) => {
      if (a[0] === UNTYPED) return 1
      if (b[0] === UNTYPED) return -1
      return a[0].localeCompare(b[0])
    })
    .map(([type, sectionTasks]) => ({ type, tasks: sectionTasks }))
}

export function TaskSections({
  tasks, onPonder, onOpenOffer, canAdd, onAdd,
}: {
  tasks: MapTask[]
  onPonder: (task: MapTask) => void
  onOpenOffer: (task: MapTask) => void
  /** Tenant admins add; everyone else reads. */
  canAdd: boolean
  /** Opens the add dialog, pre-filled with the section's type. */
  onAdd: (sectionType: string | null) => void
}) {
  const sections = useMemo(() => deriveSections(tasks), [tasks])
  const [collapsed, setCollapsed] = useState<Set<string>>(loadCollapsed)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...collapsed]))
    } catch {
      /* storage unavailable — collapse state stays session-local */
    }
  }, [collapsed])

  const toggle = useCallback((type: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }, [])

  return (
    <div className="space-y-7" data-testid="map-sections">
      {sections.map(({ type, tasks: sectionTasks }) => {
        const open = !collapsed.has(type)
        return (
          <section key={type} data-testid={`map-section-${type}`}>
            {/* Typography-led header — calm; the chevron + count + add are
                the only furniture. */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => toggle(type)}
                aria-expanded={open}
                className="focus-ring-accent -ml-1 flex items-center gap-1.5 rounded-md px-1 py-0.5"
                data-testid={`map-section-toggle-${type}`}
              >
                <ChevronDown
                  size={14}
                  className={
                    "text-content-subtle transition-transform duration-quick ease-settle " +
                    (open ? "" : "-rotate-90")
                  }
                />
                <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
                  {type}
                </h2>
                <span className="text-caption text-content-subtle">
                  {sectionTasks.length}
                </span>
              </button>
              {canAdd ? (
                <button
                  type="button"
                  onClick={() => onAdd(type === UNTYPED ? null : type)}
                  className="focus-ring-accent ml-auto flex items-center gap-1 rounded-md px-1.5 py-0.5 text-caption text-content-subtle transition-colors duration-quick hover:bg-surface-sunken hover:text-content-muted"
                  data-testid={`map-section-add-${type}`}
                >
                  <Plus size={12} /> Add
                </button>
              ) : null}
            </div>
            {open ? (
              <div
                className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
                data-testid={`map-section-grid-${type}`}
              >
                {sectionTasks.map((t) => (
                  <TaskCard
                    key={t.id}
                    task={t}
                    onPonder={onPonder}
                    onOpenOffer={onOpenOffer}
                  />
                ))}
              </div>
            ) : null}
          </section>
        )
      })}
    </div>
  )
}
