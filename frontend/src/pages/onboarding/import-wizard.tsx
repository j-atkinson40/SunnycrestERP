import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import * as onboardingService from "@/services/onboarding-service";
import type { DataImport, ImportPreview, SourceFormat } from "@/types/onboarding";

// ── Types ────────────────────────────────────────────────────────

type WizardStep = "source" | "instructions" | "mapping" | "preview" | "complete";

const STEP_ORDER: WizardStep[] = ["source", "instructions", "mapping", "preview", "complete"];

const TYPE_LABELS: Record<string, string> = {
  customers: "Customers",
  employees: "Employees",
  products: "Products",
  price_list: "Price List",
};

const TYPE_LIST_ROUTES: Record<string, string> = {
  customers: "/customers",
  employees: "/admin/users",
  products: "/products",
  price_list: "/products",
};

const TYPE_CREATE_ROUTES: Record<string, string> = {
  customers: "/customers",
  employees: "/admin/users",
  products: "/products",
  price_list: "/products",
};

// Required fields per import type
const REQUIRED_FIELDS: Record<string, string[]> = {
  customers: ["name", "email"],
  employees: ["first_name", "last_name", "email"],
  products: ["name", "sku", "price"],
  price_list: ["product_sku", "price"],
};

const PLATFORM_FIELDS: Record<string, string[]> = {
  customers: ["name", "email", "phone", "address_line_1", "address_line_2", "city", "state", "zip", "notes"],
  employees: ["first_name", "last_name", "email", "phone", "department", "title", "hire_date"],
  products: ["name", "sku", "description", "category", "price", "unit", "is_active"],
  price_list: ["product_sku", "product_name", "price", "tier", "effective_date"],
};

// ── Icons ────────────────────────────────────────────────────────

function BookIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
    </svg>
  );
}

function LedgerIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    </svg>
  );
}

function TableIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M10.875 12h-7.5c-.621 0-1.125.504-1.125 1.125M12 12h7.5c.621 0 1.125.504 1.125 1.125M12 12v1.5c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 0v1.5c0 .621-.504 1.125-1.125 1.125M12 15.375h-7.5c-.621 0-1.125.504-1.125 1.125" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
    </svg>
  );
}

function HandsIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.042 21.672 13.684 16.6m0 0-2.51 2.225.569-9.47 5.227 7.917-3.286-.672ZM12 2.25V4.5m5.834.166-1.591 1.591M20.25 10.5H18M7.757 14.743l-1.59 1.59M6 10.5H3.75m4.007-4.243-1.59-1.59" />
    </svg>
  );
}

function ArrowLeftIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
    </svg>
  );
}

function UploadIcon() {
  return (
    <svg className="h-10 w-10 text-muted-foreground" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
    </svg>
  );
}

