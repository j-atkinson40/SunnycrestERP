// CommandBar.tsx — Universal command bar (Cmd+K / Ctrl+K)

import { useState, useEffect, useRef, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Search, ArrowRight, Check, Loader2, X } from "lucide-react"

interface CommandResult {
  intent: string
  display_text: string
  navigation_url: string | null
  results: { id: string; name: string; type: string; url: string; subtitle?: string | null }[] | null
  answer: string | null
  action: {
    type: string
    parameters: Record<string, unknown>
    confirmation_required: boolean
    confirmation_text: string
  } | null
}

const SUGGESTIONS = [
  { text: "View today's services", icon: "📋" },
  { text: "Check overdue invoices", icon: "💰" },
  { text: "Open legacy library", icon: "🎨" },
  { text: "Go to companies", icon: "🏢" },
]

export default function CommandBar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<CommandResult | null>(null)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [executing, setExecuting] = useState(false)

  // Auto-focus on open
  useEffect(() => {
    if (open) {
      setQuery("")
      setResult(null)
      setSelectedIdx(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Debounced query
  const processQuery = useCallback(async (q: string) => {
    if (q.trim().length < 2) { setResult(null); return }
    setLoading(true)
    try {
      const res = await apiClient.post("/ai/command", {
        query: q,
        context: { current_page: window.location.pathname },
      })
      setResult(res.data)
      setSelectedIdx(0)
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    const t = setTimeout(() => processQuery(query), 300)
    return () => clearTimeout(t)
  }, [query, open, processQuery])

  function handleSelect() {
    if (!result) return

    if (result.intent === "navigate" && result.navigation_url) {
      navigate(result.navigation_url)
      onClose()
    } else if (result.intent === "search" && result.results && result.results[selectedIdx]) {
      navigate(result.results[selectedIdx].url)
      onClose()
    } else if (result.intent === "action" && result.action) {
      if (result.action.confirmation_required) {
        // Show confirmation — already visible
      } else {
        handleExecute()
      }
    }
  }

  async function handleExecute() {
    if (!result?.action) return
    setExecuting(true)
    try {
      const res = await apiClient.post("/ai/command/execute", {
        action_type: result.action.type,
        parameters: result.action.parameters,
      })
      if (res.data.success) {
        toast.success(res.data.message)
        onClose()
      } else {
        toast.error(res.data.message)
      }
    } catch {
      toast.error("Failed to execute action")
    } finally {
      setExecuting(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") { onClose(); return }
    if (e.key === "Enter") { handleSelect(); return }
    if (e.key === "ArrowDown") {
      e.preventDefault()
      const max = result?.results?.length || 0
      setSelectedIdx((prev) => Math.min(prev + 1, max - 1))
    }
    if (e.key === "ArrowUp") {
      e.preventDefault()
      setSelectedIdx((prev) => Math.max(prev - 1, 0))
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative w-full max-w-[640px] mx-4 bg-white rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b">
          <Search className="h-5 w-5 text-gray-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What do you want to do?"
            className="flex-1 text-base outline-none bg-transparent placeholder:text-gray-400"
          />
          {loading && <Loader2 className="h-4 w-4 animate-spin text-gray-400" />}
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results area */}
        <div className="max-h-[400px] overflow-y-auto">
          {/* No query — show suggestions */}
          {!query && !result && (
            <div className="p-3">
              <p className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold px-2 mb-1">Suggestions</p>
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { setQuery(s.text); processQuery(s.text) }}
                  className="w-full flex items-center gap-2 px-2 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-50"
                >
                  <span>{s.icon}</span> {s.text}
                </button>
              ))}
            </div>
          )}

          {/* Navigate result */}
          {result?.intent === "navigate" && result.navigation_url && (
            <button
              onClick={() => { navigate(result.navigation_url!); onClose() }}
              className="w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-gray-50"
            >
              <ArrowRight className="h-4 w-4 text-blue-500" />
              <span>{result.display_text}</span>
            </button>
          )}

          {/* Search results */}
          {result?.intent === "search" && result.results && (
            <div className="p-1">
              {result.results.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No results found</p>
              ) : (
                result.results.map((r, i) => (
                  <button
                    key={r.id}
                    onClick={() => { navigate(r.url); onClose() }}
                    className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-md ${
                      i === selectedIdx ? "bg-blue-50 text-blue-700" : "hover:bg-gray-50"
                    }`}
                  >
                    <div>
                      <span className="font-medium">{r.name}</span>
                      {r.subtitle && <span className="text-gray-400 ml-2">{r.subtitle}</span>}
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-gray-300" />
                  </button>
                ))
              )}
            </div>
          )}

          {/* Question answer */}
          {result?.intent === "question" && result.answer && (
            <div className="p-4">
              <p className="text-sm text-gray-800">{result.answer}</p>
            </div>
          )}

          {/* Action confirmation */}
          {result?.intent === "action" && result.action && (
            <div className="p-4 space-y-3">
              {result.display_text === "Action commands are disabled. Enable in AI Settings." ? (
                <p className="text-sm text-gray-500">{result.display_text}</p>
              ) : (
                <>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-1">I'll do this:</p>
                    <p className="text-sm font-medium">{result.action.confirmation_text || result.display_text}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleExecute}
                      disabled={executing}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50"
                    >
                      <Check className="h-3.5 w-3.5" /> {executing ? "..." : "Confirm"}
                    </button>
                    <button onClick={onClose} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700">
                      Cancel
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t bg-gray-50 flex items-center justify-between text-[10px] text-gray-400">
          <span>↑↓ navigate · Enter select · Esc close</span>
          <span>Powered by AI</span>
        </div>
      </div>
    </div>
  )
}
