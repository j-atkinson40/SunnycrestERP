// email.tsx — Legacy email settings: sender, branding, templates, FH config

import { useState, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { Loader2, Plus, X, Copy } from "lucide-react"

interface EmailSettings {
  sender_tier: string
  reply_to_email: string | null
  custom_from_email: string | null
  custom_from_name: string | null
  domain_verified: boolean
  proof_email_subject: string
  proof_email_body: string | null
  use_invoice_branding: boolean
  header_color: string | null
  logo_url: string | null
}

interface DNSRecord {
  type: string
  name: string
  value: string
}

export default function LegacyEmailSettingsTab() {
  const [settings, setSettings] = useState<EmailSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [verifyEmail, setVerifyEmail] = useState("")
  const [dnsRecords, setDnsRecords] = useState<DNSRecord[]>([])
  const [verifying, setVerifying] = useState(false)

  // FH config
  const [fhSearch, setFhSearch] = useState("")
  const [selectedFH, setSelectedFH] = useState<{ id: string; name: string } | null>(null)
  const [fhRecipients, setFhRecipients] = useState<{ name: string; email: string; is_primary: boolean }[]>([])
  const [fhSubject, setFhSubject] = useState("")
  const [fhNotes, setFhNotes] = useState("")
  const [newRecName, setNewRecName] = useState("")
  const [newRecEmail, setNewRecEmail] = useState("")

  useEffect(() => {
    apiClient.get("/legacy/email/settings")
      .then((r) => setSettings(r.data))
      .catch(() => toast.error("Could not load email settings"))
      .finally(() => setLoading(false))
  }, [])

  async function save(updates: Record<string, unknown>) {
    try {
      await apiClient.patch("/legacy/email/settings", updates)
      setSettings((s) => s ? { ...s, ...updates } as EmailSettings : s)
    } catch {
      toast.error("Failed to save")
    }
  }

  async function handleVerifyDomain() {
    if (!verifyEmail) return
    setVerifying(true)
    try {
      const r = await apiClient.post("/legacy/email/verify-domain", { email: verifyEmail })
      setDnsRecords(r.data.records || [])
      toast.success("DNS records generated — add them to your domain")
    } catch {
      toast.error("Failed to initiate verification")
    } finally {
      setVerifying(false)
    }
  }

  async function checkDomainStatus() {
    try {
      const r = await apiClient.get("/legacy/email/verify-domain/status")
      if (r.data.verified) {
        setSettings((s) => s ? { ...s, domain_verified: true } : s)
        toast.success("Domain verified!")
      } else {
        toast.info(`Status: ${r.data.status}`)
      }
    } catch {
      toast.error("Check failed")
    }
  }

  async function saveFHConfig() {
    if (!selectedFH) return
    try {
      await apiClient.post(`/legacy/fh-config/${selectedFH.id}`, {
        recipients: fhRecipients,
        custom_subject: fhSubject || null,
        custom_notes: fhNotes || null,
      })
      toast.success("FH email config saved")
    } catch {
      toast.error("Failed to save")
    }
  }

  function addRecipient() {
    if (!newRecName || !newRecEmail) return
    setFhRecipients([...fhRecipients, { name: newRecName, email: newRecEmail, is_primary: fhRecipients.length === 0 }])
    setNewRecName("")
    setNewRecEmail("")
  }

  if (loading || !settings) {
    return <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
  }

  return (
    <div className="space-y-6">
      {/* Sender */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Sender address</h3>
        <div className="space-y-2">
          <label className="flex items-start gap-2 text-sm cursor-pointer">
            <input type="radio" name="tier" checked={settings.sender_tier === "bridgeable"} onChange={() => save({ sender_tier: "bridgeable" })} className="mt-1 accent-blue-600" />
            <div>
              <div className="font-medium">Send from Bridgeable</div>
              <div className="text-xs text-gray-500">legacies@mail.getbridgeable.com — replies go to your email</div>
            </div>
          </label>
          {settings.sender_tier === "bridgeable" && (
            <div className="ml-6">
              <Label className="text-xs">Reply-to address</Label>
              <Input value={settings.reply_to_email || ""} onChange={(e) => save({ reply_to_email: e.target.value })} placeholder="your@email.com" className="mt-1" />
            </div>
          )}
          <label className="flex items-start gap-2 text-sm cursor-pointer">
            <input type="radio" name="tier" checked={settings.sender_tier === "custom"} onChange={() => save({ sender_tier: "custom" })} className="mt-1 accent-blue-600" />
            <div>
              <div className="font-medium">Send from your domain</div>
              <div className="text-xs text-gray-500">Professional — looks like it comes from your company</div>
            </div>
          </label>
        </div>

        {settings.sender_tier === "custom" && (
          <div className="ml-6 space-y-3">
            {settings.domain_verified ? (
              <div className="text-xs text-green-600 font-medium">Sending from: {settings.custom_from_email} ✓</div>
            ) : (
              <>
                <div>
                  <Label className="text-xs">Email address to send from</Label>
                  <div className="flex gap-2 mt-1">
                    <Input value={verifyEmail} onChange={(e) => setVerifyEmail(e.target.value)} placeholder="legacies@sunnycrest.com" className="flex-1" />
                    <Button size="sm" onClick={handleVerifyDomain} loading={verifying}>Verify domain</Button>
                  </div>
                </div>
                {dnsRecords.length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                    <p className="text-xs font-medium text-gray-700">Add these DNS records:</p>
                    {dnsRecords.map((r, i) => (
                      <div key={i} className="text-[11px] font-mono bg-white rounded p-2 flex items-center justify-between">
                        <span>{r.type} {r.name} → {r.value?.slice(0, 40)}...</span>
                        <button onClick={() => { navigator.clipboard.writeText(r.value); toast.success("Copied") }}><Copy className="h-3 w-3 text-gray-400" /></button>
                      </div>
                    ))}
                    <Button size="sm" variant="outline" onClick={checkDomainStatus}>Check verification status</Button>
                  </div>
                )}
              </>
            )}
            {settings.domain_verified && (
              <div>
                <Label className="text-xs">From name</Label>
                <Input value={settings.custom_from_name || ""} onChange={(e) => save({ custom_from_name: e.target.value })} placeholder="Sunnycrest Legacy Proofs" className="mt-1" />
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Branding */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Email branding</h3>
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="branding" checked={settings.use_invoice_branding} onChange={() => save({ use_invoice_branding: true })} className="accent-blue-600" />
            Mirror invoice branding
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="branding" checked={!settings.use_invoice_branding} onChange={() => save({ use_invoice_branding: false })} className="accent-blue-600" />
            Custom branding
          </label>
        </div>
        {!settings.use_invoice_branding && (
          <div className="space-y-2 ml-6">
            <div>
              <Label className="text-xs">Header color</Label>
              <Input type="color" value={settings.header_color || "#0F2137"} onChange={(e) => save({ header_color: e.target.value })} className="mt-1 w-20 h-8" />
            </div>
            <div>
              <Label className="text-xs">Logo URL</Label>
              <Input value={settings.logo_url || ""} onChange={(e) => save({ logo_url: e.target.value })} placeholder="https://..." className="mt-1" />
            </div>
          </div>
        )}
      </Card>

      {/* Subject template */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Proof email subject</h3>
        <Input value={settings.proof_email_subject} onChange={(e) => save({ proof_email_subject: e.target.value })} />
        <p className="text-[11px] text-gray-400">Variables: {"{name}"} {"{dates}"} {"{print_name}"} {"{funeral_home}"} {"{service_date}"}</p>
      </Card>

      {/* Per-FH config */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-sm">Per funeral home recipients</h3>
        {!selectedFH ? (
          <div>
            <Input placeholder="Search funeral home..." value={fhSearch} onChange={(e) => setFhSearch(e.target.value)} />
            <p className="text-[11px] text-gray-400 mt-1">Search and select a funeral home to configure recipients</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-sm">{selectedFH.name}</span>
              <button onClick={() => setSelectedFH(null)} className="text-xs text-blue-600">Change</button>
            </div>
            {fhRecipients.map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm bg-gray-50 rounded-lg px-3 py-2">
                <span className="flex-1">{r.name} — {r.email}</span>
                {r.is_primary && <span className="text-[10px] text-blue-600 font-medium">Primary</span>}
                <button onClick={() => setFhRecipients(fhRecipients.filter((_, j) => j !== i))}><X className="h-3.5 w-3.5 text-gray-400" /></button>
              </div>
            ))}
            <div className="flex gap-2">
              <Input placeholder="Name" value={newRecName} onChange={(e) => setNewRecName(e.target.value)} className="flex-1" />
              <Input placeholder="Email" value={newRecEmail} onChange={(e) => setNewRecEmail(e.target.value)} className="flex-1" />
              <Button size="sm" onClick={addRecipient}><Plus className="h-4 w-4" /></Button>
            </div>
            <div>
              <Label className="text-xs">Custom subject (optional)</Label>
              <Input value={fhSubject} onChange={(e) => setFhSubject(e.target.value)} className="mt-1" placeholder="Leave blank for default" />
            </div>
            <div>
              <Label className="text-xs">Custom note (optional)</Label>
              <Input value={fhNotes} onChange={(e) => setFhNotes(e.target.value)} className="mt-1" placeholder="Added to email body" />
            </div>
            <Button size="sm" onClick={saveFHConfig}>Save FH settings</Button>
          </div>
        )}
      </Card>
    </div>
  )
}
