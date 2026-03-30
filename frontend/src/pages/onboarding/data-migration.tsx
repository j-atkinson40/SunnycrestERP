/**
 * Data Migration Center
 *
 * 4-step wizard for importing data from a previous accounting system (Sage 100,
 * QuickBooks, etc.) into Bridgeable.
 *
 * Step 1 — Upload files (COA, Customers, AR Aging, Vendors, AP Aging)
 * Step 2 — Preview parsed data with tabs per data type
 * Step 3 — Live streaming import progress
 * Step 4 — Migration complete summary
 *
 * Also accessible post-onboarding at /settings/data-migration (same component).
 */

import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  FileSpreadsheet,
  FileText,
  Loader2,
  RotateCcw,
  Upload,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { getCompanySlug } from "@/lib/tenant";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ExtensionGroup {
  count: number;
  sample_names: string[];
  suggested_extensions?: string[];
  suggested_extension?: string;
}

interface ExtensionContent {
  contractor_customers: ExtensionGroup;
  wastewater_products: ExtensionGroup;
  redi_rock_products: ExtensionGroup;
  rosetta_products: ExtensionGroup;
  has_extension_content: boolean;
}

interface ParsedPreview {
  coa?: {
    count: number;
    active_count: number;
    inactive_count: number;
    sample: Array<{ account_number: string; description: string; bridgeable_account_type: string; status: string }>;
  };
  customers?: {
    count: number;
    active_count: number;
    by_division: Record<string, number>;
    sample: Array<{ name: string; customer_type: string; division: string; status: string }>;
  };
  ar_invoices?: {
    count: number;
    total_balance: number;
    customer_count: number;
    customers_with_holds: number;
    by_aging_bucket: { current: number; one_month: number; two_months: number; three_months: number; four_months: number };
    sample: Array<{ invoice_number: string; customer_name: string; balance: number; days_delinquent: number }>;
  };
  vendors?: {
    count: number;
    active_count: number;
    sample: Array<{ name: string; status: string; phone?: string }>;
  };
  ap_bills?: {
    count: number;
    total_balance: number;
    by_aging_bucket: { current: number; one_month: number; two_months: number; three_months: number; four_months: number };
    sample: Array<{ invoice_number: string; vendor_name: string; invoice_balance: number }>;
  };
  extension_content?: ExtensionContent;
}

interface ProgressEvent {
  step?: string;
  status?: string;
  progress?: number;
  total?: number;
  imported?: number;
  skipped?: number;
  errors?: string[];
  message?: string;
  summary?: MigrationSummary;
}

interface MigrationSummary {
  gl_accounts_imported: number;
  gl_accounts_skipped: number;
  customers_imported: number;
  customers_skipped: number;
  ar_invoices_imported: number;
  ar_invoices_skipped: number;
  vendors_imported: number;
  vendors_skipped: number;
  ap_bills_imported: number;
  ap_bills_skipped: number;
  total_ar_balance: number;
  total_ap_balance: number;
  warning_count: number;
  error_count: number;
  errors?: string[];
  warnings?: string[];
  hidden_contractors?: number;
  hidden_products?: number;
}

interface ExtensionDecisions {
  enable_wastewater: boolean;
  enable_redi_rock: boolean;
  enable_rosetta: boolean;
}

