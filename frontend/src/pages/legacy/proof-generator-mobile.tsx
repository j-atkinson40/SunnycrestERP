// proof-generator-mobile.tsx — Mobile step-by-step proof generator wizard.
// Steps: Type → Print → Inscription → Review/Compositor

import { useState, useEffect, useRef } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { STANDARD_PRINT_IMAGES, URN_PRINT_IMAGES } from "@/lib/legacy-print-images"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import {
  ChevronLeft, ChevronRight, Loader2, Check, Download, ExternalLink,
} from "lucide-react"
import LegacyCompositorMobile from "@/components/legacy/LegacyCompositorMobile"
import type { LegacyLayout, GenerateResult } from "@/components/legacy/LegacyCompositor"

// ── Types ────────────────────────────────────────────────────────────────────

interface PrintTemplate {
  print_name: string
  available: boolean
  default_text_color: string
  thumbnail_url: string | null
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

type WizardStep = "type" | "print" | "inscription" | "compositor" | "approved"

// ── Print categories ────────────────────────────────────────────────────────

const STANDARD_PRINT_CATEGORIES = [
  {
    category: "Religious & Spiritual",
    prints: [
      "American Flag", "Canadian Flag", "Cross — Gold", "Cross — Silver",
      "Cross — White Horizontal", "Crucifix — Bible", "Forever in God's Care",
      "Going Home", "Irish Blessing", "Irish Blessing — No Poem",
      "Jesus", "Jesus at Dawn", "Jewish 1", "Jewish 2",
      "Our Lady of Guadalupe", "Pieta",
      "Stained Glass — Gold Marble", "Stained Glass — White Marble",
      "Star of David — Gold", "Star of David — White", "Three Crosses",
    ],
  },
  {
    category: "Nature & Landscapes",
    prints: [
      "Autumn Lake", "Bridge 1", "Bridge 2", "Cardinal", "Clouds",
      "Country Road", "Dock", "Footprints", "Footprints with Poem",
      "Green Field & Barn", "Lighthouse", "Marble — Gold", "Marble — White",
      "Red Barn", "Sunrise-Sunset", "Sunrise-Sunset 2",
      "Tropical", "Whitetail Buck",
    ],
  },
  {
    category: "Floral",
    prints: ["Roses on Silk", "Red Roses", "Yellow Roses"],
  },
  {
    category: "Occupations & Hobbies",
    prints: [
      "Combine", "Corn", "EMT", "Farm Field with Tractor",
      "Father 1", "Father 2", "Firefighter", "Fisherman",
      "Fisherman with Dog", "Golf Course", "Golfer", "Gone Fishing",
      "Horses", "Mother 1", "Mother 2", "Motorcycle 1", "Motorcycle 2",
      "Music", "Police", "School", "Tobacco Barn", "Tobacco Field",
    ],
  },
]

const URN_PRINT_CATEGORIES = [
  {
    category: "Religious & Spiritual",
    prints: [
      "U.S. Flag", "Crucifix on Bible", "Forever in God's Care",
      "Going Home", "Irish Blessing", "Jesus", "Three Crosses",
    ],
  },
  {
    category: "Nature & Landscapes",
    prints: [
      "Autumn Lake", "Barn", "Bridge 1", "Bridge 2", "Cardinal",
      "Clouds", "Country Road", "Dock", "Footprints",
      "Green Field & Barn", "Horses",
    ],
  },
  {
    category: "Occupations & Hobbies",
    prints: [
      "Combine", "Corn", "EMT", "Father 1", "Father 2",
      "Firefighter", "Fisherman", "Fisherman with Dog",
      "Golf Course", "Golfer", "Gone Fishing",
    ],
  },
]

// ── Component ───────────────────────────────────────────────────────────────

export default function ProofGeneratorMobile() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const existingId = searchParams.get("legacyId")

