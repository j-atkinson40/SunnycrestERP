import { useState, useEffect, useCallback, Fragment } from "react"
import {
  Plus,
  Search,
  Package,
  Loader2,
  Upload,
  DollarSign,
  Percent,
  FileSpreadsheet,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  RefreshCw,
  Trash2,
  FileUp,
} from "lucide-react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Label } from "@/components/ui/label"

interface UrnProduct {
  id: string
  name: string
  sku: string | null
  source_type: string
  material: string | null
  style: string | null
  product_type: string | null
  available_colors: string[] | null
  color_name: string | null
  height: string | null
  width_or_diameter: string | null
  depth: string | null
  cubic_inches: number | null
  companion_of_sku: string | null
  engravable: boolean
  is_keepsake_set: boolean
  photo_etch_capable: boolean
  base_cost: number | null
  retail_price: number | null
  margin_percent: number | null
  image_url: string | null
  wilbert_description: string | null
  wilbert_long_description: string | null
  catalog_page: number | null
  discontinued: boolean
  is_active: boolean
  inventory: { qty_on_hand: number; qty_reserved: number } | null
}

function marginPercent(cost: number | null, price: number | null): string {
  if (!cost || !price || cost <= 0) return "—"
  return `${(((price - cost) / cost) * 100).toFixed(0)}%`
}

function formatPrice(val: number | null): string {
  if (val == null) return "—"
  return `$${Number(val).toFixed(2)}`
}

