// knowledge-base.tsx — Knowledge Base management page.
// Category grid, document management, pricing entries, and upload flow.

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

  // Fetch categories
  const loadCategories = useCallback(async () => {
    try {
      const res = await apiClient.get("/api/v1/knowledge-base/categories");
      setCategories(res.data);
    } catch {
      toast.error("Failed to load categories");
    }
  }, []);

  // Seed categories if none exist
  const seedIfNeeded = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/api/v1/knowledge-base/categories");
      if (res.data.length === 0) {
        await apiClient.post("/api/v1/knowledge-base/seed", { vertical: "manufacturing" });
        const res2 = await apiClient.get("/api/v1/knowledge-base/categories");
        setCategories(res2.data);
      } else {
        setCategories(res.data);
      }
    } catch {
      toast.error("Failed to load knowledge base");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    seedIfNeeded();
  }, [seedIfNeeded]);

  // Load documents for a category
  const loadDocuments = useCallback(async (categoryId: string) => {
    try {
      const res = await apiClient.get("/api/v1/knowledge-base/documents", {
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
      const res = await apiClient.get("/api/v1/knowledge-base/pricing", {
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
        `/api/v1/knowledge-base/documents/upload?category_id=${selectedCategory.id}&title=${encodeURIComponent(file.name)}`,
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
      await apiClient.post(`/api/v1/knowledge-base/documents/${docId}/reparse`);
      toast.success("Document re-parsed");
      if (selectedCategory) loadDocuments(selectedCategory.id);
    } catch {
      toast.error("Re-parse failed");
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      await apiClient.delete(`/api/v1/knowledge-base/documents/${docId}`);
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Base</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Upload documents to power Call Intelligence with product pricing, specs,
            and company policies.
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
