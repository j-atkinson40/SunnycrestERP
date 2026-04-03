// ai-settings.tsx — AI & Intelligence settings page
// Route: /settings/ai-intelligence

import { useState, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Loader2 } from "lucide-react"

interface Settings { [key: string]: unknown }

interface FeatureItem {
  key: string
  label: string
  description: string
  cost: "included" | "low_cost" | "usage_based"
  defaultOn: boolean
  subSettings?: React.ReactNode
}

const COST_BADGES: Record<string, { label: string; className: string }> = {
  included: { label: "Included", className: "bg-green-100 text-green-700" },
  low_cost: { label: "Low cost", className: "bg-yellow-100 text-yellow-700" },
  usage_based: { label: "Usage-based", className: "bg-orange-100 text-orange-700" },
}

export default function AiSettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    apiClient.get("/settings/ai")
      .then((r) => setSettings(r.data))
      .catch(() => toast.error("Could not load AI settings"))
      .finally(() => setLoading(false))
  }, [])

  function set(key: string, value: unknown) {
    setSettings((prev) => prev ? { ...prev, [key]: value } : prev)
    setDirty(true)
  }

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    try {
      const res = await apiClient.patch("/settings/ai", settings)
      setSettings(res.data)
      setDirty(false)
      toast.success("AI settings saved")
    } catch {
      toast.error("Failed to save")
    } finally {
      setSaving(false)
    }
  }

  if (loading || !settings) {
    return <div className="max-w-3xl mx-auto p-6 flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>
  }

  function renderFeature(f: FeatureItem) {
    const enabled = settings![`${f.key}_enabled`] as boolean
    const badge = COST_BADGES[f.cost]
    return (
      <div key={f.key} className="py-4 border-b border-gray-100 last:border-0">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{f.label}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${badge.className}`}>{badge.label}</span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">{f.description}</p>
          </div>
          <Switch checked={enabled} onCheckedChange={(v) => set(`${f.key}_enabled`, v)} />
        </div>
        {enabled && f.subSettings && <div className="mt-3 ml-1 pl-3 border-l-2 border-gray-100">{f.subSettings}</div>}
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AI & Intelligence</h1>
        <p className="text-sm text-gray-500 mt-1">Configure which AI features are active for your account</p>
      </div>

      {Boolean(settings.founding_licensee) && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800 flex items-center gap-2">
          <span className="text-lg">⭐</span>
          <div>
            <span className="font-medium">Founding Licensee</span> — All AI usage costs are included in your subscription for life.
          </div>
        </div>
      )}

      {/* Morning Briefing */}
      <Card className="p-5">
        <h2 className="font-semibold text-base mb-2">Morning Briefing</h2>
        {renderFeature({
          key: "briefing_narrative", label: "Daily Briefing Narrative", cost: "included", defaultOn: true,
          description: "AI-written summary at the top of your morning briefing describing your day in plain English.",
          subSettings: (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Tone:</div>
              <div className="flex gap-3">
                {["concise", "detailed"].map((t) => (
                  <label key={t} className="flex items-center gap-1.5 text-xs">
                    <input type="radio" checked={settings.briefing_narrative_tone === t} onChange={() => set("briefing_narrative_tone", t)} className="accent-blue-600" />
                    {t === "concise" ? "Concise (2-3 sentences)" : "Detailed (full paragraph)"}
                  </label>
                ))}
              </div>
            </div>
          ),
        })}
        {renderFeature({ key: "pattern_alerts", label: "Pattern Recognition Alerts", cost: "included", defaultOn: true,
          description: "Monitors order and payment data for unusual patterns and surfaces them in your briefing.",
          subSettings: (
            <div className="space-y-1">
              <div className="text-xs text-gray-500">Sensitivity:</div>
              <div className="flex gap-3">
                {["conservative", "moderate", "aggressive"].map((s) => (
                  <label key={s} className="flex items-center gap-1.5 text-xs">
                    <input type="radio" checked={settings.pattern_alerts_sensitivity === s} onChange={() => set("pattern_alerts_sensitivity", s)} className="accent-blue-600" />
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </label>
                ))}
              </div>
            </div>
          ),
        })}
        {renderFeature({ key: "weekly_summary", label: "Weekly Business Summary", cost: "included", defaultOn: false,
          description: "Weekly summary of business performance — revenue, order count, payment trends, and notable events." })}
        {renderFeature({ key: "prep_notes", label: "Prep Notes for Follow-ups", cost: "included", defaultOn: true,
          description: "Briefing includes prep notes with recent order history and suggested talking points for scheduled follow-ups." })}
        {renderFeature({ key: "seasonal_intelligence", label: "Seasonal Intelligence", cost: "included", defaultOn: false,
          description: "Learns seasonal order patterns and surfaces proactive suggestions. Requires 12+ months of order history." })}
      </Card>

      {/* CRM Intelligence */}
      <Card className="p-5">
        <h2 className="font-semibold text-base mb-2">CRM Intelligence</h2>
        {renderFeature({ key: "conversational_lookup", label: "Conversational Company Lookup", cost: "included", defaultOn: true,
          description: "Ask plain-English questions about any company on their profile page." })}
        {renderFeature({ key: "natural_language_filters", label: "Natural Language Filters", cost: "included", defaultOn: true,
          description: "Type searches like 'last month, funeral homes, over $2000' instead of using dropdown filters." })}
        {renderFeature({ key: "smart_followup", label: "Smart Follow-up Suggestions", cost: "included", defaultOn: true,
          description: "Suggests follow-ups after logged activities if the content warrants one." })}
        {renderFeature({ key: "duplicate_detection", label: "Duplicate Detection", cost: "included", defaultOn: true,
          description: "Weekly background scan that flags company records that might be duplicates." })}
        {renderFeature({ key: "auto_enrichment", label: "Auto-Enrichment Agent", cost: "low_cost", defaultOn: false,
          description: "Fills missing phone numbers, emails, and websites using Google Places. Each lookup uses one API call." })}
        {renderFeature({ key: "upsell_detector", label: "Upsell Opportunity Detector", cost: "included", defaultOn: true,
          description: "Surfaces upgrade opportunities — like funeral homes who haven't tried personalization." })}
        {renderFeature({ key: "account_rescue", label: "Account Rescue Drafts", cost: "included", defaultOn: false,
          description: "Drafts personalized outreach emails for at-risk accounts you can review and send." })}
        {renderFeature({ key: "relationship_scoring", label: "Relationship Strength Scoring", cost: "included", defaultOn: true,
          description: "Weekly relationship health score based on order consistency, payment reliability, and communication." })}
        {renderFeature({ key: "payment_prediction", label: "Payment Prediction", cost: "included", defaultOn: false,
          description: "Predicts when open invoices will be paid and generates cash flow forecasts. Requires 6+ months of history." })}
        {renderFeature({ key: "new_customer_intelligence", label: "New Customer Intelligence", cost: "included", defaultOn: true,
          description: "Researches similar customers and suggests expected order volume when a new company is added." })}
      </Card>

      {/* Command Bar */}
      <Card className="p-5">
        <h2 className="font-semibold text-base mb-2">Command Bar</h2>
        {renderFeature({
          key: "command_bar", label: "Universal Command Bar", cost: "included", defaultOn: true,
          description: "Press Cmd+K anywhere to search, navigate, and take actions using plain English.",
          subSettings: (
            <div className="space-y-2">
              <div className="text-xs text-gray-500">Action level:</div>
              {[
                { val: "view_only", label: "View & navigate only", desc: "Searches and opens pages. Never creates or changes data." },
                { val: "review", label: "Actions with review", desc: "Can create records and log activities — always confirms first." },
                { val: "auto", label: "Full auto actions", desc: "Executes immediately. 30-second undo available." },
              ].map((opt) => (
                <label key={opt.val} className="flex items-start gap-2 text-xs p-2 rounded hover:bg-gray-50 cursor-pointer">
                  <input type="radio" checked={settings.command_bar_action_tier === opt.val} onChange={() => set("command_bar_action_tier", opt.val)} className="mt-0.5 accent-blue-600" />
                  <div><div className="font-medium">{opt.label}</div><div className="text-gray-400">{opt.desc}</div></div>
                </label>
              ))}
              {settings.command_bar_action_tier === "auto" && (
                <p className="text-xs text-amber-600 bg-amber-50 rounded p-2">Actions will execute immediately without confirmation.</p>
              )}
            </div>
          ),
        })}
      </Card>

      {/* Voice */}
      <Card className="p-5">
        <h2 className="font-semibold text-base mb-2">Voice Features</h2>
        {renderFeature({ key: "voice_memo", label: "Voice Memo to Activity Log", cost: "usage_based", defaultOn: false,
          description: "Hold the microphone button and speak — transcribes and creates an activity log entry." })}
        {renderFeature({ key: "voice_commands", label: "Voice Commands", cost: "usage_based", defaultOn: false,
          description: "Use voice to navigate, complete follow-ups, and trigger actions without touching the screen." })}
      </Card>

      {/* Call Intelligence */}
      <Card className="p-5">
        <h2 className="font-semibold text-base mb-2">Call Intelligence</h2>
        <p className="text-xs text-gray-400 mb-3">Requires RingCentral integration to be connected.</p>
        {renderFeature({ key: "after_call_intelligence", label: "After-Call Intelligence", cost: "included", defaultOn: true,
          description: "Analyzes call transcripts for key topics, outcomes, and action items." })}
        {renderFeature({ key: "commitment_detection", label: "Commitment Detection", cost: "included", defaultOn: true,
          description: "Detects commitments made on calls and auto-creates follow-up tasks." })}
        {renderFeature({ key: "tone_analysis", label: "Tone Analysis", cost: "included", defaultOn: false,
          description: "Detects caller sentiment. Flags calls where a customer seemed frustrated." })}
      </Card>

      {/* Per-user */}
      <Card className="p-5">
        <h2 className="font-semibold text-base mb-2">Per-User Settings</h2>
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="font-medium text-sm">Allow Personal Preferences</span>
            <p className="text-xs text-gray-500 mt-0.5">Team members can customize their own AI feature preferences within your limits.</p>
          </div>
          <Switch checked={settings.allow_per_user_settings as boolean} onCheckedChange={(v) => set("allow_per_user_settings", v)} />
        </div>
      </Card>

      {/* Usage */}
      {Boolean(settings.usage) && (
        <Card className="p-5">
          <h2 className="font-semibold text-base mb-2">Usage This Month</h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div><div className="text-2xl font-bold">{(settings.usage as Record<string, number>).google_places_calls}</div><div className="text-xs text-gray-500">Google Places</div></div>
            <div><div className="text-2xl font-bold">{(settings.usage as Record<string, number>).transcription_minutes}</div><div className="text-xs text-gray-500">Transcription min</div></div>
            <div><div className="text-2xl font-bold">{(settings.usage as Record<string, number>).claude_api_calls}</div><div className="text-xs text-gray-500">AI calls</div></div>
          </div>
        </Card>
      )}

      {/* Run Agents */}
      <Card className="p-5 space-y-3">
        <h2 className="font-semibold text-base">Background Agents</h2>
        <p className="text-xs text-gray-500">Run AI agents manually or view recent activity.</p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={async () => {
            toast.info("Running agents... this may take a minute.")
            try {
              const res = await apiClient.get("/ai/agents/run-nightly")
              toast.success("Agents complete")
              console.log("Agent results:", JSON.stringify(res.data, null, 2))
              alert(JSON.stringify(res.data, null, 2))
            } catch (err: unknown) {
              const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
              toast.error(detail || "Agent run failed")
            }
          }}>
            Run nightly agents now
          </Button>
        </div>
      </Card>

      {/* Save */}
      {dirty && (
        <div className="sticky bottom-0 bg-white border-t py-4 -mx-6 px-6">
          <Button onClick={handleSave} disabled={saving} className="w-full">{saving ? "Saving..." : "Save settings"}</Button>
        </div>
      )}
    </div>
  )
}
