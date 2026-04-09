import { useState, useEffect } from "react"
import { Plus, Search, Package, Loader2 } from "lucide-react"
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
  available_colors: string[] | null
  engravable: boolean
  is_keepsake_set: boolean
  photo_etch_capable: boolean
  base_cost: number | null
  retail_price: number | null
  image_url: string | null
  discontinued: boolean
  is_active: boolean
  inventory: { qty_on_hand: number; qty_reserved: number } | null
}

export default function UrnCatalog() {
  const [products, setProducts] = useState<UrnProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [sourceFilter, setSourceFilter] = useState<string>("")
  const [showAdd, setShowAdd] = useState(false)
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

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (sourceFilter) params.set("source_type", sourceFilter)
    apiClient
      .get(`/urns/products?${params}`)
      .then((r) => setProducts(r.data))
      .catch(() => toast.error("Failed to load products"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [sourceFilter])

  const filtered = search
    ? products.filter(
        (p) =>
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          (p.sku && p.sku.toLowerCase().includes(search.toLowerCase()))
      )
    : products

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

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Urn Catalog</h1>
        <Button onClick={() => setShowAdd(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Product
        </Button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name or SKU..."
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
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Material</TableHead>
                <TableHead>Retail Price</TableHead>
                <TableHead>Availability</TableHead>
                <TableHead>Features</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((p) => (
                <TableRow key={p.id}>
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
                        <div>{p.name}</div>
                        {p.style && (
                          <div className="text-xs text-muted-foreground">
                            {p.style}
                          </div>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {p.sku || "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        p.source_type === "stocked" ? "default" : "secondary"
                      }
                    >
                      {p.source_type === "stocked" ? "Stocked" : "Drop Ship"}
                    </Badge>
                  </TableCell>
                  <TableCell>{p.material || "—"}</TableCell>
                  <TableCell>
                    {p.retail_price ? `$${Number(p.retail_price).toFixed(2)}` : "—"}
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
                        {p.inventory.qty_on_hand - p.inventory.qty_reserved}{" "}
                        available
                      </span>
                    ) : p.source_type === "drop_ship" ? (
                      <span className="text-blue-600">Drop Ship</span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {p.engravable && (
                        <Badge variant="outline" className="text-xs">
                          Engravable
                        </Badge>
                      )}
                      {p.is_keepsake_set && (
                        <Badge variant="outline" className="text-xs">
                          Keepsake
                        </Badge>
                      )}
                      {p.photo_etch_capable && (
                        <Badge variant="outline" className="text-xs">
                          Photo Etch
                        </Badge>
                      )}
                      {p.discontinued && (
                        <Badge variant="destructive" className="text-xs">
                          Discontinued
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                    No products found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Card>
      )}

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
    </div>
  )
}