interface FileSlot {
  key: string;
  label: string;
  description: string;
  accepts: string;
  sageInstructions: string;
  icon: React.ReactNode;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const FILE_SLOTS: FileSlot[] = [
  {
    key: "coa_file",
    label: "Chart of Accounts",
    description: "Maps your GL accounts to Bridgeable",
    accepts: ".csv,.xlsx,.xls",
    sageInstructions: "Sage 100: GL → Chart of Accounts → Print/Export → CSV",
    icon: <BarChart3 className="h-5 w-5" />,
  },
  {
    key: "customers_file",
    label: "Customer List",
    description: "Your existing customer accounts",
    accepts: ".xlsx,.xls,.csv",
    sageInstructions: "Sage 100: Accounts Receivable → Customer Maintenance → Export",
    icon: <Users className="h-5 w-5" />,
  },
  {
    key: "ar_aging_file",
    label: "AR Aging Report",
    description: "Open invoices and customer balances",
    accepts: ".csv,.xlsx,.xls",
    sageInstructions: "Sage 100: Reports → Accounts Receivable → Aged Invoice Report → All Open → Export",
    icon: <FileText className="h-5 w-5" />,
  },
  {
    key: "vendors_file",
    label: "Vendor List",
    description: "Your existing vendor accounts",
    accepts: ".xlsx,.xls,.csv",
    sageInstructions: "Sage 100: Accounts Payable → Vendor Maintenance → Export",
    icon: <FileSpreadsheet className="h-5 w-5" />,
  },
  {
    key: "ap_aging_file",
    label: "AP Aging Report",
    description: "Open bills and vendor balances",
    accepts: ".csv,.xlsx,.xls",
    sageInstructions: "Sage 100: Reports → Accounts Payable → Aged Invoice Report → All Open → Export",
    icon: <FileText className="h-5 w-5" />,
  },
];

const STEP_LABELS: Record<string, string> = {
  gl_accounts: "GL Accounts",
  customers: "Customers",
  ar_invoices: "Open Invoices",
  vendors: "Vendors",
  ap_bills: "Open Bills",
};

const fmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const fmtDec = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

// ─── Main component ───────────────────────────────────────────────────────────

export default function DataMigrationPage() {
  const navigate = useNavigate();

  const [step, setStep] = useState<1 | 2 | 2.5 | 3 | 4>(1);
  const [files, setFiles] = useState<Record<string, File>>({});
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState<ParsedPreview | null>(null);

  // Step 2.5 extension decisions
  const [extensionDecisions, setExtensionDecisions] = useState<ExtensionDecisions>({
    enable_wastewater: false,
    enable_redi_rock: false,
    enable_rosetta: false,
  });

  // Step 2 options
  const [includeInactiveAccounts, setIncludeInactiveAccounts] = useState(false);
  const [includeInactiveCustomers, setIncludeInactiveCustomers] = useState(false);
  const [includeInactiveVendors, setIncludeInactiveVendors] = useState(false);
  const [cutoverDate, setCutoverDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [activeTab, setActiveTab] = useState("accounts");
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  // Step 3 streaming
  const [progressEvents, setProgressEvents] = useState<Record<string, ProgressEvent>>({});
  const [stepOrder] = useState(["gl_accounts", "customers", "ar_invoices", "vendors", "ap_bills"]);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [importRunning, setImportRunning] = useState(false);

  // Step 4 summary
  const [summary, setSummary] = useState<MigrationSummary | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // ─── Step 1: File upload ──────────────────────────────────────────────────

  function handleFileSelect(key: string, file: File) {
    setFiles((prev) => ({ ...prev, [key]: file }));
  }

  function removeFile(key: string) {
    setFiles((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  async function handleParseAndPreview() {
    if (Object.keys(files).length === 0) {
      toast.error("Upload at least one file to continue.");
      return;
    }
    setParsing(true);
    try {
      const form = new FormData();
      Object.entries(files).forEach(([key, file]) => form.append(key, file));
      const res = await apiClient.post("/migration/parse", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setPreview(res.data);
      // Set active tab to first available
      if (res.data.coa) setActiveTab("accounts");
      else if (res.data.customers) setActiveTab("customers");
      else if (res.data.ar_invoices) setActiveTab("ar");
      else if (res.data.vendors) setActiveTab("vendors");
      else if (res.data.ap_bills) setActiveTab("ap");
      setStep(2);
      // Reset extension decisions each new parse
      setExtensionDecisions({ enable_wastewater: false, enable_redi_rock: false, enable_rosetta: false });
    } catch (e: unknown) {
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to parse files.");
    } finally {
      setParsing(false);
    }
  }

  // ─── Step 2.5: Extension content ─────────────────────────────────────────

  function renderExtensionStep() {
    const ec = preview?.extension_content;
    if (!ec) return null;

    const toggleExt = (key: keyof ExtensionDecisions) => {
      setExtensionDecisions((prev) => ({ ...prev, [key]: !prev[key] }));
    };

    const ExtButton = ({
      extKey,
      label,
      price,
    }: {
      extKey: keyof ExtensionDecisions;
      label: string;
      price: string;
    }) => {
      const enabled = extensionDecisions[extKey];
      return (
        <button
          onClick={() => toggleExt(extKey)}
          className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium border transition-colors ${
            enabled
              ? "bg-green-600 text-white border-green-600 hover:bg-green-700"
              : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
          }`}
        >
          {enabled ? `✓ ${label} — will be enabled` : `+ ${label}  ${price}`}
        </button>
      );
    };

    const hasContractors = ec.contractor_customers.count > 0;
    const hasWastewater = ec.wastewater_products.count > 0;
    const hasRediRock = ec.redi_rock_products.count > 0;
    const hasRosetta = ec.rosetta_products.count > 0;

    function sampleStr(names: string[], total: number): string {
      const shown = names.slice(0, 3).join(", ");
      const rest = total - names.slice(0, 3).length;
      return rest > 0 ? `${shown} and ${rest} more` : shown;
    }

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">We found content for additional features</h2>
            <p className="mt-1 text-sm text-slate-500">
              Everything will be imported. Choose which extensions to enable now, or enable them later from Settings.
            </p>
          </div>
          <button onClick={() => setStep(2)} className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1">
            ← Back to Preview
          </button>
        </div>

        <div className="space-y-4">
          {/* Contractor customers card */}
          {hasContractors && (
            <div className="rounded-lg border border-slate-200 bg-white p-5 space-y-3">
              <div className="flex items-start gap-3">
                <span className="text-2xl">👷</span>
                <div>
                  <p className="font-semibold text-slate-900">{ec.contractor_customers.count.toLocaleString()} Contractor Customers</p>
                  <p className="text-sm text-slate-500 mt-0.5">{sampleStr(ec.contractor_customers.sample_names, ec.contractor_customers.count)}</p>
                </div>
              </div>
              <p className="text-sm text-slate-600">
                These customers work with product lines beyond burial vaults. They'll be hidden until you enable a product line extension.
              </p>
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Enable now:</p>
                <div className="flex flex-wrap gap-2">
                  <ExtButton extKey="enable_wastewater" label="Wastewater Extension" price="$49/mo" />
                  <ExtButton extKey="enable_redi_rock" label="Redi-Rock Extension" price="$49/mo" />
                </div>
              </div>
              <p className="text-xs text-slate-400">All content is imported regardless of your choices. Extensions only control visibility.</p>
            </div>
          )}

          {/* Wastewater products card */}
          {hasWastewater && (
            <div className="rounded-lg border border-slate-200 bg-white p-5 space-y-3">
              <div className="flex items-start gap-3">
                <span className="text-2xl">🚰</span>
                <div>
                  <p className="font-semibold text-slate-900">{ec.wastewater_products.count.toLocaleString()} Wastewater Products</p>
                  <p className="text-sm text-slate-500 mt-0.5">{sampleStr(ec.wastewater_products.sample_names, ec.wastewater_products.count)}</p>
                </div>
              </div>
              <p className="text-sm text-slate-600">Requires Wastewater extension.</p>
              <ExtButton extKey="enable_wastewater" label="Enable Wastewater Extension" price="$49/mo" />
              <p className="text-xs text-slate-400">All content is imported regardless of your choices. Extensions only control visibility.</p>
            </div>
          )}

          {/* Redi-Rock products card */}
          {hasRediRock && (
            <div className="rounded-lg border border-slate-200 bg-white p-5 space-y-3">
              <div className="flex items-start gap-3">
                <span className="text-2xl">🪨</span>
                <div>
                  <p className="font-semibold text-slate-900">{ec.redi_rock_products.count.toLocaleString()} Redi-Rock Products</p>
                  <p className="text-sm text-slate-500 mt-0.5">{sampleStr(ec.redi_rock_products.sample_names, ec.redi_rock_products.count)}</p>
                </div>
              </div>
              <p className="text-sm text-slate-600">Requires Redi-Rock extension.</p>
              <ExtButton extKey="enable_redi_rock" label="Enable Redi-Rock Extension" price="$49/mo" />
              <p className="text-xs text-slate-400">All content is imported regardless of your choices. Extensions only control visibility.</p>
            </div>
          )}

          {/* Rosetta products card */}
          {hasRosetta && (
            <div className="rounded-lg border border-slate-200 bg-white p-5 space-y-3">
              <div className="flex items-start gap-3">
                <span className="text-2xl">🏗</span>
                <div>
                  <p className="font-semibold text-slate-900">{ec.rosetta_products.count.toLocaleString()} Rosetta Products</p>
                  <p className="text-sm text-slate-500 mt-0.5">{sampleStr(ec.rosetta_products.sample_names, ec.rosetta_products.count)}</p>
                </div>
              </div>
              <p className="text-sm text-slate-600">Requires Rosetta extension.</p>
              <ExtButton extKey="enable_rosetta" label="Enable Rosetta Extension" price="$49/mo" />
              <p className="text-xs text-slate-400">All content is imported regardless of your choices. Extensions only control visibility.</p>
            </div>
          )}
        </div>

        <div className="flex justify-between pt-2">
          <button onClick={() => setStep(2)} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            ← Back to Preview
          </button>
          <button
            onClick={() => setShowConfirmModal(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Continue to Import →
          </button>
        </div>
      </div>
    );
  }

  // ─── Step 3: Run import ───────────────────────────────────────────────────

  async function runImport() {
    setShowConfirmModal(false);
    setStep(3);
    setImportRunning(true);
    setProgressEvents({});
    setCurrentStep("gl_accounts");

    const form = new FormData();
    Object.entries(files).forEach(([key, file]) => form.append(key, file));
    form.append(
      "options",
      JSON.stringify({
        include_inactive_accounts: includeInactiveAccounts,
        include_inactive_customers: includeInactiveCustomers,
        include_inactive_vendors: includeInactiveVendors,
        cutover_date: cutoverDate,
        extension_decisions: extensionDecisions,
      })
    );

    try {
      const token = localStorage.getItem("access_token");
      const slug = getCompanySlug();
      const apiBase = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";
      const fetchHeaders: Record<string, string> = {};
      if (token) fetchHeaders["Authorization"] = `Bearer ${token}`;
      if (slug) fetchHeaders["X-Company-Slug"] = slug;
      const response = await fetch(`${apiBase}/api/v1/migration/run`, {
        method: "POST",
        headers: fetchHeaders,
        body: form,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event: ProgressEvent = JSON.parse(line);
            if (event.step) {
              setCurrentStep(event.step);
              setProgressEvents((prev) => ({ ...prev, [event.step!]: event }));
            }
            if (event.status === "complete" && event.summary) {
              setSummary(event.summary);
              setWarnings([]);
              setStep(4);
            }
          } catch {
            // skip malformed line
          }
        }
      }
    } catch (e: unknown) {
      toast.error("Import failed: " + (e instanceof Error ? e.message : "Unknown error"));
    } finally {
      setImportRunning(false);
    }
  }

  // ─── Render helpers ───────────────────────────────────────────────────────

  function StepIndicator() {
    const steps = ["Upload Files", "Preview & Confirm", "Importing", "Complete"];
    // step 2.5 is sub-step of "Preview & Confirm" — show step 2 as active, not done
    const effectiveStep = step === 2.5 ? 2 : step;
    return (
      <div className="flex items-center gap-2 mb-8">
        {steps.map((label, i) => {
          const num = i + 1;
          const active = effectiveStep === num;
          const done = effectiveStep > num;
          return (
            <div key={num} className="flex items-center gap-2">
              <div className={`flex items-center gap-1.5 text-sm font-medium ${active ? "text-blue-600" : done ? "text-green-600" : "text-slate-400"}`}>
                <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${active ? "bg-blue-600 text-white" : done ? "bg-green-500 text-white" : "bg-slate-200 text-slate-500"}`}>
                  {done ? "✓" : num}
                </span>
                <span className="hidden sm:inline">{label}</span>
              </div>
              {i < steps.length - 1 && <ChevronRight className="h-4 w-4 text-slate-300" />}
            </div>
          );
        })}
      </div>
    );
  }

  // ─── Step 1: Upload ────────────────────────────────────────────────────────

  function renderUpload() {
    const hasFiles = Object.keys(files).length > 0;
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Import from your previous system</h2>
          <p className="mt-1 text-sm text-slate-500">
            Upload your accounting exports and we'll bring your data into Bridgeable. Upload as many or as few files as you have.
          </p>
        </div>

        <div className="grid gap-4">
          {FILE_SLOTS.map((slot) => {
            const file = files[slot.key];
            return (
              <div key={slot.key} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                    {slot.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <p className="font-medium text-slate-900">{slot.label}</p>
                        <p className="text-sm text-slate-500">{slot.description}</p>
                      </div>
                      {file ? (
                        <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-1.5 text-sm text-green-700 border border-green-200">
                          <CheckCircle2 className="h-4 w-4" />
                          <span className="truncate max-w-[140px]">{file.name}</span>
                          <button onClick={() => removeFile(slot.key)} className="text-green-500 hover:text-green-700">
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => fileInputRefs.current[slot.key]?.click()}
                          className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                        >
                          <Upload className="h-3.5 w-3.5" />
                          Upload
                        </button>
                      )}
                    </div>
                    <p className="mt-2 text-xs text-slate-400">{slot.sageInstructions}</p>
                  </div>
                </div>
                <input
                  ref={(el) => { fileInputRefs.current[slot.key] = el; }}
                  type="file"
                  accept={slot.accepts}
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFileSelect(slot.key, f);
                    e.target.value = "";
                  }}
                />
              </div>
            );
          })}
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={handleParseAndPreview}
            disabled={!hasFiles || parsing}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {parsing ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            {parsing ? "Parsing files…" : "Parse and Preview →"}
          </button>
        </div>
      </div>
    );
  }