export default function UrnCatalog() {
  const [products, setProducts] = useState<UrnProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [sourceFilter, setSourceFilter] = useState<string>("")
  const [materialFilter, setMaterialFilter] = useState<string>("")
  const [typeFilter, setTypeFilter] = useState<string>("")
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  // Dialogs
  const [showAdd, setShowAdd] = useState(false)
  const [showSync, setShowSync] = useState(false)
  const [showBulkMarkup, setShowBulkMarkup] = useState(false)
  const [showCsvImport, setShowCsvImport] = useState(false)
  const [showProductImport, setShowProductImport] = useState(false)
  const [showBulkDelete, setShowBulkDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState("")

  // Inline price editing
  const [editingPrice, setEditingPrice] = useState<{
    id: string
    field: "base_cost" | "retail_price"
    value: string
  } | null>(null)

  // Sync state
  const [syncing, setSyncing] = useState(false)
  const [syncFile, setSyncFile] = useState<File | null>(null)

  // Bulk markup state
  const [markupForm, setMarkupForm] = useState({
    material: "",
    product_type: "",
    markup_percent: "40",
    rounding: "1.00",
    only_unpriced: false,
  })

  const [form, setForm] = useState({
    name: "",
    sku: "",
    source_type: "drop_ship",
    material: "",
    style: "",
    engravable: true,
    base_cost: "",
    retail_price: "",
  })

  const load = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (sourceFilter) params.set("source_type", sourceFilter)
    if (materialFilter) params.set("material", materialFilter)
    params.set("limit", "200")
    apiClient
      .get(`/urns/products?${params}`)
      .then((r) => setProducts(r.data))
      .catch(() => toast.error("Failed to load products"))
      .finally(() => setLoading(false))
  }, [sourceFilter, materialFilter])

  useEffect(() => {
    load()
  }, [load])

  // Derive unique materials and types from data
  const materials = [...new Set(products.map((p) => p.material).filter(Boolean))] as string[]
  const productTypes = [...new Set(products.map((p) => p.product_type).filter(Boolean))] as string[]

  // Count unpriced products
  const unpricedCount = products.filter(
    (p) => p.base_cost == null && p.retail_price == null && !p.discontinued
  ).length

  const filtered = products.filter((p) => {
    if (typeFilter && p.product_type !== typeFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return (
        p.name.toLowerCase().includes(q) ||
        (p.sku && p.sku.toLowerCase().includes(q)) ||
        (p.material && p.material.toLowerCase().includes(q))
      )
    }
    return true
  })

  // --- Handlers ---

  const handleCreate = () => {
    apiClient
      .post("/urns/products", {
        ...form,
        base_cost: form.base_cost ? parseFloat(form.base_cost) : null,
        retail_price: form.retail_price ? parseFloat(form.retail_price) : null,
      })
      .then(() => {
        toast.success("Product created")
        setShowAdd(false)
        setForm({
          name: "",
          sku: "",
          source_type: "drop_ship",
          material: "",
          style: "",
          engravable: true,
          base_cost: "",
          retail_price: "",
        })
        load()
      })
      .catch(() => toast.error("Failed to create product"))
  }

  const handlePriceUpdate = (productId: string, field: string, value: string) => {
    const numVal = value ? parseFloat(value) : null
    apiClient
      .patch(`/urns/products/${productId}/pricing`, { [field]: numVal })
      .then(() => {
        toast.success("Price updated")
        setEditingPrice(null)
        load()
      })
      .catch(() => toast.error("Failed to update price"))
  }

  const handlePdfSync = () => {
    if (!syncFile) return
    setSyncing(true)
    const formData = new FormData()
    formData.append("file", syncFile)
    apiClient
      .post("/urns/catalog/ingest-pdf?enrich_from_website=true", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 300000,
      })
      .then((r) => {
        const d = r.data
        toast.success(
          `Sync complete: ${d.products_added} added, ${d.products_updated} updated, ${d.products_skipped} skipped`
        )
        setShowSync(false)
        setSyncFile(null)
        load()
      })
      .catch((e) => toast.error(e.response?.data?.detail || "Sync failed"))
      .finally(() => setSyncing(false))
  }

  const handleFetchPdf = () => {
    setSyncing(true)
    apiClient
      .post("/urns/catalog/fetch-pdf?force=true", null, { timeout: 300000 })
      .then((r) => {
        const d = r.data
        if (!d.downloaded) {
          toast.error("Could not download catalog PDF from Wilbert")
        } else {
          toast.success(
            `Catalog synced: ${d.products_added} added, ${d.products_updated} updated, ${d.products_skipped} skipped`
          )
          setShowSync(false)
          load()
        }
      })
      .catch((e) => toast.error(e.response?.data?.detail || "PDF fetch failed"))
      .finally(() => setSyncing(false))
  }

  const handleBulkMarkup = () => {
    apiClient
      .post("/urns/pricing/bulk-markup", {
        material: markupForm.material || null,
        product_type: markupForm.product_type || null,
        markup_percent: parseFloat(markupForm.markup_percent),
        rounding: markupForm.rounding,
        only_unpriced: markupForm.only_unpriced,
      })
      .then((r) => {
        toast.success(`Updated ${r.data.updated_count} products (${r.data.skipped_count} skipped)`)
        setShowBulkMarkup(false)
        load()
      })
      .catch(() => toast.error("Bulk markup failed"))
  }

  const handleCsvImport = (file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    apiClient
      .post("/urns/pricing/import-csv", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => {
        const d = r.data
        let msg = `Matched ${d.matched}, updated ${d.updated}`
        if (d.not_found.length > 0) {
          msg += `. ${d.not_found.length} SKUs not found.`
        }
        toast.success(msg)
        setShowCsvImport(false)
        load()
      })
      .catch(() => toast.error("CSV import failed"))
  }

  const handleProductCsvImport = (file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    apiClient
      .post("/urns/catalog/import-csv", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => {
        const d = r.data
        let msg = `${d.products_created} created, ${d.products_updated} updated`
        if (d.rows_skipped > 0) msg += `, ${d.rows_skipped} skipped`
        if (d.errors?.length > 0) msg += `. ${d.errors.length} error(s).`
        toast.success(msg)
        setShowProductImport(false)
        load()
      })
      .catch((e) => toast.error(e.response?.data?.detail || "Product import failed"))
  }

  const handleBulkDelete = () => {
    setDeleting(true)
    apiClient
      .post("/urns/products/bulk-delete", { delete_all: true })
      .then((r) => {
        toast.success(`Deleted ${r.data.deleted_count} products`)
        setShowBulkDelete(false)
        setDeleteConfirmText("")
        load()
      })
      .catch((e) => toast.error(e.response?.data?.detail || "Delete failed"))
      .finally(() => setDeleting(false))
  }

  const handleDeleteSingle = (productId: string, productName: string) => {
    if (!window.confirm(`Delete "${productName}"? This cannot be undone.`)) return
    apiClient
      .delete(`/urns/products/${productId}`)
      .then(() => {
        toast.success("Product deleted")
        load()
      })
      .catch((e) => toast.error(e.response?.data?.detail || "Delete failed"))
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Urn Catalog</h1>
          <p className="text-sm text-muted-foreground">
            {products.length} products
            {unpricedCount > 0 && (
              <span className="ml-2 text-amber-600">
                <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
                {unpricedCount} unpriced
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowSync(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Sync from Wilbert
          </Button>
          <Button variant="outline" onClick={() => setShowProductImport(true)}>
            <FileUp className="mr-2 h-4 w-4" />
            Import CSV
          </Button>
          <Button variant="outline" onClick={() => setShowBulkMarkup(true)}>
            <Percent className="mr-2 h-4 w-4" />
            Bulk Markup
          </Button>
          <Button variant="outline" onClick={() => setShowCsvImport(true)}>
            <FileSpreadsheet className="mr-2 h-4 w-4" />
            Import Prices
          </Button>
          {products.length > 0 && (
            <Button variant="outline" className="text-red-600 hover:text-red-700" onClick={() => setShowBulkDelete(true)}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete All
            </Button>
          )}
          <Button onClick={() => setShowAdd(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Product
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name, SKU, or material..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
        >
          <option value="">All Sources</option>
          <option value="stocked">Stocked</option>
          <option value="drop_ship">Drop Ship</option>
        </select>
        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={materialFilter}
          onChange={(e) => setMaterialFilter(e.target.value)}
        >
          <option value="">All Materials</option>
          {materials.map((m) => (
            <option key={m} value={m}>
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </option>
          ))}
        </select>
        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">All Types</option>
          {productTypes.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8"></TableHead>
                <TableHead>Product</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Material</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead className="text-right">Retail</TableHead>
                <TableHead className="text-right">Margin</TableHead>
                <TableHead>Availability</TableHead>
                <TableHead>Features</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((p) => (
                <Fragment key={p.id}>
                  <TableRow
                    className={`cursor-pointer ${
                      p.base_cost == null && p.retail_price == null && !p.discontinued
                        ? "bg-amber-50/50"
                        : ""
                    }`}
                    onClick={() =>
                      setExpandedRow(expandedRow === p.id ? null : p.id)
                    }
                  >
                    <TableCell className="w-8 px-2">
                      {expandedRow === p.id ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                    </TableCell>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-3">
                        {p.image_url ? (
                          <img
                            src={p.image_url}
                            alt={p.name}
                            className="h-10 w-10 rounded object-cover"
                          />
                        ) : (
                          <div className="flex h-10 w-10 items-center justify-center rounded bg-muted">
                            <Package className="h-5 w-5 text-muted-foreground" />
                          </div>
                        )}
                        <div>
                          <div className="max-w-[200px] truncate">{p.name}</div>
                          {p.wilbert_description && (
                            <div className="max-w-[200px] truncate text-xs text-muted-foreground">
                              {p.wilbert_description}
                            </div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {p.sku || "—"}
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{p.product_type || "—"}</span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm capitalize">{p.material || "—"}</span>
                    </TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      {editingPrice?.id === p.id && editingPrice?.field === "base_cost" ? (
                        <Input
                          type="number"
                          step="0.01"
                          className="h-7 w-24 text-right text-sm"
                          autoFocus
                          defaultValue={p.base_cost ?? ""}
                          onBlur={(e) => handlePriceUpdate(p.id, "base_cost", e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handlePriceUpdate(p.id, "base_cost", (e.target as HTMLInputElement).value)
                            if (e.key === "Escape") setEditingPrice(null)
                          }}
                        />
                      ) : (
                        <span
                          className="cursor-text rounded px-1 py-0.5 hover:bg-muted"
                          onClick={() => setEditingPrice({ id: p.id, field: "base_cost", value: String(p.base_cost ?? "") })}
                        >
                          {formatPrice(p.base_cost)}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      {editingPrice?.id === p.id && editingPrice?.field === "retail_price" ? (
                        <Input
                          type="number"
                          step="0.01"
                          className="h-7 w-24 text-right text-sm"
                          autoFocus
                          defaultValue={p.retail_price ?? ""}
                          onBlur={(e) => handlePriceUpdate(p.id, "retail_price", e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handlePriceUpdate(p.id, "retail_price", (e.target as HTMLInputElement).value)
                            if (e.key === "Escape") setEditingPrice(null)
                          }}
                        />
                      ) : (
                        <span
                          className="cursor-text rounded px-1 py-0.5 hover:bg-muted"
                          onClick={() => setEditingPrice({ id: p.id, field: "retail_price", value: String(p.retail_price ?? "") })}
                        >
                          {formatPrice(p.retail_price)}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {marginPercent(p.base_cost, p.retail_price)}
                    </TableCell>
                    <TableCell>
                      {p.source_type === "stocked" && p.inventory ? (
                        <span
                          className={
                            p.inventory.qty_on_hand - p.inventory.qty_reserved > 0
                              ? "text-green-600"
                              : "text-red-600"
                          }
                        >
                          {p.inventory.qty_on_hand - p.inventory.qty_reserved} avail
                        </span>
                      ) : p.source_type === "drop_ship" ? (
                        <span className="text-xs text-blue-600">Drop Ship</span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {p.engravable && (
                          <Badge variant="outline" className="text-xs">
                            E
                          </Badge>
                        )}
                        {p.is_keepsake_set && (
                          <Badge variant="outline" className="text-xs">
                            K
                          </Badge>
                        )}
                        {p.discontinued && (
                          <Badge variant="destructive" className="text-xs">
                            Disc
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>

                  {/* Expanded detail row */}
                  {expandedRow === p.id && (
                    <TableRow key={`${p.id}-detail`}>
                      <TableCell colSpan={10} className="bg-muted/30 p-4">
                        <div className="grid grid-cols-3 gap-6">
                          <div>
                            <h4 className="mb-2 text-sm font-semibold">Dimensions</h4>
                            <div className="space-y-1 text-sm">
                              <div>
                                <span className="text-muted-foreground">Height:</span>{" "}
                                {p.height || "—"}
                              </div>
                              <div>
                                <span className="text-muted-foreground">Width/Diameter:</span>{" "}
                                {p.width_or_diameter || "—"}
                              </div>
                              {p.depth && (
                                <div>
                                  <span className="text-muted-foreground">Depth:</span>{" "}
                                  {p.depth}
                                </div>
                              )}
                              <div>
                                <span className="text-muted-foreground">Cubic Inches:</span>{" "}
                                {p.cubic_inches ?? "—"}
                              </div>
                            </div>
                          </div>
                          <div>
                            <h4 className="mb-2 text-sm font-semibold">Description</h4>
                            <p className="text-sm text-muted-foreground">
                              {p.wilbert_description || p.wilbert_long_description || "No description available"}
                            </p>
                            {p.companion_of_sku && (
                              <div className="mt-2 text-sm">
                                <span className="text-muted-foreground">Companion of:</span>{" "}
                                <span className="font-mono">{p.companion_of_sku}</span>
                              </div>
                            )}
                            {p.catalog_page && (
                              <div className="mt-1 text-xs text-muted-foreground">
                                Catalog page {p.catalog_page}
                              </div>
                            )}
                          </div>
                          <div>
                            <h4 className="mb-2 text-sm font-semibold">Details</h4>
                            <div className="space-y-1 text-sm">
                              <div>
                                <span className="text-muted-foreground">Source:</span>{" "}
                                {p.source_type === "stocked" ? "Stocked" : "Drop Ship"}
                              </div>
                              <div>
                                <span className="text-muted-foreground">Type:</span>{" "}
                                {p.product_type || "—"}
                              </div>
                              {p.color_name && (
                                <div>
                                  <span className="text-muted-foreground">Color:</span>{" "}
                                  {p.color_name}
                                </div>
                              )}
                              {p.available_colors && p.available_colors.length > 0 && (
                                <div>
                                  <span className="text-muted-foreground">Colors:</span>{" "}
                                  {p.available_colors.join(", ")}
                                </div>
                              )}
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              className="mt-3 text-red-600 hover:text-red-700"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDeleteSingle(p.id, p.name)
                              }}
                            >
                              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                              Delete Product
                            </Button>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={10}
                    className="py-8 text-center text-muted-foreground"
                  >
                    No products found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Add Product Dialog */}
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Urn Product</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Name *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>SKU</Label>
                <Input
                  value={form.sku}
                  onChange={(e) => setForm({ ...form, sku: e.target.value })}
                />
              </div>
              <div>
                <Label>Source Type</Label>
                <select
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={form.source_type}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      source_type: e.target.value,
                      engravable:
                        e.target.value === "stocked" ? false : form.engravable,
                    })
                  }
                >
                  <option value="drop_ship">Drop Ship</option>
                  <option value="stocked">Stocked</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Material</Label>
                <Input
                  value={form.material}
                  onChange={(e) =>
                    setForm({ ...form, material: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Style</Label>
                <Input
                  value={form.style}
                  onChange={(e) => setForm({ ...form, style: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Base Cost</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.base_cost}
                  onChange={(e) =>
                    setForm({ ...form, base_cost: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Retail Price</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.retail_price}
                  onChange={(e) =>
                    setForm({ ...form, retail_price: e.target.value })
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdd(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={!form.name}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync from Wilbert Dialog */}
      <Dialog open={showSync} onOpenChange={setShowSync}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Sync from Wilbert Catalog</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Downloads the latest Cremation Choices catalog PDF from wilbert.com,
              extracts all products with SKUs and dimensions, and enriches them with
              descriptions and images from Wilbert's website.
            </p>
            <Button
              className="w-full"
              onClick={handleFetchPdf}
              disabled={syncing}
            >
              {syncing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Syncing catalog...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Fetch &amp; Sync Catalog
                </>
              )}
            </Button>

            <div className="border-t pt-3">
              <p className="mb-2 text-xs text-muted-foreground font-medium">
                Or upload a PDF manually
              </p>
              <Input
                type="file"
                accept=".pdf"
                onChange={(e) => setSyncFile(e.target.files?.[0] || null)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSync(false)}>
              Cancel
            </Button>
            <Button
              onClick={handlePdfSync}
              disabled={!syncFile || syncing}
            >
              {syncing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Syncing...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload &amp; Sync
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Markup Dialog */}
      <Dialog open={showBulkMarkup} onOpenChange={setShowBulkMarkup}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bulk Markup</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Apply a markup percentage to products&apos; base cost to set retail prices.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Material (optional)</Label>
                <select
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={markupForm.material}
                  onChange={(e) =>
                    setMarkupForm({ ...markupForm, material: e.target.value })
                  }
                >
                  <option value="">All Materials</option>
                  {materials.map((m) => (
                    <option key={m} value={m}>
                      {m.charAt(0).toUpperCase() + m.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label>Product Type (optional)</Label>
                <select
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={markupForm.product_type}
                  onChange={(e) =>
                    setMarkupForm({ ...markupForm, product_type: e.target.value })
                  }
                >
                  <option value="">All Types</option>
                  {productTypes.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Markup %</Label>
                <Input
                  type="number"
                  value={markupForm.markup_percent}
                  onChange={(e) =>
                    setMarkupForm({ ...markupForm, markup_percent: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Round to nearest</Label>
                <select
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={markupForm.rounding}
                  onChange={(e) =>
                    setMarkupForm({ ...markupForm, rounding: e.target.value })
                  }
                >
                  <option value="0.01">$0.01 (no rounding)</option>
                  <option value="0.50">$0.50</option>
                  <option value="1.00">$1.00</option>
                  <option value="5.00">$5.00</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="only-unpriced"
                checked={markupForm.only_unpriced}
                onChange={(e) =>
                  setMarkupForm({ ...markupForm, only_unpriced: e.target.checked })
                }
              />
              <label htmlFor="only-unpriced" className="text-sm">
                Only apply to products without a retail price
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBulkMarkup(false)}>
              Cancel
            </Button>
            <Button onClick={handleBulkMarkup}>
              <DollarSign className="mr-2 h-4 w-4" />
              Apply Markup
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CSV Price Import Dialog */}
      <Dialog open={showCsvImport} onOpenChange={setShowCsvImport}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import Prices from CSV</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Upload a CSV with columns: <code className="rounded bg-muted px-1">sku</code>,{" "}
              <code className="rounded bg-muted px-1">base_cost</code>,{" "}
              <code className="rounded bg-muted px-1">retail_price</code>.
              Products are matched by SKU.
            </p>
            <Input
              type="file"
              accept=".csv"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleCsvImport(file)
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCsvImport(false)}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Full Product CSV Import Dialog */}
      <Dialog open={showProductImport} onOpenChange={setShowProductImport}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Import Products from CSV</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Upload a CSV to create or update products. Products with matching SKUs
              will be updated; new SKUs will be created.
            </p>
            <div className="rounded-md bg-muted p-3 text-xs space-y-1">
              <p className="font-medium">Supported columns:</p>
              <p>
                <code>name</code>, <code>sku</code>, <code>material</code>,{" "}
                <code>product_type</code>, <code>source_type</code>,{" "}
                <code>height</code>, <code>width</code>, <code>depth</code>,{" "}
                <code>cubic_inches</code>, <code>engravable</code>,{" "}
                <code>base_cost</code>, <code>retail_price</code>,{" "}
                <code>style</code>, <code>color</code>, <code>description</code>
              </p>
              <p className="text-muted-foreground mt-1">
                Only <code>name</code> or <code>sku</code> is required per row.
                Column names are flexible (e.g., "cost" works for "base_cost").
              </p>
            </div>
            <Input
              type="file"
              accept=".csv"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleProductCsvImport(file)
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowProductImport(false)}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog open={showBulkDelete} onOpenChange={(open) => {
        setShowBulkDelete(open)
        if (!open) setDeleteConfirmText("")
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-red-600">Delete All Products</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              This will permanently delete <strong>{products.length} products</strong> from your
              catalog. Products with existing orders will be skipped.
            </p>
            <p className="text-sm text-muted-foreground">
              Type <code className="rounded bg-muted px-1 font-bold">DELETE</code> to confirm:
            </p>
            <Input
              value={deleteConfirmText}
              onChange={(e) => setDeleteConfirmText(e.target.value)}
              placeholder="Type DELETE to confirm"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowBulkDelete(false); setDeleteConfirmText("") }}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleBulkDelete}
              disabled={deleteConfirmText !== "DELETE" || deleting}
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete All Products
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
