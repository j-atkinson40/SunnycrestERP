// knowledge-base.tsx — Knowledge Base management page.
// Category grid, document management, pricing entries, upload flow, and drag-and-drop.

import { useCallback, useEffect, useRef, useState } from "react";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { KBCoachingBanner } from "@/components/kb-coaching-banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  BookOpen,
  Upload,
  FileText,
  DollarSign,
  Package,
  Palette,
  MapPin,
  Truck,
  Search,
  ChevronLeft,
  Trash2,
  RotateCcw,
  Loader2,
  FolderUp,
  X,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface KBCategory {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  display_order: number;
  is_system: boolean;
  icon: string | null;
  document_count: number;
}

interface KBDocument {
  id: string;
  category_id: string;
  title: string;
  description: string | null;
  file_name: string | null;
  file_type: string | null;
  file_size_bytes: number | null;
  parsing_status: string;
  parsing_error: string | null;
  chunk_count: number;
  last_parsed_at: string | null;
  created_at: string | null;
}

interface KBPricingEntry {
  id: string;
  product_name: string;
  product_code: string | null;
  description: string | null;
  standard_price: string | null;
  contractor_price: string | null;
  homeowner_price: string | null;
  unit: string;
  notes: string | null;
  document_id: string | null;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Icon resolver
// ---------------------------------------------------------------------------

const ICON_MAP: Record<string, typeof BookOpen> = {
  DollarSign,
  Package,
  Palette,
  FileText,
  MapPin,
  Truck,
  BookOpen,
};

function CategoryIcon({ icon, className }: { icon: string | null; className?: string }) {
  const Icon = (icon && ICON_MAP[icon]) || BookOpen;
  return <Icon className={className} />;
}

// ---------------------------------------------------------------------------
// Drag-and-drop helpers
// ---------------------------------------------------------------------------

const ALLOWED_EXTENSIONS = new Set(["pdf", "docx", "csv", "txt"]);
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

function getFileExtension(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() || "";
}

function validateDroppedFile(file: File): string | null {
  const ext = getFileExtension(file.name);
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return `"${file.name}" is not a supported file type. Use PDF, DOCX, CSV, or TXT.`;
  }
  if (file.size > MAX_FILE_SIZE) {
    return `"${file.name}" exceeds the 10 MB size limit.`;
  }
  return null;
}

/** Detect the most likely KB category based on filename patterns. */
function detectCategory(
  filename: string,
  categories: KBCategory[],
): { category: KBCategory; confidence: "high" | "medium" | "low" } | null {
  const lower = filename.toLowerCase();

  // Price patterns → Pricing category
  if (/price|pricing|rate\s?sheet|rate\s?card|price\s?list|cost/i.test(lower)) {
    const cat = categories.find((c) => c.slug === "pricing" || c.name.toLowerCase().includes("pricing"));
    if (cat) return { category: cat, confidence: "high" };
  }

  // Product spec patterns → Product Specs
  if (/spec|dimension|weight|material|product\s?info|catalog|datasheet/i.test(lower)) {
    const cat = categories.find((c) => c.slug === "product_specs" || c.name.toLowerCase().includes("spec"));
    if (cat) return { category: cat, confidence: "high" };
  }

  // Policy patterns → Company Policies
  if (/policy|policies|procedure|handbook|manual|guidelines|terms/i.test(lower)) {
    const cat = categories.find((c) => c.slug === "company_policies" || c.name.toLowerCase().includes("polic"));
    if (cat) return { category: cat, confidence: "high" };
  }

  // Cemetery patterns → Cemetery Policies
  if (/cemetery|burial|interment|plot|section|grave/i.test(lower)) {
    const cat = categories.find((c) => c.slug === "cemetery_policies" || c.name.toLowerCase().includes("cemetery"));
    if (cat) return { category: cat, confidence: "high" };
  }

  // Personalization patterns
  if (/personali[sz]|engrav|custom|emblem|panel|medallion/i.test(lower)) {
    const cat = categories.find((c) => c.slug === "personalization_options" || c.name.toLowerCase().includes("personal"));
    if (cat) return { category: cat, confidence: "medium" };
  }

  return null;
}