  // ─── Step 2: Preview ──────────────────────────────────────────────────────

  function renderPreview() {
    if (!preview) return null;

    const tabs = [
      preview.coa && { key: "accounts", label: `Accounts (${preview.coa.count})` },
      preview.customers && { key: "customers", label: `Customers (${preview.customers.count})` },
      preview.ar_invoices && { key: "ar", label: `Open Invoices (${preview.ar_invoices.count})` },
      preview.vendors && { key: "vendors", label: `Vendors (${preview.vendors.count})` },
      preview.ap_bills && { key: "ap", label: `Open Bills (${preview.ap_bills.count})` },
    ].filter(Boolean) as Array<{ key: string; label: string }>;

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">Preview your data</h2>
            <p className="mt-1 text-sm text-slate-500">Review the parsed data before importing.</p>
          </div>
          <button onClick={() => setStep(1)} className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1">
            ← Back
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-slate-200">
          <div className="flex gap-4">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`pb-2 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.key ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-700"}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div>
          {activeTab === "accounts" && preview.coa && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-600">Active: <strong>{preview.coa.active_count}</strong></span>
                <span className="text-slate-400">|</span>
                <span className="text-slate-600">Inactive: <strong>{preview.coa.inactive_count}</strong></span>
                <label className="ml-auto flex items-center gap-2 text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={includeInactiveAccounts} onChange={(e) => setIncludeInactiveAccounts(e.target.checked)} className="rounded" />
                  Include inactive accounts
                </label>
              </div>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Account #</th>
                      <th className="px-4 py-2 text-left">Description</th>
                      <th className="px-4 py-2 text-left">Type</th>
                      <th className="px-4 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.coa.sample.map((a, i) => (
                      <tr key={i} className={a.status === "inactive" ? "opacity-50" : ""}>
                        <td className="px-4 py-2 font-mono text-slate-700">{a.account_number}</td>
                        <td className="px-4 py-2 text-slate-900">{a.description}</td>
                        <td className="px-4 py-2 text-slate-500">{a.bridgeable_account_type}</td>
                        <td className="px-4 py-2">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${a.status === "active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                            {a.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {preview.coa.count > 10 && <p className="text-xs text-slate-400">Showing first 10 of {preview.coa.count} accounts.</p>}
            </div>
          )}

          {activeTab === "customers" && preview.customers && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 text-sm flex-wrap">
                <span className="text-slate-600">Active: <strong>{preview.customers.active_count}</strong></span>
                {Object.entries(preview.customers.by_division).map(([k, v]) => (
                  <span key={k} className="text-slate-600 capitalize">{k}: <strong>{v}</strong></span>
                ))}
                <label className="ml-auto flex items-center gap-2 text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={includeInactiveCustomers} onChange={(e) => setIncludeInactiveCustomers(e.target.checked)} className="rounded" />
                  Include inactive customers
                </label>
              </div>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Name</th>
                      <th className="px-4 py-2 text-left">Type</th>
                      <th className="px-4 py-2 text-left">Division</th>
                      <th className="px-4 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.customers.sample.map((c, i) => (
                      <tr key={i} className={c.status === "Inactive" ? "opacity-50" : ""}>
                        <td className="px-4 py-2 text-slate-900">{c.name}</td>
                        <td className="px-4 py-2 text-slate-500 capitalize">{c.customer_type.replace("_", " ")}</td>
                        <td className="px-4 py-2 text-slate-500">{c.division}</td>
                        <td className="px-4 py-2">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${c.status === "Active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                            {c.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "ar" && preview.ar_invoices && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
                {[
                  ["Current", preview.ar_invoices.by_aging_bucket.current],
                  ["1–30 days", preview.ar_invoices.by_aging_bucket.one_month],
                  ["31–60 days", preview.ar_invoices.by_aging_bucket.two_months],
                  ["61–90 days", preview.ar_invoices.by_aging_bucket.three_months],
                  ["90+ days", preview.ar_invoices.by_aging_bucket.four_months],
                ].map(([label, val]) => (
                  <div key={label as string} className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs text-slate-500">{label as string}</p>
                    <p className="text-sm font-semibold text-slate-900">{fmt.format(val as number)}</p>
                  </div>
                ))}
              </div>
              <div className="flex gap-4 text-sm text-slate-600">
                <span>Total AR: <strong className="text-slate-900">{fmtDec.format(preview.ar_invoices.total_balance)}</strong></span>
                <span>·</span>
                <span>{preview.ar_invoices.customer_count} customers</span>
                {preview.ar_invoices.customers_with_holds > 0 && (
                  <>
                    <span>·</span>
                    <span className="text-amber-600 font-medium">{preview.ar_invoices.customers_with_holds} on credit hold</span>
                  </>
                )}
              </div>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Invoice #</th>
                      <th className="px-4 py-2 text-left">Customer</th>
                      <th className="px-4 py-2 text-right">Balance</th>
                      <th className="px-4 py-2 text-right">Days Past Due</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.ar_invoices.sample.map((inv, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2 font-mono text-slate-700">{inv.invoice_number}</td>
                        <td className="px-4 py-2 text-slate-900">{inv.customer_name}</td>
                        <td className={`px-4 py-2 text-right font-medium ${inv.balance < 0 ? "text-green-700" : "text-slate-900"}`}>
                          {fmtDec.format(inv.balance)}
                        </td>
                        <td className={`px-4 py-2 text-right ${inv.days_delinquent > 90 ? "text-red-600 font-medium" : inv.days_delinquent > 30 ? "text-amber-600" : "text-slate-500"}`}>
                          {inv.days_delinquent > 0 ? `${inv.days_delinquent}d` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "vendors" && preview.vendors && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-600">Active: <strong>{preview.vendors.active_count}</strong></span>
                <span className="text-slate-400">|</span>
                <span className="text-slate-600">Total: <strong>{preview.vendors.count}</strong></span>
                <label className="ml-auto flex items-center gap-2 text-slate-600 cursor-pointer">
                  <input type="checkbox" checked={includeInactiveVendors} onChange={(e) => setIncludeInactiveVendors(e.target.checked)} className="rounded" />
                  Include inactive vendors
                </label>
              </div>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Name</th>
                      <th className="px-4 py-2 text-left">Status</th>
                      <th className="px-4 py-2 text-left">Phone</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.vendors.sample.map((v, i) => (
                      <tr key={i} className={v.status !== "Active" ? "opacity-50" : ""}>
                        <td className="px-4 py-2 text-slate-900">{v.name}</td>
                        <td className="px-4 py-2">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${v.status === "Active" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                            {v.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-slate-500">{v.phone ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "ap" && preview.ap_bills && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
                {[
                  ["Current", preview.ap_bills.by_aging_bucket.current],
                  ["1–30 days", preview.ap_bills.by_aging_bucket.one_month],
                  ["31–60 days", preview.ap_bills.by_aging_bucket.two_months],
                  ["61–90 days", preview.ap_bills.by_aging_bucket.three_months],
                  ["90+ days", preview.ap_bills.by_aging_bucket.four_months],
                ].map(([label, val]) => (
                  <div key={label as string} className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs text-slate-500">{label as string}</p>
                    <p className="text-sm font-semibold text-slate-900">{fmt.format(val as number)}</p>
                  </div>
                ))}
              </div>
              <p className="text-sm text-slate-600">
                Total AP: <strong className="text-slate-900">{fmtDec.format(preview.ap_bills.total_balance)}</strong> across {preview.ap_bills.count} bills
              </p>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wide">
                    <tr>
                      <th className="px-4 py-2 text-left">Invoice #</th>
                      <th className="px-4 py-2 text-left">Vendor</th>
                      <th className="px-4 py-2 text-right">Balance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.ap_bills.sample.map((b, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2 font-mono text-slate-700">{b.invoice_number}</td>
                        <td className="px-4 py-2 text-slate-900">{b.vendor_name}</td>
                        <td className="px-4 py-2 text-right font-medium text-slate-900">{fmtDec.format(b.invoice_balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Cutover date + import button */}
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Migration as of date</label>
            <input
              type="date"
              value={cutoverDate}
              onChange={(e) => setCutoverDate(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-slate-500">Transactions before this date remain in your previous system.</p>
          </div>
          <div className="sm:ml-auto">
            <button
              onClick={() => {
                if (preview?.extension_content?.has_extension_content) {
                  setStep(2.5);
                } else {
                  setShowConfirmModal(true);
                }
              }}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
            >
              {preview?.extension_content?.has_extension_content ? "Continue →" : "Import All Data →"}
            </button>
          </div>
        </div>

        {/* Confirm modal */}
        {showConfirmModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
              <h3 className="text-lg font-semibold text-slate-900 mb-2">Confirm Import</h3>
              <p className="text-sm text-slate-600 mb-4">
                This will import:
                {preview.coa && <span className="block mt-1">· <strong>{preview.coa.active_count}</strong> GL accounts</span>}
                {preview.customers && <span className="block">· <strong>{preview.customers.active_count}</strong> customers</span>}
                {preview.ar_invoices && <span className="block">· <strong>{preview.ar_invoices.count}</strong> open invoices (<strong>{fmtDec.format(preview.ar_invoices.total_balance)}</strong>)</span>}
                {preview.vendors && <span className="block">· <strong>{preview.vendors.active_count}</strong> vendors</span>}
                {preview.ap_bills && <span className="block">· <strong>{preview.ap_bills.count}</strong> open bills (<strong>{fmtDec.format(preview.ap_bills.total_balance)}</strong>)</span>}
                <span className="block mt-2 text-slate-500">as of {cutoverDate}.</span>
                <span className="block mt-2 text-xs text-slate-400">This can be undone from Settings → Data Migration if you need to re-import.</span>
              </p>
              <div className="flex gap-3 justify-end">
                <button onClick={() => setShowConfirmModal(false)} className="px-4 py-2 text-sm rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50">Cancel</button>
                <button onClick={runImport} className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700">Confirm Import</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ─── Step 3: Progress ─────────────────────────────────────────────────────

  function renderProgress() {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Importing your data…</h2>
          <p className="mt-1 text-sm text-slate-500">This may take a few minutes. Don't close this window.</p>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white divide-y divide-slate-100">
          {stepOrder.map((stepKey) => {
            const event = progressEvents[stepKey];
            const isActive = currentStep === stepKey && importRunning && !event?.status?.includes("complete") && !event?.status?.includes("error");
            const isDone = event?.status === "complete";
            const isError = event?.status === "error";
            const isWaiting = !event && !isActive;

            return (
              <div key={stepKey} className="flex items-center gap-4 px-5 py-4">
                <div className="flex-none">
                  {isDone && <CheckCircle2 className="h-5 w-5 text-green-500" />}
                  {isError && <AlertTriangle className="h-5 w-5 text-red-500" />}
                  {isActive && <Loader2 className="h-5 w-5 animate-spin text-blue-500" />}
                  {isWaiting && <CircleDot className="h-5 w-5 text-slate-300" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${isDone ? "text-slate-900" : isActive ? "text-blue-700" : isError ? "text-red-700" : "text-slate-400"}`}>
                    {STEP_LABELS[stepKey]}
                  </p>
                  {event?.status === "running" && event.total && event.total > 0 && (
                    <p className="text-xs text-slate-500">{event.progress ?? 0} / {event.total}</p>
                  )}
                </div>
                <div className="text-right text-sm">
                  {isDone && (
                    <span className="text-slate-600">
                      {event.imported} imported{event.skipped ? `, ${event.skipped} skipped` : ""}
                    </span>
                  )}
                  {isError && <span className="text-red-600 text-xs">{event.message ?? "Error"}</span>}
                  {isWaiting && <span className="text-slate-300 text-xs">Waiting…</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ─── Step 4: Complete ─────────────────────────────────────────────────────

  function renderComplete() {
    if (!summary) return null;
    return (
      <div className="space-y-6">
        <div className="rounded-xl border border-green-200 bg-green-50 p-6">
          <div className="flex items-start gap-4">
            <CheckCircle2 className="h-8 w-8 text-green-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-green-900">Migration Complete</h2>
              <p className="text-sm text-green-700 mt-0.5">Your data has been imported into Bridgeable.</p>

              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                {[
                  ["GL Accounts", `${summary.gl_accounts_imported} imported`, summary.gl_accounts_skipped],
                  ["Customers", `${summary.customers_imported} imported`, summary.customers_skipped],
                  ["Open Invoices", summary.total_ar_balance ? `${fmtDec.format(summary.total_ar_balance)} across ${summary.ar_invoices_imported} items` : `${summary.ar_invoices_imported} imported`, summary.ar_invoices_skipped],
                  ["Vendors", `${summary.vendors_imported} imported`, summary.vendors_skipped],
                  ["Open Bills", summary.total_ap_balance ? `${fmtDec.format(summary.total_ap_balance)} across ${summary.ap_bills_imported} items` : `${summary.ap_bills_imported} imported`, summary.ap_bills_skipped],
                ].map(([label, val, skipped]) => (
                  <div key={label as string}>
                    <p className="text-green-600">{label as string}</p>
                    <p className="font-semibold text-green-900">{val as string}</p>
                    {(skipped as number) > 0 && <p className="text-xs text-green-600">{skipped as number} already existed, skipped</p>}
                  </div>
                ))}
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <button onClick={() => navigate("/ar/aging")} className="inline-flex items-center gap-1.5 rounded-lg border border-green-300 bg-white px-4 py-2 text-sm font-medium text-green-800 hover:bg-green-100">
                  View AR Aging
                </button>
                <button onClick={() => navigate("/customers")} className="inline-flex items-center gap-1.5 rounded-lg border border-green-300 bg-white px-4 py-2 text-sm font-medium text-green-800 hover:bg-green-100">
                  View Customers
                </button>
                <button onClick={() => navigate("/onboarding")} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700">
                  Continue Setup →
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Hidden content notice */}
        {((summary?.hidden_contractors ?? 0) > 0 || (summary?.hidden_products ?? 0) > 0) && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium text-amber-900">Some content is hidden until extensions are enabled</p>
              <ul className="text-sm text-amber-800 space-y-0.5">
                {(summary?.hidden_contractors ?? 0) > 0 && (
                  <li>· {summary!.hidden_contractors} contractor customer{summary!.hidden_contractors! > 1 ? "s" : ""} — hidden until a product-line extension is active</li>
                )}
                {(summary?.hidden_products ?? 0) > 0 && (
                  <li>· {summary!.hidden_products} product{summary!.hidden_products! > 1 ? "s" : ""} — hidden until the matching extension is active</li>
                )}
              </ul>
            </div>
            <button
              onClick={() => navigate("/settings/extensions")}
              className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100"
            >
              Enable Extensions <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {(summary?.errors ?? []).length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-red-700 flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-red-500" /> {(summary?.errors ?? []).length} import error{(summary?.errors ?? []).length > 1 ? "s" : ""}
            </p>
            <ul className="space-y-1 rounded-lg border border-red-200 bg-red-50 p-4 max-h-48 overflow-y-auto">
              {(summary?.errors ?? []).map((e, i) => (
                <li key={i} className="text-xs text-red-800 font-mono">{e}</li>
              ))}
            </ul>
          </div>
        )}

        {warnings.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700 flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-amber-500" /> {warnings.length} warning{warnings.length > 1 ? "s" : ""}
            </p>
            <ul className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-4">
              {warnings.map((w, i) => (
                <li key={i} className="text-sm text-amber-800">{w}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex items-center gap-3 text-sm text-slate-500">
          <RotateCcw className="h-4 w-4" />
          <span>Need to re-import? Go to <button onClick={() => { setStep(1); setPreview(null); setSummary(null); setProgressEvents({}); }} className="text-blue-600 underline">start over</button> or roll back from Settings → Data Migration.</span>
        </div>
      </div>
    );
  }

  // ─── Layout ───────────────────────────────────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Data Migration Center</h1>
        <p className="text-sm text-slate-500 mt-1">Import your existing data from Sage 100, QuickBooks, or another accounting system.</p>
      </div>

      <StepIndicator />

      {step === 1 && renderUpload()}
      {step === 2 && renderPreview()}
      {step === 2.5 && renderExtensionStep()}
      {step === 3 && renderProgress()}
      {step === 4 && renderComplete()}
    </div>
  );
}
