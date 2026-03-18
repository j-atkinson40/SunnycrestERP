import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import * as XLSX from "xlsx";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import * as urnService from "@/services/urn-catalog-service";
import type { UrnImportItem, ColumnMapping } from "@/types/urn-catalog";

// ── Constants ────────────────────────────────────────────────────

const STEP_LABELS = [
  "Upload",
  "Map Columns",
  "Filter to Urns",
  "Set Markup",
  "Review & Import",
];

const AUTO_MAP_SKU = ["item #", "item number", "sku", "part #", "part number", "wilbert #"];
const AUTO_MAP_NAME = ["description", "product", "name", "item description"];
const AUTO_MAP_COST = ["price", "cost", "wholesale", "list price", "your cost", "net price"];
const AUTO_MAP_CATEGORY = ["category", "type", "product type"];
const AUTO_MAP_SIZE = ["size", "capacity", "type"];

const URN_KEYWORDS = ["urn", "marble", "cremation", "keepsake"];

const PAGE_SIZE = 50;

// ── Helpers ──────────────────────────────────────────────────────

function autoMapColumns(headers: string[]): ColumnMapping {
  const mapping: ColumnMapping = { sku: null, name: null, cost: null, category: null, size: null };
  const lowerHeaders = headers.map((h) => h.toLowerCase().trim());

  for (let i = 0; i < lowerHeaders.length; i++) {
    const h = lowerHeaders[i];
    if (!mapping.sku && AUTO_MAP_SKU.some((k) => h.includes(k))) mapping.sku = headers[i];
    if (!mapping.name && AUTO_MAP_NAME.some((k) => h.includes(k))) mapping.name = headers[i];
    if (!mapping.cost && AUTO_MAP_COST.some((k) => h.includes(k))) mapping.cost = headers[i];
    if (!mapping.category && AUTO_MAP_CATEGORY.some((k) => h === k)) mapping.category = headers[i];
    if (!mapping.size && AUTO_MAP_SIZE.some((k) => h === k)) mapping.size = headers[i];
  }

  return mapping;
}

function parseNumeric(val: unknown): number {
  if (typeof val === "number") return val;
  if (typeof val === "string") {
    const cleaned = val.replace(/[$,\s]/g, "");
    const n = parseFloat(cleaned);
    return isNaN(n) ? 0 : n;
  }
  return 0;
}

function applyRounding(value: number, rounding: string): number {
  const r = parseFloat(rounding);
  if (!r || r <= 0) return value;
  return Math.round(value / r) * r;
}

// ── Progress Bar ─────────────────────────────────────────────────