function CheckCircleIcon() {
  return (
    <svg className="h-12 w-12 text-green-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

// ── Source cards config ──────────────────────────────────────────

interface SourceOption {
  key: SourceFormat | "manual_entry";
  title: string;
  description: string;
  icon: React.ReactNode;
}

const SOURCE_OPTIONS: SourceOption[] = [
  {
    key: "quickbooks_export",
    title: "QuickBooks",
    description: "I use QuickBooks Online or Desktop",
    icon: <BookIcon />,
  },
  {
    key: "sage_export",
    title: "Sage",
    description: "I use Sage 100 or Sage 50",
    icon: <LedgerIcon />,
  },
  {
    key: "csv_upload",
    title: "Spreadsheet",
    description: "I have an Excel or CSV file",
    icon: <TableIcon />,
  },
  {
    key: "manual_entry",
    title: "Type it in",
    description: "I'll enter them manually",
    icon: <PencilIcon />,
  },
  {
    key: "white_glove",
    title: "Ask us to do it",
    description: "White-glove import — send us your data and we'll import it for you",
    icon: <HandsIcon />,
  },
];

// ── Instructions per source ─────────────────────────────────────

const SOURCE_INSTRUCTIONS: Record<string, { steps: string[]; showUpload: boolean; downloadTemplate?: boolean }> = {
  quickbooks_export: {
    steps: [
      "Open QuickBooks and go to Reports.",
      "Run the Customer/Employee/Item list report (depending on what you're importing).",
      "Click Export > Export to Excel or Export to CSV.",
      "Save the file to your computer.",
      "Upload the file below.",
    ],
    showUpload: true,
  },
  sage_export: {
    steps: [
      "Open Sage 100 or Sage 50.",
      "Navigate to File > Export.",
      "Select the list you want to export (Customers, Employees, Items, etc.).",
      "Choose CSV as the export format.",
      "Save the file to your computer.",
      "Upload the file below.",
    ],
    showUpload: true,
  },
  csv_upload: {
    steps: [
      "Download our template file to see the expected format.",
      "Fill in your data in the spreadsheet.",
      "Save as CSV or keep as XLSX.",
      "Upload the file below.",
    ],
    showUpload: true,
    downloadTemplate: true,
  },
};

// ── Main Component ───────────────────────────────────────────────

export default function ImportWizardPage() {
  const { type } = useParams<{ type: string }>();
  const navigate = useNavigate();
  const importType = type ?? "customers";
  const typeLabel = TYPE_LABELS[importType] ?? importType;

  const [step, setStep] = useState<WizardStep>("source");
  const [sourceFormat, setSourceFormat] = useState<SourceFormat | null>(null);
  const [importSession, setImportSession] = useState<DataImport | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);

  // White-glove form state
  const [wgDescription, setWgDescription] = useState("");
  const [wgEmail, setWgEmail] = useState("");
  const [wgSubmitted, setWgSubmitted] = useState(false);

  // Field mapping state
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({});
  const [sourceColumns, setSourceColumns] = useState<string[]>([]);

  const currentStepIndex = STEP_ORDER.indexOf(step);

  // ── Navigation helpers ─────────────────────────────────────

  const goBack = useCallback(() => {
    if (step === "instructions") setStep("source");
    else if (step === "mapping") setStep("instructions");
    else if (step === "preview") setStep("mapping");
  }, [step]);

  // ── Source selection ───────────────────────────────────────

  const handleSourceSelect = async (key: SourceFormat | "manual_entry") => {
    if (key === "manual_entry") {
      navigate(TYPE_CREATE_ROUTES[importType] ?? "/");
      return;
    }
    setSourceFormat(key as SourceFormat);

    if (key === "white_glove") {
      setStep("instructions");
      return;
    }

    try {
      const session = await onboardingService.createDataImport(importType, key);
      setImportSession(session);
      setStep("instructions");
    } catch {
      toast.error("Failed to start import session");
    }
  };

  // ── File upload ────────────────────────────────────────────

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
  };

  const handleUpload = async () => {
    if (!file || !importSession) return;
    setUploading(true);
    try {
      // Update the import session with file info
      const updated = await onboardingService.updateDataImport(importSession.id, {
        status: "mapping",
        file_url: file.name,
      });
      setImportSession(updated);

      // Get preview to extract source columns
      const previewData = await onboardingService.previewImport(importSession.id);
      setPreview(previewData);

      // Extract source columns from preview
      if (previewData.preview_rows.length > 0) {
        const cols = Object.keys(previewData.preview_rows[0]);
        setSourceColumns(cols);
        // Auto-map obvious matches
        const autoMap: Record<string, string> = {};
        const platformFields = PLATFORM_FIELDS[importType] ?? [];
        for (const col of cols) {
          const normalized = col.toLowerCase().replace(/[\s_-]+/g, "_");
          const match = platformFields.find(
            (f) => f === normalized || f.includes(normalized) || normalized.includes(f)
          );
          if (match) autoMap[col] = match;
        }
        setFieldMapping(autoMap);
      }

      // Pre-apply mapped fields from server if available
      if (previewData.mapped_fields.length > 0) {
        const serverMap: Record<string, string> = {};
        for (const m of previewData.mapped_fields) {
          serverMap[m.source_column] = m.target_field;
        }
        setFieldMapping((prev) => ({ ...serverMap, ...prev }));
      }

      setStep("mapping");
    } catch {
      toast.error("Failed to upload file");
    } finally {
      setUploading(false);
    }
  };

  // ── White glove submit ─────────────────────────────────────

  const handleWhiteGloveSubmit = async () => {
    if (!wgDescription.trim() || !wgEmail.trim()) {
      toast.error("Please fill in all fields");
      return;
    }
    try {
      await onboardingService.requestWhiteGlove({
        import_type: importType,
        description: wgDescription,
        contact_email: wgEmail,
      });
      setWgSubmitted(true);
      toast.success("White-glove import request submitted");
    } catch {
      toast.error("Failed to submit request");
    }
  };

  // ── Field mapping update ───────────────────────────────────

  const updateFieldMapping = (sourceCol: string, targetField: string) => {
    setFieldMapping((prev) => {
      const next = { ...prev };
      if (targetField === "") {
        delete next[sourceCol];
      } else {
        next[sourceCol] = targetField;
      }
      return next;
    });
  };

  const requiredFields = REQUIRED_FIELDS[importType] ?? [];
  const mappedTargets = Object.values(fieldMapping);
  const unmappedRequired = requiredFields.filter((f) => !mappedTargets.includes(f));

  // ── Move to preview ────────────────────────────────────────

  const handleGoToPreview = async () => {
    if (!importSession) return;
    try {
      await onboardingService.updateDataImport(importSession.id, {
        status: "preview",
        field_mapping: fieldMapping,
      });
      // Refresh preview with mapping applied
      const previewData = await onboardingService.previewImport(importSession.id);
      setPreview(previewData);
      setStep("preview");
    } catch {
      toast.error("Failed to generate preview");
    }
  };

  // ── Execute import ─────────────────────────────────────────

  const handleExecuteImport = async () => {
    if (!importSession) return;
    setExecuting(true);
    setStep("complete");

    // Simulate progress
    const interval = setInterval(() => {
      setImportProgress((prev) => {
        if (prev >= 90) return prev;
        return prev + Math.random() * 15;
      });
    }, 300);

    try {
      const result = await onboardingService.executeImport(importSession.id);
      setImportSession(result);
      setImportProgress(100);
    } catch {
      toast.error("Import failed");
      setStep("preview");
    } finally {
      clearInterval(interval);
      setExecuting(false);
    }
  };

  // ── Step indicator ─────────────────────────────────────────

  const stepLabels = sourceFormat === "white_glove"
    ? ["Source", "Request"]
    : ["Source", "Upload", "Map Fields", "Preview", "Complete"];

  // ── Render ─────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-4xl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          {step !== "source" && (
            <button
              type="button"
              onClick={goBack}
              className="rounded-md p-1 hover:bg-muted transition-colors"
            >
              <ArrowLeftIcon />
            </button>
          )}
          <h1 className="text-2xl font-bold tracking-tight">
            Import {typeLabel}
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {step === "source" && "Choose how you'd like to bring your data in."}
          {step === "instructions" && sourceFormat === "white_glove" && "Tell us about your data and we'll handle the rest."}
          {step === "instructions" && sourceFormat !== "white_glove" && "Follow the steps below, then upload your file."}
          {step === "mapping" && "Map the columns from your file to platform fields."}
          {step === "preview" && "Review your data before importing."}
          {step === "complete" && "Your import is being processed."}
        </p>
      </div>

      {/* Step indicators */}
      {sourceFormat !== "white_glove" && (
        <div className="mb-8 flex items-center gap-2">
          {stepLabels.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                  i < currentStepIndex
                    ? "bg-primary text-primary-foreground"
                    : i === currentStepIndex
                      ? "bg-primary text-primary-foreground ring-2 ring-primary/30"
                      : "bg-muted text-muted-foreground"
                )}
              >
                {i < currentStepIndex ? (
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={cn(
                  "hidden text-xs font-medium sm:inline",
                  i <= currentStepIndex ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {label}
              </span>
              {i < stepLabels.length - 1 && (
                <div
                  className={cn(
                    "h-px w-6 sm:w-10",
                    i < currentStepIndex ? "bg-primary" : "bg-border"
                  )}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Step 1: Source ─────────────────────────────────── */}
      {step === "source" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {SOURCE_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              type="button"
              onClick={() => handleSourceSelect(opt.key)}
              className="group text-left"
            >
              <Card className="h-full transition-all group-hover:ring-2 group-hover:ring-primary/30">
                <CardContent className="flex flex-col items-center text-center py-6">
                  <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-xl bg-muted text-foreground group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                    {opt.icon}
                  </div>
                  <p className="font-semibold text-sm">{opt.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{opt.description}</p>
                </CardContent>
              </Card>
            </button>
          ))}
        </div>
      )}

      {/* ── Step 2: Instructions (file sources) ───────────── */}
      {step === "instructions" && sourceFormat && sourceFormat !== "white_glove" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Export from {SOURCE_OPTIONS.find((o) => o.key === sourceFormat)?.title}
              </CardTitle>
              <CardDescription>Follow these steps to export your data</CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="space-y-3">
                {(SOURCE_INSTRUCTIONS[sourceFormat]?.steps ?? []).map((s, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                      {i + 1}
                    </span>
                    <span className="pt-0.5">{s}</span>
                  </li>
                ))}
              </ol>

              {SOURCE_INSTRUCTIONS[sourceFormat]?.downloadTemplate && (
                <div className="mt-4">
                  <Button variant="outline" size="sm">
                    Download Template
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* File upload area */}
          {SOURCE_INSTRUCTIONS[sourceFormat]?.showUpload && (
            <Card>
              <CardContent className="py-6">
                <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border p-8 text-center hover:border-primary/40 transition-colors">
                  <UploadIcon />
                  <p className="mt-3 text-sm font-medium">
                    {file ? file.name : "Drop your file here or click to browse"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">CSV, XLSX, or XLS</p>
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileChange}
                    className="absolute inset-0 cursor-pointer opacity-0"
                    style={{ position: "relative" }}
                  />
                  {file && (
                    <div className="mt-4">
                      <Button onClick={handleUpload} disabled={uploading}>
                        {uploading ? (
                          <>
                            <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                            Uploading...
                          </>
                        ) : (
                          "Upload & Continue"
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ── Step 2: White Glove ────────────────────────────── */}
      {step === "instructions" && sourceFormat === "white_glove" && (
        <Card>
          <CardHeader>
            <CardTitle>White-Glove Import</CardTitle>
            <CardDescription>
              Send us your data in any format and our team will import it for you.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {wgSubmitted ? (
              <div className="flex flex-col items-center py-8 text-center">
                <CheckCircleIcon />
                <h3 className="mt-4 text-lg font-semibold">Request Submitted</h3>
                <p className="mt-2 text-sm text-muted-foreground max-w-md">
                  Our team will review your data and reach out to {wgEmail} within 1-2 business days.
                </p>
                <Button
                  variant="outline"
                  className="mt-6"
                  onClick={() => navigate(TYPE_LIST_ROUTES[importType] ?? "/")}
                >
                  Back to {typeLabel}
                </Button>
              </div>
            ) : (
              <div className="space-y-4 max-w-lg">
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Describe your data
                  </label>
                  <textarea
                    value={wgDescription}
                    onChange={(e) => setWgDescription(e.target.value)}
                    rows={4}
                    placeholder={`Tell us about your ${typeLabel.toLowerCase()} data — what format it's in, where it came from, any special notes...`}
                    className="w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    File upload <span className="text-muted-foreground font-normal">(any format)</span>
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      type="file"
                      onChange={handleFileChange}
                      className="text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-primary-foreground hover:file:bg-primary/80"
                    />
                    {file && (
                      <Badge variant="secondary">{file.name}</Badge>
                    )}
                  </div>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Contact email
                  </label>
                  <Input
                    type="email"
                    value={wgEmail}
                    onChange={(e) => setWgEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="max-w-sm"
                  />
                </div>
                <div className="pt-2">
                  <Button onClick={handleWhiteGloveSubmit}>
                    Submit Request
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Step 3: Field Mapping ─────────────────────────── */}
      {step === "mapping" && (
        <div className="space-y-6">
          {unmappedRequired.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-800">
                Required fields not yet mapped:{" "}
                {unmappedRequired.map((f) => (
                  <Badge key={f} variant="outline" className="ml-1 text-amber-700 border-amber-300">
                    {f}
                  </Badge>
                ))}
              </p>
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Map Your Columns</CardTitle>
              <CardDescription>
                Match each column from your file to a platform field. Required fields are marked with *.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source Column</TableHead>
                    <TableHead>Platform Field</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sourceColumns.map((col) => {
                    const mapped = fieldMapping[col] ?? "";
                    return (
                      <TableRow key={col}>
                        <TableCell className="font-mono text-sm">{col}</TableCell>
                        <TableCell>
                          <select
                            value={mapped}
                            onChange={(e) => updateFieldMapping(col, e.target.value)}
                            className={cn(
                              "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
                              !mapped && requiredFields.some((f) => !mappedTargets.includes(f))
                                ? ""
                                : ""
                            )}
                          >
                            <option value="">— Skip this column —</option>
                            {(PLATFORM_FIELDS[importType] ?? []).map((field) => (
                              <option key={field} value={field}>
                                {field}
                                {requiredFields.includes(field) ? " *" : ""}
                              </option>
                            ))}
                          </select>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Preview first 3 rows */}
          {preview && preview.preview_rows.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Sample Data</CardTitle>
                <CardDescription>First {Math.min(3, preview.preview_rows.length)} rows from your file</CardDescription>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {sourceColumns.map((col) => (
                        <TableHead key={col} className="whitespace-nowrap text-xs">
                          {col}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.preview_rows.slice(0, 3).map((row, i) => (
                      <TableRow key={i}>
                        {sourceColumns.map((col) => (
                          <TableCell key={col} className="text-xs whitespace-nowrap max-w-[200px] truncate">
                            {String(row[col] ?? "")}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          <div className="flex justify-end">
            <Button
              onClick={handleGoToPreview}
              disabled={unmappedRequired.length > 0}
            >
              Continue to Preview
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 4: Preview ───────────────────────────────── */}
      {step === "preview" && preview && (
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Badge variant="secondary" className="text-sm">
              {preview.total_records} total records
            </Badge>
            {importSession?.error_log && importSession.error_log.length > 0 && (
              <Badge variant="destructive" className="text-sm">
                {importSession.error_log.length} errors
              </Badge>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Preview</CardTitle>
              <CardDescription>
                Showing first {Math.min(5, preview.preview_rows.length)} of {preview.total_records} records
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {Object.values(fieldMapping).map((field) => (
                      <TableHead key={field} className="whitespace-nowrap text-xs">
                        {field}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.preview_rows.slice(0, 5).map((row, i) => {
                    const hasError = importSession?.error_log?.some(
                      (e) => (e as Record<string, unknown>).row === i
                    );
                    return (
                      <TableRow
                        key={i}
                        className={hasError ? "bg-destructive/5" : ""}
                      >
                        {Object.entries(fieldMapping).map(([srcCol, _field]) => (
                          <TableCell key={srcCol} className="text-xs whitespace-nowrap max-w-[200px] truncate">
                            {String(row[srcCol] ?? "")}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {importSession?.error_log && importSession.error_log.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-destructive">Errors</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5 text-sm">
                  {importSession.error_log.slice(0, 10).map((err, i) => {
                    const e = err as Record<string, unknown>;
                    return (
                      <li key={i} className="text-destructive">
                        Row {String(e.row ?? i + 1)}: {String(e.message ?? "Unknown error")}
                      </li>
                    );
                  })}
                </ul>
              </CardContent>
            </Card>
          )}

          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={goBack}>
              Back to Mapping
            </Button>
            <Button onClick={handleExecuteImport}>
              Import {preview.total_records} {typeLabel}
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 5: Complete ──────────────────────────────── */}
      {step === "complete" && (
        <Card>
          <CardContent className="flex flex-col items-center py-12 text-center">
            {executing ? (
              <>
                {/* Progress bar */}
                <div className="w-full max-w-md">
                  <div className="mb-3 text-sm font-medium">
                    Importing {typeLabel.toLowerCase()}...
                  </div>
                  <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-300"
                      style={{ width: `${Math.min(importProgress, 100)}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {Math.round(importProgress)}% complete
                  </p>
                </div>
              </>
            ) : (
              <>
                <CheckCircleIcon />
                <h3 className="mt-4 text-lg font-semibold">Import Complete</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Successfully imported{" "}
                  <span className="font-semibold text-foreground">
                    {importSession?.imported_records ?? 0}
                  </span>{" "}
                  {typeLabel.toLowerCase()}.
                  {(importSession?.failed_records ?? 0) > 0 && (
                    <span className="text-destructive">
                      {" "}{importSession?.failed_records} records failed.
                    </span>
                  )}
                </p>

                {importSession?.error_log && importSession.error_log.length > 0 && (
                  <Button variant="outline" size="sm" className="mt-4">
                    Download Error Log
                  </Button>
                )}

                <div className="mt-6 flex gap-3">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setStep("source");
                      setSourceFormat(null);
                      setFile(null);
                      setImportSession(null);
                      setPreview(null);
                      setFieldMapping({});
                      setSourceColumns([]);
                      setImportProgress(0);
                    }}
                  >
                    Import More
                  </Button>
                  <Button onClick={() => navigate(TYPE_LIST_ROUTES[importType] ?? "/")}>
                    View {typeLabel}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
