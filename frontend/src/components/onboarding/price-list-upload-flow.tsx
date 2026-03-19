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

type Step = "upload" | "processing" | "review" | "confirm";

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

    const poll = async () => {
      try {
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
    "high_confidence" | "low_confidence" | "unmatched"
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
    if (!reviewData) return { high: [], low: [], unmatched: [] };
    const get = (ids: PriceListImportItem[] | undefined) =>
      (ids || []).map((i) => localItems[i.id] ?? i);
    return {
      high: get(reviewData.high_confidence),
      low: get(reviewData.low_confidence),
      unmatched: get(reviewData.unmatched),
    };
  }, [reviewData, localItems]);

  // ── Step 4: Confirm ──

  const [confirming, setConfirming] = useState(false);

  const confirmSummary = useMemo(() => {
    const included = Object.values(localItems).filter(
      (i) => i.action === "create_product" || i.action === "create_custom",
    );
    // Group by category-ish extracted from name
    const groups: Record<string, { count: number; min: number; max: number }> =
      {};
    for (const item of included) {
      // Try to infer category from matched template or product name
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

      const price = item.final_price ?? 0;
      if (!groups[category]) {
        groups[category] = { count: 0, min: price, max: price };
      }
      groups[category].count++;
      if (price < groups[category].min) groups[category].min = price;
      if (price > groups[category].max) groups[category].max = price;
    }

    return { groups, total: included.length };
  }, [localItems]);

  const handleConfirm = useCallback(async () => {
    if (!importData) return;
    setConfirming(true);
    try {
      const result = await importService.confirmImport(importData.id);
      toast.success(
        `Catalog built! ${result.products_created} products created.`,
      );
      navigate("/products");
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
    ];

    const currentItems =
      activeTab === "high_confidence"
        ? tabItems.high
        : activeTab === "low_confidence"
          ? tabItems.low
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
                {(reviewData?.import_info.items_extracted ?? 0)}
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

        {/* Table */}
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
                        tab={activeTab}
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

function ReviewRow({ item, tab, onAction, onUpdate, importId }: ReviewRowProps) {
  const isSkipped = item.action === "skip";

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
        <p className="font-medium">{item.extracted_name}</p>
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
        {tab === "low_confidence" ? (
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
        {tab === "low_confidence" ? (
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
            onAction(item.id, isSkipped ? "create_product" : "skip")
          }
          className={cn(
            "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors",
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
              <Check className="h-3 w-3" />
              Include
            </>
          )}
        </button>
      </td>
    </tr>
  );
}
