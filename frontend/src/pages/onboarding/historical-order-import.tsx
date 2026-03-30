/**
 * Historical Order Import Wizard
 *
 * Step 0 — Choose: Have history to import, or skip?
 * Step 1 — Upload & Preview: upload CSV, review detected mapping, set cutover date
 * Step 2 — Importing: spinner while backend runs
 * Step 3 — Complete: results summary with enrichment highlights
 */

import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import apiClient from "@/lib/api-client";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  Folder,
  Loader2,
  Lock,
  SkipForward,
  Upload,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ParseResult {
  import_id: string;
  format_detected: string;
  total_rows: number;
  column_mapping: Record<string, string>;
  mapping_confidence: Record<string, number>;
  preview: {
    funeral_homes: { count: number; sample: string[]; matched: number; unmatched: number };
    cemeteries: { count: number; sample: string[]; matched: number; unmatched: number };
    products: { count: number; matched: number; unmatched: number; unmapped: string[]; top: {name: string; count: number}[] };
    date_range: { earliest: string; latest: string };
    equipment_breakdown: Record<string, number>;
  };
  warnings: string[];
}

interface ImportSummary {
  imported: number;
  skipped: number;
  errors: number;
  customers_created: number;
  customers_matched: number;
  cemeteries_created: number;
  cemeteries_matched: number;
  fh_cemetery_pairs: number;
  recommended_templates: Array<{
    product_name: string;
    equipment: string;
    order_count: number;
    pct_of_total: number;
    suggested_template_name: string;
  }>;
  warnings: string[];
}

// Human-readable field names for the mapping table
const FIELD_LABELS: Record<string, string> = {
  funeral_home_name: "Funeral home",
  cemetery_name: "Cemetery",
  product_name: "Product name",
  equipment_description: "Equipment",
  scheduled_date: "Service date",
  service_time: "Service time",
  service_place_type: "Service place",
  quantity: "Quantity",
  notes: "Notes",
  source_order_number: "Order number",
  csr_name: "CSR",
  order_method: "Via (phone/email)",
  fulfillment_type: "Fulfillment type",
  is_spring_surcharge: "Spring surcharge",
  skip_privacy: "⚠ Skipped (privacy)",
  ignore: "Ignored",
  cemetery_city: "Cemetery city",
  eta_time: "ETA time",
  order_taken_by: "Taken by",
  confirmed_by: "Confirmed by",
  confirmation_method: "Confirm method",
  created_at_raw: "Order logged date",
};

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

function confidenceLabel(conf: number): string {
  if (conf >= 0.99) return "✓ 99%";
  if (conf >= 0.90) return `✓ ${Math.round(conf * 100)}%`;
  if (conf >= 0.70) return `~ ${Math.round(conf * 100)}%`;
  return `? ${Math.round(conf * 100)}%`;
}

// ---------------------------------------------------------------------------
// Step 0 — Choose
// ---------------------------------------------------------------------------

function ChooseStep({ onHaveHistory, onSkip }: { onHaveHistory: () => void; onSkip: () => void }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Do you have historical funeral order records?</h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-xl">
          If you track orders in a spreadsheet, Airtable, or any system you can export to CSV,
          importing them makes your platform smarter from day one.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Have history */}
        <button
          type="button"
          onClick={onHaveHistory}
          className="text-left rounded-xl border-2 border-gray-200 hover:border-blue-400 hover:bg-blue-50/30 p-6 space-y-3 transition-all group"
        >
          <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center group-hover:bg-blue-200 transition-colors">
            <Folder className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <p className="font-semibold text-base">Yes, I have order records</p>
            <p className="text-sm text-muted-foreground mt-1">
              Upload a CSV or Excel file from any system. We'll map the columns automatically.
            </p>
          </div>
          <Button size="sm" className="mt-2">
            Upload my order history
          </Button>
        </button>

        {/* Skip */}
        <button
          type="button"
          onClick={onSkip}
          className="text-left rounded-xl border-2 border-gray-200 hover:border-gray-300 hover:bg-gray-50 p-6 space-y-3 transition-all group"
        >
          <div className="h-10 w-10 rounded-lg bg-gray-100 flex items-center justify-center group-hover:bg-gray-200 transition-colors">
            <SkipForward className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <p className="font-semibold text-base">Skip for now</p>
            <p className="text-sm text-muted-foreground mt-1">
              Your platform starts fresh. Smart suggestions build automatically as you take real orders.
            </p>
          </div>
          <span className="inline-block mt-2 text-sm text-muted-foreground underline underline-offset-2">
            Continue without history
          </span>
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1 — Upload & Preview
// ---------------------------------------------------------------------------

