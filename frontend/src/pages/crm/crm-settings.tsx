// crm-settings.tsx — CRM feature toggles and health score thresholds
// Route: /crm/settings

import { useState, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"

export default function CrmSettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [pipeline, setPipeline] = useState(false)
  const [healthScoring, setHealthScoring] = useState(true)
  const [activityLog, setActivityLog] = useState(true)
  const [multiplier, setMultiplier] = useState("2.0")
  const [trendDays, setTrendDays] = useState("7")
  const [thresholdDays, setThresholdDays] = useState("30")

  useEffect(() => {
    apiClient.get("/companies/crm-settings")
      .then((r) => {
        setPipeline(r.data.pipeline_enabled)
        setHealthScoring(r.data.health_scoring_enabled)
        setActivityLog(r.data.activity_log_enabled)
        setMultiplier(String(r.data.at_risk_days_multiplier))
        setTrendDays(String(r.data.at_risk_payment_trend_days))
        setThresholdDays(String(r.data.at_risk_payment_threshold_days))
      })
      .catch(() => toast.error("Could not load settings"))
      .finally(() => setLoading(false))
  }, [])

  async function handleSave() {
    setSaving(true)
    try {
      await apiClient.patch("/companies/crm-settings", {
        pipeline_enabled: pipeline,
        health_scoring_enabled: healthScoring,
        activity_log_enabled: activityLog,
        at_risk_days_multiplier: parseFloat(multiplier) || 2.0,
        at_risk_payment_trend_days: parseInt(trendDays) || 7,
        at_risk_payment_threshold_days: parseInt(thresholdDays) || 30,
      })
      toast.success("CRM settings saved")
    } catch {
      toast.error("Failed to save")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="max-w-2xl mx-auto p-6 text-gray-400">Loading...</div>

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
      <h1 className="text-2xl font-bold">CRM Settings</h1>

      {/* Health Scoring */}
      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">Account health scoring</h3>
            <p className="text-sm text-gray-500 mt-0.5">Automatically monitors funeral home accounts and flags those needing attention.</p>
          </div>
          <Switch checked={healthScoring} onCheckedChange={setHealthScoring} />
        </div>
        {healthScoring && (
          <div className="space-y-3 pt-3 border-t border-gray-100">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Thresholds</p>
            <div>
              <Label className="text-sm">Order gap multiplier</Label>
              <p className="text-xs text-gray-400">Flag when gap exceeds N× their average</p>
              <Input type="number" step="0.5" min="1" max="5" value={multiplier} onChange={(e) => setMultiplier(e.target.value)} className="mt-1 w-32" />
            </div>
            <div>
              <Label className="text-sm">Payment trend threshold (days)</Label>
              <p className="text-xs text-gray-400">Flag when avg payment time increases by this many days</p>
              <Input type="number" min="1" max="30" value={trendDays} onChange={(e) => setTrendDays(e.target.value)} className="mt-1 w-32" />
            </div>
            <div>
              <Label className="text-sm">Payment concern threshold (days)</Label>
              <p className="text-xs text-gray-400">Only flag if avg exceeds this many days</p>
              <Input type="number" min="7" max="90" value={thresholdDays} onChange={(e) => setThresholdDays(e.target.value)} className="mt-1 w-32" />
            </div>
          </div>
        )}
      </Card>

      {/* Activity Log */}
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">Activity log</h3>
            <p className="text-sm text-gray-500 mt-0.5">Automatically logs orders, payments, and legacy proofs in each company's activity feed.</p>
          </div>
          <Switch checked={activityLog} onCheckedChange={setActivityLog} />
        </div>
      </Card>

      {/* Pipeline */}
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">Sales pipeline</h3>
            <p className="text-sm text-gray-500 mt-0.5">Track prospective funeral homes through a kanban-style pipeline. Most useful for licensees actively growing their territory.</p>
          </div>
          <Switch checked={pipeline} onCheckedChange={setPipeline} />
        </div>
      </Card>

      <div className="sticky bottom-0 bg-white border-t py-4 -mx-6 px-6">
        <Button onClick={handleSave} disabled={saving} className="w-full">{saving ? "Saving..." : "Save settings"}</Button>
      </div>
    </div>
  )
}
