// delivery.tsx — Legacy delivery settings: print deadline, contacts, Dropbox, Drive, watermark

import { useState, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Loader2, Plus, X, ExternalLink } from "lucide-react"

interface DeliverySettings {
  print_deadline_days_before: number
  watermark_enabled: boolean
  watermark_text: string
  watermark_opacity: number
  watermark_position: string
  dropbox_connected: boolean
  dropbox_target_folder: string | null
  dropbox_auto_save: boolean
  gdrive_connected: boolean
  gdrive_folder_name: string | null
  gdrive_auto_save: boolean
  print_shop_delivery: string
  contacts: { id: string; name: string; email: string; is_primary: boolean }[]
}

export default function LegacyDeliverySettingsTab() {
  const [settings, setSettings] = useState<DeliverySettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState("")
  const [newEmail, setNewEmail] = useState("")

  useEffect(() => {
    apiClient.get("/legacy/settings")
      .then((r) => setSettings(r.data))
      .catch(() => toast.error("Could not load settings"))
      .finally(() => setLoading(false))
  }, [])

  async function save(updates: Record<string, unknown>) {
    try {
      await apiClient.patch("/legacy/settings", updates)
      setSettings((s) => s ? { ...s, ...updates } as DeliverySettings : s)
    } catch {
      toast.error("Failed to save")
    }
  }

  async function addContact() {
    if (!newName.trim() || !newEmail.trim()) return
    try {
      await apiClient.post("/legacy/settings/contacts", { name: newName, email: newEmail })
      setNewName("")
      setNewEmail("")
      const r = await apiClient.get("/legacy/settings")
      setSettings(r.data)
      toast.success("Contact added")
    } catch {
      toast.error("Failed")
    }
  }

  async function removeContact(id: string) {
    try {
      await apiClient.delete(`/legacy/settings/contacts/${id}`)
      setSettings((s) => s ? { ...s, contacts: s.contacts.filter((c) => c.id !== id) } : s)
    } catch {
      toast.error("Failed")
    }
  }

  if (loading || !settings) {
    return <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
  }

  return (
    <div className="space-y-6">
      {/* Print deadline */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Print deadline</h3>
        <div className="flex items-center gap-2">
          <Input type="number" min={0} max={14} value={settings.print_deadline_days_before} onChange={(e) => save({ print_deadline_days_before: parseInt(e.target.value) || 1 })} className="w-20" />
          <span className="text-sm text-gray-600">days before service</span>
        </div>
      </Card>

      {/* Print shop contacts */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Print shop recipients</h3>
        {settings.contacts.map((c) => (
          <div key={c.id} className="flex items-center justify-between text-sm bg-gray-50 rounded-lg px-3 py-2">
            <span>{c.name} — {c.email} {c.is_primary && <span className="text-[10px] text-blue-600 ml-1">Primary</span>}</span>
            <button onClick={() => removeContact(c.id)}><X className="h-4 w-4 text-gray-400" /></button>
          </div>
        ))}
        <div className="flex gap-2">
          <Input placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} className="flex-1" />
          <Input placeholder="Email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} className="flex-1" />
          <Button size="sm" onClick={addContact}><Plus className="h-4 w-4" /></Button>
        </div>
      </Card>

      {/* Delivery method */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Print file delivery</h3>
        {[
          { value: "link", label: "Download link", desc: "Dropbox or Drive link in email" },
          { value: "attachment", label: "Email attachment", desc: "TIF attached directly (50-200MB)" },
          { value: "both", label: "Both", desc: "Link and attachment" },
        ].map((opt) => (
          <label key={opt.value} className="flex items-start gap-2 text-sm">
            <input type="radio" name="delivery" checked={settings.print_shop_delivery === opt.value} onChange={() => save({ print_shop_delivery: opt.value })} className="mt-1 accent-blue-600" />
            <div><div className="font-medium">{opt.label}</div><div className="text-xs text-gray-500">{opt.desc}</div></div>
          </label>
        ))}
      </Card>

      {/* Dropbox */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Dropbox</h3>
        {settings.dropbox_connected ? (
          <>
            <p className="text-xs text-green-600 font-medium">Connected ✓</p>
            <div><Label className="text-xs">Target folder</Label><Input value={settings.dropbox_target_folder || ""} onChange={(e) => save({ dropbox_target_folder: e.target.value })} placeholder="/Bridgeable Legacies" className="mt-1" /></div>
            <div className="flex items-center justify-between"><Label className="text-sm">Auto-save on approval</Label><Switch checked={settings.dropbox_auto_save} onCheckedChange={(v: boolean) => save({ dropbox_auto_save: v })} /></div>
          </>
        ) : (
          <Button onClick={() => apiClient.get("/legacy/auth/dropbox/connect").then((r) => { window.location.href = r.data.auth_url }).catch(() => toast.error("Not configured"))}><ExternalLink className="h-4 w-4 mr-1" /> Connect Dropbox</Button>
        )}
      </Card>

      {/* Google Drive */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Google Drive</h3>
        {settings.gdrive_connected ? (
          <>
            <p className="text-xs text-green-600 font-medium">Connected ✓</p>
            {settings.gdrive_folder_name && <p className="text-xs text-gray-600">Folder: {settings.gdrive_folder_name}</p>}
            <div className="flex items-center justify-between"><Label className="text-sm">Auto-save on approval</Label><Switch checked={settings.gdrive_auto_save} onCheckedChange={(v: boolean) => save({ gdrive_auto_save: v })} /></div>
          </>
        ) : (
          <Button onClick={() => apiClient.get("/legacy/auth/gdrive/connect").then((r) => { window.location.href = r.data.auth_url }).catch(() => toast.error("Not configured"))}><ExternalLink className="h-4 w-4 mr-1" /> Connect Google Drive</Button>
        )}
      </Card>

      {/* Watermark */}
      <Card className="p-4 space-y-3">
        <div className="flex items-center justify-between"><h3 className="font-semibold text-sm">Proof watermark</h3><Switch checked={settings.watermark_enabled} onCheckedChange={(v: boolean) => save({ watermark_enabled: v })} /></div>
        {settings.watermark_enabled && (
          <>
            <div><Label className="text-xs">Text</Label><Input value={settings.watermark_text} onChange={(e) => save({ watermark_text: e.target.value })} className="mt-1" /></div>
            <div><Label className="text-xs">Opacity ({Math.round(settings.watermark_opacity * 100)}%)</Label><input type="range" min="0.1" max="0.8" step="0.05" value={settings.watermark_opacity} onChange={(e) => save({ watermark_opacity: parseFloat(e.target.value) })} className="w-full mt-1" /></div>
            <div><Label className="text-xs">Position</Label>
              <div className="flex gap-2 mt-1 flex-wrap">
                {["center", "bottom-right", "bottom-left", "top-right"].map((p) => (
                  <button key={p} onClick={() => save({ watermark_position: p })} className={`px-3 py-1.5 text-xs rounded-lg border ${settings.watermark_position === p ? "bg-gray-900 text-white border-gray-900" : "border-gray-200"}`}>{p.replace("-", " ")}</button>
                ))}
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
