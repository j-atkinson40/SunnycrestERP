// price-management-templates.tsx — PDF Template Builder for price lists.

import { useCallback, useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  ChevronLeft,
  FileText,
  Loader2,
  Plus,
  Save,
  Star,
  Trash2,
} from "lucide-react";
import { Link } from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PDFTemplate {
  id: string;
  name: string;
  is_default: boolean;
  layout_type: string;
  columns: number;
  show_product_codes: boolean;
  show_descriptions: boolean;
  show_notes: boolean;
  show_category_headers: boolean;
  logo_position: string;
  primary_color: string;
  font_family: string;
  header_text: string | null;
  footer_text: string | null;
  show_effective_date: boolean;
  show_page_numbers: boolean;
  show_contractor_price: boolean;
  show_homeowner_price: boolean;
}

const EMPTY_TEMPLATE: Omit<PDFTemplate, "id"> & { id: string | null } = {
  id: null,
  name: "New Template",
  is_default: false,
  layout_type: "grouped",
  columns: 1,
  show_product_codes: true,
  show_descriptions: true,
  show_notes: true,
  show_category_headers: true,
  logo_position: "top-left",
  primary_color: "#000000",
  font_family: "helvetica",
  header_text: null,
  footer_text: null,
  show_effective_date: true,
  show_page_numbers: true,
  show_contractor_price: false,
  show_homeowner_price: false,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PriceManagementTemplatesPage() {
  const [templates, setTemplates] = useState<PDFTemplate[]>([]);
  const [selected, setSelected] = useState<(PDFTemplate & { id: string | null }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await apiClient.get("/price-management/templates");
      setTemplates(res.data);
    } catch {
      toast.error("Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const payload = { ...selected };
      if (!payload.id) delete (payload as Record<string, unknown>).id;
      const res = await apiClient.post("/price-management/templates", payload);
      toast.success("Template saved");
      setSelected(res.data);
      load();
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/price-management/templates/${id}`);
      toast.success("Template deleted");
      if (selected?.id === id) setSelected(null);
      load();
    } catch {
      toast.error("Delete failed");
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Link to="/price-management">
          <Button variant="ghost" size="sm">
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">PDF Templates</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Configure how your price list PDFs look.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Template list */}
        <div className="space-y-3">
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={() => setSelected({ ...EMPTY_TEMPLATE })}
          >
            <Plus className="h-4 w-4 mr-1.5" />
            New Template
          </Button>

          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelected(t)}
              className={cn(
                "w-full text-left rounded-lg border p-3 transition-all",
                selected?.id === t.id ? "border-indigo-400 bg-indigo-50" : "bg-white hover:border-gray-300",
              )}
            >
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="font-medium text-sm truncate">{t.name}</span>
                {t.is_default && <Star className="h-3.5 w-3.5 text-amber-500 shrink-0" />}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {t.layout_type} · {t.font_family} · {t.primary_color}
              </p>
            </button>
          ))}
        </div>

        {/* Editor */}
        {selected ? (
          <div className="lg:col-span-2 rounded-xl border bg-white p-5 space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">
                {selected.id ? "Edit Template" : "New Template"}
              </h3>
              <div className="flex gap-2">
                {selected.id && (
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(selected.id!)} className="text-red-500">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
                <Button size="sm" onClick={handleSave} disabled={saving}>
                  {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
                  Save
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Name</label>
                <Input value={selected.name} onChange={(e) => setSelected({ ...selected, name: e.target.value })} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Font Family</label>
                <select
                  value={selected.font_family}
                  onChange={(e) => setSelected({ ...selected, font_family: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                >
                  <option value="helvetica">Helvetica</option>
                  <option value="arial">Arial</option>
                  <option value="georgia">Georgia</option>
                  <option value="times">Times New Roman</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Primary Color</label>
                <div className="flex gap-2 items-center">
                  <input
                    type="color"
                    value={selected.primary_color}
                    onChange={(e) => setSelected({ ...selected, primary_color: e.target.value })}
                    className="w-10 h-8 rounded border cursor-pointer"
                  />
                  <Input value={selected.primary_color} onChange={(e) => setSelected({ ...selected, primary_color: e.target.value })} className="flex-1" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Layout</label>
                <select
                  value={selected.layout_type}
                  onChange={(e) => setSelected({ ...selected, layout_type: e.target.value })}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                >
                  <option value="grouped">Grouped by Category</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Header Text</label>
              <Input
                value={selected.header_text || ""}
                onChange={(e) => setSelected({ ...selected, header_text: e.target.value || null })}
                placeholder="Optional text above the price table..."
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Footer Text</label>
              <Input
                value={selected.footer_text || ""}
                onChange={(e) => setSelected({ ...selected, footer_text: e.target.value || null })}
                placeholder="Optional text below the price table..."
              />
            </div>

            {/* Toggles */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { key: "is_default", label: "Default template" },
                { key: "show_product_codes", label: "Show product codes" },
                { key: "show_descriptions", label: "Show descriptions" },
                { key: "show_notes", label: "Show notes" },
                { key: "show_category_headers", label: "Show category headers" },
                { key: "show_effective_date", label: "Show effective date" },
                { key: "show_page_numbers", label: "Show page numbers" },
                { key: "show_contractor_price", label: "Show contractor price" },
                { key: "show_homeowner_price", label: "Show homeowner price" },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean((selected as Record<string, unknown>)[key])}
                    onChange={(e) => setSelected({ ...selected, [key]: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        ) : (
          <div className="lg:col-span-2 rounded-xl border bg-gray-50 p-10 text-center">
            <FileText className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-muted-foreground">Select a template to edit or create a new one.</p>
          </div>
        )}
      </div>
    </div>
  );
}
