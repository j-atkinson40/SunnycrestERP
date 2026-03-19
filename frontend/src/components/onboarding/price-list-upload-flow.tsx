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

  const confirmSummary = useMemo(() => {
    const allItems = Object.values(localItems);
    const included = allItems.filter(
      (i) =>
        (i.action === "create_product" || i.action === "create_custom" || i.action === "create_bundle") &&
        !i.charge_category,
    );
    // Group by category-ish extracted from name
    const groups: Record<string, { count: number; min: number; max: number }> =
      {};
    for (const item of included) {
      const name = item.final_product_name || item.extracted_name;
      let category = "Other";
      const nameLower = name.toLowerCase();
      if (nameLower.includes("burial") || nameLower.includes("vault")) {
        if (nameLower.includes("urn")) {
          category = "Urn Vaults";
        } else {
          category = "Burial Vaults";
        }
      } else if (nameLower.includes("urn")) {
        category = "Urns";
      } else if (
        nameLower.includes("lowering") ||
        nameLower.includes("tent") ||
        nameLower.includes("grass") ||
        nameLower.includes("chair") ||
        nameLower.includes("equipment")
      ) {
        category = "Cemetery Equipment";
      } else if (
        nameLower.includes("marker") ||
        nameLower.includes("memorial") ||
        nameLower.includes("monument")
      ) {
        category = "Memorials";
      }
      if (item.action === "create_bundle") {
        category = "Equipment Bundles";
      }

      const price = item.final_price ?? 0;
      if (!groups[category]) {
        groups[category] = { count: 0, min: price, max: price };
      }
      groups[category].count++;
      if (price < groups[category].min) groups[category].min = price;
      if (price > groups[category].max) groups[category].max = price;
    }

    // Charge library summary
    const chargeItems = allItems.filter((i) => i.charge_category && i.action === "create_custom");
    const chargesMatched = chargeItems.filter((i) => i.matched_charge_id).length;
    const chargesNew = chargeItems.filter((i) => !i.matched_charge_id).length;

    return {
      groups,
      total: included.length,
      chargesMatched,
      chargesNew,
      chargesTotal: chargeItems.length,
    };
  }, [localItems]);

  const [confirmResult, setConfirmResult] = useState<{
    products_created: number;
    charges_created: number;
    charges_updated: number;
  } | null>(null);

  const handleConfirm = useCallback(async () => {
    if (!importData) return;
    setConfirming(true);
    try {
      const result = await importService.confirmImport(importData.id);
      const parts: string[] = [];
      if (result.products_created > 0)
        parts.push(`${result.products_created} products created`);
      if (result.charges_created > 0)
        parts.push(`${result.charges_created} new charges added`);
      if (result.charges_updated > 0)
        parts.push(`${result.charges_updated} charges updated`);
      toast.success(`Catalog built! ${parts.join(", ")}.`);
      setConfirmResult(result);
      // If charges were created/updated, show success step before navigating
      if (result.charges_created > 0 || result.charges_updated > 0) {
        setStep("done");
      } else {
        navigate("/products");
      }
    } catch {
      toast.error("Failed to build catalog. Please try again.");
    } finally {
      setConfirming(false);
    }
  }, [importData, navigate]);

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
            Looks good — build my catalog
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
          <h1 className="text-2xl font-bold">Catalog built successfully!</h1>
          <p className="mt-2 text-muted-foreground">
            Your products and charges are ready to use.
          </p>
        </div>

        <Card>
          <CardContent className="space-y-4 pt-6">
            {confirmResult.products_created > 0 && (
              <div className="flex items-center justify-between rounded-lg border px-4 py-3">
                <div className="flex items-center gap-3">
                  <Package className="h-5 w-5 text-green-600" />
                  <p className="font-medium">Products Created</p>
                </div>
                <Badge variant="secondary">{confirmResult.products_created}</Badge>
              </div>
            )}
            {confirmResult.charges_updated > 0 && (
              <div className="flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
                <div className="flex items-center gap-3">
                  <Link2 className="h-5 w-5 text-blue-600" />
                  <p className="font-medium text-blue-900">Charges Updated</p>
                </div>
                <Badge className="bg-blue-100 text-blue-700">{confirmResult.charges_updated}</Badge>
              </div>
            )}
            {confirmResult.charges_created > 0 && (
              <div className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-4 py-3">
                <div className="flex items-center gap-3">
                  <Zap className="h-5 w-5 text-green-600" />
                  <p className="font-medium text-green-900">New Charges Added</p>
                </div>
                <Badge className="bg-green-100 text-green-700">{confirmResult.charges_created}</Badge>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex items-center justify-center gap-3">
          <Button onClick={() => navigate("/products")}>
            View Products
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          {(confirmResult.charges_created > 0 || confirmResult.charges_updated > 0) && (
            <Button variant="outline" onClick={() => navigate("/settings/charges")}>
              Manage Charges
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Confirm your catalog</h1>
        <p className="mt-2 text-muted-foreground">
          Here's what we'll create from your price list.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 pt-6">
          {Object.entries(confirmSummary.groups)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([category, data]) => (
              <div
                key={category}
                className="flex items-center justify-between rounded-lg border px-4 py-3"
              >
                <div>
                  <p className="font-medium">{category}</p>
                  <p className="text-sm text-muted-foreground">
                    {data.count} product{data.count !== 1 ? "s" : ""}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">
                  {formatPrice(data.min)}
                  {data.min !== data.max && ` — ${formatPrice(data.max)}`}
                </p>
              </div>
            ))}

          <div className="border-t pt-4">
            <div className="flex items-center justify-between">
              <p className="text-lg font-semibold">Total</p>
              <p className="text-lg font-semibold">
                {confirmSummary.total} product
                {confirmSummary.total !== 1 ? "s" : ""}
              </p>
            </div>
          </div>

          {/* Charge library section */}
          {confirmSummary.chargesTotal > 0 && (
            <>
              <div className="border-t pt-4">
                <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Charge Library
                </p>
                {confirmSummary.chargesMatched > 0 && (
                  <div className="mb-2 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Link2 className="h-5 w-5 text-blue-600" />
                      <p className="text-sm font-medium text-blue-900">
                        Existing charges to update
                      </p>
                    </div>
                    <Badge className="bg-blue-100 text-blue-700">
                      {confirmSummary.chargesMatched}
                    </Badge>
                  </div>
                )}
                {confirmSummary.chargesNew > 0 && (
                  <div className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Zap className="h-5 w-5 text-green-600" />
                      <p className="text-sm font-medium text-green-900">
                        New charges to add
                      </p>
                    </div>
                    <Badge className="bg-green-100 text-green-700">
                      {confirmSummary.chargesNew}
                    </Badge>
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => setStep("review")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to review
        </Button>
        <Button onClick={handleConfirm} disabled={confirming}>
          {confirming ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Building catalog...
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              Build My Catalog
            </>
          )}
        </Button>
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
      <tr className={cn(isSkipped && "opacity-50")}>
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
                  : "bg-primary/10 text-primary hover:bg-primary/20",
              )}
            >
              {isSkipped ? (
                <>
                  <SkipForward className="h-3 w-3" />
                  Skipped
                </>
              ) : (
                <>
                  <Plus className="h-3 w-3" />
                  Add as Custom
                </>
              )}
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className={cn(isSkipped && "opacity-50")}>
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
              : isBundle
                ? "bg-purple-50 text-purple-700 hover:bg-purple-100"
                : "bg-green-50 text-green-700 hover:bg-green-100",
          )}
        >
          {isSkipped ? (
            <>
              <SkipForward className="h-3 w-3" />
              Skip
            </>
          ) : isBundle ? (
            <>
              <Package className="h-3 w-3" />
              Create Bundle
            </>
          ) : (
            <>
              <Check className="h-3 w-3" />
              Include
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
                  : "bg-green-50 text-green-700 hover:bg-green-100",
              )}
            >
              {isSkipped ? (
                <>
                  <SkipForward className="h-3 w-3" />
                  Skip
                </>
              ) : (
                <>
                  <Zap className="h-3 w-3" />
                  Add to Library
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
