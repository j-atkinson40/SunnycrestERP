// BlockLibrary — persistent right sidebar content. Categorized, searchable,
// draggable block types. Click to append at the end of the workflow; drag
// to drop anywhere on the canvas.

import { useMemo, useState } from "react"
import { Search as SearchIcon, X, ChevronDown, GripVertical } from "lucide-react"

export interface BlockDefinition {
  type: "input" | "action" | "condition" | "output"
  inputType?: string
  actionType?: string
  icon: string
  label: string
  description: string
  defaultConfig: Record<string, unknown>
}

interface CategoryDef {
  id: string
  label: string
  color: "blue" | "purple" | "amber" | "green" | "gray"
  blocks: BlockDefinition[]
}

const BLOCK_CATEGORIES: CategoryDef[] = [
  {
    id: "collect",
    label: "Collect Input",
    color: "blue",
    blocks: [
      {
        type: "input", inputType: "crm_search",
        icon: "🔍", label: "Search contacts",
        description: "Search CRM for a company or contact",
        defaultConfig: { input_type: "crm_search", prompt: "Which customer?", required: true },
      },
      {
        type: "input", inputType: "record_search",
        icon: "📋", label: "Search records",
        description: "Search orders, cases, deliveries",
        defaultConfig: { input_type: "record_search", prompt: "Which record?", required: true },
      },
      {
        type: "input", inputType: "select",
        icon: "✓", label: "Choose an option",
        description: "Pick from a list of options",
        defaultConfig: {
          input_type: "select", prompt: "Choose one:",
          options: [
            { value: "option_1", label: "Option 1" },
            { value: "option_2", label: "Option 2" },
          ],
          required: true,
        },
      },
      {
        type: "input", inputType: "date_picker",
        icon: "📅", label: "Pick a date",
        description: "Select a date",
        defaultConfig: { input_type: "date_picker", prompt: "Which date?", required: true },
      },
      {
        type: "input", inputType: "datetime_picker",
        icon: "🕐", label: "Date and time",
        description: "Select a date and time",
        defaultConfig: { input_type: "datetime_picker", prompt: "When?", required: true },
      },
      {
        type: "input", inputType: "number",
        icon: "🔢", label: "Enter a number",
        description: "Numeric input (quantity, mileage, etc.)",
        defaultConfig: { input_type: "number", prompt: "Enter a number:", required: true },
      },
      {
        type: "input", inputType: "text",
        icon: "📝", label: "Type a response",
        description: "Free text input",
        defaultConfig: { input_type: "text", prompt: "Enter text:", required: false },
      },
      {
        type: "input", inputType: "user_search",
        icon: "👤", label: "Search team members",
        description: "Search your team",
        defaultConfig: { input_type: "user_search", prompt: "Which team member?", required: true },
      },
    ],
  },
  {
    id: "actions",
    label: "Take Action",
    color: "purple",
    blocks: [
      {
        type: "action", actionType: "create_record",
        icon: "📋", label: "Create a record",
        description: "Create an order, case, delivery, etc.",
        defaultConfig: { action_type: "create_record", record_type: "order", fields: {} },
      },
      {
        type: "action", actionType: "update_record",
        icon: "✏️", label: "Update a record",
        description: "Update fields on an existing record",
        defaultConfig: { action_type: "update_record", record_type: "order", fields: {} },
      },
      {
        type: "action", actionType: "send_email",
        icon: "📧", label: "Send an email",
        description: "Send an email to anyone",
        defaultConfig: { action_type: "send_email", to: "", subject: "", body: "" },
      },
      {
        type: "action", actionType: "send_sms",
        icon: "💬", label: "Send a text message",
        description: "Send an SMS via RingCentral",
        defaultConfig: { action_type: "send_sms", to: "", body: "" },
      },
      {
        type: "action", actionType: "send_notification",
        icon: "🔔", label: "Send a notification",
        description: "In-platform notification",
        defaultConfig: { action_type: "send_notification", notify_roles: ["admin"], title: "", body: "" },
      },
      {
        type: "action", actionType: "generate_document",
        icon: "📄", label: "Generate a document",
        description: "Create a PDF or document",
        defaultConfig: { action_type: "generate_document", document_type: "statement" },
      },
      {
        type: "action", actionType: "log_vault_item",
        icon: "📌", label: "Log to timeline",
        description: "Record an event in the vault timeline",
        defaultConfig: {
          action_type: "log_vault_item", item_type: "event", event_type: "", title: "",
        },
      },
    ],
  },
  {
    id: "control",
    label: "Control Flow",
    color: "amber",
    blocks: [
      {
        type: "condition",
        icon: "◆", label: "If / Then",
        description: "Branch based on a condition",
        defaultConfig: { field: "", operator: "equals", value: "" },
      },
      {
        type: "action", actionType: "wait",
        icon: "⏱️", label: "Wait",
        description: "Pause before the next step",
        defaultConfig: { action_type: "wait", duration_hours: 24 },
      },
    ],
  },
  {
    id: "finish",
    label: "Finish",
    color: "green",
    blocks: [
      {
        type: "output", actionType: "open_slide_over",
        icon: "📂", label: "Open for editing",
        description: "Open a record in a slide-over",
        defaultConfig: { action_type: "open_slide_over", record_type: "order" },
      },
      {
        type: "output", actionType: "show_confirmation",
        icon: "✓", label: "Show confirmation",
        description: "Show a success message",
        defaultConfig: { action_type: "show_confirmation", message: "Done!" },
      },
      {
        type: "output", actionType: "navigate",
        icon: "↗", label: "Navigate to page",
        description: "Go to a page in the platform",
        defaultConfig: { action_type: "navigate", route: "/" },
      },
    ],
  },
]

