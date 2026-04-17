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
  color: "blue" | "purple" | "amber" | "green" | "gray" | "slate"
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
    id: "automated",
    label: "Automated Actions",
    color: "slate",
    blocks: [
      {
        type: "action", actionType: "playwright_action",
        icon: "🤖", label: "Place order on Uline",
        description: "Automatically log in and place a supply order on Uline",
        defaultConfig: {
          action_type: "playwright_action",
          script_name: "uline_place_order",
          requires_approval: true,
          approval_prompt: "Place order on Uline?",
          input_mapping: { item_number: "", quantity: "" },
          output_mapping: {
            uline_confirmation: "confirmation_number",
            uline_total: "order_total",
            uline_delivery: "estimated_delivery",
          },
        },
      },
      {
        type: "action", actionType: "playwright_action",
        icon: "🛡️", label: "Submit SS Certificate",
        description: "Submit a Social Service certificate form via browser automation",
        defaultConfig: {
          action_type: "playwright_action",
          script_name: "ss_certificate_submit",
          requires_approval: true,
          approval_prompt: "Submit Social Service certificate?",
          input_mapping: {},
          output_mapping: {},
        },
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

// Workflow-specific suggested blocks — shown at the top of the library
// when a matching workflowId is provided. Each entry is a fully-formed
// BlockDefinition (icon, label, defaults) that drops in ready-to-use.
const WORKFLOW_SUGGESTIONS: Record<string, BlockDefinition[]> = {
  wf_mfg_disinterment: [
    {
      type: "action", actionType: "send_email",
      icon: "📧", label: "Email confirmation to FH",
      description: "Confirm receipt to the funeral home",
      defaultConfig: {
        action_type: "send_email",
        to: "{input.ask_funeral_home.email}",
        subject: "Disinterment order received",
        body: "Your disinterment order has been received and is being processed.",
      },
    },
    {
      type: "action", actionType: "send_notification",
      icon: "🔔", label: "Notify your team",
      description: "Alert admins about the new order",
      defaultConfig: {
        action_type: "send_notification", notify_roles: ["admin"],
        title: "New disinterment order",
        body: "Disinterment for {input.ask_funeral_home.name}",
      },
    },
    {
      type: "action", actionType: "log_vault_item",
      icon: "📌", label: "Log to timeline",
      description: "Record event in vault timeline",
      defaultConfig: {
        action_type: "log_vault_item", item_type: "event",
        event_type: "disinterment_initiated",
        title: "Disinterment for {input.ask_funeral_home.name}",
      },
    },
  ],
  wf_mfg_create_order: [
    {
      type: "action", actionType: "send_email",
      icon: "📧", label: "Email order confirmation",
      description: "Send confirmation to customer",
      defaultConfig: {
        action_type: "send_email",
        to: "{input.ask_customer.email}",
        subject: "Order received",
        body: "Thank you, your order has been received.",
      },
    },
    {
      type: "action", actionType: "send_notification",
      icon: "🔔", label: "Notify production",
      description: "Alert production team of new order",
      defaultConfig: {
        action_type: "send_notification", notify_roles: ["production", "admin"],
        title: "New vault order",
        body: "Order from {input.ask_customer.name}",
      },
    },
  ],
  wf_mfg_schedule_delivery: [
    {
      type: "action", actionType: "send_sms",
      icon: "💬", label: "Text the driver",
      description: "SMS the assigned driver",
      defaultConfig: {
        action_type: "send_sms",
        to: "{input.ask_driver.phone}",
        body: "Delivery assigned: {input.ask_date}.",
      },
    },
    {
      type: "action", actionType: "send_email",
      icon: "📧", label: "Confirm delivery to customer",
      description: "Email the customer their delivery date",
      defaultConfig: {
        action_type: "send_email",
        to: "{current_record.customer_email}",
        subject: "Delivery scheduled",
        body: "Your delivery is confirmed for {input.ask_date}.",
      },
    },
  ],
  wf_mfg_log_pour: [
    {
      type: "action", actionType: "send_notification",
      icon: "🔔", label: "Notify admin of pour",
      description: "Alert admin when pour is logged",
      defaultConfig: {
        action_type: "send_notification", notify_roles: ["admin"],
        title: "Production pour logged",
        body: "{input.ask_quantity} units of {input.ask_product.name} poured.",
      },
    },
  ],
  wf_fh_first_call: [
    {
      type: "action", actionType: "send_sms",
      icon: "💬", label: '"In our care" message',
      description: "Send comfort message to family",
      defaultConfig: {
        action_type: "send_sms",
        to: "{input.ask_contact.phone}",
        body: "Your loved one is now in our care. We will be in touch shortly.",
      },
    },
    {
      type: "action", actionType: "send_notification",
      icon: "🔔", label: "Notify on-call director",
      description: "Alert the assigned director",
      defaultConfig: {
        action_type: "send_notification",
        notify_user_id: "{input.ask_director.id}",
        title: "New first call assigned",
        body: "A new case has been assigned to you.",
      },
    },
  ],
  wf_fh_schedule_arrangement: [
    {
      type: "action", actionType: "send_sms",
      icon: "💬", label: "Text family reminder",
      description: "Send family a text reminder",
      defaultConfig: {
        action_type: "send_sms",
        to: "{input.ask_case.primary_contact_phone}",
        body: "Reminder: your arrangement conference is {input.ask_datetime}.",
      },
    },
    {
      type: "action", actionType: "send_email",
      icon: "📧", label: "Email arrangement confirmation",
      description: "Send email confirmation to family",
      defaultConfig: {
        action_type: "send_email",
        to: "{input.ask_case.primary_contact_email}",
        subject: "Arrangement conference confirmed",
        body: "Your arrangement conference is confirmed for {input.ask_datetime}.",
      },
    },
  ],
}

const CATEGORY_COLOR: Record<CategoryDef["color"], string> = {
  blue: "bg-blue-50 text-blue-600",
  purple: "bg-violet-50 text-violet-600",
  amber: "bg-amber-50 text-amber-700",
  green: "bg-emerald-50 text-emerald-700",
  gray: "bg-slate-50 text-slate-600",
  slate: "bg-slate-100 text-slate-700",
}

// ─────────────────────────────────────────────────────────────────────

export function BlockLibrary({
  onDragStart,
  onClick,
  workflowId,
}: {
  onDragStart: (block: BlockDefinition) => void
  onClick: (block: BlockDefinition) => void
  /** When provided, shows workflow-specific suggested blocks at the top. */
  workflowId?: string
}) {
  const suggestions = workflowId ? WORKFLOW_SUGGESTIONS[workflowId] ?? [] : []
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
        {/* Workflow-specific suggestions — shown above categories when
            no search is active and the workflow has suggestions. */}
        {suggestions.length > 0 && !isSearching && (
          <div>
            <div className="px-4 py-2.5 flex items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-600">
                ✨ Suggested
              </span>
              <span className="text-[10px] text-slate-400">for this workflow</span>
            </div>
            <div className="px-3 pb-3 space-y-1">
              {suggestions.map((block, i) => (
                <BlockItem
                  key={`sug-${i}`}
                  block={block}
                  color="blue"
                  onDragStart={onDragStart}
                  onClick={onClick}
                />
              ))}
            </div>
            <div className="mx-4 border-t border-slate-100 mb-1" />
          </div>
        )}

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
