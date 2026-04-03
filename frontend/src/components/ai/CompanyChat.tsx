// CompanyChat.tsx — Conversational company lookup on detail page

import { useState } from "react"
import apiClient from "@/lib/api-client"
import { ChevronDown, ChevronUp, Send, Loader2 } from "lucide-react"

interface Message {
  role: "user" | "assistant"
  content: string
}

const SUGGESTIONS = [
  "Last order?",
  "Open balance?",
  "Payment history?",
  "Most ordered vault?",
  "Any complaints?",
]

export default function CompanyChat({ masterCompanyId, companyName }: { masterCompanyId: string; companyName: string }) {
  const [expanded, setExpanded] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)

  async function sendMessage(text: string) {
    if (!text.trim()) return
    const userMsg: Message = { role: "user", content: text }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput("")
    setLoading(true)

    try {
      const res = await apiClient.post("/ai/company-chat", {
        master_company_id: masterCompanyId,
        message: text,
        conversation_history: newMessages.slice(-8),
      })
      setMessages((prev) => [...prev, { role: "assistant", content: res.data.answer || "I couldn't find an answer." }])
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I couldn't process that right now." }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100"
      >
        <span>Ask about {companyName}</span>
        {expanded ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
      </button>

      {expanded && (
        <div className="p-3 space-y-3">
          {/* Suggestion chips */}
          {messages.length === 0 && (
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full text-xs hover:bg-blue-100 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Messages */}
          {messages.length > 0 && (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {messages.map((msg, i) => (
                <div key={i} className={`text-sm ${msg.role === "user" ? "text-right" : ""}`}>
                  <span className={`inline-block px-3 py-1.5 rounded-lg max-w-[85%] ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}>
                    {msg.content}
                  </span>
                </div>
              ))}
              {loading && (
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <Loader2 className="h-3 w-3 animate-spin" /> Thinking...
                </div>
              )}
            </div>
          )}

          {/* Input */}
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !loading) sendMessage(input) }}
              placeholder={`Ask about ${companyName}...`}
              className="flex-1 px-3 py-1.5 text-sm border rounded-md outline-none focus:ring-1 focus:ring-blue-300"
              disabled={loading}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              className="px-2.5 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