const CATEGORY_COLOR: Record<CategoryDef["color"], string> = {
  blue: "bg-blue-50 text-blue-600",
  purple: "bg-violet-50 text-violet-600",
  amber: "bg-amber-50 text-amber-700",
  green: "bg-emerald-50 text-emerald-700",
  gray: "bg-slate-50 text-slate-600",
}

// ─────────────────────────────────────────────────────────────────────

export function BlockLibrary({
  onDragStart,
  onClick,
}: {
  onDragStart: (block: BlockDefinition) => void
  onClick: (block: BlockDefinition) => void
}) {
  const [query, setQuery] = useState("")
  const [expanded, setExpanded] = useState<Set<string>>(
    new Set(["collect", "actions"]),
  )

  const categories = useMemo<CategoryDef[]>(() => {
    if (!query.trim()) return BLOCK_CATEGORIES
    const q = query.toLowerCase()
    const hits = BLOCK_CATEGORIES.flatMap((c) => c.blocks).filter(
      (b) =>
        b.label.toLowerCase().includes(q) ||
        b.description.toLowerCase().includes(q),
    )
    return [{ id: "results", label: "Results", color: "gray", blocks: hits }]
  }, [query])

  const toggleCategory = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const isSearching = !!query.trim()

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-4 border-b border-slate-100">
        <h3 className="text-sm font-semibold text-slate-900 mb-3">Add a step</h3>
        <div className="relative">
          <SearchIcon className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search blocks…"
            className="w-full pl-8 pr-8 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-2 top-2 p-0.5 text-slate-400 hover:text-slate-700"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pb-4">
        {categories.map((category) => {
          const isOpen = isSearching || expanded.has(category.id)
          return (
            <div key={category.id}>
              <button
                onClick={() => toggleCategory(category.id)}
                className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-slate-50"
              >
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {category.label}
                </span>
                <ChevronDown
                  className={`h-3.5 w-3.5 text-slate-400 transition-transform ${isOpen ? "" : "-rotate-90"}`}
                />
              </button>
              {isOpen && (
                <div className="px-3 pb-2 space-y-1">
                  {category.blocks.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-slate-400">
                      No matches
                    </div>
                  ) : (
                    category.blocks.map((block) => (
                      <BlockItem
                        key={`${block.type}-${block.inputType || block.actionType || block.label}`}
                        block={block}
                        color={category.color}
                        onDragStart={onDragStart}
                        onClick={onClick}
                      />
                    ))
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="px-4 py-3 border-t border-slate-100 bg-slate-50 text-center">
        <p className="text-[11px] text-slate-400">
          Drag onto canvas or click to add at the end
        </p>
      </div>
    </div>
  )
}

function BlockItem({
  block,
  color,
  onDragStart,
  onClick,
}: {
  block: BlockDefinition
  color: CategoryDef["color"]
  onDragStart: (b: BlockDefinition) => void
  onClick: (b: BlockDefinition) => void
}) {
  const [dragging, setDragging] = useState(false)
  return (
    <div
      draggable
      onDragStart={(e) => {
        setDragging(true)
        e.dataTransfer.setData("application/x-workflow-block", JSON.stringify(block))
        e.dataTransfer.effectAllowed = "copy"
        onDragStart(block)
      }}
      onDragEnd={() => setDragging(false)}
      onClick={() => onClick(block)}
      className={`group flex items-center gap-3 px-3 py-2 rounded-lg cursor-grab active:cursor-grabbing border transition ${
        dragging
          ? "opacity-50 border-slate-300 bg-slate-50"
          : "border-transparent hover:border-slate-200 hover:bg-slate-50"
      }`}
    >
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center text-base flex-shrink-0 ${CATEGORY_COLOR[color]}`}
      >
        {block.icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-slate-800 truncate">{block.label}</div>
        <div className="text-[10px] text-slate-400 truncate">{block.description}</div>
      </div>
      <GripVertical className="h-3.5 w-3.5 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Helpers exported for WorkflowBuilder

export function stepDraftFromBlock(
  block: BlockDefinition,
  orderIndex: number,
): {
  step_order: number
  step_key: string
  step_type: BlockDefinition["type"]
  config: Record<string, unknown>
} {
  const keyBase =
    block.type === "input"
      ? `ask_${block.inputType ?? "input"}`
      : block.type === "action"
        ? block.actionType ?? "action"
        : block.type === "output"
          ? block.actionType ?? "output"
          : "branch"
  return {
    step_order: orderIndex + 1,
    step_key: `${keyBase}_${orderIndex + 1}`,
    step_type: block.type,
    config: { ...block.defaultConfig },
  }
}
