/**
 * Unified Import Wizard — /onboarding/import
 *
 * Four-phase import: Sources → Processing → Review → Apply
 * Replaces fragmented data_migration + import_order_history steps.
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Cloud,
  FileSpreadsheet,
  Loader2,
  MapPin,
  Building,
  Upload,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import apiClient from "@/lib/api-client"
import { getApiErrorMessage } from "@/lib/api-error"

// ── Types ─────────────────────────────────────────────────────────

interface ImportSession {
  id: string
  phase: string
  accounting_source: string | null
  accounting_status: string
  order_history_status: string
  cemetery_csv_status: string
  funeral_home_csv_status: string
  processing_summary: ProcessingSummary | null
  apply_summary: ApplySummary | null
  staging_customers_count: number
  staging_cemeteries_count: number
  staging_funeral_homes_count: number
  staging_orders_count: number
}

interface ProcessingSummary {
  total_records: number
  auto_applied: number
  needs_review: number
  clusters_found: number
  total_records_in_clusters: number
  by_type: Record<string, number>
  sources_used: string[]
}

interface ApplySummary {
  customers_created: number
  cemeteries_created: number
  company_entities_created: number
  contacts_created: number
  duplicates_merged: number
  skipped: number
  by_type: Record<string, number>
}

interface CsvUploadResult {
  column_mapping: Record<string, string>
  confidence: Record<string, number>
  unmapped_fields: string[]
  extra_columns: string[]
  total_rows: number
  sample_rows: Record<string, string>[]
  needs_confirmation: boolean
  available_headers: string[]
}

interface ReviewData {
  clusters: ClusterGroup[]
  bulk_classification_groups: ClassificationGroup[]
  auto_applied_count: number
  pending_count: number
  cluster_count: number
}

interface ClusterGroup {
  cluster_id: string
  members: StagingRow[]
  suggested_primary_id: string | null
}

interface ClassificationGroup {
  suggested_type: string
  count: number
  examples: StagingRow[]
  all_ids: string[]
}

interface StagingRow {
  id: string
  source_type: string
  name: string
  city: string | null
  state: string | null
  phone: string | null
  suggested_type: string | null
  classification_confidence: number | null
  cross_ref_confidence: number | null
  matched_sources: string[]
  cluster_id: string | null
  is_cluster_primary: boolean
  review_status: string
  order_count: number
  appears_as_cemetery_count: number
}

// ── Main component ────────────────────────────────────────────────

export default function UnifiedImportPage() {
  const navigate = useNavigate()
  const [session, setSession] = useState<ImportSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [applying, setApplying] = useState(false)

  // CSV upload state
  const [cemCsvResult, setCemCsvResult] = useState<CsvUploadResult | null>(null)
  const [fhCsvResult, setFhCsvResult] = useState<CsvUploadResult | null>(null)
  const [cemMapping, setCemMapping] = useState<Record<string, string>>({})
  const [fhMapping, setFhMapping] = useState<Record<string, string>>({})

  // Review state
  const [reviewData, setReviewData] = useState<ReviewData | null>(null)
  const [reviewTab, setReviewTab] = useState<"duplicates" | "classification">("duplicates")

  const loadSession = useCallback(async () => {
    try {
      const { data } = await apiClient.post("/api/v1/onboarding/import/session/start")
      setSession(data)
      if (data.phase === "review") {
        await loadReview()
      }
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadReview = async () => {
    try {
      const { data } = await apiClient.get("/api/v1/onboarding/import/review")
      setReviewData(data)
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  useEffect(() => {
    loadSession()
  }, [loadSession])

  if (loading || !session) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const phase = session.phase

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Phase indicator */}
      <PhaseBar phase={phase} />

      {phase === "uploading" && (
        <SourcesPhase
          session={session}
          setSession={setSession}
          cemCsvResult={cemCsvResult}
          setCemCsvResult={setCemCsvResult}
          fhCsvResult={fhCsvResult}
          setFhCsvResult={setFhCsvResult}
          cemMapping={cemMapping}
          setCemMapping={setCemMapping}
          fhMapping={fhMapping}
          setFhMapping={setFhMapping}
          processing={processing}
          setProcessing={setProcessing}
          onProcessed={async () => {
            await loadSession()
            await loadReview()
          }}
        />
      )}

      {phase === "processing" && (
        <div className="flex flex-col items-center gap-4 py-16">
          <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
          <p className="text-lg font-medium">Cross-referencing sources...</p>
          <p className="text-muted-foreground text-sm">This may take a moment</p>
        </div>
      )}

      {phase === "review" && reviewData && (
        <ReviewPhase
          session={session}
          setSession={setSession}
          reviewData={reviewData}
          setReviewData={setReviewData}
          reviewTab={reviewTab}
          setReviewTab={setReviewTab}
          applying={applying}
          setApplying={setApplying}
          onApplied={loadSession}
        />
      )}

      {phase === "complete" && (
        <CompletePhase session={session} navigate={navigate} />
      )}

      {phase === "error" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-lg font-medium text-red-800">Import encountered an error</p>
          <p className="mt-2 text-sm text-red-600">{(session as any).processing_error || "Unknown error"}</p>
          <Button className="mt-4" onClick={() => loadSession()}>
            Retry
          </Button>
        </div>
      )}
    </div>
  )
}

