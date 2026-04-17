// Drop zones for the workflow canvas.
//
// InterStepDropZone: sits between two step cards. Idle state is a subtle
// connector line; on hover it grows a [+ Add step] button; on drag-over
// it expands into a full drop target.
//
// EndDropZone: always visible after the last step — bigger, clearly
// invites adding the next step. Used as the primary affordance on
// brand-new workflows too.
//
// Both accept blocks serialized via the mime type used by BlockLibrary:
// "application/x-workflow-block".

import { useRef, useState } from "react"
import { Plus } from "lucide-react"
import type { BlockDefinition } from "@/components/workflow/BlockLibrary"

const MIME = "application/x-workflow-block"

function parseBlockDrop(e: React.DragEvent): BlockDefinition | null {
  const data = e.dataTransfer.getData(MIME)
  if (!data) return null
  try {
    return JSON.parse(data) as BlockDefinition
  } catch {
    return null
  }
}

// ─────────────────────────────────────────────────────────────────────

export function InterStepDropZone({
  onDrop,
  onClickAdd,
}: {
  onDrop: (block: BlockDefinition) => void
  onClickAdd: () => void
}) {
  const [dragOver, setDragOver] = useState(false)
  const [hovered, setHovered] = useState(false)
  const counter = useRef(0)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onDragEnter={(e) => {
        if (!e.dataTransfer.types.includes(MIME)) return
        e.preventDefault()
        counter.current++
        setDragOver(true)
      }}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes(MIME)) e.preventDefault()
      }}
      onDragLeave={() => {
        counter.current--
        if (counter.current <= 0) {
          counter.current = 0
          setDragOver(false)
        }
      }}
      onDrop={(e) => {
        counter.current = 0
        setDragOver(false)
        const block = parseBlockDrop(e)
        if (!block) return
        e.preventDefault()
        e.stopPropagation()
        onDrop(block)
      }}
      className="relative flex justify-center"
    >
      {dragOver ? (
        <div className="my-1 w-full max-w-[560px] h-12 rounded-xl border-2 border-dashed border-blue-400 bg-blue-50 grid place-items-center transition-all">
          <span className="text-blue-600 text-sm font-medium">Drop here</span>
        </div>
      ) : (
        <div className="flex items-center w-full max-w-[560px] gap-3 py-1">
          <div
            className={`flex-1 h-px transition-colors ${
              hovered ? "bg-blue-300" : "bg-slate-300"
            }`}
          />
          <button
            onClick={onClickAdd}
            tabIndex={hovered ? 0 : -1}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition ${
              hovered
                ? "border-blue-400 bg-white text-blue-600 shadow-sm"
                : "border-transparent bg-transparent text-transparent"
            }`}
          >
            <Plus className="h-3 w-3" />
            Add step
          </button>
          <div
            className={`flex-1 h-px transition-colors ${
              hovered ? "bg-blue-300" : "bg-slate-300"
            }`}
          />
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────

export function EndDropZone({
  onDrop,
  onClickAdd,
  compact = false,
}: {
  onDrop: (block: BlockDefinition) => void
  onClickAdd: () => void
  /** Render a small variant for Tier-1 workflows where the primary canvas
   *  is compressed (no need for a big invitation block). */
  compact?: boolean
}) {
  const [dragOver, setDragOver] = useState(false)
  const counter = useRef(0)

  const handlers = {
    onDragEnter: (e: React.DragEvent) => {
      if (!e.dataTransfer.types.includes(MIME)) return
      e.preventDefault()
      counter.current++
      setDragOver(true)
    },
    onDragOver: (e: React.DragEvent) => {
      if (e.dataTransfer.types.includes(MIME)) e.preventDefault()
    },
    onDragLeave: () => {
      counter.current--
      if (counter.current <= 0) {
        counter.current = 0
        setDragOver(false)
      }
    },
    onDrop: (e: React.DragEvent) => {
      counter.current = 0
      setDragOver(false)
      const block = parseBlockDrop(e)
      if (!block) return
      e.preventDefault()
      e.stopPropagation()
      onDrop(block)
    },
  }

  return (
    <div className="mt-2">
      <div className="flex justify-center">
        <div className="h-5 w-0.5 bg-slate-400" />
      </div>
      <button
        onClick={onClickAdd}
        {...handlers}
        className={`block w-full max-w-[560px] mx-auto rounded-xl border-2 border-dashed text-center transition ${
          dragOver
            ? "border-blue-400 bg-blue-50"
            : "border-slate-300 bg-slate-50/50 hover:border-blue-300 hover:bg-blue-50/30"
        } ${compact ? "p-4" : "p-6"}`}
      >
        <div
          className={`mx-auto rounded-lg grid place-items-center transition-colors ${
            compact ? "h-8 w-8 text-lg" : "h-10 w-10 text-xl"
          } ${dragOver ? "bg-blue-100 text-blue-600" : "bg-white text-slate-400 border border-slate-200"}`}
        >
          +
        </div>
        <div className={`text-sm font-medium text-slate-700 ${compact ? "mt-2" : "mt-3"}`}>
          Add what happens next
        </div>
        <div className="mt-0.5 text-[11px] text-slate-500">
          Drag a block from the sidebar or click to choose
        </div>
      </button>
    </div>
  )
}