/** Drag overlay component */
function DropOverlay({
  active,
  categoryName,
}: {
  active: boolean;
  categoryName?: string;
}) {
  if (!active) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-indigo-600/10 backdrop-blur-sm pointer-events-none">
      <div className="rounded-2xl border-2 border-dashed border-indigo-400 bg-white/90 p-10 text-center shadow-xl">
        <FolderUp className="h-12 w-12 text-indigo-500 mx-auto mb-3" />
        <p className="text-lg font-semibold text-gray-900">
          {categoryName ? `Drop to upload to ${categoryName}` : "Drop file to upload"}
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          PDF, DOCX, CSV, or TXT — up to 10 MB
        </p>
      </div>
    </div>
  );
}

/** Category picker modal for dropped files on the main page */
function CategoryPickerModal({
  file,
  categories,
  detectedCategory,
  onSelect,
  onCancel,
}: {
  file: File;
  categories: KBCategory[];
  detectedCategory: { category: KBCategory; confidence: string } | null;
  onSelect: (categoryId: string) => void;
  onCancel: () => void;
}) {
  const uploadCategories = categories.filter((c) => c.slug !== "pricing");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="rounded-xl bg-white p-6 shadow-xl max-w-md w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Choose a Category</h3>
          <button
            onClick={onCancel}
            className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="text-sm text-muted-foreground mb-1">
          Uploading: <span className="font-medium text-gray-900">{file.name}</span>
        </p>
        {detectedCategory && (
          <p className="text-sm text-indigo-600 mb-3">
            Suggested: <span className="font-semibold">{detectedCategory.category.name}</span>
          </p>
        )}
        <div className="space-y-1.5 max-h-64 overflow-y-auto mt-3">
          {/* Show detected category first if available */}
          {detectedCategory && (
            <button
              onClick={() => onSelect(detectedCategory.category.id)}
              className="w-full text-left rounded-lg border-2 border-indigo-300 bg-indigo-50 p-3 hover:bg-indigo-100 transition-colors flex items-center gap-3"
            >
              <CategoryIcon icon={detectedCategory.category.icon} className="h-5 w-5 text-indigo-600" />
              <div>
                <p className="font-medium text-sm">{detectedCategory.category.name}</p>
                <p className="text-xs text-indigo-600">Recommended</p>
              </div>
            </button>
          )}
          {uploadCategories
            .filter((c) => !detectedCategory || c.id !== detectedCategory.category.id)
            .map((cat) => (
              <button
                key={cat.id}
                onClick={() => onSelect(cat.id)}
                className="w-full text-left rounded-lg border p-3 hover:bg-gray-50 transition-colors flex items-center gap-3"
              >
                <CategoryIcon icon={cat.icon} className="h-5 w-5 text-indigo-600" />
                <div>
                  <p className="font-medium text-sm">{cat.name}</p>
                  <p className="text-xs text-muted-foreground">{cat.document_count} docs</p>
                </div>
              </button>
            ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type ViewMode = "categories" | "documents" | "pricing";

export default function KnowledgeBasePage() {
  const [categories, setCategories] = useState<KBCategory[]>([]);
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [pricingEntries, setPricingEntries] = useState<KBPricingEntry[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<KBCategory | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("categories");
  const [loading, setLoading] = useState(true);
  const [pricingSearch, setPricingSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Drag-and-drop state
  const [dragActive, setDragActive] = useState(false);
  const [pendingDrop, setPendingDrop] = useState<{
    file: File;
    detected: { category: KBCategory; confidence: string } | null;
  } | null>(null);
  const dragCounter = useRef(0);

  // Drag-and-drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer?.types.includes("Files")) {
      setDragActive(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setDragActive(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  // Fetch categories (backend auto-seeds on first access)
  const loadCategories = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/knowledge-base/categories");
      setCategories(res.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string }; status?: number } })?.response?.data?.detail
        || (err as { response?: { status?: number } })?.response?.status
        || (err as Error)?.message
        || "Unknown error";
      toast.error(`Failed to load knowledge base: ${msg}`);
      console.error("KB load error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  // Load documents for a category
  const loadDocuments = useCallback(async (categoryId: string) => {
    try {
      const res = await apiClient.get("/knowledge-base/documents", {
        params: { category_id: categoryId },
      });
      setDocuments(res.data);
    } catch {
      toast.error("Failed to load documents");
    }
  }, []);

  // Load pricing entries
  const loadPricing = useCallback(async (search?: string) => {
    try {
      const res = await apiClient.get("/knowledge-base/pricing", {
        params: search ? { search } : {},
      });
      setPricingEntries(res.data);
    } catch {
      toast.error("Failed to load pricing");
    }
  }, []);

  // Handlers
  const handleCategoryClick = (cat: KBCategory) => {
    if (cat.slug === "pricing") {
      setViewMode("pricing");
      loadPricing();
    } else {
      setSelectedCategory(cat);
      setViewMode("documents");
      loadDocuments(cat.id);
    }
  };

  const handleBack = () => {
    setViewMode("categories");
    setSelectedCategory(null);
    loadCategories();
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedCategory) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      await apiClient.post(
        `/knowledge-base/documents/upload?category_id=${selectedCategory.id}&title=${encodeURIComponent(file.name)}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      toast.success("Document uploaded and parsed");
      loadDocuments(selectedCategory.id);
    } catch {
      toast.error("Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleReparse = async (docId: string) => {
    try {
      await apiClient.post(`/knowledge-base/documents/${docId}/reparse`);
      toast.success("Document re-parsed");
      if (selectedCategory) loadDocuments(selectedCategory.id);
    } catch {
      toast.error("Re-parse failed");
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      await apiClient.delete(`/knowledge-base/documents/${docId}`);
      toast.success("Document deleted");
      if (selectedCategory) loadDocuments(selectedCategory.id);
    } catch {
      toast.error("Delete failed");
    }
  };

  const handleCoachingNavigate = (section: string) => {
    if (section === "pricing") {
      setViewMode("pricing");
      loadPricing();
    }
  };

  // Drag-and-drop upload
  const uploadFileToCategory = useCallback(
    async (file: File, categoryId: string) => {
      setUploading(true);
      const formData = new FormData();
      formData.append("file", file);

      try {
        await apiClient.post(
          `/knowledge-base/documents/upload?category_id=${categoryId}&title=${encodeURIComponent(file.name)}`,
          formData,
          { headers: { "Content-Type": "multipart/form-data" } },
        );
        toast.success(`"${file.name}" uploaded and parsed`);
        if (selectedCategory) {
          loadDocuments(selectedCategory.id);
        }
        loadCategories();
      } catch {
        toast.error(`Failed to upload "${file.name}"`);
      } finally {
        setUploading(false);
      }
    },
    [selectedCategory, loadDocuments, loadCategories],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setDragActive(false);

      const files = Array.from(e.dataTransfer?.files || []);
      if (files.length === 0) return;

      const file = files[0];
      const error = validateDroppedFile(file);
      if (error) {
        toast.error(error);
        return;
      }

      // In document view → upload directly to selected category
      if (viewMode === "documents" && selectedCategory) {
        uploadFileToCategory(file, selectedCategory.id);
        return;
      }

      // On main categories page → detect category and show picker
      const detected = detectCategory(file.name, categories);
      setPendingDrop({ file, detected });
    },
    [viewMode, selectedCategory, categories, uploadFileToCategory],
  );

  const handleCategoryPick = useCallback(
    (categoryId: string) => {
      if (!pendingDrop) return;
      uploadFileToCategory(pendingDrop.file, categoryId);
      setPendingDrop(null);
    },
    [pendingDrop, uploadFileToCategory],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div
      className="space-y-6 p-6 relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drag overlay */}
      <DropOverlay
        active={dragActive}
        categoryName={viewMode === "documents" && selectedCategory ? selectedCategory.name : undefined}
      />

      {/* Category picker modal for dropped files */}
      {pendingDrop && (
        <CategoryPickerModal
          file={pendingDrop.file}
          categories={categories}
          detectedCategory={pendingDrop.detected}
          onSelect={handleCategoryPick}
          onCancel={() => setPendingDrop(null)}
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Base</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Upload documents to power Call Intelligence with product pricing, specs,
            and company policies. Drag and drop files anywhere on this page.
          </p>
        </div>
      </div>

      {viewMode === "categories" && (
        <KBCoachingBanner onNavigate={handleCoachingNavigate} />
      )}

      {/* Category Grid */}
      {viewMode === "categories" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => handleCategoryClick(cat)}
              className="text-left rounded-xl border bg-white p-5 hover:border-indigo-300 hover:shadow-md transition-all group"
            >
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-indigo-50 p-2.5 group-hover:bg-indigo-100 transition-colors">
                  <CategoryIcon icon={cat.icon} className="h-5 w-5 text-indigo-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-sm">{cat.name}</h3>
                  {cat.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {cat.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="secondary" className="text-xs">
                      {cat.document_count} {cat.document_count === 1 ? "doc" : "docs"}
                    </Badge>
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Document List */}
      {viewMode === "documents" && selectedCategory && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={handleBack}>
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
            <div className="flex items-center gap-2">
              <CategoryIcon icon={selectedCategory.icon} className="h-5 w-5 text-indigo-600" />
              <h2 className="font-semibold text-lg">{selectedCategory.name}</h2>
            </div>
            <div className="ml-auto flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.csv,.txt"
                onChange={handleUpload}
              />
              <Button
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4 mr-1.5" />
                )}
                Upload Document
              </Button>
            </div>
          </div>

          {documents.length === 0 ? (
            <div className="rounded-xl border bg-gray-50 p-10 text-center">
              <FileText className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">
                No documents in this category yet.
              </p>
              <Button
                size="sm"
                className="mt-3"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4 mr-1.5" />
                Upload First Document
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="rounded-lg border bg-white p-4 flex items-center gap-4"
                >
                  <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{doc.title}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      {doc.file_name && <span>{doc.file_name}</span>}
                      {doc.file_size_bytes && (
                        <span>{Math.round(doc.file_size_bytes / 1024)} KB</span>
                      )}
                      <span>{doc.chunk_count} chunks</span>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px]",
                          doc.parsing_status === "complete"
                            ? "border-green-300 text-green-700"
                            : doc.parsing_status === "failed"
                              ? "border-red-300 text-red-700"
                              : "border-amber-300 text-amber-700",
                        )}
                      >
                        {doc.parsing_status}
                      </Badge>
                    </div>
                    {doc.parsing_error && (
                      <p className="text-xs text-red-600 mt-1 truncate">
                        {doc.parsing_error}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleReparse(doc.id)}
                      title="Re-parse"
                    >
                      <RotateCcw className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteDoc(doc.id)}
                      title="Delete"
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pricing View */}
      {viewMode === "pricing" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={handleBack}>
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-indigo-600" />
              <h2 className="font-semibold text-lg">Product Pricing</h2>
            </div>
          </div>

          <div className="flex gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search products..."
                value={pricingSearch}
                onChange={(e) => {
                  setPricingSearch(e.target.value);
                  loadPricing(e.target.value || undefined);
                }}
                className="pl-9"
              />
            </div>
          </div>

          {pricingEntries.length === 0 ? (
            <div className="rounded-xl border bg-gray-50 p-10 text-center">
              <DollarSign className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">
                {pricingSearch
                  ? "No pricing entries match your search."
                  : "No pricing entries yet. Upload a pricing document to auto-extract entries."}
              </p>
            </div>
          ) : (
            <div className="rounded-xl border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left px-4 py-2.5 font-medium">Product</th>
                    <th className="text-left px-4 py-2.5 font-medium">Code</th>
                    <th className="text-right px-4 py-2.5 font-medium">Standard</th>
                    <th className="text-right px-4 py-2.5 font-medium">Contractor</th>
                    <th className="text-right px-4 py-2.5 font-medium">Homeowner</th>
                    <th className="text-left px-4 py-2.5 font-medium">Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {pricingEntries.map((entry) => (
                    <tr key={entry.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="px-4 py-2.5">
                        <p className="font-medium">{entry.product_name}</p>
                        {entry.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-xs">
                            {entry.description}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {entry.product_code || "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono">
                        {entry.standard_price ? `$${entry.standard_price}` : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono">
                        {entry.contractor_price ? `$${entry.contractor_price}` : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono">
                        {entry.homeowner_price ? `$${entry.homeowner_price}` : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{entry.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
