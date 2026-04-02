// proof-generator.tsx — Standalone legacy proof generator
// Route: /legacy/generator  and  /legacy/generator?legacyId={id}

import { useState, useEffect, useCallback } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { ChevronLeft, Loader2, Check, Download, Mail, ExternalLink } from "lucide-react"
import LegacyCompositor from "@/components/legacy/LegacyCompositor"
import type { LegacyLayout, GenerateResult } from "@/components/legacy/LegacyCompositor"

// ── Types ────────────────────────────────────────────────────────────────────

interface PrintTemplate {
  print_name: string
  available: boolean
  default_text_color: string
}

interface LegacyRecord {
  id: string
  status: string
  legacy_type: string
  print_name: string | null
  is_urn: boolean
  inscription_name: string | null
  inscription_dates: string | null
  inscription_additional: string | null
  customer_id: string | null
  deceased_name: string | null
  service_date: string | null
  proof_url: string | null
  tif_url: string | null
  background_url: string | null
  approved_layout: Record<string, unknown> | null
  version_count: number
}

type Phase = "setup" | "compositor" | "approved"

// ── Print categories (from personalization config) ──────────────────────────

const PRINT_CATEGORIES = [
  {
    category: "Religious & Spiritual",
    prints: ["American Flag", "Crucifix — Bible", "Forever in God's Care — Cross",
      "Forever in God's Care — Sunset", "Forever in Our Hearts — Cloud",
      "Forever in Our Hearts — Sunset", "Going Home", "Irish Blessing",
      "Jesus", "Jesus at Dawn", "Jewish", "Three Crosses"],
  },
  {
    category: "Nature & Landscapes",
    prints: ["Autumn Lake", "Bridge 1", "Bridge 2", "Clouds", "Country Road",
      "Dock", "Field and Barn", "Footprints", "Footprints with Poem",
      "Lighthouse", "Red Barn", "Sunrise", "Sunset", "Tropical"],
  },
  {
    category: "Floral",
    prints: ["Roses on Silk", "Red Roses", "Yellow Roses"],
  },
  {
    category: "Occupations & Hobbies",
    prints: ["Combine", "Corn", "EMT", "Farm Field with Tractor",
      "Father 1", "Father 2", "Firefighter", "Fisherman",
      "Fisherman with Dog", "Golf Course", "Golfer", "Gone Fishing",
      "Horses", "Mother 1", "Mother 2", "Motorcycle 1", "Motorcycle 2",
      "Music", "Police", "School", "Tobacco Barn", "Tobacco Field"],
  },
]

// ── Component ────────────────────────────────────────────────────────────────