// ── Phase bar ─────────────────────────────────────────────────────

function PhaseBar({ phase }: { phase: string }) {
  const steps = [
    { key: "uploading", label: "Sources" },
    { key: "processing", label: "Processing" },
    { key: "review", label: "Review" },
    { key: "complete", label: "Complete" },
  ]
  const currentIdx = steps.findIndex((s) => s.key === phase)

  return (
    <div className="flex items-center gap-2 mb-2">
      {steps.map((step, i) => (
        <div key={step.key} className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${
              i < currentIdx
                ? "bg-green-100 text-green-700"
                : i === currentIdx
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-400"
            }`}
          >
            {i < currentIdx ? <Check className="h-3.5 w-3.5" /> : null}
            {step.label}
          </div>
          {i < steps.length - 1 && <ArrowRight className="h-4 w-4 text-gray-300" />}
        </div>
      ))}
    </div>
  )
}

// ── Sources phase ─────────────────────────────────────────────────

function SourcesPhase({
  session,
  setSession,
  cemCsvResult,
  setCemCsvResult,
  fhCsvResult,
  setFhCsvResult,
  cemMapping,
  setCemMapping,
  fhMapping,
  setFhMapping,
  processing,
  setProcessing,
  onProcessed,
}: {
  session: ImportSession
  setSession: (s: ImportSession) => void
  cemCsvResult: CsvUploadResult | null
  setCemCsvResult: (r: CsvUploadResult | null) => void
  fhCsvResult: CsvUploadResult | null
  setFhCsvResult: (r: CsvUploadResult | null) => void
  cemMapping: Record<string, string>
  setCemMapping: (m: Record<string, string>) => void
  fhMapping: Record<string, string>
  setFhMapping: (m: Record<string, string>) => void
  processing: boolean
  setProcessing: (b: boolean) => void
  onProcessed: () => Promise<void>
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploadTarget, setUploadTarget] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [sageTab, setSageTab] = useState<"qbo" | "sage" | "csv" | "skip">("sage")

  const sourcesAdded = [
    session.accounting_status,
    session.order_history_status,
    session.cemetery_csv_status,
    session.funeral_home_csv_status,
  ].filter((s) => s === "uploaded" || s === "processed" || s === "skipped").length

  const hasAnyUploaded = [
    session.accounting_status,
    session.order_history_status,
    session.cemetery_csv_status,
    session.funeral_home_csv_status,
  ].some((s) => s === "uploaded" || s === "processed")

  const handleFileUpload = async (target: string, file: File) => {
    setUploading(true)
    const form = new FormData()
    form.append("file", file)

    try {
      if (target === "sage-customers") {
        const sageForm = new FormData()
        sageForm.append("customer_file", file)
        const { data } = await apiClient.post("/api/v1/onboarding/import/accounting/upload-sage", sageForm)
        setSession(data.session)
        toast.success(`Imported ${data.result.customers} customers from Sage`)
      } else if (target === "order-history") {
        const { data } = await apiClient.post("/api/v1/onboarding/import/order-history/upload", form)
        setSession(data.session)
        toast.success(`Parsed ${data.total_rows} orders`)
      } else if (target === "cemetery-csv") {
        const { data } = await apiClient.post("/api/v1/onboarding/import/cemetery-csv/upload", form)
        setCemCsvResult(data)
        setCemMapping(data.column_mapping)
        if (!data.needs_confirmation) {
          await confirmCemCsv(data.column_mapping)
        }
      } else if (target === "fh-csv") {
        const { data } = await apiClient.post("/api/v1/onboarding/import/funeral-home-csv/upload", form)
        setFhCsvResult(data)
        setFhMapping(data.column_mapping)
        if (!data.needs_confirmation) {
          await confirmFhCsv(data.column_mapping)
        }
      }
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    } finally {
      setUploading(false)
    }
  }

  const confirmCemCsv = async (mapping: Record<string, string>) => {
    try {
      const { data } = await apiClient.post("/api/v1/onboarding/import/cemetery-csv/confirm", {
        column_mapping: mapping,
      })
      setSession(data.session)
      setCemCsvResult(null)
      toast.success(`Ingested ${data.ingested_count} cemeteries`)
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  const confirmFhCsv = async (mapping: Record<string, string>) => {
    try {
      const { data } = await apiClient.post("/api/v1/onboarding/import/funeral-home-csv/confirm", {
        column_mapping: mapping,
      })
      setSession(data.session)
      setFhCsvResult(null)
      toast.success(`Ingested ${data.ingested_count} funeral homes`)
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  const skipSource = async (source: string) => {
    try {
      const { data } = await apiClient.post(`/api/v1/onboarding/import/${source}/skip`)
      setSession(data)
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  const processAll = async () => {
    setProcessing(true)
    try {
      const { data } = await apiClient.post("/api/v1/onboarding/import/process")
      setSession(data.session)
      await onProcessed()
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    } finally {
      setProcessing(false)
    }
  }

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold">Import your business data</h1>
        <p className="text-muted-foreground mt-1">
          Add your data sources below. More sources = better accuracy. You can always add more later.
        </p>
      </div>

      {/* Accounting system */}
      <SourceCard
        icon={<Cloud className="h-5 w-5" />}
        title="Accounting system"
        status={session.accounting_status}
        count={session.staging_customers_count}
        countLabel="customers"
      >
        {session.accounting_status === "pending" ? (
          <div className="space-y-3">
            <div className="flex gap-2">
              {(["sage", "qbo", "csv", "skip"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setSageTab(t)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    sageTab === t ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {t === "sage" ? "Sage 100" : t === "qbo" ? "QuickBooks" : t === "csv" ? "Other CSV" : "Skip"}
                </button>
              ))}
            </div>

            {sageTab === "sage" && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  Upload your Sage 100 Customer List export (XLSX) and/or AR Aging report (CSV).
                </p>
                <Button
                  size="sm"
                  onClick={() => {
                    setUploadTarget("sage-customers")
                    fileRef.current?.click()
                  }}
                  disabled={uploading}
                >
                  {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Upload className="h-4 w-4 mr-1" />}
                  Upload Sage export
                </Button>
              </div>
            )}

            {sageTab === "qbo" && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Connect QuickBooks Online to sync your data.</p>
                <Button
                  size="sm"
                  onClick={async () => {
                    try {
                      const { data } = await apiClient.post("/api/v1/onboarding/import/accounting/connect-qbo")
                      window.open(data.auth_url, "_blank", "width=600,height=700")
                    } catch (e) {
                      toast.error(getApiErrorMessage(e))
                    }
                  }}
                >
                  Connect QuickBooks
                </Button>
              </div>
            )}

            {sageTab === "csv" && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Upload a customer export CSV from any accounting system.</p>
                <Button
                  size="sm"
                  onClick={() => {
                    setUploadTarget("sage-customers")
                    fileRef.current?.click()
                  }}
                  disabled={uploading}
                >
                  <Upload className="h-4 w-4 mr-1" /> Upload CSV
                </Button>
              </div>
            )}

            {sageTab === "skip" && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Start with an empty system. You can import later.</p>
                <Button size="sm" variant="outline" onClick={() => skipSource("accounting")}>
                  Skip accounting import
                </Button>
              </div>
            )}
          </div>
        ) : null}
      </SourceCard>

      {/* Order history */}
      <SourceCard
        icon={<FileSpreadsheet className="h-5 w-5" />}
        title="Order history"
        badge="Recommended"
        status={session.order_history_status}
        count={session.staging_orders_count}
        countLabel="orders"
      >
        {session.order_history_status === "pending" ? (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => {
                setUploadTarget("order-history")
                fileRef.current?.click()
              }}
              disabled={uploading}
            >
              <Upload className="h-4 w-4 mr-1" /> Upload order history CSV
            </Button>
            <Button size="sm" variant="ghost" onClick={() => skipSource("order-history")}>
              Skip
            </Button>
          </div>
        ) : null}
      </SourceCard>

      {/* Cemetery CSV */}
      <SourceCard
        icon={<MapPin className="h-5 w-5" />}
        title="Cemetery data"
        badge="Recommended"
        status={session.cemetery_csv_status}
        count={session.staging_cemeteries_count}
        countLabel="cemeteries"
      >
        {session.cemetery_csv_status === "pending" && !cemCsvResult ? (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => {
                setUploadTarget("cemetery-csv")
                fileRef.current?.click()
              }}
              disabled={uploading}
            >
              <Upload className="h-4 w-4 mr-1" /> Upload cemetery CSV
            </Button>
            <Button size="sm" variant="ghost" onClick={() => skipSource("cemetery-csv")}>
              Skip
            </Button>
          </div>
        ) : cemCsvResult ? (
          <ColumnMappingEditor
            result={cemCsvResult}
            mapping={cemMapping}
            setMapping={setCemMapping}
            onConfirm={() => confirmCemCsv(cemMapping)}
            onCancel={() => setCemCsvResult(null)}
          />
        ) : null}
      </SourceCard>

      {/* Funeral home CSV */}
      <SourceCard
        icon={<Building className="h-5 w-5" />}
        title="Funeral home data"
        badge="Recommended"
        status={session.funeral_home_csv_status}
        count={session.staging_funeral_homes_count}
        countLabel="funeral homes"
      >
        {session.funeral_home_csv_status === "pending" && !fhCsvResult ? (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => {
                setUploadTarget("fh-csv")
                fileRef.current?.click()
              }}
              disabled={uploading}
            >
              <Upload className="h-4 w-4 mr-1" /> Upload funeral home CSV
            </Button>
            <Button size="sm" variant="ghost" onClick={() => skipSource("funeral-home-csv")}>
              Skip
            </Button>
          </div>
        ) : fhCsvResult ? (
          <ColumnMappingEditor
            result={fhCsvResult}
            mapping={fhMapping}
            setMapping={setFhMapping}
            onConfirm={() => confirmFhCsv(fhMapping)}
            onCancel={() => setFhCsvResult(null)}
          />
        ) : null}
      </SourceCard>

      {/* Hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept=".csv,.xlsx,.xls,.txt"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file && uploadTarget) handleFileUpload(uploadTarget, file)
          e.target.value = ""
        }}
      />

      {/* Footer */}
      <div className="flex items-center justify-between rounded-lg border bg-gray-50 p-4">
        <p className="text-sm text-muted-foreground">Sources added: {sourcesAdded} of 4</p>
        <Button onClick={processAll} disabled={!hasAnyUploaded || processing}>
          {processing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-1" /> Processing...
            </>
          ) : (
            <>
              Process all sources <ArrowRight className="h-4 w-4 ml-1" />
            </>
          )}
        </Button>
      </div>
    </>
  )
}

// ── Source card ────────────────────────────────────────────────────

function SourceCard({
  icon,
  title,
  badge,
  status,
  count,
  countLabel,
  children,
}: {
  icon: React.ReactNode
  title: string
  badge?: string
  status: string
  count?: number
  countLabel?: string
  children: React.ReactNode
}) {
  const isDone = status === "uploaded" || status === "processed"
  const isSkipped = status === "skipped"

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-semibold">{title}</h3>
          {badge && !isDone && !isSkipped && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">{badge}</span>
          )}
        </div>
        {isDone && (
          <span className="flex items-center gap-1 text-sm font-medium text-green-600">
            <CheckCircle2 className="h-4 w-4" />
            {count ? `${count} ${countLabel}` : "Done"}
          </span>
        )}
        {isSkipped && <span className="text-sm text-muted-foreground">Skipped</span>}
      </div>
      {!isDone && !isSkipped && children}
    </Card>
  )
}

// ── Column mapping editor ─────────────────────────────────────────

function ColumnMappingEditor({
  result,
  mapping,
  setMapping,
  onConfirm,
  onCancel,
}: {
  result: CsvUploadResult
  mapping: Record<string, string>
  setMapping: (m: Record<string, string>) => void
  onConfirm: () => void
  onCancel: () => void
}) {
  const [editing, setEditing] = useState(false)

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        We detected {result.total_rows} rows. Confirm column mapping:
      </p>

      {!editing ? (
        <div className="space-y-1">
          {Object.entries(mapping).map(([field, col]) => (
            <div key={field} className="flex items-center gap-2 text-sm">
              <span className="font-medium w-28 capitalize">{field.replace("_", " ")}</span>
              <ArrowRight className="h-3 w-3 text-gray-400" />
              <span>{col}</span>
              {result.confidence[field] >= 0.90 ? (
                <Check className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <span className="text-xs text-amber-600">({Math.round(result.confidence[field] * 100)}%)</span>
              )}
            </div>
          ))}
          {result.unmapped_fields.length > 0 && (
            <p className="text-xs text-amber-600 mt-1">
              Unmapped: {result.unmapped_fields.join(", ")}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {Object.entries(mapping).map(([field, col]) => (
            <div key={field} className="flex items-center gap-2 text-sm">
              <span className="font-medium w-28 capitalize">{field.replace("_", " ")}</span>
              <select
                className="rounded border px-2 py-1 text-sm"
                value={col}
                onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}
              >
                <option value="">-- select --</option>
                {result.available_headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        {!editing ? (
          <>
            <Button size="sm" onClick={onConfirm}>
              <Check className="h-4 w-4 mr-1" /> Looks right
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Fix column mapping
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" onClick={() => { setEditing(false); onConfirm() }}>
              <Check className="h-4 w-4 mr-1" /> Confirm mapping
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </>
        )}
        <Button size="sm" variant="ghost" onClick={onCancel}>
          <X className="h-4 w-4 mr-1" /> Remove
        </Button>
      </div>
    </div>
  )
}

// ── Review phase ──────────────────────────────────────────────────

function ReviewPhase({
  session,
  setSession,
  reviewData,
  setReviewData,
  reviewTab,
  setReviewTab,
  applying,
  setApplying,
  onApplied,
}: {
  session: ImportSession
  setSession: (s: ImportSession) => void
  reviewData: ReviewData
  setReviewData: (d: ReviewData) => void
  reviewTab: "duplicates" | "classification"
  setReviewTab: (t: "duplicates" | "classification") => void
  applying: boolean
  setApplying: (b: boolean) => void
  onApplied: () => Promise<void>
}) {
  const summary = session.processing_summary

  const handleAcceptAll = async () => {
    try {
      const { data } = await apiClient.post("/api/v1/onboarding/import/review/accept-all-high-confidence")
      toast.success(`Merged ${data.clusters_merged} clusters, approved ${data.records_approved} records`)
      // Reload review data
      const { data: rd } = await apiClient.get("/api/v1/onboarding/import/review")
      setReviewData(rd)
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  const handleMerge = async (clusterId: string, primaryId: string) => {
    try {
      await apiClient.post(`/api/v1/onboarding/import/review/cluster/${clusterId}/merge`, {
        primary_staging_id: primaryId,
      })
      const { data } = await apiClient.get("/api/v1/onboarding/import/review")
      setReviewData(data)
      toast.success("Cluster merged")
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  const handleSplit = async (clusterId: string) => {
    try {
      await apiClient.post(`/api/v1/onboarding/import/review/cluster/${clusterId}/split`)
      const { data } = await apiClient.get("/api/v1/onboarding/import/review")
      setReviewData(data)
      toast.success("Records kept separate")
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  const handleBulkClassify = async (ids: string[], type: string) => {
    try {
      await apiClient.post("/api/v1/onboarding/import/review/bulk-classify", {
        staging_ids: ids,
        customer_type: type,
      })
      const { data } = await apiClient.get("/api/v1/onboarding/import/review")
      setReviewData(data)
      toast.success(`Classified ${ids.length} records as ${type}`)
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    }
  }

  const handleApply = async () => {
    setApplying(true)
    try {
      const { data } = await apiClient.post("/api/v1/onboarding/import/apply")
      setSession(data.session)
      await onApplied()
      toast.success("Import applied successfully!")
    } catch (e) {
      toast.error(getApiErrorMessage(e))
    } finally {
      setApplying(false)
    }
  }

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold">Review and confirm</h1>
      </div>

      {/* Summary bar */}
      {summary && (
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-green-600">{summary.auto_applied}</p>
            <p className="text-sm text-muted-foreground">Auto-ready</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-amber-600">{reviewData.cluster_count}</p>
            <p className="text-sm text-muted-foreground">Duplicate groups</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">{reviewData.pending_count}</p>
            <p className="text-sm text-muted-foreground">Needs classification</p>
          </Card>
        </div>
      )}

      {/* Accept all */}
      {(reviewData.cluster_count > 0 || reviewData.pending_count > 0) && (
        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={handleAcceptAll}>
            <Check className="h-4 w-4 mr-1" /> Accept all high-confidence suggestions
          </Button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        <button
          className={`px-3 py-1.5 text-sm font-medium rounded-t ${
            reviewTab === "duplicates" ? "border-b-2 border-blue-500 text-blue-700" : "text-gray-500"
          }`}
          onClick={() => setReviewTab("duplicates")}
        >
          Duplicates ({reviewData.cluster_count})
        </button>
        <button
          className={`px-3 py-1.5 text-sm font-medium rounded-t ${
            reviewTab === "classification" ? "border-b-2 border-blue-500 text-blue-700" : "text-gray-500"
          }`}
          onClick={() => setReviewTab("classification")}
        >
          Classification ({reviewData.bulk_classification_groups.length})
        </button>
      </div>

      {/* Duplicates tab */}
      {reviewTab === "duplicates" && (
        <div className="space-y-4">
          {reviewData.clusters.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No duplicate groups to review</p>
          ) : (
            reviewData.clusters.map((cluster) => (
              <ClusterCard
                key={cluster.cluster_id}
                cluster={cluster}
                onMerge={handleMerge}
                onSplit={handleSplit}
              />
            ))
          )}
        </div>
      )}

      {/* Classification tab */}
      {reviewTab === "classification" && (
        <div className="space-y-4">
          {reviewData.bulk_classification_groups.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">All records classified</p>
          ) : (
            reviewData.bulk_classification_groups.map((group) => (
              <ClassificationCard key={group.suggested_type} group={group} onClassify={handleBulkClassify} />
            ))
          )}
        </div>
      )}

      {/* Apply button */}
      <div className="flex justify-end pt-4 border-t">
        <Button onClick={handleApply} disabled={applying} size="lg">
          {applying ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-1" /> Applying...
            </>
          ) : (
            <>
              Apply all changes <ArrowRight className="h-4 w-4 ml-1" />
            </>
          )}
        </Button>
      </div>
    </>
  )
}

// ── Cluster card ──────────────────────────────────────────────────

function ClusterCard({
  cluster,
  onMerge,
  onSplit,
}: {
  cluster: ClusterGroup
  onMerge: (clusterId: string, primaryId: string) => void
  onSplit: (clusterId: string) => void
}) {
  const [selectedPrimary, setSelectedPrimary] = useState(cluster.suggested_primary_id)

  return (
    <Card className="p-4">
      <p className="text-sm font-medium text-muted-foreground mb-3">
        These {cluster.members.length} records may be the same company:
      </p>
      <div className="space-y-2">
        {cluster.members.map((m) => (
          <div
            key={m.id}
            className={`flex items-center justify-between rounded-md border p-3 text-sm ${
              m.id === selectedPrimary ? "border-blue-300 bg-blue-50" : ""
            }`}
          >
            <div>
              <div className="flex items-center gap-2">
                {m.id === cluster.suggested_primary_id && (
                  <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">Suggested</span>
                )}
                <span className="font-medium">{m.name}</span>
                {m.city && <span className="text-muted-foreground">— {m.city}</span>}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {m.order_count > 0 && <span>{m.order_count} orders</span>}
                {m.matched_sources.length > 0 && <span> · Matched: {m.matched_sources.join(", ")}</span>}
                {" · Source: "}{m.source_type}
              </div>
            </div>
            <input
              type="radio"
              name={`cluster-${cluster.cluster_id}`}
              checked={m.id === selectedPrimary}
              onChange={() => setSelectedPrimary(m.id)}
            />
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-3">
        <Button
          size="sm"
          onClick={() => selectedPrimary && onMerge(cluster.cluster_id, selectedPrimary)}
          disabled={!selectedPrimary}
        >
          Merge all
        </Button>
        <Button size="sm" variant="outline" onClick={() => onSplit(cluster.cluster_id)}>
          These are different locations
        </Button>
      </div>
    </Card>
  )
}

// ── Classification card ───────────────────────────────────────────

function ClassificationCard({
  group,
  onClassify,
}: {
  group: ClassificationGroup
  onClassify: (ids: string[], type: string) => void
}) {
  const typeLabels: Record<string, string> = {
    funeral_home: "Funeral Home",
    cemetery: "Cemetery",
    contractor: "Contractor",
    individual: "Individual",
    unknown: "Unknown",
  }

  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="font-medium">
            {group.count} records classified as{" "}
            <span className="text-blue-600">{typeLabels[group.suggested_type] || group.suggested_type}</span>
          </p>
        </div>
      </div>
      <div className="space-y-1 mb-3">
        {(expanded ? group.examples : group.examples.slice(0, 3)).map((ex) => (
          <p key={ex.id} className="text-sm text-muted-foreground">
            {ex.name}
            {ex.city && ` — ${ex.city}`}
          </p>
        ))}
        {group.count > 3 && !expanded && (
          <button className="text-sm text-blue-500 hover:underline" onClick={() => setExpanded(true)}>
            + {group.count - 3} more
          </button>
        )}
      </div>
      <div className="flex gap-2 flex-wrap">
        <Button size="sm" onClick={() => onClassify(group.all_ids, group.suggested_type)}>
          <Check className="h-4 w-4 mr-1" /> Confirm as {typeLabels[group.suggested_type] || group.suggested_type}
        </Button>
        {group.suggested_type !== "funeral_home" && (
          <Button size="sm" variant="outline" onClick={() => onClassify(group.all_ids, "funeral_home")}>
            Funeral Home
          </Button>
        )}
        {group.suggested_type !== "cemetery" && (
          <Button size="sm" variant="outline" onClick={() => onClassify(group.all_ids, "cemetery")}>
            Cemetery
          </Button>
        )}
        {group.suggested_type !== "contractor" && (
          <Button size="sm" variant="outline" onClick={() => onClassify(group.all_ids, "contractor")}>
            Contractor
          </Button>
        )}
      </div>
    </Card>
  )
}

// ── Complete phase ────────────────────────────────────────────────

function CompletePhase({
  session,
  navigate,
}: {
  session: ImportSession
  navigate: (path: string) => void
}) {
  const summary = session.apply_summary

  return (
    <Card className="p-8 text-center">
      <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto mb-4" />
      <h2 className="text-2xl font-bold mb-6">Import complete</h2>

      {summary && (
        <div className="text-left max-w-md mx-auto space-y-2 mb-8">
          <div className="flex justify-between text-sm">
            <span>Companies imported</span>
            <span className="font-medium">{summary.customers_created}</span>
          </div>
          {Object.entries(summary.by_type || {}).map(([type, count]) => (
            <div key={type} className="flex justify-between text-sm pl-4">
              <span className="text-muted-foreground capitalize">{type.replace("_", " ")}</span>
              <span>{count}</span>
            </div>
          ))}
          <div className="flex justify-between text-sm pt-2 border-t">
            <span>Duplicates merged</span>
            <span className="font-medium">{summary.duplicates_merged}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span>Cemeteries created</span>
            <span className="font-medium">{summary.cemeteries_created}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span>Contacts imported</span>
            <span className="font-medium">{summary.contacts_created}</span>
          </div>
        </div>
      )}

      <Button size="lg" onClick={() => navigate("/onboarding")}>
        Continue onboarding <ArrowRight className="h-4 w-4 ml-1" />
      </Button>
    </Card>
  )
}