  const [step, setStep] = useState<WizardStep>("type")
  const [legacyId, setLegacyId] = useState<string | null>(existingId)
  const [existing, setExisting] = useState<LegacyRecord | null>(null)
  const [loading, setLoading] = useState(!!existingId)

  // Form state
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

  // Templates
  const [templates, setTemplates] = useState<PrintTemplate[]>([])
  const [expandedCategory, setExpandedCategory] = useState<string | null>("Religious & Spiritual")
  const [brokenImages, setBrokenImages] = useState<Set<string>>(new Set())

  // Approved state
  const [approvedProofUrl, setApprovedProofUrl] = useState<string | null>(null)
  const [approvedTifUrl, setApprovedTifUrl] = useState<string | null>(null)

  // Load templates
  useEffect(() => {
    apiClient
      .get(`/legacy/templates?type=${isUrn ? "urn" : "standard"}`)
      .then((r) => setTemplates(r.data || []))
      .catch(() => {})
  }, [isUrn])

  // Load existing record
  useEffect(() => {
    if (!existingId) return
    apiClient
      .get(`/legacy-studio/${existingId}`)
      .then((r) => {
        const d = r.data as LegacyRecord
        setExisting(d)
        setLegacyType(d.legacy_type === "custom" ? "custom" : "standard")
        setIsUrn(d.is_urn)
        setSelectedPrint(d.print_name)
        setName(d.inscription_name || "")
        setDates(d.inscription_dates || "")
        setAdditional(d.inscription_additional || "")
        if (d.background_url) setBackgroundUrl(d.background_url)
        if (d.proof_url) {
          setBackgroundUrl(d.background_url || "")
          setStep("compositor")
        }
      })
      .catch(() => toast.error("Could not load legacy"))
      .finally(() => setLoading(false))
  }, [existingId])

  // Pre-fetch background when print selected
  useEffect(() => {
    if (!selectedPrint || legacyType !== "standard") return
    setBgLoading(true)
    apiClient
      .post("/legacy/background", { print_name: selectedPrint, is_urn: isUrn })
      .then((r) => setBackgroundUrl(r.data.background_url))
      .catch(() => toast.error("Could not load background"))
      .finally(() => setBgLoading(false))
  }, [selectedPrint, isUrn, legacyType])

  // Custom background upload
  const customBgRef = useRef<HTMLInputElement>(null)
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

  // Download helper
  async function downloadFile(url: string, filename: string) {
    try {
      const resp = await fetch(url)
      const blob = await resp.blob()
      const blobUrl = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = blobUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } catch {
      window.open(url, "_blank")
    }
  }

