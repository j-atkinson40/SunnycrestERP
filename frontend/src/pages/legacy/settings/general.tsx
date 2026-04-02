// general.tsx — Legacy general settings: file naming, output quality, library defaults

import { useState, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Loader2 } from "lucide-react"

export default function LegacyGeneralSettingsTab() {
  const [template, setTemplate] = useState("{print_name} - {name}.tif")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient.get("/legacy/settings")
      .then((r) => {
        if (r.data.tif_filename_template) setTemplate(r.data.tif_filename_template)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function saveTemplate(val: string) {
    setTemplate(val)
    try {
      await apiClient.patch("/legacy/settings", { tif_filename_template: val })
    } catch {
      toast.error("Failed to save")
    }
  }

  const preview = template
    .replace("{print_name}", "Autumn Lake")
    .replace("{name}", "Robert James Smith")
    .replace("{dates}", "1942 — 2026")
    .replace("{fh_name}", "Johnson Funeral Home")
    .replace("{date}", new Date().toISOString().split("T")[0])

  if (loading) {
    return <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
  }

  return (
    <div className="space-y-6">
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">TIF file naming</h3>
        <Input value={template} onChange={(e) => saveTemplate(e.target.value)} />
        <p className="text-[11px] text-gray-400">
          Variables: {"{print_name}"} {"{name}"} {"{dates}"} {"{fh_name}"} {"{order_number}"} {"{date}"}
        </p>
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <Label className="text-[10px] text-gray-500">Preview</Label>
          <p className="text-sm font-mono text-gray-700">{preview}</p>
        </div>
      </Card>

      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Proof output quality</h3>
        <div className="space-y-2">
          <label className="flex items-start gap-2 text-sm">
            <input type="radio" name="quality" defaultChecked className="mt-1 accent-blue-600" />
            <div>
              <div className="font-medium">High (2400px)</div>
              <div className="text-xs text-gray-500">Recommended for screen and email (~400KB)</div>
            </div>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="radio" name="quality" className="mt-1 accent-blue-600" />
            <div>
              <div className="font-medium">Very high (3600px)</div>
              <div className="text-xs text-gray-500">For large displays (~800KB)</div>
            </div>
          </label>
        </div>
        <p className="text-[11px] text-gray-400">Print TIF files are always full resolution at 400 DPI.</p>
      </Card>

      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Library defaults</h3>
        <div>
          <Label className="text-xs">Default sort order</Label>
          <div className="space-y-1 mt-1">
            <label className="flex items-center gap-2 text-sm"><input type="radio" name="sort" defaultChecked className="accent-blue-600" /> Newest first</label>
            <label className="flex items-center gap-2 text-sm"><input type="radio" name="sort" className="accent-blue-600" /> Service date (soonest first)</label>
            <label className="flex items-center gap-2 text-sm"><input type="radio" name="sort" className="accent-blue-600" /> Funeral home A-Z</label>
          </div>
        </div>
      </Card>
    </div>
  )
}
