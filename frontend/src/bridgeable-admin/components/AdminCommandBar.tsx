import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useNavigate } from "react-router-dom"
import { Search, Sparkles, X, ChevronRight } from "lucide-react"
import {
  isQuestion,
  rankActions,
  type CommandAction,
} from "../lib/admin-command-actions"

interface CommandBarContextValue {
  open: boolean
  setOpen: (v: boolean) => void
  mode: "command" | "chat"
}

const CommandBarContext = createContext<CommandBarContextValue | null>(null)

export function AdminCommandBarProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<"command" | "chat">("command")

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((o) => !o)
        setMode("command")
      }
      if (e.key === "Escape") {
        setOpen(false)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  return (
    <CommandBarContext.Provider value={{ open, setOpen, mode }}>
      {children}
      {open && <CommandBarDialog />}
    </CommandBarContext.Provider>
  )
}

export function useCommandBar() {
  const ctx = useContext(CommandBarContext)
  if (!ctx) throw new Error("useCommandBar must be inside provider")
  return ctx
}

type ChatMsg = { role: "user" | "assistant"; content: string }

function CommandBarDialog() {
  const { setOpen } = useCommandBar()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [query, setQuery] = useState("")
  const [selected, setSelected] = useState(0)
  const [isChatMode, setIsChatMode] = useState(false)
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState("")
  const [streaming, setStreaming] = useState(false)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const ranked = useMemo(() => {
    if (isChatMode) return []
    const q = isQuestion(query)
    const ranked = rankActions(query)
    if (q) {
      // Ensure ASK action is at top
      const ask = ranked.find((a) => a.type === "ASK") || {
        id: "ask",
        title: "Ask Bridgeable Assistant",
        subtitle: query.slice(0, 60),
        keywords: [],
        type: "ASK" as const,
        handler: "openChatMode",
      }
      return [ask, ...ranked.filter((a) => a.type !== "ASK")]
    }
    return ranked
  }, [query, isChatMode])

  // Number key shortcuts Cmd+1..5
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && /^[1-9]$/.test(e.key)) {
        const idx = parseInt(e.key, 10) - 1
        if (ranked[idx]) {
          e.preventDefault()
          executeAction(ranked[idx])
        }
      }
      if (!isChatMode) {
        if (e.key === "ArrowDown") {
          e.preventDefault()
          setSelected((s) => Math.min(ranked.length - 1, s + 1))
        }
        if (e.key === "ArrowUp") {
          e.preventDefault()
          setSelected((s) => Math.max(0, s - 1))
        }
        if (e.key === "Enter" && ranked[selected]) {
          e.preventDefault()
          executeAction(ranked[selected])
        }
      }
    }
    window.addEventListener("keydown", h)
    return () => window.removeEventListener("keydown", h)
  }, [ranked, selected, isChatMode])

  const executeAction = (action: CommandAction) => {
    if (action.type === "NAVIGATE") {
      navigate(action.handler)
      setOpen(false)
      return
    }
    if (action.type === "ASK") {
      setIsChatMode(true)
      const seed = query.trim() || ""
      setChatInput(seed)
      if (seed) {
        void sendChatMessage(seed)
        setChatInput("")
      }
      return
    }
    // COMMAND actions that need confirmation or modal
    if (action.handler === "searchTenants") {
      navigate(`/bridgeable-admin/tenants?q=${encodeURIComponent(query)}`)
      setOpen(false)
      return
    }
    if (action.handler === "createStagingTenant") {
      navigate("/bridgeable-admin/staging/create")
      setOpen(false)
      return
    }
    if (action.handler === "showSavedPrompts") {
      navigate("/bridgeable-admin/saved-prompts")
      setOpen(false)
      return
    }
    // Fallback: just close
    setOpen(false)
  }

  async function sendChatMessage(content: string) {
    setMessages((m) => [...m, { role: "user", content }])
    setStreaming(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || "https://api.getbridgeable.com"}/api/platform/admin/chat/message`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("bridgeable-admin-token-production") || localStorage.getItem("bridgeable-admin-token-staging") || ""}`,
        },
        body: JSON.stringify({
          message: content,
          conversation_history: messages,
        }),
      })
      if (!res.body) {
        setStreaming(false)
        return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let assistantText = ""
      setMessages((m) => [...m, { role: "assistant", content: "" }])
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        // Parse SSE frames: `data: <content>\n\n`
        const lines = chunk.split("\n")
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const payload = line.slice(6).replace(/\\n/g, "\n")
            assistantText += payload
            setMessages((m) => [
              ...m.slice(0, -1),
              { role: "assistant", content: assistantText },
            ])
          }
        }
      }
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `Error: ${(err as Error).message}` },
      ])
    } finally {
      setStreaming(false)
    }
  }

  const handleChatSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim() || streaming) return
    const msg = chatInput
    setChatInput("")
    void sendChatMessage(msg)
  }

  const resetToCommand = () => {
    setIsChatMode(false)
    setMessages([])
    setQuery("")
    setChatInput("")
    inputRef.current?.focus()
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 z-[60] flex items-start justify-center pt-[10vh]"
      onClick={() => setOpen(false)}
    >
      <div
        className="bg-white rounded-lg shadow-2xl w-full max-w-2xl mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input */}
        {!isChatMode ? (
          <div className="flex items-center border-b border-slate-200 px-4">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setSelected(0)
              }}
              placeholder="Type a command or ask a question..."
              className="flex-1 py-3 px-3 outline-none text-slate-800"
            />
            <button onClick={() => setOpen(false)} className="p-1 hover:bg-slate-100 rounded">
              <X className="h-4 w-4 text-slate-400" />
            </button>
          </div>
        ) : (
          <div className="flex items-center border-b border-slate-200 px-4 py-2 bg-violet-50">
            <Sparkles className="h-4 w-4 text-violet-600" />
            <span className="flex-1 ml-2 text-sm font-medium text-violet-900">
              Chat with Bridgeable Assistant
            </span>
            <button
              onClick={resetToCommand}
              className="text-xs text-violet-700 hover:text-violet-900 mr-2"
            >
              New question
            </button>
            <button onClick={() => setOpen(false)} className="p-1 hover:bg-slate-100 rounded">
              <X className="h-4 w-4 text-slate-400" />
            </button>
          </div>
        )}

        {/* Results or chat */}
        {!isChatMode ? (
          <div className="max-h-[50vh] overflow-y-auto">
            {ranked.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">No matching actions</div>
            ) : (
              ranked.map((a, i) => (
                <button
                  key={a.id}
                  onClick={() => executeAction(a)}
                  onMouseEnter={() => setSelected(i)}
                  className={`w-full flex items-center justify-between text-left px-4 py-3 ${
                    i === selected ? "bg-slate-100" : "hover:bg-slate-50"
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-900">{a.title}</span>
                      <span
                        className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                          a.type === "ASK"
                            ? "bg-violet-100 text-violet-700"
                            : a.type === "NAVIGATE"
                              ? "bg-blue-100 text-blue-700"
                              : a.type === "RECORD"
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {a.type}
                      </span>
                    </div>
                    {a.subtitle && <div className="text-xs text-slate-500 mt-0.5">{a.subtitle}</div>}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <kbd className="px-1.5 py-0.5 border border-slate-300 rounded bg-slate-50">
                      ⌘{i + 1}
                    </kbd>
                    <ChevronRight className="h-4 w-4" />
                  </div>
                </button>
              ))
            )}
          </div>
        ) : (
          <div className="flex flex-col max-h-[60vh]">
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`${
                    m.role === "user" ? "bg-slate-100 text-slate-900" : "bg-violet-50 text-slate-800"
                  } px-3 py-2 rounded text-sm whitespace-pre-wrap`}
                >
                  {m.content}
                </div>
              ))}
              {streaming && (
                <div className="text-xs text-slate-400 animate-pulse">Streaming…</div>
              )}
            </div>
            <form onSubmit={handleChatSubmit} className="border-t border-slate-200 p-2 flex gap-2">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    handleChatSubmit(e as any)
                  }
                }}
                placeholder="Ask anything about the platform..."
                rows={2}
                className="flex-1 px-3 py-2 border border-slate-200 rounded text-sm outline-none focus:border-violet-400 resize-none"
                disabled={streaming}
              />
              <button
                type="submit"
                disabled={streaming || !chatInput.trim()}
                className="px-4 py-2 bg-violet-600 text-white rounded text-sm hover:bg-violet-700 disabled:opacity-50"
              >
                Send
              </button>
            </form>
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-slate-200 px-4 py-2 flex justify-between text-xs text-slate-400 bg-slate-50">
          <div>
            <kbd className="px-1 border border-slate-300 rounded bg-white">↑↓</kbd> navigate
            {" · "}
            <kbd className="px-1 border border-slate-300 rounded bg-white">⏎</kbd> execute
            {" · "}
            <kbd className="px-1 border border-slate-300 rounded bg-white">esc</kbd> close
          </div>
          <div>⌘K to toggle</div>
        </div>
      </div>
    </div>
  )
}