export default function ProofGeneratorPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const existingId = searchParams.get("legacyId")

  const [phase, setPhase] = useState<Phase>("setup")
  const [legacyId, setLegacyId] = useState<string | null>(existingId)
  const [existing, setExisting] = useState<LegacyRecord | null>(null)
  const [loading, setLoading] = useState(!!existingId)

  // Setup form
  const [legacyType, setLegacyType] = useState<"standard" | "custom">("standard")
  const [isUrn, setIsUrn] = useState(false)
  const [selectedPrint, setSelectedPrint] = useState<string | null>(null)
  const [backgroundUrl, setBackgroundUrl] = useState<string | null>(null)
  const [bgLoading, setBgLoading] = useState(false)
  const [customBgUrl, setCustomBgUrl] = useState<string | null>(null)
  const [customBgUploading, setCustomBgUploading] = useState(false)

  // Inscription
  const [name, setName] = useState("")
  const [dates, setDates] = useState("")
  const [additional, setAdditional] = useState("")

  // FH details
  const [customerId, setCustomerId] = useState<string | null>(null)
  const [deceasedName, setDeceasedName] = useState("")
  const [serviceDate, setServiceDate] = useState("")

  // Templates
  const [templates, setTemplates] = useState<PrintTemplate[]>([])
  const [expandedCategory, setExpandedCategory] = useState<string | null>("Religious & Spiritual")

  // Approved state
  const [approvedProofUrl, setApprovedProofUrl] = useState<string | null>(null)
  const [approvedTifUrl, setApprovedTifUrl] = useState<string | null>(null)

  // Load templates
  useEffect(() => {
    apiClient.get(`/legacy/templates?type=${isUrn ? "urn" : "standard"}`)
      .then((r) => setTemplates(r.data || []))
      .catch(() => {})
  }, [isUrn])

  // Load existing record
  useEffect(() => {
    if (!existingId) return
    apiClient.get(`/legacy-studio/${existingId}`)
      .then((r) => {
        const d = r.data as LegacyRecord
        setExisting(d)
        setLegacyType(d.legacy_type === "custom" ? "custom" : "standard")
        setIsUrn(d.is_urn)
        setSelectedPrint(d.print_name)
        setName(d.inscription_name || "")
        setDates(d.inscription_dates || "")
        setAdditional(d.inscription_additional || "")
        setDeceasedName(d.deceased_name || "")
        setServiceDate(d.service_date || "")
        setCustomerId(d.customer_id)
        if (d.background_url) setBackgroundUrl(d.background_url)
        if (d.proof_url) {
          setBackgroundUrl(d.background_url || "")
          setPhase("compositor")
        }
      })
      .catch(() => toast.error("Could not load legacy"))
      .finally(() => setLoading(false))
  }, [existingId])

  // Pre-fetch background when print selected
  useEffect(() => {
    if (!selectedPrint || legacyType !== "standard") return
    setBgLoading(true)
    apiClient.post("/legacy/background", { print_name: selectedPrint, is_urn: isUrn })
      .then((r) => setBackgroundUrl(r.data.background_url))
      .catch(() => toast.error("Could not load background"))
      .finally(() => setBgLoading(false))
  }, [selectedPrint, isUrn, legacyType])

  // Custom background upload
  async function handleCustomBgUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setCustomBgUploading(true)
    try {
      const form = new FormData()
      form.append("file", file)
      const id = legacyId || "preview"
      const res = await apiClient.post(`/legacy/custom-background?order_id=${id}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setCustomBgUrl(res.data.background_url)
      setBackgroundUrl(res.data.background_url)
    } catch {
      toast.error("Failed to process background")
    } finally {
      setCustomBgUploading(false)
    }
  }

  // Open compositor
  async function handleOpenCompositor() {
    // Create legacy record if needed
    if (!legacyId) {
      try {
        const res = await apiClient.post("/legacy-studio", {
          source: "standalone",
          legacy_type: legacyType,
          print_name: selectedPrint,
          is_urn: isUrn,
          customer_id: customerId,
          deceased_name: deceasedName || name,
          service_date: serviceDate || null,
          inscription_name: name,
          inscription_dates: dates,
          inscription_additional: additional,
        })
        setLegacyId(res.data.id)
      } catch {
        toast.error("Failed to create legacy record")
        return
      }
    }
    setPhase("compositor")
  }

  // Generate handler
  async function handleGenerate(layout: LegacyLayout): Promise<GenerateResult> {
    const res = await apiClient.post("/legacy/generate", {
      order_id: null,
      print_name: selectedPrint,
      is_urn: isUrn,
      is_custom: legacyType === "custom",
      layout,
    })

    // Update legacy record
    if (legacyId) {
      await apiClient.patch(`/legacy-studio/${legacyId}`, {
        proof_url: res.data.proof_url,
        tif_url: res.data.tif_url,
        approved_layout: layout,
        status: "proof_generated",
      }).catch(() => {})
    }

    return res.data
  }

  // Approve handler
  async function handleApprove(layout: LegacyLayout, proofUrl: string, tifUrl: string) {
    if (legacyId) {
      await apiClient.post(`/legacy-studio/${legacyId}/approve`, {}).catch(() => {})
    }
    setApprovedProofUrl(proofUrl)
    setApprovedTifUrl(tifUrl)
    setPhase("approved")
    toast.success("Proof approved")
  }

  // Convert to order
  async function handleConvertToOrder() {
    if (!legacyId) return
    try {
      const res = await apiClient.post(`/legacy-studio/${legacyId}/convert-to-order`, {})
      toast.success(res.data.action === "created" ? "Draft order created" : "Linked")
      navigate(`/ar/orders/${res.data.order_id}`)
    } catch {
      toast.error("Failed")
    }
  }

  const canOpenCompositor =
    name.trim().length > 0 &&
    ((legacyType === "standard" && selectedPrint && backgroundUrl) ||
     (legacyType === "custom" && customBgUrl))

  const templateAvailability = new Map(templates.map((t) => [t.print_name, t.available]))

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>
  }

  // ── PHASE: APPROVED ──────────────────────────────────────────────────────

  if (phase === "approved") {
    return (
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium mb-4">
            <Check className="h-4 w-4" /> Proof approved
          </div>
          <h1 className="text-2xl font-bold">{name}</h1>
          <p className="text-gray-500">{selectedPrint || "Custom Legacy"}</p>
        </div>

        {approvedProofUrl && (
          <img src={approvedProofUrl} alt="Approved proof" className="w-full rounded-lg border" />
        )}

        <Card className="p-4 space-y-3">
          <h3 className="font-semibold text-sm">Delivery</h3>
          {approvedProofUrl && (
            <a href={approvedProofUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm text-blue-600">
              <Download className="h-4 w-4" /> Download proof JPEG
            </a>
          )}
          {approvedTifUrl && (
            <a href={approvedTifUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm text-blue-600">
              <Download className="h-4 w-4" /> Download print TIF
            </a>
          )}
        </Card>

        <Card className="p-4 space-y-3">
          <h3 className="font-semibold text-sm">Next steps</h3>
          <Button variant="outline" className="w-full" onClick={handleConvertToOrder}>
            <ExternalLink className="h-4 w-4 mr-1" /> Create order from proof
          </Button>
          <Button className="w-full" onClick={() => navigate(`/legacy/library/${legacyId}`)}>
            Done — go to library
          </Button>
        </Card>
      </div>
    )
  }

  // ── PHASE: COMPOSITOR ────────────────────────────────────────────────────

  if (phase === "compositor" && backgroundUrl) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <button onClick={() => setPhase("setup")} className="flex items-center gap-1 text-sm text-gray-500 mb-1">
              <ChevronLeft className="h-4 w-4" /> Back to setup
            </button>
            <h1 className="text-xl font-bold">
              {existing && existing.version_count > 0
                ? `Revising ${name} · v${existing.version_count + 1}`
                : "Proof Generator"}
            </h1>
          </div>
        </div>

        <LegacyCompositor
          backgroundUrl={backgroundUrl}
          mode="manufacturer"
          initialLayout={existing?.approved_layout as unknown as LegacyLayout | undefined}
          name={name}
          dates={dates}
          additionalText={additional}
          defaultTextColor="white"
          onGenerate={handleGenerate}
          onApprove={handleApprove}
          onCancel={() => setPhase("setup")}
          generatedProofUrl={existing?.proof_url || undefined}
        />
      </div>
    )
  }

  // ── PHASE: SETUP ─────────────────────────────────────────────────────────

  return (
    <div className="max-w-[680px] mx-auto px-6 py-8 space-y-8">
      <div>
        <button onClick={() => navigate("/legacy/library")} className="flex items-center gap-1 text-sm text-gray-500 mb-3">
          <ChevronLeft className="h-4 w-4" /> Back to library
        </button>
        <h1 className="text-2xl font-bold">Proof Generator</h1>
        {existing && existing.version_count > 0 && (
          <p className="text-sm text-amber-600 mt-1">
            Creating version {existing.version_count + 1} — previous version saved.
          </p>
        )}
      </div>

      {/* Legacy type */}
      <div className="space-y-2">
        <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Legacy type</Label>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => { setLegacyType("standard"); setCustomBgUrl(null) }}
            className={`p-4 rounded-xl border text-left transition-colors ${
              legacyType === "standard" ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300"
            }`}
          >
            <div className="font-semibold text-sm">✨ Standard Legacy</div>
            <div className="text-xs text-gray-500 mt-1">Choose from Legacy Series prints</div>
          </button>
          <button
            onClick={() => { setLegacyType("custom"); setSelectedPrint(null); setBackgroundUrl(null) }}
            className={`p-4 rounded-xl border text-left transition-colors ${
              legacyType === "custom" ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300"
            }`}
          >
            <div className="font-semibold text-sm">🎨 Custom Legacy</div>
            <div className="text-xs text-gray-500 mt-1">Use a family-provided photo</div>
          </button>
        </div>
      </div>

      {/* Vault type (standard only) */}
      {legacyType === "standard" && (
        <div className="space-y-2">
          <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Vault type</Label>
          <div className="flex gap-2">
            <button
              onClick={() => { setIsUrn(false); setSelectedPrint(null) }}
              className={`px-4 py-2 rounded-lg text-sm font-medium border ${!isUrn ? "bg-gray-900 text-white border-gray-900" : "border-gray-200"}`}
            >
              Standard vault
            </button>
            <button
              onClick={() => { setIsUrn(true); setSelectedPrint(null) }}
              className={`px-4 py-2 rounded-lg text-sm font-medium border ${isUrn ? "bg-gray-900 text-white border-gray-900" : "border-gray-200"}`}
            >
              Urn vault
            </button>
          </div>
        </div>
      )}

      {/* Print selection (standard only) */}
      {legacyType === "standard" && (
        <div className="space-y-2">
          <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Print selection</Label>
          {PRINT_CATEGORIES.map((cat) => (
            <div key={cat.category} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedCategory(expandedCategory === cat.category ? null : cat.category)}
                className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100"
              >
                {cat.category} ({cat.prints.length})
                <span className="text-gray-400">{expandedCategory === cat.category ? "−" : "+"}</span>
              </button>
              {expandedCategory === cat.category && (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 p-3">
                  {cat.prints.map((print) => {
                    const available = templateAvailability.get(print) ?? false
                    const isSelected = selectedPrint === print
                    return (
                      <button
                        key={print}
                        disabled={!available}
                        onClick={() => setSelectedPrint(print)}
                        className={`relative p-2 rounded-lg border text-center text-[11px] transition-colors ${
                          isSelected ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200" :
                          available ? "border-gray-200 hover:border-blue-300" :
                          "border-gray-100 opacity-40 cursor-not-allowed"
                        }`}
                      >
                        {isSelected && <Check className="absolute top-1 right-1 h-3 w-3 text-blue-600" />}
                        <div className="font-medium text-gray-800 leading-tight">{print}</div>
                        {!available && <div className="text-[9px] text-gray-400 mt-0.5">Coming soon</div>}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
          {bgLoading && <p className="text-xs text-gray-400">Loading background...</p>}
          {backgroundUrl && !bgLoading && (
            <p className="text-xs text-green-600">Background ready ✓</p>
          )}
        </div>
      )}

      {/* Custom background upload */}
      {legacyType === "custom" && (
        <div className="space-y-2">
          <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Background photo</Label>
          <p className="text-xs text-gray-500">
            This photo will be blurred and stretched to fill the legacy canvas. The family's portrait can be added on top.
          </p>
          <label className="cursor-pointer">
            <input type="file" accept="image/*" className="hidden" onChange={handleCustomBgUpload} />
            <span className="inline-flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium">
              {customBgUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {customBgUploading ? "Processing..." : "Upload background photo"}
            </span>
          </label>
          {customBgUrl && (
            <div>
              <img src={customBgUrl} alt="Background" className="w-72 rounded-lg border mt-2" />
              <p className="text-xs text-green-600 mt-1">Background ready ✓</p>
            </div>
          )}
        </div>
      )}

      {/* Inscription */}
      <div className="space-y-3">
        <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Inscription</Label>
        <div>
          <Label htmlFor="gen-name">Name *</Label>
          <Input id="gen-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Robert James Smith" className="mt-1" />
        </div>
        <div>
          <Label htmlFor="gen-dates">Dates</Label>
          <Input id="gen-dates" value={dates} onChange={(e) => setDates(e.target.value)} placeholder="e.g. April 4, 1942 — March 28, 2026" className="mt-1" />
        </div>
        <div>
          <Label htmlFor="gen-additional">Additional text</Label>
          <Input id="gen-additional" value={additional} onChange={(e) => setAdditional(e.target.value)} placeholder="e.g. Beloved Husband and Father" className="mt-1" />
        </div>
      </div>

      {/* FH details */}
      <div className="space-y-3">
        <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Details (optional)</Label>
        <div>
          <Label htmlFor="gen-deceased">Deceased name</Label>
          <Input id="gen-deceased" value={deceasedName} onChange={(e) => setDeceasedName(e.target.value)} placeholder="e.g. Robert Smith" className="mt-1" />
          <p className="text-[11px] text-gray-400 mt-0.5">Can differ from the inscription name</p>
        </div>
        <div>
          <Label htmlFor="gen-date">Service date</Label>
          <Input id="gen-date" type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} className="mt-1" />
        </div>
      </div>

      {/* Action bar */}
      <div className="sticky bottom-0 bg-white border-t py-4 -mx-6 px-6 flex gap-3">
        <Button variant="outline" onClick={() => navigate("/legacy/library")}>Cancel</Button>
        <Button className="flex-1" disabled={!canOpenCompositor} onClick={handleOpenCompositor}>
          Open in Compositor →
        </Button>
      </div>
    </div>
  )
}