function ProgressBar({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2">
      {STEP_LABELS.map((label, i) => (
        <div key={label} className="flex flex-1 flex-col items-center gap-1">
          <div
            className={cn(
              "h-2 w-full rounded-full transition-colors",
              i < current ? "bg-primary" : i === current ? "bg-primary/60" : "bg-muted",
            )}
          />
          <span
            className={cn(
              "text-xs hidden sm:block",
              i === current ? "text-foreground font-medium" : "text-muted-foreground",
            )}
          >
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────

export default function UrnImportWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  // Step 0 — Upload
  const [fileName, setFileName] = useState("");
  const [sheets, setSheets] = useState<string[]>([]);
  const [selectedSheet, setSelectedSheet] = useState("");
  const [rawData, setRawData] = useState<Record<string, unknown>[]>([]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [headerRow, setHeaderRow] = useState(0);
  const [workbook, setWorkbook] = useState<XLSX.WorkBook | null>(null);
  const [dragging, setDragging] = useState(false);

  // Step 1 — Column mapping
  const [mapping, setMapping] = useState<ColumnMapping>({ sku: null, name: null, cost: null, category: null, size: null });

  // Step 2 — Filter
  const [items, setItems] = useState<UrnImportItem[]>([]);
  const [filterSearch, setFilterSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [page, setPage] = useState(0);

  // Step 3 — Markup
  const [markupMode, setMarkupMode] = useState<"percent" | "individual">("percent");
  const [markupPercent, setMarkupPercent] = useState("50");
  const [rounding, setRounding] = useState("1.00");
  const [individualPrices, setIndividualPrices] = useState<Record<number, string>>({});

  // Step 4 — Import
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ created: number; updated: number; errors: unknown[] } | null>(null);

  // ── Upload handlers ────────────────────────────────────────────

  const processFile = useCallback((file: File) => {
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: "array" });
        setWorkbook(wb);
        setSheets(wb.SheetNames);
        if (wb.SheetNames.length === 1) {
          setSelectedSheet(wb.SheetNames[0]);
          parseSheet(wb, wb.SheetNames[0], 0);
        } else {
          setSelectedSheet(wb.SheetNames[0]);
          parseSheet(wb, wb.SheetNames[0], 0);
        }
      } catch {
        toast.error("Failed to parse Excel file. Please check the file format.");
      }
    };
    reader.readAsArrayBuffer(file);
  }, []);

  const parseSheet = useCallback((wb: XLSX.WorkBook, sheetName: string, hRow: number) => {
    const ws = wb.Sheets[sheetName];
    const json = XLSX.utils.sheet_to_json(ws, { header: 1, defval: "" }) as unknown[][];

    if (json.length <= hRow) {
      setHeaders([]);
      setRawData([]);
      return;
    }

    const hdrs = (json[hRow] as unknown[]).map((h) => String(h ?? "").trim()).filter(Boolean);
    setHeaders(hdrs);

    const rows: Record<string, unknown>[] = [];
    for (let i = hRow + 1; i < json.length; i++) {
      const row = json[i] as unknown[];
      if (!row || row.every((c) => c === "" || c == null)) continue;
      const obj: Record<string, unknown> = {};
      for (let j = 0; j < hdrs.length; j++) {
        obj[hdrs[j]] = row[j] ?? "";
      }
      rows.push(obj);
    }
    setRawData(rows);

    // Auto-map columns
    const autoMapping = autoMapColumns(hdrs);
    setMapping(autoMapping);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }, [processFile]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  }, [processFile]);

  const handleSheetChange = useCallback((sheetName: string) => {
    setSelectedSheet(sheetName);
    if (workbook) parseSheet(workbook, sheetName, headerRow);
  }, [workbook, headerRow, parseSheet]);

  const handleHeaderRowChange = useCallback((row: number) => {
    setHeaderRow(row);
    if (workbook && selectedSheet) parseSheet(workbook, selectedSheet, row);
  }, [workbook, selectedSheet, parseSheet]);

  // ── Step 1 → Step 2 transition ────────────────────────────────

  const buildItems = useCallback(() => {
    const result: UrnImportItem[] = rawData.map((row) => {
      const sku = mapping.sku ? String(row[mapping.sku] ?? "").trim() : "";
      const name = mapping.name ? String(row[mapping.name] ?? "").trim() : "";
      const cost = mapping.cost ? parseNumeric(row[mapping.cost]) : 0;
      const category = mapping.category ? String(row[mapping.category] ?? "").trim() : null;
      const size = mapping.size ? String(row[mapping.size] ?? "").trim() : null;

      const isUrn = URN_KEYWORDS.some(
        (kw) =>
          name.toLowerCase().includes(kw) ||
          (category && category.toLowerCase().includes(kw)),
      );

      return {
        wilbert_sku: sku,
        name,
        wholesale_cost: cost,
        selling_price: null,
        category,
        size,
        selected: isUrn,
      };
    }).filter((item) => item.name);

    setItems(result);
    setPage(0);
  }, [rawData, mapping]);

  // ── Filtering ──────────────────────────────────────────────────

  const categories = useMemo(() => {
    const cats = new Set<string>();
    items.forEach((item) => { if (item.category) cats.add(item.category); });
    return [...cats].sort();
  }, [items]);

  const filteredItems = useMemo(() => {
    let list = items;
    if (filterSearch.trim()) {
      const q = filterSearch.toLowerCase();
      list = list.filter(
        (item) =>
          item.name.toLowerCase().includes(q) ||
          item.wilbert_sku.toLowerCase().includes(q) ||
          (item.category && item.category.toLowerCase().includes(q)),
      );
    }
    if (filterCategory) {
      list = list.filter((item) => item.category === filterCategory);
    }
    return list;
  }, [items, filterSearch, filterCategory]);

  const totalPages = Math.ceil(filteredItems.length / PAGE_SIZE);
  const pageItems = filteredItems.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const selectedCount = items.filter((i) => i.selected).length;

  // ── Markup calculations ────────────────────────────────────────

  const selectedItems = useMemo(() => items.filter((i) => i.selected), [items]);

  const previewItems = useMemo(() => {
    if (markupMode === "individual") return selectedItems;
    const pct = parseFloat(markupPercent) || 0;
    return selectedItems.map((item, idx) => {
      const indPrice = individualPrices[idx];
      if (indPrice !== undefined && indPrice !== "") {
        return { ...item, selling_price: parseFloat(indPrice) || null };
      }
      const sellingRaw = item.wholesale_cost * (1 + pct / 100);
      const selling = applyRounding(sellingRaw, rounding);
      return { ...item, selling_price: selling };
    });
  }, [selectedItems, markupMode, markupPercent, rounding, individualPrices]);

  // ── Import ─────────────────────────────────────────────────────

  const handleImport = async () => {
    setImporting(true);
    try {
      const payload = previewItems.map((item) => ({
        wilbert_sku: item.wilbert_sku,
        name: item.name,
        wholesale_cost: item.wholesale_cost,
        selling_price: item.selling_price,
        category: item.category,
      }));

      const result = await urnService.bulkImportUrns(
        payload,
        markupMode === "percent" ? parseFloat(markupPercent) : undefined,
        rounding,
      );
      setImportResult(result);

      if (result.errors.length === 0) {
        toast.success(`Successfully imported ${result.created + result.updated} urns`);
        navigate("/products/urns");
      } else {
        setStep(5); // Conflict resolution
      }
    } catch {
      toast.error("Import failed. Please try again.");
    } finally {
      setImporting(false);
    }
  };

  // ── Step Renderers ─────────────────────────────────────────────

  function renderUpload() {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Upload Wilbert Price List</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={cn(
              "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors cursor-pointer",
              dragging ? "border-primary bg-primary/5" : "border-muted-foreground/30 hover:border-muted-foreground/50",
            )}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <div className="text-center">
              <p className="text-lg font-medium">
                {fileName || "Drop your Excel file here"}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Accepts .xlsx and .xls files
              </p>
              {!fileName && (
                <p className="mt-2 text-sm text-muted-foreground">
                  or click to browse
                </p>
              )}
            </div>
            <input
              id="file-input"
              type="file"
              accept=".xlsx,.xls"
              onChange={handleFileInput}
              className="hidden"
            />
          </div>

          {/* Sheet selector */}
          {sheets.length > 1 && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">Select Sheet</Label>
              <div className="flex flex-wrap gap-2">
                {sheets.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleSheetChange(s)}
                    className={cn(
                      "rounded-md border px-3 py-1.5 text-sm transition-colors",
                      s === selectedSheet
                        ? "border-primary bg-primary/10 text-primary font-medium"
                        : "border-border hover:bg-muted",
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Header row selector */}
          {rawData.length > 0 && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">Header Row</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="0"
                  max="10"
                  value={headerRow}
                  onChange={(e) => handleHeaderRowChange(parseInt(e.target.value) || 0)}
                  className="w-20"
                />
                <span className="text-xs text-muted-foreground">
                  Row {headerRow + 1} in the spreadsheet (0-indexed)
                </span>
              </div>
            </div>
          )}

          {/* Preview */}
          {headers.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Preview (first 5 rows)</h3>
              <div className="overflow-x-auto rounded border">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted">
                      {headers.map((h) => (
                        <th key={h} className="whitespace-nowrap px-3 py-2 text-left font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rawData.slice(0, 5).map((row, ri) => (
                      <tr key={ri} className="border-t">
                        {headers.map((h) => (
                          <td key={h} className="whitespace-nowrap px-3 py-1.5">
                            {String(row[h] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground">
                {rawData.length} total rows found
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  function renderColumnMapping() {
    const fields: Array<{ key: keyof ColumnMapping; label: string; required: boolean }> = [
      { key: "sku", label: "SKU / Item Number", required: true },
      { key: "name", label: "Product Name", required: true },
      { key: "cost", label: "Wholesale Cost", required: true },
      { key: "category", label: "Category", required: false },
      { key: "size", label: "Size", required: false },
    ];

    return (
      <Card>
        <CardHeader>
          <CardTitle>Map Columns</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Match the columns in your file to the platform fields. We have auto-mapped what we could detect.
          </p>

          <div className="space-y-3">
            {fields.map(({ key, label, required }) => (
              <div
                key={key}
                className={cn(
                  "flex items-center gap-4 rounded-lg border p-3",
                  required && !mapping[key] ? "border-amber-300 bg-amber-50" : "border-border",
                )}
              >
                <div className="w-40 shrink-0">
                  <span className="text-sm font-medium">{label}</span>
                  {required && <span className="ml-1 text-xs text-red-500">*</span>}
                </div>
                <select
                  value={mapping[key] || ""}
                  onChange={(e) =>
                    setMapping((prev) => ({ ...prev, [key]: e.target.value || null }))
                  }
                  className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">-- Select column --</option>
                  {headers.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
                <div className="w-48 shrink-0 text-xs text-muted-foreground truncate">
                  {mapping[key] && rawData[0] ? String(rawData[0][mapping[key]!] ?? "") : ""}
                </div>
              </div>
            ))}
          </div>

          <Button
            variant="outline"
            onClick={() => {
              buildItems();
              setStep(2);
            }}
            disabled={!mapping.sku || !mapping.name || !mapping.cost}
          >
            Preview Mapped Data
          </Button>
        </CardContent>
      </Card>
    );
  }

  function renderFilterUrns() {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Filter to Urns</CardTitle>
            <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              {selectedCount} selected
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Select which rows are urns to import. We have pre-selected rows that appear to be urn products.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <Input
              placeholder="Search..."
              value={filterSearch}
              onChange={(e) => { setFilterSearch(e.target.value); setPage(0); }}
              className="max-w-xs"
            />
            <select
              value={filterCategory}
              onChange={(e) => { setFilterCategory(e.target.value); setPage(0); }}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setItems((prev) =>
                  prev.map((item) => {
                    const isUrn = URN_KEYWORDS.some(
                      (kw) =>
                        item.name.toLowerCase().includes(kw) ||
                        (item.category && item.category.toLowerCase().includes(kw)),
                    );
                    return { ...item, selected: isUrn };
                  }),
                );
              }}
            >
              Select All Urns
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setItems((prev) => prev.map((i) => ({ ...i, selected: false })))}
            >
              Deselect All
            </Button>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded border">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted text-left text-xs">
                  <th className="w-10 px-3 py-2">
                    <input
                      type="checkbox"
                      checked={pageItems.every((i) => i.selected)}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        const pageSkus = new Set(pageItems.map((i) => i.wilbert_sku + i.name));
                        setItems((prev) =>
                          prev.map((i) =>
                            pageSkus.has(i.wilbert_sku + i.name) ? { ...i, selected: checked } : i,
                          ),
                        );
                      }}
                      className="h-3.5 w-3.5 rounded accent-primary"
                    />
                  </th>
                  <th className="px-3 py-2 font-medium">SKU</th>
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Category</th>
                  <th className="px-3 py-2 font-medium text-right">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {pageItems.map((item, idx) => {
                  const globalIdx = items.indexOf(item);
                  return (
                    <tr
                      key={`${item.wilbert_sku}-${idx}`}
                      className={cn(
                        "hover:bg-muted/30",
                        item.selected && "bg-primary/5",
                      )}
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={item.selected}
                          onChange={(e) => {
                            setItems((prev) => {
                              const next = [...prev];
                              next[globalIdx] = { ...next[globalIdx], selected: e.target.checked };
                              return next;
                            });
                          }}
                          className="h-3.5 w-3.5 rounded accent-primary"
                        />
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{item.wilbert_sku}</td>
                      <td className="px-3 py-2">{item.name}</td>
                      <td className="px-3 py-2 text-muted-foreground">{item.category || "-"}</td>
                      <td className="px-3 py-2 text-right">${item.wholesale_cost.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filteredItems.length)} of {filteredItems.length}
              </span>
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  function renderMarkup() {
    const exampleCost = selectedItems[0]?.wholesale_cost ?? 150;
    const examplePct = parseFloat(markupPercent) || 0;
    const exampleSelling = applyRounding(exampleCost * (1 + examplePct / 100), rounding);

    return (
      <Card>
        <CardHeader>
          <CardTitle>Set Markup</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <p className="text-sm text-muted-foreground">
            Choose how to price the {selectedCount} selected urns.
          </p>

          {/* Mode selection */}
          <div className="grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setMarkupMode("percent")}
              className={cn(
                "rounded-lg border-2 p-4 text-left transition-colors",
                markupMode === "percent"
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-muted-foreground/30",
              )}
            >
              <div className="flex items-center gap-2">
                <div className={cn("h-4 w-4 rounded-full border-2", markupMode === "percent" ? "border-primary bg-primary" : "border-muted-foreground/40")} />
                <span className="font-medium">Apply Markup %</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground pl-6">
                Apply a uniform markup percentage to all selected urns
              </p>
            </button>
            <button
              type="button"
              onClick={() => setMarkupMode("individual")}
              className={cn(
                "rounded-lg border-2 p-4 text-left transition-colors",
                markupMode === "individual"
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-muted-foreground/30",
              )}
            >
              <div className="flex items-center gap-2">
                <div className={cn("h-4 w-4 rounded-full border-2", markupMode === "individual" ? "border-primary bg-primary" : "border-muted-foreground/40")} />
                <span className="font-medium">Set Prices Individually</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground pl-6">
                Set selling prices per urn after import
              </p>
            </button>
          </div>

          {markupMode === "percent" && (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="space-y-1">
                  <Label className="text-sm">Markup Percentage</Label>
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      step="1"
                      min="0"
                      max="500"
                      value={markupPercent}
                      onChange={(e) => setMarkupPercent(e.target.value)}
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">%</span>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-sm">Rounding</Label>
                  <select
                    value={rounding}
                    onChange={(e) => setRounding(e.target.value)}
                    className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="0.01">$0.01 (exact)</option>
                    <option value="0.50">$0.50</option>
                    <option value="1.00">$1.00</option>
                    <option value="5.00">$5.00</option>
                  </select>
                </div>
              </div>

              {/* Example calculation */}
              <div className="rounded-lg border border-dashed border-muted-foreground/30 p-4">
                <p className="text-sm text-muted-foreground">
                  Example: ${exampleCost.toFixed(2)} wholesale + {examplePct}% markup = <strong className="text-foreground">${exampleSelling.toFixed(2)}</strong> selling price
                </p>
              </div>

              {/* Preview table */}
              <div className="overflow-x-auto rounded border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-muted text-left text-xs">
                      <th className="px-3 py-2 font-medium">Name</th>
                      <th className="px-3 py-2 font-medium text-right">Wholesale</th>
                      <th className="px-3 py-2 font-medium text-right">Selling Price</th>
                      <th className="px-3 py-2 font-medium text-right">Markup</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {previewItems.slice(0, 20).map((item, idx) => (
                      <tr key={`${item.wilbert_sku}-${idx}`}>
                        <td className="px-3 py-2">{item.name}</td>
                        <td className="px-3 py-2 text-right text-muted-foreground">${item.wholesale_cost.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            value={individualPrices[idx] ?? item.selling_price?.toFixed(2) ?? ""}
                            onChange={(e) => {
                              setIndividualPrices((prev) => ({ ...prev, [idx]: e.target.value }));
                            }}
                            className="ml-auto w-28 text-right"
                          />
                        </td>
                        <td className="px-3 py-2 text-right text-muted-foreground">
                          {item.selling_price && item.wholesale_cost > 0
                            ? `${(((item.selling_price - item.wholesale_cost) / item.wholesale_cost) * 100).toFixed(1)}%`
                            : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {previewItems.length > 20 && (
                <p className="text-xs text-muted-foreground">
                  Showing first 20 of {previewItems.length} items
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  function renderReview() {
    const newCount = previewItems.length;
    return (
      <Card>
        <CardHeader>
          <CardTitle>Review & Import</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold">{newCount}</p>
              <p className="text-sm text-muted-foreground">Urns to Import</p>
            </div>
            <div className="rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold">
                {markupMode === "percent" ? `${markupPercent}%` : "Manual"}
              </p>
              <p className="text-sm text-muted-foreground">Markup Applied</p>
            </div>
            <div className="rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold">${rounding}</p>
              <p className="text-sm text-muted-foreground">Rounding</p>
            </div>
          </div>

          <div className="overflow-x-auto rounded border">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted text-left text-xs">
                  <th className="px-3 py-2 font-medium">SKU</th>
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Category</th>
                  <th className="px-3 py-2 font-medium text-right">Wholesale</th>
                  <th className="px-3 py-2 font-medium text-right">Selling</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {previewItems.slice(0, 30).map((item, idx) => (
                  <tr key={`${item.wilbert_sku}-${idx}`}>
                    <td className="px-3 py-1.5 font-mono text-xs">{item.wilbert_sku}</td>
                    <td className="px-3 py-1.5">{item.name}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{item.category || "-"}</td>
                    <td className="px-3 py-1.5 text-right">${item.wholesale_cost.toFixed(2)}</td>
                    <td className="px-3 py-1.5 text-right font-semibold">
                      {item.selling_price != null ? `$${item.selling_price.toFixed(2)}` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {previewItems.length > 30 && (
            <p className="text-xs text-muted-foreground">
              Showing first 30 of {previewItems.length} items
            </p>
          )}

          <div className="flex justify-center">
            <Button
              size="lg"
              className="bg-green-600 hover:bg-green-700 text-white px-8"
              onClick={handleImport}
              disabled={importing || selectedCount === 0}
            >
              {importing ? "Importing..." : `Import ${selectedCount} Urns`}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  function renderConflicts() {
    if (!importResult) return null;
    return (
      <Card>
        <CardHeader>
          <CardTitle>Import Results</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-center">
              <p className="text-2xl font-bold text-green-700">{importResult.created}</p>
              <p className="text-sm text-green-600">Created</p>
            </div>
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-center">
              <p className="text-2xl font-bold text-blue-700">{importResult.updated}</p>
              <p className="text-sm text-blue-600">Updated</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
              <p className="text-2xl font-bold text-red-700">{importResult.errors.length}</p>
              <p className="text-sm text-red-600">Errors</p>
            </div>
          </div>

          {importResult.errors.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Problem Rows</h3>
              <div className="space-y-2">
                {importResult.errors.map((err, idx) => (
                  <div key={idx} className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                    {String(err)}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-center gap-3">
            <Button variant="outline" onClick={() => navigate("/products/urns")}>
              Go to Urn Catalog
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // ── Render ─────────────────────────────────────────────────────

  const stepRenderers = [renderUpload, renderColumnMapping, renderFilterUrns, renderMarkup, renderReview, renderConflicts];

  const canAdvance = () => {
    switch (step) {
      case 0: return headers.length > 0 && rawData.length > 0;
      case 1: return !!(mapping.sku && mapping.name && mapping.cost);
      case 2: return selectedCount > 0;
      case 3: return true;
      case 4: return false; // import button handles this
      default: return false;
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Import from Wilbert Price List</h1>
        <p className="text-sm text-muted-foreground">
          Upload your Wilbert price list Excel file to import your urn catalog.
        </p>
      </div>

      {step < 5 && <ProgressBar current={step} />}

      {stepRenderers[step]()}

      {/* Navigation */}
      {step < 5 && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={() => {
              if (step === 0) {
                navigate("/products/urns");
              } else {
                setStep((s) => s - 1);
              }
            }}
          >
            {step === 0 ? "Cancel" : "Back"}
          </Button>
          {step < 4 && (
            <Button
              onClick={() => {
                if (step === 1) buildItems();
                setStep((s) => s + 1);
              }}
              disabled={!canAdvance()}
            >
              Continue
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
