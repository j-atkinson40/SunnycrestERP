// template-upload.tsx — Admin page to upload blank TIF templates to R2
// Route: /legacy/templates/upload

import { useState, useEffect, useCallback, useRef } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader2, Check, X, CloudUpload, RefreshCw } from "lucide-react"

type TemplateType = "standard" | "urn" | "bv_standard" | "bv_urn"

interface TemplateStatus {
  print_name: string
  r2_key: string
  available: boolean
  in_r2: boolean
}

interface UploadResult {
  filename: string
  r2_key?: string
  size_mb?: number
  matched_template?: string | null
  error?: string
}

export default function TemplateUploadPage() {
  const [templateType, setTemplateType] = useState<TemplateType>("standard")
  const [statuses, setStatuses] = useState<TemplateStatus[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<UploadResult[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  const loadStatus = useCallback(async () => {
    setLoading(true)
    try {
      const apiType = templateType.startsWith("bv_") ? templateType.replace("bv_", "") : templateType
      const res = await apiClient.get(`/legacy/admin/template-status?type=${apiType}`)
      setStatuses(res.data || [])
    } catch {
      toast.error("Could not load template status")
    } finally {
      setLoading(false)
    }
  }, [templateType])

  useEffect(() => { loadStatus() }, [loadStatus])

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return
    setUploading(true)
    setResults([])

    const formData = new FormData()
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i])
    }

    try {
      const res = await apiClient.post(
        `/legacy/admin/upload-templates-bulk?template_type=${templateType}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" }, timeout: 300000 }
      )
      setResults(res.data.results || [])
      toast.success(`Uploaded ${res.data.uploaded} files${res.data.errors > 0 ? ` (${res.data.errors} errors)` : ""}`)
      loadStatus()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Upload failed")
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  const inR2 = statuses.filter((s) => s.in_r2).length
  const total = statuses.length

  const TYPE_LABELS: Record<TemplateType, string> = {
    standard: "Standard Vault (WLP)",
    urn: "Urn Vault (WLP-UV)",
    bv_standard: "Bronze Vault (BV)",
    bv_urn: "Bronze Urn Vault (UV)",
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Template Upload</h1>
        <p className="text-sm text-gray-500 mt-1">Upload blank TIF template files to cloud storage</p>
      </div>

      {/* Type selector */}
      <div className="flex gap-2 flex-wrap">
        {(Object.entries(TYPE_LABELS) as [TemplateType, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTemplateType(key)}
            className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors ${
              templateType === key ? "bg-gray-900 text-white border-gray-900" : "border-gray-200 text-gray-600 hover:border-gray-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Upload area */}
      <div
        className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors cursor-pointer"
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-blue-400", "bg-blue-50") }}
        onDragLeave={(e) => { e.currentTarget.classList.remove("border-blue-400", "bg-blue-50") }}
        onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove("border-blue-400", "bg-blue-50"); handleUpload(e.dataTransfer.files) }}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".tif,.tiff"
          multiple
          className="hidden"
          onChange={(e) => handleUpload(e.target.files)}
        />
        {uploading ? (
          <div className="space-y-2">
            <Loader2 className="h-8 w-8 mx-auto animate-spin text-blue-500" />
            <p className="text-sm text-gray-600">Uploading TIF files... this may take a while for large files</p>
          </div>
        ) : (
          <div className="space-y-2">
            <CloudUpload className="h-8 w-8 mx-auto text-gray-400" />
            <p className="text-sm font-medium text-gray-700">Drop TIF files here or click to browse</p>
            <p className="text-xs text-gray-400">Select all {TYPE_LABELS[templateType]} blank templates at once</p>
          </div>
        )}
      </div>

      {/* Upload results */}
      {results.length > 0 && (
        <div className="rounded-md border overflow-hidden">
          <div className="bg-gray-50 px-3 py-2 text-xs font-medium text-gray-500 uppercase">Upload results</div>
          <div className="divide-y divide-gray-100">
            {results.map((r, i) => (
              <div key={i} className="px-3 py-2 flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  {r.error ? <X className="h-4 w-4 text-red-500" /> : <Check className="h-4 w-4 text-green-500" />}
                  <span className={r.error ? "text-red-600" : ""}>{r.filename}</span>
                </div>
                <div className="flex items-center gap-2">
                  {r.size_mb && <span className="text-xs text-gray-400">{r.size_mb} MB</span>}
                  {r.matched_template && <Badge variant="secondary" className="text-green-600 text-[10px]">Matched: {r.matched_template}</Badge>}
                  {r.error && <span className="text-xs text-red-500">{r.error}</span>}
                  {!r.error && !r.matched_template && <Badge variant="secondary" className="text-amber-600 text-[10px]">Not in registry</Badge>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Template status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="font-semibold text-sm">Registered Templates</h2>
          {!loading && <span className="text-xs text-gray-500">{inR2} / {total} uploaded to R2</span>}
        </div>
        <Button variant="outline" size="sm" onClick={loadStatus} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
      ) : statuses.length === 0 ? (
        <p className="text-center text-sm text-gray-400 py-8">No templates registered for this type</p>
      ) : (
        <div className="rounded-md border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-3 py-2 text-left">Template</th>
                <th className="px-3 py-2 text-left">R2 Key</th>
                <th className="px-3 py-2 text-center">In R2</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {statuses.map((s) => (
                <tr key={s.r2_key} className={s.in_r2 ? "" : "bg-red-50"}>
                  <td className="px-3 py-2 font-medium">{s.print_name}</td>
                  <td className="px-3 py-2 text-xs text-gray-400 font-mono">{s.r2_key}</td>
                  <td className="px-3 py-2 text-center">
                    {s.in_r2 ? <Check className="h-4 w-4 text-green-500 mx-auto" /> : <X className="h-4 w-4 text-red-400 mx-auto" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
