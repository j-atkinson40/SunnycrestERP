// PlaceholderCard — inline canvas block picker shown when a drop zone's
// [+ Add step] button is clicked. Six quick-add tiles; Escape or Cancel
// closes it; "Or drag any block from the sidebar →" hints that the full
// library is still usable.

import { useEffect } from "react"
import type { BlockDefinition } from "@/components/workflow/BlockLibrary"

const QUICK_ADD_BLOCKS: BlockDefinition[] = [
  {
    type: "input", inputType: "crm_search",
    icon: "🔍", label: "Search contacts", description: "Search CRM",
    defaultConfig: { input_type: "crm_search", prompt: "Which customer?", required: true },
  },
  {
    type: "input", inputType: "select",
    icon: "✓", label: "Choose option", description: "Select from list",
    defaultConfig: { input_type: "select", prompt: "Choose one:", options: [] },
  },
  {
    type: "action", actionType: "create_record",
    icon: "📋", label: "Create record", description: "Order, case, etc.",
    defaultConfig: { action_type: "create_record", record_type: "order", fields: {} },
  },
  {
    type: "action", actionType: "send_email",
    icon: "📧", label: "Send email", description: "Email anyone",
    defaultConfig: { action_type: "send_email", to: "", subject: "", body: "" },
  },
  {
    type: "action", actionType: "send_notification",
    icon: "🔔", label: "Notify team", description: "In-platform alert",
    defaultConfig: {
      action_type: "send_notification", notify_roles: ["admin"], title: "",
    },
  },
  {
    type: "output", actionType: "show_confirmation",
    icon: "✓", label: "Confirmation", description: "Show success message",
    defaultConfig: { action_type: "show_confirmation", message: "Done!" },
  },
]

export function PlaceholderCard({
  onSelect,
  onCancel,
}: {
  onSelect: (block: BlockDefinition) => void
  onCancel: () => void
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault()
        onCancel()
      }
    }
    document.addEventListener("keydown", h)
    return () => document.removeEventListener("keydown", h)
  }, [onCancel])

  return (
    <div className="w-full max-w-[560px] mx-auto rounded-xl border-2 border-dashed border-blue-300 bg-blue-50/40 p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-blue-700">
          Choose a step type
        </span>
        <button
          onClick={onCancel}
          className="text-[11px] text-blue-500 hover:text-blue-700"
        >
          Cancel
        </button>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {QUICK_ADD_BLOCKS.map((block, i) => (
          <button
            key={`${block.type}-${block.actionType || block.inputType || i}`}
            onClick={() => onSelect(block)}
            className="group flex flex-col items-center gap-1.5 p-3 rounded-lg bg-white border border-slate-200 hover:border-blue-400 hover:bg-blue-50 transition text-center"
          >
            <span className="text-xl group-hover:scale-110 transition-transform">
              {block.icon}
            </span>
            <span className="text-[11px] font-medium text-slate-700 leading-tight">
              {block.label}
            </span>
          </button>
        ))}
      </div>
      <div className="text-center">
        <span className="text-[11px] text-slate-500">
          Or drag any block from the sidebar →
        </span>
      </div>
    </div>
  )
}