  // Open compositor — create record if needed
  async function handleOpenCompositor() {
    if (!legacyId) {
      try {
        const res = await apiClient.post("/legacy-studio", {
          source: "standalone",
          legacy_type: legacyType,
          print_name: selectedPrint,
          is_urn: isUrn,
          customer_id: null,
          deceased_name: name,
          service_date: null,
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
    setStep("compositor")
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
    if (legacyId) {
      await apiClient
        .patch(`/legacy-studio/${legacyId}`, {
          proof_url: res.data.proof_url,
          tif_url: res.data.tif_url,
          approved_layout: layout,
          status: "proof_generated",
        })
        .catch(() => {})
    }
    return res.data
  }

  // Approve handler
  async function handleApprove(_layout: LegacyLayout, proofUrl: string, tifUrl: string) {
    if (legacyId) {
      await apiClient.post(`/legacy-studio/${legacyId}/approve`, {}).catch(() => {})
    }
    setApprovedProofUrl(proofUrl)
    setApprovedTifUrl(tifUrl)
    setStep("approved")
    toast.success("Legacy approved")

    if (tifUrl) {
      try {
        const resp = await fetch(tifUrl)
        const blob = await resp.blob()
        const blobUrl = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = blobUrl
        a.download = `${name || "legacy"}.tif`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(blobUrl)
      } catch {
        window.open(tifUrl, "_blank")
      }
    }
  }

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

  const templateAvailability = new Map(templates.map((t) => [t.print_name, t.available]))
  const templateThumbnails = new Map(templates.map((t) => [t.print_name, t.thumbnail_url]))
  const printCategories = isUrn ? URN_PRINT_CATEGORIES : STANDARD_PRINT_CATEGORIES
  const printImages = isUrn ? URN_PRINT_IMAGES : STANDARD_PRINT_IMAGES

  const canProceedFromType =
    legacyType === "custom" || legacyType === "standard"

  const canProceedFromPrint =
    (legacyType === "standard" && selectedPrint && backgroundUrl) ||
    (legacyType === "custom" && customBgUrl)

  const canProceedFromInscription = name.trim().length > 0

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  // ── STEP: APPROVED ────────────────────────────────────────────────────

  if (step === "approved") {
    return (
      <div className="min-h-screen bg-white px-4 py-6 space-y-5">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium mb-3">
            <Check className="h-4 w-4" /> Proof approved
          </div>
          <h1 className="text-xl font-bold">{name}</h1>
          <p className="text-gray-500 text-sm">{selectedPrint || "Custom Legacy"}</p>
        </div>

        {approvedProofUrl && (
          <img src={approvedProofUrl} alt="Approved proof" className="w-full rounded-lg border" />
        )}

        <Card className="p-4 space-y-3">
          <h3 className="font-semibold text-sm">Delivery</h3>
          {approvedProofUrl && (
            <button
              onClick={() => downloadFile(approvedProofUrl, `${name || "legacy"}_proof.jpg`)}
              className="flex items-center gap-2 text-sm text-blue-600"
            >
              <Download className="h-4 w-4" /> Download proof JPEG
            </button>
          )}
          {approvedTifUrl && (
            <button
              onClick={() => downloadFile(approvedTifUrl, `${name || "legacy"}.tif`)}
              className="flex items-center gap-2 text-sm text-blue-600"
            >
              <Download className="h-4 w-4" /> Download print TIF
            </button>
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

  // ── STEP: COMPOSITOR ──────────────────────────────────────────────────

  if (step === "compositor" && backgroundUrl) {
    return (
      <LegacyCompositorMobile
        backgroundUrl={backgroundUrl}
        mode="manufacturer"
        initialLayout={existing?.approved_layout as unknown as LegacyLayout | undefined}
        name={name}
        dates={dates}
        additionalText={additional}
        defaultTextColor="white"
        onGenerate={handleGenerate}
        onApprove={handleApprove}
        onCancel={() => setStep("inscription")}
        generatedProofUrl={existing?.proof_url || undefined}
      />
    )
  }

  // ── Wizard header ─────────────────────────────────────────────────────

  const stepLabels: { key: WizardStep; label: string }[] = [
    { key: "type", label: "Type" },
    { key: "print", label: legacyType === "custom" ? "Photo" : "Print" },
    { key: "inscription", label: "Text" },
  ]
  const currentStepIdx = stepLabels.findIndex((s) => s.key === step)

  function goBack() {
    if (step === "print") setStep("type")
    else if (step === "inscription") setStep("print")
    else navigate("/legacy/library")
  }

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Header */}
      <div className="border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={goBack} className="text-gray-500">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-base font-semibold">
              {existing && existing.version_count > 0
                ? `Revising v${existing.version_count + 1}`
                : "New Legacy"}
            </h1>
          </div>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-1 mt-3">
          {stepLabels.map((s, i) => (
            <div key={s.key} className="flex items-center flex-1">
              <div
                className={`h-1 flex-1 rounded-full ${
                  i <= currentStepIdx ? "bg-blue-500" : "bg-gray-200"
                }`}
              />
            </div>
          ))}
        </div>
        <div className="flex justify-between mt-1">
          {stepLabels.map((s) => (
            <span
              key={s.key}
              className={`text-[10px] ${s.key === step ? "text-blue-600 font-medium" : "text-gray-400"}`}
            >
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-4 py-5 space-y-5">
        {/* ── STEP: TYPE ──────────────────────────────────────────────── */}
        {step === "type" && (
          <>
            {!existingId && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
                <p className="font-medium">Standalone Proof</p>
                <p className="text-xs mt-0.5">
                  To create from an order, place the order first.{" "}
                  <Link to="/orders" className="underline font-medium">
                    Have an order? →
                  </Link>
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
                Legacy type
              </Label>
              <div className="space-y-2">
                <button
                  onClick={() => {
                    setLegacyType("standard")
                    setCustomBgUrl(null)
                  }}
                  className={`w-full p-4 rounded-xl border text-left transition-colors ${
                    legacyType === "standard"
                      ? "border-blue-400 bg-blue-50"
                      : "border-gray-200"
                  }`}
                >
                  <div className="font-semibold text-sm">Standard Legacy</div>
                  <div className="text-xs text-gray-500 mt-1">Choose from Legacy Series prints</div>
                </button>
                <button
                  onClick={() => {
                    setLegacyType("custom")
                    setSelectedPrint(null)
                    setBackgroundUrl(null)
                  }}
                  className={`w-full p-4 rounded-xl border text-left transition-colors ${
                    legacyType === "custom"
                      ? "border-blue-400 bg-blue-50"
                      : "border-gray-200"
                  }`}
                >
                  <div className="font-semibold text-sm">Custom Legacy</div>
                  <div className="text-xs text-gray-500 mt-1">Use a family-provided photo</div>
                </button>
              </div>
            </div>

            {legacyType === "standard" && (
              <div className="space-y-2">
                <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
                  Vault type
                </Label>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setIsUrn(false)
                      setSelectedPrint(null)
                      setBrokenImages(new Set())
                    }}
                    className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border ${
                      !isUrn ? "bg-gray-900 text-white border-gray-900" : "border-gray-200"
                    }`}
                  >
                    Standard
                  </button>
                  <button
                    onClick={() => {
                      setIsUrn(true)
                      setSelectedPrint(null)
                      setBrokenImages(new Set())
                    }}
                    className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border ${
                      isUrn ? "bg-gray-900 text-white border-gray-900" : "border-gray-200"
                    }`}
                  >
                    Urn
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── STEP: PRINT ─────────────────────────────────────────────── */}
        {step === "print" && legacyType === "standard" && (
          <>
            <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
              Select a print
            </Label>
            {printCategories.map((cat) => (
              <div key={cat.category} className="border border-gray-200 rounded-lg overflow-hidden">
                <button
                  onClick={() =>
                    setExpandedCategory(expandedCategory === cat.category ? null : cat.category)
                  }
                  className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50"
                >
                  {cat.category} ({cat.prints.length})
                  <span className="text-gray-400">
                    {expandedCategory === cat.category ? "−" : "+"}
                  </span>
                </button>
                {expandedCategory === cat.category && (
                  <div className="grid grid-cols-3 gap-2 p-2">
                    {cat.prints.map((print) => {
                      const available = templateAvailability.get(print) ?? false
                      const isSelected = selectedPrint === print
                      const cdnUrl = printImages[print]
                      const r2Thumbnail = templateThumbnails.get(print)
                      const isBroken = brokenImages.has(print)
                      const imageUrl = cdnUrl && !isBroken ? cdnUrl : r2Thumbnail
                      return (
                        <button
                          key={print}
                          disabled={!available}
                          onClick={() => available && setSelectedPrint(print)}
                          className={`relative rounded-lg border overflow-hidden text-center transition-all ${
                            isSelected
                              ? "border-blue-500 ring-2 ring-blue-200"
                              : available
                                ? "border-gray-200"
                                : "border-gray-100 cursor-not-allowed"
                          }`}
                        >
                          <div className="relative" style={{ aspectRatio: "16 / 4.5" }}>
                            {imageUrl ? (
                              <img
                                src={imageUrl}
                                alt={print}
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  if (cdnUrl && e.currentTarget.src === cdnUrl && r2Thumbnail) {
                                    e.currentTarget.src = r2Thumbnail
                                  } else {
                                    setBrokenImages((prev) => new Set(prev).add(print))
                                  }
                                }}
                              />
                            ) : (
                              <div className="w-full h-full bg-gray-200 flex items-center justify-center">
                                <span className="text-[9px] text-gray-400 px-0.5 leading-tight">
                                  {print}
                                </span>
                              </div>
                            )}
                            {!available && (
                              <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                                <span className="text-white text-[9px] font-medium">Soon</span>
                              </div>
                            )}
                            {isSelected && (
                              <div className="absolute top-0.5 right-0.5 w-4 h-4 bg-blue-600 rounded-full flex items-center justify-center">
                                <Check className="h-2.5 w-2.5 text-white" />
                              </div>
                            )}
                          </div>
                          <div className="px-0.5 py-1">
                            <span
                              className={`text-[10px] font-medium leading-tight ${
                                available ? "text-gray-800" : "text-gray-400"
                              }`}
                            >
                              {print}
                            </span>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}
            {bgLoading && <p className="text-xs text-gray-400">Loading background...</p>}
            {backgroundUrl && !bgLoading && selectedPrint && (
              <p className="text-xs text-green-600">Background ready ✓</p>
            )}
          </>
        )}

        {step === "print" && legacyType === "custom" && (
          <div className="space-y-3">
            <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
              Background photo
            </Label>
            <p className="text-xs text-gray-500">
              This photo will be blurred and stretched to fill the canvas. The portrait can be added on top.
            </p>
            <input
              ref={customBgRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleCustomBgUpload}
            />
            <Button
              variant="outline"
              className="w-full"
              onClick={() => customBgRef.current?.click()}
              loading={customBgUploading}
            >
              {customBgUploading ? "Processing..." : "Upload background photo"}
            </Button>
            {customBgUrl && (
              <div>
                <img src={customBgUrl} alt="Background" className="w-full rounded-lg border mt-2" />
                <p className="text-xs text-green-600 mt-1">Background ready ✓</p>
              </div>
            )}
          </div>
        )}

        {/* ── STEP: INSCRIPTION ───────────────────────────────────────── */}
        {step === "inscription" && (
          <div className="space-y-4">
            <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
              Inscription
            </Label>
            <div>
              <Label htmlFor="m-name">Name *</Label>
              <Input
                id="m-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Robert James Smith"
                className="mt-1"
                autoFocus
              />
            </div>
            <div>
              <Label htmlFor="m-dates">Dates</Label>
              <Input
                id="m-dates"
                value={dates}
                onChange={(e) => setDates(e.target.value)}
                placeholder="e.g. April 4, 1942 — March 28, 2026"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="m-additional">Additional text</Label>
              <Input
                id="m-additional"
                value={additional}
                onChange={(e) => setAdditional(e.target.value)}
                placeholder="e.g. Beloved Husband and Father"
                className="mt-1"
              />
            </div>

            {/* Summary preview */}
            {backgroundUrl && (
              <div className="mt-4">
                <p className="text-xs text-gray-400 mb-1">Background preview</p>
                <img
                  src={backgroundUrl}
                  alt="Selected background"
                  className="w-full rounded-lg border opacity-80"
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom action bar */}
      <div className="border-t bg-white px-4 py-3 safe-bottom">
        {step === "type" && (
            <Button
              className="w-full"
              disabled={!canProceedFromType}
              onClick={() => setStep("print")}
            >
              Next — Select print <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}

          {step === "print" && (
            <Button
              className="w-full"
              disabled={!canProceedFromPrint}
              onClick={() => setStep("inscription")}
            >
              Next — Inscription <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}

          {step === "inscription" && (
            <Button
              className="w-full"
              disabled={!canProceedFromInscription}
              onClick={handleOpenCompositor}
            >
              Open Compositor <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
        )}
      </div>
    </div>
  )
}