const STANDARD_FIELD_OPTIONS = [
  "funeral_home_name", "cemetery_name", "product_name", "equipment_description",
  "scheduled_date", "service_time", "service_place_type", "quantity", "notes",
  "source_order_number", "csr_name", "order_method", "fulfillment_type",
  "is_spring_surcharge", "cemetery_city", "skip_privacy", "ignore",
];

function UploadStep({
  onParsed,
}: {
  onParsed: (result: ParseResult) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [mappingOpen, setMappingOpen] = useState(false);
  const [userMapping, setUserMapping] = useState<Record<string, string>>({});
  const [cutoverDate, setCutoverDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().split("T")[0];
  });
  const [createCustomers, setCreateCustomers] = useState(true);
  const [createCemeteries, setCreateCemeteries] = useState(true);
  const [running, setRunning] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    if (!file) return;
    setUploading(true);
    setParseResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const { data } = await apiClient.post<ParseResult>("/historical-orders/parse", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setParseResult(data);
      setUserMapping({});  // reset overrides
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Failed to parse file. Please check the format.";
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }, []);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  async function handleRunImport() {
    if (!parseResult) return;
    setRunning(true);

    const formData = new FormData();
    formData.append("import_id", parseResult.import_id);
    formData.append("column_mapping", JSON.stringify(userMapping));
    formData.append("cutover_date", cutoverDate);
    formData.append("create_missing_customers", String(createCustomers));
    formData.append("create_missing_cemeteries", String(createCemeteries));

    try {
      const { data } = await apiClient.post<{ status: string; import_id: string; summary: ImportSummary }>(
        "/historical-orders/run",
        formData,
        { headers: { "Content-Type": "multipart/form-data" }, timeout: 300000 }
      );
      onParsed({ ...parseResult, ...data.summary as unknown as ParseResult });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Import failed. Please try again.";
      toast.error(msg);
      setRunning(false);
    }
  }

  const pr = parseResult;
  const effectiveMapping = { ...(pr?.column_mapping ?? {}), ...userMapping };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Upload your order history</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-xl">
          Export your orders as CSV from your spreadsheet, Airtable, or order management system.
          We'll detect the format automatically.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => fileRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
          uploading
            ? "border-blue-300 bg-blue-50"
            : "border-gray-300 hover:border-blue-400 hover:bg-blue-50/20",
        )}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.txt"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
            <p className="text-sm text-muted-foreground">Reading your file...</p>
          </div>
        ) : pr ? (
          <div className="flex flex-col items-center gap-2">
            <FileText className="h-8 w-8 text-green-600" />
            <p className="text-sm font-medium">File loaded — replace by uploading another</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <Upload className="h-8 w-8 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Drag and drop your order history</p>
              <p className="text-xs text-muted-foreground">or click to browse — CSV files supported</p>
            </div>
          </div>
        )}
      </div>

      {/* Preview summary */}
      {pr && (
        <div className="space-y-4">
          <div className="rounded-xl border bg-green-50/40 p-5 space-y-3">
            <div className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-600 shrink-0" />
              <p className="font-semibold">
                We found {pr.total_rows.toLocaleString()} orders
                {pr.format_detected === "sunnycrest_green_sheet" && (
                  <span className="ml-2 text-xs font-normal text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                    Sunnycrest green sheet detected
                  </span>
                )}
              </p>
            </div>

            {pr.preview.date_range.earliest && (
              <p className="text-sm text-muted-foreground">
                📅 {new Date(pr.preview.date_range.earliest).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
                {" → "}
                {new Date(pr.preview.date_range.latest).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
              </p>
            )}

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="font-medium">👥 {pr.preview.funeral_homes.count} funeral homes</p>
                <p className="text-xs text-muted-foreground">
                  {pr.preview.funeral_homes.matched} matched · {pr.preview.funeral_homes.unmatched} new
                </p>
              </div>
              <div>
                <p className="font-medium">🏛 {pr.preview.cemeteries.count} cemeteries</p>
                <p className="text-xs text-muted-foreground">
                  {pr.preview.cemeteries.matched} matched · {pr.preview.cemeteries.unmatched} new
                </p>
              </div>
            </div>

            {pr.preview.products.top.length > 0 && (
              <div className="text-sm">
                <p className="font-medium">📦 Top products:</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {pr.preview.products.top.slice(0, 4)
                    .map((p) => `${p.name} (${p.count})`)
                    .join(" · ")}
                </p>
              </div>
            )}
          </div>

          {/* Warnings */}
          {pr.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 space-y-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                <p className="text-sm font-medium text-amber-800">A few things to note:</p>
              </div>
              <ul className="space-y-1 pl-6">
                {pr.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-700 list-disc">{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Privacy note */}
          <div className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
            <Lock className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
            <p className="text-xs text-muted-foreground">
              <strong>Privacy:</strong> Decedent names (Family Name column) are not stored — they
              are skipped entirely during import.
            </p>
          </div>

          {/* Column mapping review */}
          <div className="border rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => setMappingOpen((v) => !v)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
            >
              <span className="text-sm font-medium">Review column mapping</span>
              {mappingOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>

            {mappingOpen && (
              <div className="border-t divide-y max-h-72 overflow-y-auto">
                {Object.entries(effectiveMapping).map(([col, field]) => {
                  const isPrivacy = field === "skip_privacy";
                  const isIgnored = field === "ignore";
                  const conf = pr.mapping_confidence[col] ?? 0;
                  return (
                    <div key={col} className="flex items-center gap-3 px-4 py-2 text-sm">
                      <span className="w-32 truncate font-medium text-muted-foreground">{col}</span>
                      <span className="text-muted-foreground">→</span>
                      {isPrivacy ? (
                        <span className="flex items-center gap-1 text-amber-700 text-xs">
                          <Lock className="h-3 w-3" />
                          Skipped (privacy — decedent name)
                        </span>
                      ) : (
                        <select
                          value={effectiveMapping[col] ?? "ignore"}
                          onChange={(e) => setUserMapping((m) => ({ ...m, [col]: e.target.value }))}
                          className="flex-1 rounded border border-gray-200 px-2 py-1 text-xs bg-white"
                        >
                          {STANDARD_FIELD_OPTIONS.map((f) => (
                            <option key={f} value={f}>{fieldLabel(f)}</option>
                          ))}
                        </select>
                      )}
                      {!isPrivacy && !isIgnored && (
                        <span className={cn("text-xs shrink-0", conf >= 0.9 ? "text-green-700" : "text-amber-600")}>
                          {confidenceLabel(conf)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Cutover date */}
          <div className="space-y-1.5">
            <Label className="text-sm">Import orders up to what date?</Label>
            <Input
              type="date"
              value={cutoverDate}
              onChange={(e) => setCutoverDate(e.target.value)}
              className="w-48"
            />
            <p className="text-xs text-muted-foreground">
              Orders before this date are imported as history. Orders from this date forward will
              be entered fresh in Bridgeable.
            </p>
          </div>

          {/* Options */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={createCustomers} onChange={(e) => setCreateCustomers(e.target.checked)} className="rounded" />
              Create new funeral home records for unmatched names
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={createCemeteries} onChange={(e) => setCreateCemeteries(e.target.checked)} className="rounded" />
              Create new cemetery records for unmatched locations
            </label>
          </div>

          {/* Run button */}
          <div className="flex items-center justify-between pt-2 border-t">
            <p className="text-xs text-muted-foreground">
              {pr.total_rows.toLocaleString()} orders · this may take 15–30 seconds
            </p>
            <Button onClick={handleRunImport} disabled={running}>
              {running ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  Import Order History <ArrowRight className="ml-1.5 h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3 — Complete
// ---------------------------------------------------------------------------

function CompleteStep({ summary, navigate }: { summary: ImportSummary; navigate: (p: string) => void }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center shrink-0">
          <Check className="h-6 w-6 text-green-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Order history imported</h1>
          <p className="text-sm text-muted-foreground">
            {summary.imported.toLocaleString()} orders imported · {summary.skipped} skipped
          </p>
        </div>
      </div>

      <p className="text-sm font-medium">Here's what's ready for you:</p>

      <div className="space-y-3">
        {/* Cemetery shortlists */}
        {summary.fh_cemetery_pairs > 0 && (
          <Card className="p-4 space-y-1">
            <p className="font-medium text-sm flex items-center gap-2">
              🏛 Cemetery shortlists ready
            </p>
            <p className="text-sm text-muted-foreground">
              {summary.customers_matched + summary.customers_created} funeral homes have their most common
              cemeteries pre-loaded in the order form shortlist.
            </p>
          </Card>
        )}

        {/* New cemeteries */}
        {summary.cemeteries_created > 0 && (
          <Card className="p-4 space-y-2">
            <p className="font-medium text-sm">
              🗺 {summary.cemeteries_created} new cemeteries added
            </p>
            <p className="text-sm text-muted-foreground">
              Review equipment settings when ready.
            </p>
            <Button size="sm" variant="outline" onClick={() => navigate("/settings/cemeteries")}>
              Settings → Cemeteries
            </Button>
          </Card>
        )}

        {/* Template recommendations */}
        {summary.recommended_templates.length > 0 && (
          <Card className="p-4 space-y-3">
            <p className="font-medium text-sm">📋 Template recommendations ready</p>
            <p className="text-sm text-muted-foreground">
              Based on your history, these are your most common order combinations:
            </p>
            <div className="space-y-1.5">
              {summary.recommended_templates.slice(0, 5).map((t, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="font-medium">{t.suggested_template_name}</span>
                  <span className="text-xs text-muted-foreground">
                    {t.order_count} orders · {t.pct_of_total}%
                  </span>
                </div>
              ))}
            </div>
            <Button size="sm" variant="outline" onClick={() => navigate("/onboarding/quick-orders")}>
              Set up templates →
            </Button>
          </Card>
        )}

        {/* Equipment hints */}
        {summary.warnings.filter((w) => w.startsWith("Hint:")).length > 0 && (
          <Card className="p-4 space-y-2 border-amber-200 bg-amber-50/40">
            <p className="font-medium text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Equipment hints
            </p>
            <ul className="space-y-1">
              {summary.warnings
                .filter((w) => w.startsWith("Hint:"))
                .map((w, i) => (
                  <li key={i} className="text-xs text-amber-800 list-disc ml-4">{w.replace("Hint: ", "")}</li>
                ))}
            </ul>
            <Button size="sm" variant="outline" onClick={() => navigate("/settings/cemeteries")}>
              Review hints →
            </Button>
          </Card>
        )}

        {/* Privacy confirmation */}
        <div className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
          <Lock className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <p className="text-xs text-muted-foreground">
            Decedent names were not imported and are not stored in Bridgeable.
          </p>
        </div>
      </div>

      <div className="flex justify-end pt-2 border-t">
        <Button onClick={() => navigate("/onboarding")}>
          Continue setup <ArrowRight className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main wizard
// ---------------------------------------------------------------------------

export default function HistoricalOrderImportPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<0 | 1 | 3>(0);
  const [importSummary, setImportSummary] = useState<ImportSummary | null>(null);

  async function handleSkip() {
    try {
      await apiClient.post("/tenant-onboarding/checklist/items/import_order_history/skip");
    } catch {
      // Non-critical
    }
    navigate("/onboarding");
  }

  function handleImportComplete(result: ParseResult & ImportSummary) {
    // result is merged ParseResult + ImportSummary from the run endpoint
    setImportSummary(result as unknown as ImportSummary);
    // Mark checklist item complete
    apiClient.post("/tenant-onboarding/checklist/items/import_order_history/complete").catch(() => {});
    setStep(3);
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      {step === 0 && (
        <ChooseStep
          onHaveHistory={() => setStep(1)}
          onSkip={handleSkip}
        />
      )}
      {step === 1 && (
        <UploadStep onParsed={handleImportComplete as (r: ParseResult) => void} />
      )}
      {step === 3 && importSummary && (
        <CompleteStep summary={importSummary} navigate={navigate} />
      )}
    </div>
  );
}
