import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Upload,
  FileSpreadsheet,
  FileText,
  CheckCircle2,
  Circle,
  Loader2,
  ArrowRight,
  ArrowLeft,
  X,
  AlertTriangle,
  Sparkles,
  Check,
  SkipForward,
  Plus,
  Package,
  Zap,
  Link2,
  ToggleLeft,
  ToggleRight,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  ClipboardList,
} from "lucide-react";
import type {
  PriceListImport,
  PriceListImportItem,
  ReviewData,
} from "@/types/price-list-import";
import * as importService from "@/services/price-list-import-service";

// ── Helpers ──────────────────────────────────────────────────────

const ACCEPTED_TYPES = [
  ".xlsx",
  ".xls",
  ".pdf",
  ".docx",
  ".doc",
  ".csv",
];
const ACCEPTED_MIME = [
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "text/csv",
];

function formatPrice(v: number | null | undefined): string {
  if (v == null) return "--";
  return `$${v.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return <FileText className="h-8 w-8 text-red-500" />;
  if (ext === "csv") return <FileSpreadsheet className="h-8 w-8 text-green-600" />;
  if (ext === "xlsx" || ext === "xls")
    return <FileSpreadsheet className="h-8 w-8 text-green-600" />;
  return <FileText className="h-8 w-8 text-blue-500" />;
}

// ── Component ────────────────────────────────────────────────────

type Step = "upload" | "processing" | "review" | "confirm" | "done";

interface SummaryGroup {
  key: string;
  label: string;
  icon: string;
  items: (PriceListImportItem & { source: string })[];
}

interface Props {
  onBack: () => void;
}

export default function PriceListUploadFlow({ onBack }: Props) {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("upload");
  const [importData, setImportData] = useState<PriceListImport | null>(null);
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);

  // ── Step 1: Upload ──

  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback((f: File) => {
    const ext = `.${f.name.split(".").pop()?.toLowerCase()}`;
    if (!ACCEPTED_TYPES.includes(ext) && !ACCEPTED_MIME.includes(f.type)) {
      toast.error("Unsupported file type. Please use Excel, PDF, Word, or CSV.");
      return;
    }
    setFile(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFileSelect(f);
    },
    [handleFileSelect],
  );

  const handleAnalyze = useCallback(async () => {
    if (!file) return;
    setUploading(true);
    try {
      const result = await importService.uploadPriceList(file);
      setImportData(result);
      setStep("processing");
    } catch {
      toast.error("Failed to upload file. Please try again.");
    } finally {
      setUploading(false);
    }
  }, [file]);

  // ── Step 2: Processing ──

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (step !== "processing" || !importData) return;

    const startTime = Date.now();
    const TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

    const poll = async () => {
      try {
        // Safety timeout — if analysis takes longer than 3 minutes, show error
        if (Date.now() - startTime > TIMEOUT_MS) {
          if (pollRef.current) clearInterval(pollRef.current);
          setImportData((prev) =>
            prev
              ? {
                  ...prev,
                  status: "failed" as const,
                  error_message:
                    "Analysis is taking longer than expected. Please try again.",
                }
              : prev,
          );
          return;
        }

        const status = await importService.getImportStatus(importData.id);
        setImportData(status);

        if (status.status === "review_ready") {
          if (pollRef.current) clearInterval(pollRef.current);
          const review = await importService.getReviewData(importData.id);
          setReviewData(review);
          setStep("review");
        } else if (status.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {
        // Keep polling on transient errors
      }
    };

    pollRef.current = setInterval(poll, 2000);
    // Initial immediate poll
    poll();

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [step, importData?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const processingSteps = useMemo(() => {
    const s = importData?.status;
    return [
      {
        label: "Reading your file...",
        done: s !== "uploaded",
        active: s === "uploaded",
      },
      {
        label: "Identifying products and prices...",
        done: s === "extracted" || s === "matching" || s === "review_ready",
        active: s === "extracting",
      },
      {
        label: "Matching to product catalog...",
        done: s === "review_ready",
        active: s === "extracted" || s === "matching",
      },
      {
        label: "Building your review...",
        done: s === "review_ready",
        active: s === "matching",
      },
    ];
  }, [importData?.status]);

  const handleRetry = useCallback(() => {
    setImportData(null);
    setFile(null);
    setStep("upload");
  }, []);

  // ── Step 3: Review ──

  const [activeTab, setActiveTab] = useState<
    "high_confidence" | "low_confidence" | "unmatched" | "charges"
  >("high_confidence");
  const [localItems, setLocalItems] = useState<
    Record<string, PriceListImportItem>
  >({});
  const [acceptingAll, setAcceptingAll] = useState(false);

  // Populate local item state from review data
  useEffect(() => {
    if (!reviewData) return;
    const map: Record<string, PriceListImportItem> = {};
    for (const item of [
      ...(reviewData.high_confidence || []),
      ...(reviewData.low_confidence || []),
      ...(reviewData.unmatched || []),
      ...(reviewData.charges || []),
    ]) {
      map[item.id] = { ...item };
    }
    setLocalItems(map);
  }, [reviewData]);

  const updateLocalItem = useCallback(
    (itemId: string, patch: Partial<PriceListImportItem>) => {
      setLocalItems((prev) => ({
        ...prev,
        [itemId]: { ...prev[itemId], ...patch },
      }));
    },
    [],
  );

  const handleItemAction = useCallback(
    async (
      itemId: string,
      action: PriceListImportItem["action"],
    ) => {
      if (!importData) return;
      updateLocalItem(itemId, { action });
      try {
        await importService.updateItem(importData.id, itemId, { action });
      } catch {
        toast.error("Failed to update item.");
      }
    },
    [importData, updateLocalItem],
  );

  const handleAcceptAll = useCallback(async () => {
    if (!importData) return;
    setAcceptingAll(true);
    try {
      await importService.acceptAll(importData.id);
      // Mark all local items as create_product
      setLocalItems((prev) => {
        const next = { ...prev };
        for (const id in next) {
          if (next[id].action !== "skip") {
            next[id] = { ...next[id], action: "create_product" };
          }
        }
        return next;
      });
      toast.success("All suggestions accepted!");
    } catch {
      toast.error("Failed to accept all.");
    } finally {
      setAcceptingAll(false);
    }
  }, [importData]);

  // Items organized by tab
  const tabItems = useMemo(() => {
    if (!reviewData) return { high: [], low: [], unmatched: [], charges: [] };
    const get = (ids: PriceListImportItem[] | undefined) =>
      (ids || []).map((i) => localItems[i.id] ?? i);
    return {
      high: get(reviewData.high_confidence),
      low: get(reviewData.low_confidence),
      unmatched: get(reviewData.unmatched),
      charges: get(reviewData.charges),
    };
  }, [reviewData, localItems]);

  // ── Step 4: Confirm ──

  const [confirming, setConfirming] = useState(false);

  // ── Summary data for the pre-confirmation summary screen ──────
  const summaryData = useMemo(() => {
    const allItems = Object.values(localItems);

    // Categorize included items
    const included = allItems.filter(
      (i) =>
        (i.action === "create_product" ||
          i.action === "create_custom" ||
          i.action === "create_bundle") &&
        !i.charge_category,
    );

    const charges = allItems.filter(
      (i) => i.charge_category && i.action !== "skip",
    );

    const skipped = allItems.filter((i) => i.action === "skip");

    // Determine source label
    function getSource(item: PriceListImportItem): string {
      if (item.action === "create_bundle") return "Equipment package";
      if (item.match_status === "high_confidence" && item.matched_template_id)
        return "Matched to template";
      if (item.match_status === "low_confidence" && item.matched_template_id)
        return "Confirmed match";
      if (item.match_status === "custom" || item.match_status === "unmatched")
        return "Created as detected";
      return "From price list";
    }

    // Categorize by product type
    function getCategory(item: PriceListImportItem): string {
      const name = (item.final_product_name || item.extracted_name).toLowerCase();
      if (name.includes("urn vault") || (name.includes("urn") && name.includes("vault")))
        return "urn_vaults";
      if (name.includes("burial") || name.includes("vault") || name.includes("graveliner") || name.includes("liner"))
        return "burial_vaults";
      if (name.includes("urn")) return "urns";
      if (
        item.action === "create_bundle" ||
        name.includes("equipment") ||
        name.includes("lowering") ||
        name.includes("tent") ||
        name.includes("grass") ||
        name.includes("chair") ||
        name.includes("strap") ||
        name.includes("cremation table") ||
        name.includes("setup")
      )
        return "equipment";
      return "other";
    }

    const groupMap: Record<string, (PriceListImportItem & { source: string })[]> = {
      burial_vaults: [],
      urn_vaults: [],
      urns: [],
      equipment: [],
      other: [],
    };

    for (const item of included) {
      const cat = getCategory(item);
      groupMap[cat].push({ ...item, source: getSource(item) });
    }

    // Sort items within each group alphabetically
    for (const items of Object.values(groupMap)) {
      items.sort((a, b) =>
        (a.final_product_name || a.extracted_name).localeCompare(
          b.final_product_name || b.extracted_name,
        ),
      );
    }

    const GROUP_DEFS: { key: string; label: string; icon: string }[] = [
      { key: "burial_vaults", label: "Burial Vaults", icon: "📦" },
      { key: "urn_vaults", label: "Urn Vaults", icon: "🏺" },
      { key: "urns", label: "Urns", icon: "⚱️" },
      { key: "equipment", label: "Equipment", icon: "🧰" },
      { key: "other", label: "Other Products", icon: "📋" },
    ];

    const groups: SummaryGroup[] = GROUP_DEFS.filter(
      (g) => groupMap[g.key].length > 0,
    ).map((g) => ({
      ...g,
      items: groupMap[g.key],
    }));

    const chargesWithSource = charges.map((c) => ({
      ...c,
      source: c.matched_charge_id
        ? `Updates existing charge${c.matched_charge_name ? ` "${c.matched_charge_name}"` : ""}`
        : "New charge",
    }));

    return {
      groups,
      charges: chargesWithSource,
      skipped,
      totalProducts: included.filter((i) => i.action !== "create_bundle").length,
      totalPackages: included.filter((i) => i.action === "create_bundle").length,
      totalCharges: charges.length,
      totalSkipped: skipped.length,
    };
  }, [localItems]);

  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const toggleGroup = (key: string) =>
    setExpandedGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  const isGroupExpanded = (key: string) => expandedGroups[key] !== false; // default expanded

  const [showSkipped, setShowSkipped] = useState(false);

  // ── Confirm with progress ─────────────────────────────────────
  const [confirmProgress, setConfirmProgress] = useState<string[]>([]);

  const [confirmResult, setConfirmResult] = useState<{
    products_created: number;
    charges_created: number;
    charges_updated: number;
  } | null>(null);

  const handleConfirm = useCallback(async () => {
    if (!importData) return;
    setConfirming(true);
    setConfirmProgress([]);

    // Show progress messages as we go
    const addProgress = (msg: string) =>
      setConfirmProgress((prev) => [...prev, msg]);

    // Pre-compute counts for progress messages
    const sd = summaryData;
    for (const g of sd.groups) {
      addProgress(`Adding ${g.items.length} ${g.label.toLowerCase()} to catalog...`);
      await new Promise((r) => setTimeout(r, 300));
    }
    if (sd.charges.length > 0) {
      addProgress(`Processing ${sd.charges.length} charges...`);
      await new Promise((r) => setTimeout(r, 200));
    }

    try {
      const result = await importService.confirmImport(importData.id);

      // Replace progress with success lines
      const progress: string[] = [];
      for (const g of sd.groups) {
        progress.push(`✓ ${g.items.length} ${g.label.toLowerCase()} added to product catalog`);
      }
      if (result.charges_updated > 0) {
        progress.push(`✓ ${result.charges_updated} charges updated in charge library`);
      }
      if (result.charges_created > 0) {
        progress.push(`✓ ${result.charges_created} new charges added to charge library`);
      }
      setConfirmProgress(progress);

      setConfirmResult(result);
      setStep("done");
    } catch {
      toast.error("Failed to build catalog. Please try again.");
      setConfirmProgress([]);
    } finally {
      setConfirming(false);
    }
  }, [importData, summaryData]);

  // ── Render ─────────────────────────────────────────────────────

  if (step === "upload") {
    return (
      <div className="mx-auto max-w-2xl space-y-6 py-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Upload your price list</h1>
          <p className="mt-2 text-muted-foreground">
            We'll read your file, identify products and prices, and match them
            to the platform catalog automatically.
          </p>
        </div>

        {/* Drop zone */}
        <div
          className={cn(
            "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors",
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-muted-foreground/50",
            file && "border-primary/40 bg-primary/5",
          )}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_TYPES.join(",")}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFileSelect(f);
            }}
          />

          {file ? (
            <div className="flex items-center gap-4">
              {fileIcon(file.name)}
              <div>
                <p className="font-medium">{file.name}</p>
                <p className="text-sm text-muted-foreground">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
                className="ml-4 rounded-full p-1 hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <>
              <Upload className="mb-3 h-10 w-10 text-muted-foreground/50" />
              <p className="font-medium">
                Drop your price list here, or click to browse
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Excel, PDF, Word, or CSV
              </p>
            </>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>

          <Button
            onClick={handleAnalyze}
            disabled={!file || uploading}
          >
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Analyze Price List
              </>
            )}
          </Button>
        </div>
      </div>
    );
  }

  if (step === "processing") {
    return (
      <div className="mx-auto max-w-lg space-y-8 py-16">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Analyzing your price list</h1>
          <p className="mt-2 text-muted-foreground">
            {importData?.file_name ?? "your file"}
          </p>
        </div>

        <Card>
          <CardContent className="space-y-4 pt-6">
            {processingSteps.map((s, i) => (
              <div key={i} className="flex items-center gap-3">
                {s.done ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : s.active ? (
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                ) : (
                  <Circle className="h-5 w-5 text-muted-foreground/30" />
                )}
                <span
                  className={cn(
                    "text-sm",
                    s.done && "text-green-700",
                    s.active && "font-medium",
                    !s.done && !s.active && "text-muted-foreground",
                  )}
                >
                  {s.label}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        {importData?.status === "failed" && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-red-500" />
              <div>
                <p className="font-medium text-red-800">
                  Something went wrong
                </p>
                <p className="mt-1 text-sm text-red-700">
                  {importData.error_message ||
                    "We couldn't process your file. Please check the format and try again."}
                </p>
              </div>
            </div>
            <div className="flex justify-center">
              <Button variant="outline" onClick={handleRetry}>
                Try a different file
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (step === "review") {
    const tabs = [
      {
        key: "high_confidence" as const,
        label: "Ready",
        count: tabItems.high.length,
      },
      {
        key: "low_confidence" as const,
        label: "Review Needed",
        count: tabItems.low.length,
      },
      {
        key: "unmatched" as const,
        label: "Not Matched",
        count: tabItems.unmatched.length,
      },
      ...(tabItems.charges.length > 0
        ? [
            {
              key: "charges" as const,
              label: "Add-On Charges",
              count: tabItems.charges.length,
            },
          ]
        : []),
    ];

    const currentItems =
      activeTab === "high_confidence"
        ? tabItems.high
        : activeTab === "low_confidence"
          ? tabItems.low
          : activeTab === "charges"
            ? tabItems.charges
            : tabItems.unmatched;

    return (
      <div className="mx-auto max-w-5xl space-y-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Review your catalog</h1>
            <p className="mt-1 text-muted-foreground">
              We found{" "}
              <strong>
                {(reviewData?.import_info?.items_extracted ?? 0)}
              </strong>{" "}
              products in your price list.
            </p>
          </div>
          {(() => {
            // Check if all non-skip items are already accepted
            const allItems = Object.values(localItems);
            const allAccepted = allItems.length > 0 && allItems.every(
              (i) => i.action === "create_product" || i.action === "create_bundle" || i.action === "create_custom" || i.action === "skip",
            );
            const nonSkipAccepted = allItems.filter(
              (i) => i.action !== "skip",
            ).length;
            return allAccepted && nonSkipAccepted > 0 ? (
              <Button variant="outline" disabled className="border-green-200 bg-green-50 text-green-700 opacity-100">
                <CheckCircle2 className="mr-2 h-4 w-4" />
                All {nonSkipAccepted} items accepted
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={handleAcceptAll}
                disabled={acceptingAll}
              >
                {acceptingAll ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Check className="mr-2 h-4 w-4" />
                )}
                Accept all suggestions
              </Button>
            );
          })()}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-lg border bg-muted/50 p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "bg-background shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
              <Badge
                variant={
                  activeTab === tab.key ? "default" : "secondary"
                }
              >
                {tab.count}
              </Badge>
            </button>
          ))}
        </div>

        {/* Table / Cards */}
        {activeTab === "charges" ? (
          <div className="space-y-3">
            {currentItems.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Zap className="mb-3 h-10 w-10 text-muted-foreground/30" />
                  <p>No add-on charges detected</p>
                </CardContent>
              </Card>
            ) : (
              currentItems.map((item) => (
                <ChargeCard
                  key={item.id}
                  item={item}
                  onAction={handleItemAction}
                  onUpdate={updateLocalItem}
                  importId={importData?.id ?? ""}
                />
              ))
            )}
          </div>
        ) : (
          <Card>
            <CardContent className="p-0">
              {currentItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Package className="mb-3 h-10 w-10 text-muted-foreground/30" />
                  <p>No items in this category</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/30 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        <th className="px-4 py-3">Your Price List</th>
                        {activeTab !== "unmatched" && (
                          <>
                            <th className="px-2 py-3 text-center w-8" />
                            <th className="px-4 py-3">Platform Product</th>
                          </>
                        )}
                        <th className="px-4 py-3 text-right">Price</th>
                        <th className="px-4 py-3 text-center">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {currentItems.map((item) => (
                        <ReviewRow
                          key={item.id}
                          item={item}
                          tab={activeTab as "high_confidence" | "low_confidence" | "unmatched"}
                          onAction={handleItemAction}
                          onUpdate={updateLocalItem}
                          importId={importData?.id ?? ""}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={handleRetry}>
            Start over
          </Button>
          <Button onClick={() => setStep("confirm")}>
            Review Summary
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  // ── Step 4: Confirm ──

  if (step === "done" && confirmResult) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 py-8">
        <div className="text-center">
          <CheckCircle2 className="mx-auto mb-4 h-16 w-16 text-green-500" />
          <h1 className="text-2xl font-bold">Your catalog is ready</h1>
          <p className="mt-2 text-muted-foreground">
            {confirmResult.products_created} products
            {summaryData.totalPackages > 0 &&
              ` · ${summaryData.totalPackages} equipment packages`}
            {(confirmResult.charges_created > 0 || confirmResult.charges_updated > 0) &&
              ` · ${confirmResult.charges_created + confirmResult.charges_updated} charges`}
          </p>
        </div>

        {/* Progress log */}
        {confirmProgress.length > 0 && (
          <Card>
            <CardContent className="space-y-2 pt-6">
              {confirmProgress.map((line, i) => (
                <p key={i} className="flex items-center gap-2 text-sm">
                  {line.startsWith("✓") ? (
                    <Check className="h-4 w-4 shrink-0 text-green-600" />
                  ) : (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                  )}
                  <span className={line.startsWith("✓") ? "text-green-900" : "text-muted-foreground"}>
                    {line.replace(/^✓\s*/, "")}
                  </span>
                </p>
              ))}
            </CardContent>
          </Card>
        )}

        <div className="flex items-center justify-center gap-3">
          <Button onClick={() => navigate("/products")}>
            View Product Catalog
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          {(confirmResult.charges_created > 0 || confirmResult.charges_updated > 0) && (
            <Button variant="outline" onClick={() => navigate("/settings/charges")}>
              View Charge Library
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          )}
          <Button
            variant="default"
            className="bg-green-600 hover:bg-green-700"
            onClick={() => navigate("/onboarding")}
          >
            Continue Onboarding
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-24 pt-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">
          Here's what will be added to your catalog
        </h1>
        <p className="mt-1 text-muted-foreground">
          Review everything before we build your catalog. You can go back and
          make changes.
        </p>
      </div>

      {/* Running totals bar */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border bg-muted/30 px-4 py-2.5 text-sm">
        {summaryData.totalProducts > 0 && (
          <span>
            <strong>{summaryData.totalProducts}</strong> Products
          </span>
        )}
        {summaryData.totalPackages > 0 && (
          <>
            <span className="text-muted-foreground">·</span>
            <span>
              <strong>{summaryData.totalPackages}</strong> Equipment Packages
            </span>
          </>
        )}
        {summaryData.totalCharges > 0 && (
          <>
            <span className="text-muted-foreground">·</span>
            <span>
              <strong>{summaryData.totalCharges}</strong> Charges
            </span>
          </>
        )}
        {summaryData.totalSkipped > 0 && (
          <>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">
              <strong>{summaryData.totalSkipped}</strong> Skipped
            </span>
          </>
        )}
      </div>

      {/* ── SECTION 1: Product Catalog ────────────────────────────── */}
      {summaryData.groups.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Product Catalog</h2>
              <p className="text-sm text-muted-foreground">
                These items will appear in your product catalog and can be added
                to orders and invoices.
              </p>
            </div>
            <a
              href="/products"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-sm text-blue-600 hover:underline"
            >
              View your product catalog
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>

          {summaryData.groups.map((group) => (
            <Card key={group.key}>
              <button
                className="flex w-full items-center justify-between px-5 py-3.5 text-left"
                onClick={() => toggleGroup(group.key)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{group.icon}</span>
                  <span className="font-semibold">{group.label}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant="secondary">
                    {group.items.length}{" "}
                    {group.key === "equipment"
                      ? group.items.length === 1
                        ? "package"
                        : "packages"
                      : group.items.length === 1
                        ? "product"
                        : "products"}
                  </Badge>
                  {isGroupExpanded(group.key) ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              </button>

              {isGroupExpanded(group.key) && (
                <div className="border-t">
                  {/* Equipment packages — special layout */}
                  {group.key === "equipment" ? (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/40 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          <th className="px-5 py-2">Package Name</th>
                          <th className="px-3 py-2">With Vault</th>
                          <th className="px-3 py-2">Without Vault</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.items.map((item) => (
                          <tr key={item.id} className="border-b last:border-b-0">
                            <td className="px-5 py-2.5 font-medium">
                              {item.final_product_name || item.extracted_name}
                            </td>
                            <td className="px-3 py-2.5">
                              {item.has_conditional_pricing && item.extracted_price_with_vault
                                ? formatPrice(item.extracted_price_with_vault)
                                : item.final_price
                                  ? formatPrice(item.final_price)
                                  : "--"}
                            </td>
                            <td className="px-3 py-2.5">
                              {item.has_conditional_pricing && item.extracted_price_standalone
                                ? formatPrice(item.extracted_price_standalone)
                                : "--"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    /* Regular products — standard table */
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/40 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          <th className="px-5 py-2">Product Name</th>
                          <th className="px-3 py-2">SKU</th>
                          <th className="px-3 py-2 text-right">Price</th>
                          <th className="px-3 py-2 text-right">Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.items.map((item) => (
                          <tr key={item.id} className="border-b last:border-b-0">
                            <td className="px-5 py-2.5 font-medium">
                              {item.final_product_name || item.extracted_name}
                            </td>
                            <td className="px-3 py-2.5 text-muted-foreground">
                              {item.final_sku || item.extracted_sku || "--"}
                            </td>
                            <td className="px-3 py-2.5 text-right">
                              {item.has_conditional_pricing ? (
                                <span className="space-x-1">
                                  <span className="text-xs text-muted-foreground">w/ vault:</span>{" "}
                                  {formatPrice(item.extracted_price_with_vault)}
                                  <br />
                                  <span className="text-xs text-muted-foreground">standalone:</span>{" "}
                                  {formatPrice(item.extracted_price_standalone)}
                                </span>
                              ) : (
                                formatPrice(item.final_price ?? item.extracted_price)
                              )}
                            </td>
                            <td className="px-3 py-2.5 text-right text-xs text-muted-foreground">
                              {item.source}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* ── SECTION 2: Charge Library ─────────────────────────────── */}
      {summaryData.charges.length > 0 && (
        <div className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">Charge Library</h2>
            <p className="text-sm text-muted-foreground">
              These fees and surcharges will be added to your charge library and
              can be applied to orders.
            </p>
          </div>

          {/* Destination callout */}
          <div className="rounded-lg border border-blue-200 bg-blue-50/50 px-5 py-4">
            <div className="flex items-start gap-3">
              <ClipboardList className="mt-0.5 h-5 w-5 text-blue-600" />
              <div className="text-sm">
                <p className="font-medium text-blue-900">
                  These charges go to your Charge Library
                </p>
                <p className="mt-0.5 text-blue-800/70">
                  Not your product catalog — a separate place in your settings
                  where you manage fees and surcharges.
                </p>
                <a
                  href="/settings/charges"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1.5 inline-flex items-center gap-1 text-blue-600 hover:underline"
                >
                  Preview charge library
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>

          {/* Charge rows */}
          <Card>
            <div className="divide-y">
              {summaryData.charges.map((charge) => (
                <div key={charge.id} className="px-5 py-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold">
                        {charge.final_product_name || charge.extracted_name}
                      </p>
                      <Badge
                        variant="outline"
                        className="mt-1 text-xs capitalize"
                      >
                        {(charge.charge_category || "other").replace(/_/g, " ")}
                      </Badge>
                    </div>
                    <div className="text-right text-sm">
                      {charge.has_conditional_pricing ? (
                        <>
                          <span className="text-xs text-muted-foreground">
                            w/ vault:
                          </span>{" "}
                          {formatPrice(charge.extracted_price_with_vault)}
                          <br />
                          <span className="text-xs text-muted-foreground">
                            standalone:
                          </span>{" "}
                          {formatPrice(charge.extracted_price_standalone)}
                        </>
                      ) : charge.pricing_type_suggestion === "variable" ? (
                        <span className="text-muted-foreground">
                          Variable — dispatcher enters amount
                        </span>
                      ) : charge.extracted_price != null ? (
                        formatPrice(charge.extracted_price)
                      ) : (
                        <span className="text-muted-foreground">
                          Variable — dispatcher enters amount
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="mt-1.5 text-sm">
                    {charge.matched_charge_id ? (
                      <span className="text-green-700">
                        → Updates existing charge
                        {charge.matched_charge_name &&
                          ` "${charge.matched_charge_name}"`}{" "}
                        in your library
                      </span>
                    ) : (
                      <span className="text-blue-700">
                        → New charge — will be added to your library
                      </span>
                    )}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ── SKIPPED ITEMS ─────────────────────────────────────────── */}
      {summaryData.totalSkipped > 0 && (
        <div>
          <button
            className="flex w-full items-center gap-2 rounded-lg border bg-muted/20 px-4 py-3 text-left text-sm font-medium text-muted-foreground hover:bg-muted/40"
            onClick={() => setShowSkipped((v) => !v)}
          >
            {showSkipped ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            Skipped items ({summaryData.totalSkipped})
          </button>

          {showSkipped && (
            <div className="mt-2 space-y-1 rounded-lg border px-5 py-4">
              {summaryData.skipped.map((item) => (
                <p key={item.id} className="text-sm text-muted-foreground">
                  · "{item.final_product_name || item.extracted_name}" — skipped
                </p>
              ))}
              <p className="mt-3 text-xs text-muted-foreground">
                Skipped items are not added to your catalog. You can add them
                manually from your Products or Charge Library settings at any
                time.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Confirm progress (visible during confirm) ─────────────── */}
      {confirming && confirmProgress.length > 0 && (
        <Card>
          <CardContent className="space-y-2 pt-6">
            {confirmProgress.map((line, i) => (
              <p key={i} className="flex items-center gap-2 text-sm">
                {line.startsWith("✓") ? (
                  <Check className="h-4 w-4 shrink-0 text-green-600" />
                ) : (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                )}
                <span className={line.startsWith("✓") ? "text-green-900" : "text-muted-foreground"}>
                  {line.replace(/^✓\s*/, "")}
                </span>
              </p>
            ))}
          </CardContent>
        </Card>
      )}

      {/* ── Sticky Footer ─────────────────────────────────────────── */}
      <div className="fixed inset-x-0 bottom-0 z-50 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
          <Button variant="outline" onClick={() => setStep("review")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Review
          </Button>

          <span className="hidden text-sm text-muted-foreground md:block">
            {summaryData.totalProducts + summaryData.totalPackages > 0 &&
              `${summaryData.totalProducts + summaryData.totalPackages} products`}
            {summaryData.totalPackages > 0 &&
              ` · ${summaryData.totalPackages} packages`}
            {summaryData.totalCharges > 0 &&
              ` · ${summaryData.totalCharges} charges`}
          </span>

          <Button
            onClick={handleConfirm}
            disabled={confirming}
            className="bg-green-600 hover:bg-green-700"
          >
            {confirming ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Building your catalog...
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Confirm and Build Catalog
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Review Row Sub-component ─────────────────────────────────────

interface ReviewRowProps {
  item: PriceListImportItem;
  tab: "high_confidence" | "low_confidence" | "unmatched";
  onAction: (itemId: string, action: PriceListImportItem["action"]) => void;
  onUpdate: (itemId: string, patch: Partial<PriceListImportItem>) => void;
  importId: string;
}

function getBundleType(name: string): { label: string; color: string; hint: string } | null {
  const lower = name.toLowerCase();
  if (lower.endsWith(" only")) {
    return {
      label: "Single Item Service",
      color: "bg-amber-100 text-amber-700",
      hint: "This is a single-item graveside service. The customer pays this flat rate when ordering just this item.",
    };
  }
  if (lower.includes(" & ")) {
    return {
      label: "Equipment Package",
      color: "bg-blue-100 text-blue-700",
      hint: "This is a partial equipment package — includes the items named in the title.",
    };
  }
  if (
    lower.includes("full") ||
    lower.includes("equipment") ||
    lower.includes("setup") ||
    lower.includes("package")
  ) {
    return {
      label: "Equipment Package",
      color: "bg-purple-100 text-purple-700",
      hint: "Full equipment package — manufacturer defines what's included.",
    };
  }
  return null;
}

function ReviewRow({ item, tab, onAction, onUpdate, importId }: ReviewRowProps) {
  const isSkipped = item.action === "skip";
  const isAccepted = item.action === "create_product" || item.action === "create_bundle" || item.action === "create_custom";
  const isBundle = item.match_status === "bundle" || item.action === "create_bundle";
  const bundleType = isBundle ? getBundleType(item.extracted_name) : null;
  const hasNamedComponents = item.match_reasoning?.includes("[named-in-title]") ?? false;

  const handlePriceChange = useCallback(
    (value: string) => {
      const num = parseFloat(value);
      onUpdate(item.id, { final_price: isNaN(num) ? null : num });
      // Debounced server update handled by parent or could be added here
      if (!isNaN(num) && importId) {
        importService.updateItem(importId, item.id, { final_price: num }).catch(() => {});
      }
    },
    [item.id, importId, onUpdate],
  );

  const handleNameChange = useCallback(
    (value: string) => {
      onUpdate(item.id, { final_product_name: value });
      if (importId) {
        importService.updateItem(importId, item.id, { final_product_name: value }).catch(() => {});
      }
    },
    [item.id, importId, onUpdate],
  );

  if (tab === "unmatched") {
    return (
      <tr className={cn(
        isSkipped && "opacity-50",
        isAccepted && "bg-green-50/50",
      )}>
        <td className="px-4 py-3">
          <Input
            value={item.final_product_name}
            onChange={(e) => handleNameChange(e.target.value)}
            className="h-8 text-sm"
          />
        </td>
        <td className="px-4 py-3 text-right">
          <Input
            type="number"
            step="0.01"
            value={item.final_price ?? ""}
            onChange={(e) => handlePriceChange(e.target.value)}
            className="h-8 w-28 text-right text-sm ml-auto"
          />
        </td>
        <td className="px-4 py-3 text-center">
          <div className="flex items-center justify-center gap-1">
            <button
              type="button"
              onClick={() =>
                onAction(
                  item.id,
                  isSkipped ? "create_custom" : "skip",
                )
              }
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors",
                isSkipped
                  ? "bg-muted text-muted-foreground hover:bg-muted/80"
                  : "bg-green-100 text-green-700 hover:bg-green-200",
              )}
            >
              {isSkipped ? (
                <>
                  <SkipForward className="h-3 w-3" />
                  Skipped
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-3 w-3" />
                  Included
                </>
              )}
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className={cn(
      isSkipped && "opacity-50",
      isAccepted && "bg-green-50/50",
    )}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-medium">{item.extracted_name}</p>
          {isBundle && bundleType ? (
            <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium", bundleType.color)}>
              <Package className="h-3 w-3" /> {bundleType.label}
            </span>
          ) : isBundle ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-medium text-purple-700">
              <Package className="h-3 w-3" /> Bundle
            </span>
          ) : null}
          {hasNamedComponents && (
            <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-600 border border-amber-200">
              Named in title
            </span>
          )}
        </div>
        {item.extracted_sku && (
          <p className="text-xs text-muted-foreground">
            SKU: {item.extracted_sku}
          </p>
        )}
      </td>
      <td className="px-2 py-3 text-center">
        <ArrowRight className="h-4 w-4 text-muted-foreground/40 mx-auto" />
      </td>
      <td className="px-4 py-3">
        {isBundle ? (
          <div>
            <p className="text-sm font-medium">{item.final_product_name}</p>
            {bundleType && (
              <p className="mt-1 text-xs text-muted-foreground">
                {bundleType.hint}
              </p>
            )}
            {item.match_reasoning && (() => {
              // Extract suggested components from reasoning text
              const compMatch = item.match_reasoning.match(/Suggested components: (.+)$/);
              if (compMatch) {
                const components = compMatch[1].split(", ");
                return (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {components.map((comp, i) => {
                      const isNamed = comp.includes("[named-in-title]");
                      const cleanName = comp.replace(/ \[.*?\]/g, "").trim();
                      return (
                        <span
                          key={i}
                          className={cn(
                            "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium",
                            isNamed
                              ? "bg-amber-50 text-amber-700 border border-amber-200"
                              : "bg-muted text-muted-foreground",
                          )}
                        >
                          {cleanName}
                        </span>
                      );
                    })}
                  </div>
                );
              }
              // Show plain reasoning if no components
              const plainReasoning = item.match_reasoning.split(" | Suggested components:")[0];
              return plainReasoning ? (
                <p className="mt-1 text-xs italic text-muted-foreground">
                  {plainReasoning}
                </p>
              ) : null;
            })()}
          </div>
        ) : tab === "low_confidence" ? (
          <div>
            <Input
              value={item.final_product_name}
              onChange={(e) => handleNameChange(e.target.value)}
              className="h-8 text-sm"
            />
            {item.match_reasoning && (
              <p className="mt-1 text-xs italic text-muted-foreground">
                {item.match_reasoning}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm">
            {item.matched_template_name || item.final_product_name}
          </p>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        {isBundle && item.has_conditional_pricing ? (
          <div className="space-y-1.5 text-right">
            <div className="flex items-center justify-end gap-1.5">
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">w/ vault:</span>
              <Input
                type="number"
                step="0.01"
                value={item.extracted_price_with_vault ?? ""}
                onChange={(e) => {
                  const num = parseFloat(e.target.value);
                  onUpdate(item.id, { extracted_price_with_vault: isNaN(num) ? null : num } as any);
                  if (!isNaN(num) && importId) {
                    importService.updateItem(importId, item.id, { extracted_price_with_vault: num } as any).catch(() => {});
                  }
                }}
                className="h-7 w-24 text-right text-xs"
              />
            </div>
            <div className="flex items-center justify-end gap-1.5">
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">standalone:</span>
              <Input
                type="number"
                step="0.01"
                value={item.extracted_price_standalone ?? ""}
                onChange={(e) => {
                  const num = parseFloat(e.target.value);
                  onUpdate(item.id, { extracted_price_standalone: isNaN(num) ? null : num } as any);
                  if (!isNaN(num) && importId) {
                    importService.updateItem(importId, item.id, { extracted_price_standalone: num } as any).catch(() => {});
                  }
                }}
                className="h-7 w-24 text-right text-xs"
              />
            </div>
            {item.extracted_price_with_vault != null && item.extracted_price_standalone != null &&
              item.extracted_price_with_vault > item.extracted_price_standalone && (
              <p className="text-[10px] text-amber-600">Usually vault price is lower</p>
            )}
          </div>
        ) : tab === "low_confidence" ? (
          <Input
            type="number"
            step="0.01"
            value={item.final_price ?? ""}
            onChange={(e) => handlePriceChange(e.target.value)}
            className="h-8 w-28 text-right text-sm ml-auto"
          />
        ) : (
          <span className="text-sm">{formatPrice(item.final_price)}</span>
        )}
      </td>
      <td className="px-4 py-3 text-center">
        <button
          type="button"
          onClick={() =>
            onAction(item.id, isSkipped ? (isBundle ? "create_bundle" : "create_product") : "skip")
          }
          className={cn(
            "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors",
            isSkipped
              ? "bg-muted text-muted-foreground hover:bg-muted/80"
              : "bg-green-100 text-green-700 hover:bg-green-200",
          )}
        >
          {isSkipped ? (
            <>
              <SkipForward className="h-3 w-3" />
              Skip
            </>
          ) : isBundle ? (
            <>
              <CheckCircle2 className="h-3 w-3" />
              Bundle
            </>
          ) : (
            <>
              <CheckCircle2 className="h-3 w-3" />
              Included
            </>
          )}
        </button>
      </td>
    </tr>
  );
}

// ── Charge Card Sub-component ────────────────────────────────────

const PRICING_TYPE_LABELS: Record<string, string> = {
  fixed: "Flat Fee",
  variable: "Variable",
  per_mile: "Per Mile",
};

const CATEGORY_LABELS: Record<string, string> = {
  service: "Service Fee",
  delivery: "Delivery",
  surcharge: "Surcharge",
  labor: "Labor",
  other: "Other",
};

interface ChargeCardProps {
  item: PriceListImportItem;
  onAction: (itemId: string, action: PriceListImportItem["action"]) => void;
  onUpdate: (itemId: string, patch: Partial<PriceListImportItem>) => void;
  importId: string;
}

function ChargeCard({ item, onAction, onUpdate, importId }: ChargeCardProps) {
  const isSkipped = item.action === "skip";
  const isMatched = !!item.matched_charge_id;
  const matchType = item.charge_match_type;

  const handleTogglePricingType = useCallback(
    (type: string) => {
      onUpdate(item.id, { pricing_type_suggestion: type as any });
      importService
        .updateItem(importId, item.id, { pricing_type_suggestion: type })
        .catch(() => {});
    },
    [item.id, importId, onUpdate],
  );

  const handleToggleEnable = useCallback(() => {
    const next = !item.enable_on_import;
    onUpdate(item.id, { enable_on_import: next });
    importService
      .updateItem(importId, item.id, { enable_on_import: next })
      .catch(() => {});
  }, [item.id, item.enable_on_import, importId, onUpdate]);

  return (
    <Card className={cn(isSkipped && "opacity-50")}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          {/* Left: Name + match status */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-medium">{item.extracted_name}</p>
              {/* Category badge */}
              {item.charge_category && (
                <Badge variant="secondary" className="text-[10px]">
                  {CATEGORY_LABELS[item.charge_category] || item.charge_category}
                </Badge>
              )}
              {/* Match status badge */}
              {isMatched ? (
                <Badge className="bg-green-100 text-green-700 text-[10px]">
                  <Link2 className="mr-1 h-3 w-3" />
                  {matchType === "exact_key"
                    ? "Exact match"
                    : "Matched to existing"}
                </Badge>
              ) : (
                <Badge className="bg-blue-100 text-blue-700 text-[10px]">
                  <Plus className="mr-1 h-3 w-3" />
                  New charge
                </Badge>
              )}
            </div>

            {/* Matched charge name */}
            {isMatched && item.matched_charge_name && (
              <p className="mt-1 text-xs text-muted-foreground">
                Maps to: <span className="font-medium">{item.matched_charge_name}</span>
                {item.charge_key_to_use && (
                  <span className="ml-1 text-muted-foreground/60">
                    ({item.charge_key_to_use})
                  </span>
                )}
              </p>
            )}

            {/* Charge key suggestion for new charges */}
            {!isMatched && item.charge_key_suggestion && (
              <p className="mt-1 text-xs text-muted-foreground">
                Key: <code className="rounded bg-muted px-1 py-0.5 text-[10px]">{item.charge_key_suggestion}</code>
              </p>
            )}
          </div>

          {/* Right: Price + controls */}
          <div className="flex flex-col items-end gap-2 shrink-0">
            {/* Price display */}
            {item.has_conditional_pricing ? (
              <div className="space-y-1 text-right">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-muted-foreground">w/ vault:</span>
                  <span className="text-sm font-medium">
                    {formatPrice(item.extracted_price_with_vault)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-muted-foreground">standalone:</span>
                  <span className="text-sm font-medium">
                    {formatPrice(item.extracted_price_standalone)}
                  </span>
                </div>
              </div>
            ) : (
              <span className="text-sm font-medium">
                {formatPrice(item.extracted_price)}
              </span>
            )}

            {/* Action button */}
            <button
              type="button"
              onClick={() =>
                onAction(item.id, isSkipped ? "create_custom" : "skip")
              }
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                isSkipped
                  ? "bg-muted text-muted-foreground hover:bg-muted/80"
                  : "bg-green-100 text-green-700 hover:bg-green-200",
              )}
            >
              {isSkipped ? (
                <>
                  <SkipForward className="h-3 w-3" />
                  Skip
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-3 w-3" />
                  Added to Library
                </>
              )}
            </button>
          </div>
        </div>

        {/* Bottom controls row — only if not skipped */}
        {!isSkipped && (
          <div className="mt-3 flex items-center gap-4 border-t pt-3">
            {/* Pricing type toggle */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Type:</span>
              <div className="flex gap-1">
                {["fixed", "variable", "per_mile"].map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => handleTogglePricingType(type)}
                    className={cn(
                      "rounded-md px-2 py-0.5 text-[10px] font-medium transition-colors",
                      (item.pricing_type_suggestion || "variable") === type
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80",
                    )}
                  >
                    {PRICING_TYPE_LABELS[type]}
                  </button>
                ))}
              </div>
            </div>

            {/* Enable on import toggle */}
            <button
              type="button"
              onClick={handleToggleEnable}
              className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {item.enable_on_import ? (
                <ToggleRight className="h-4 w-4 text-green-600" />
              ) : (
                <ToggleLeft className="h-4 w-4" />
              )}
              {item.enable_on_import ? "Enabled" : "Disabled"}
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
