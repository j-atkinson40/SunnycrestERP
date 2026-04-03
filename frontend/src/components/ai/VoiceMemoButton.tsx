// VoiceMemoButton.tsx — Record voice memo → transcribe → create activity

import { useState, useRef, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Mic, Square, Loader2, Check, X, Pencil } from "lucide-react"

interface VoiceMemoResult {
  activity_id: string
  transcript: string
  title: string
  body: string
  activity_type: string
  follow_up_created: boolean
  follow_up_date: string | null
  action_items: string[]
  error?: string
}

type State = "idle" | "recording" | "processing" | "review" | "error"

const ACTIVITY_ICONS: Record<string, string> = {
  call: "📞", visit: "🤝", note: "📝", complaint: "⚠", follow_up: "📅",
}

export default function VoiceMemoButton({
  masterCompanyId,
  onComplete,
  compact = false,
}: {
  masterCompanyId?: string
  onComplete?: () => void
  compact?: boolean
}) {
  const [state, setState] = useState<State>("idle")
  const [duration, setDuration] = useState(0)
  const [result, setResult] = useState<VoiceMemoResult | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop())
    }
  }, [])

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" })
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" })
        stream.getTracks().forEach((t) => t.stop())
        processAudio(blob)
      }

      recorder.start(1000) // Collect data every second
      recorderRef.current = recorder
      setState("recording")
      setDuration(0)

      timerRef.current = setInterval(() => {
        setDuration((d) => {
          if (d >= 300) { stopRecording(); return d } // 5 min max
          return d + 1
        })
      }, 1000)
    } catch {
      toast.error("Microphone access denied. Check browser permissions.")
      setState("idle")
    }
  }

  function stopRecording() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop()
    }
    setState("processing")
  }

  async function processAudio(blob: Blob) {
    try {
      const form = new FormData()
      form.append("audio", blob, "memo.webm")
      if (masterCompanyId) form.append("master_company_id", masterCompanyId)

      const res = await apiClient.post("/ai/voice-memo", form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      })

      if (res.data.error) {
        toast.error(res.data.error)
        setState("error")
        return
      }

      setResult(res.data)
      setState("review")
    } catch {
      toast.error("Failed to process voice memo")
      setState("error")
    }
  }

  function handleSave() {
    toast.success("Activity logged from voice memo")
    setState("idle")
    setResult(null)
    onComplete?.()
  }

  function handleDiscard() {
    if (!window.confirm("Discard this memo? The transcript will be lost.")) return
    // TODO: delete the activity that was already created
    setState("idle")
    setResult(null)
  }

  function fmtDuration(s: number) {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, "0")}`
  }

  // Idle
  if (state === "idle" || state === "error") {
    return (
      <button
        onClick={startRecording}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
          compact
            ? "bg-gray-100 hover:bg-gray-200 text-gray-700 p-2"
            : "bg-red-50 hover:bg-red-100 text-red-700 border border-red-200"
        }`}
        title="Record voice memo"
      >
        <Mic className={compact ? "h-4 w-4" : "h-3.5 w-3.5"} />
        {!compact && "Voice memo"}
      </button>
    )
  }

  // Recording
  if (state === "recording") {
    return (
      <div className="inline-flex items-center gap-2">
        <button
          onClick={stopRecording}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm font-medium animate-pulse"
        >
          <Square className="h-3.5 w-3.5" />
          Recording... {fmtDuration(duration)}
        </button>
        {duration >= 270 && <span className="text-xs text-amber-600">{300 - duration}s remaining</span>}
      </div>
    )
  }

  // Processing
  if (state === "processing") {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg text-sm text-gray-600">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Transcribing...
      </div>
    )
  }

  // Review
  if (state === "review" && result) {
    return (
      <Card className="p-4 space-y-3 border-blue-200 max-w-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-green-700">
            <Check className="h-4 w-4" /> Voice memo processed
          </div>
          <span className="text-xs text-gray-400">{ACTIVITY_ICONS[result.activity_type] || "📝"} {result.activity_type}</span>
        </div>

        <p className="text-sm text-gray-800 bg-gray-50 rounded p-2">{result.body}</p>

        {result.follow_up_created && result.follow_up_date && (
          <p className="text-xs text-blue-600">Follow-up: {result.follow_up_date}</p>
        )}

        {result.action_items.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 font-medium">Action items:</p>
            {result.action_items.map((item, i) => (
              <p key={i} className="text-xs text-gray-600">• {item}</p>
            ))}
          </div>
        )}

        <details className="text-xs text-gray-400">
          <summary className="cursor-pointer hover:text-gray-600">View transcript</summary>
          <p className="mt-1 italic">{result.transcript}</p>
        </details>

        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave}><Check className="h-3 w-3 mr-0.5" /> Save</Button>
          <Button size="sm" variant="ghost" onClick={handleDiscard}><X className="h-3 w-3 mr-0.5" /> Discard</Button>
        </div>
      </Card>
    )
  }

  return null
}
