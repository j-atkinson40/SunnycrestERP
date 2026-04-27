import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, Search } from "lucide-react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"

interface Product {
  id: string
  name: string
  sku: string | null
  source_type: string
  material: string | null
  retail_price: number | null
  image_url: string | null
  match_score: number
  availability_note: string | null
}

export default function UrnOrderForm() {
  const navigate = useNavigate()
  const [step, setStep] = useState<"product" | "details" | "engraving">(
    "product"
  )
  const [search, setSearch] = useState("")
  const [searchResults, setSearchResults] = useState<Product[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    funeral_home_id: "",
    fh_contact_email: "",
    quantity: 1,
    need_by_date: "",
    delivery_method: "",
    notes: "",
  })
  const [engraving, setEngraving] = useState({
    engraving_line_1: "",
    engraving_line_2: "",
    engraving_line_3: "",
    engraving_line_4: "",
    font_selection: "",
    color_selection: "",
  })

  const doSearch = () => {
    if (!search.trim()) return
    setSearching(true)
    apiClient
      .get(`/urns/products/search?q=${encodeURIComponent(search)}`)
      .then((r) => setSearchResults(r.data))
      .catch(() => toast.error("Search failed"))
      .finally(() => setSearching(false))
  }

  const handleSubmit = () => {
    if (!selectedProduct) return
    setSubmitting(true)

    const payload: Record<string, unknown> = {
      urn_product_id: selectedProduct.id,
      quantity: form.quantity,
      delivery_method: form.delivery_method || null,
      notes: form.notes || null,
      need_by_date: form.need_by_date || null,
      funeral_home_id: form.funeral_home_id || null,
      fh_contact_email: form.fh_contact_email || null,
    }

    if (
      selectedProduct.source_type === "drop_ship" &&
      engraving.engraving_line_1
    ) {
      payload.engraving_specs = [
        { piece_label: "main", ...engraving },
      ]
    }

    apiClient
      .post("/urns/orders", payload)
      .then(() => {
        toast.success("Order created")
        navigate(`/urns/orders`)
      })
      .catch(() => toast.error("Failed to create order"))
      .finally(() => setSubmitting(false))
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-bold">New Urn Order</h1>

      {/* Step indicators */}
      <div className="flex gap-2">
        {["product", "details", "engraving"].map((s) => (
          <Badge
            key={s}
            variant={step === s ? "default" : "outline"}
            className="cursor-pointer capitalize"
            onClick={() => {
              if (s === "product" || selectedProduct) setStep(s as typeof step)
            }}
          >
            {s === "product"
              ? "1. Select Product"
              : s === "details"
                ? "2. Order Details"
                : "3. Engraving"}
          </Badge>
        ))}
      </div>

      {/* Step 1: Product Selection */}
      {step === "product" && (
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">Select Urn Product</h2>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name, SKU, material..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doSearch()}
                className="pl-10"
              />
            </div>
            <Button onClick={doSearch} disabled={searching}>
              {searching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Search"
              )}
            </Button>
          </div>

          {searchResults.length > 0 && (
            <div className="space-y-2">
              {searchResults.map((p) => (
                <div
                  key={p.id}
                  className={`flex cursor-pointer items-center justify-between rounded-lg border p-3 transition hover:bg-accent-subtle ${
                    selectedProduct?.id === p.id ? "border-accent bg-accent-subtle" : ""
                  }`}
                  onClick={() => {
                    setSelectedProduct(p)
                    setStep("details")
                  }}
                >
                  <div>
                    <div className="font-medium">{p.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {p.sku && <span className="font-mono">{p.sku}</span>}
                      {p.material && <span> &middot; {p.material}</span>}
                    </div>
                  </div>
                  <div className="text-right">
                    {p.retail_price && (
                      <div className="font-medium">
                        ${Number(p.retail_price).toFixed(2)}
                      </div>
                    )}
                    {p.availability_note && (
                      <div className="text-xs text-muted-foreground">
                        {p.availability_note}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Step 2: Order Details */}
      {step === "details" && selectedProduct && (
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">Order Details</h2>
          <div className="rounded-md bg-muted p-3">
            <span className="font-medium">{selectedProduct.name}</span>
            <Badge variant="secondary" className="ml-2">
              {selectedProduct.source_type === "stocked"
                ? "Stocked"
                : "Drop Ship"}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Quantity</Label>
              <Input
                type="number"
                min={1}
                value={form.quantity}
                onChange={(e) =>
                  setForm({ ...form, quantity: parseInt(e.target.value) || 1 })
                }
              />
            </div>
            <div>
              <Label>Need By Date</Label>
              <Input
                type="date"
                value={form.need_by_date}
                onChange={(e) =>
                  setForm({ ...form, need_by_date: e.target.value })
                }
              />
            </div>
          </div>

          <div>
            <Label>Delivery Method</Label>
            <select
              className="w-full rounded-md border px-3 py-2 text-sm"
              value={form.delivery_method}
              onChange={(e) =>
                setForm({ ...form, delivery_method: e.target.value })
              }
            >
              <option value="">Select...</option>
              <option value="with_vault">With Vault Delivery</option>
              <option value="separate_delivery">Separate Delivery</option>
              <option value="will_call">Will Call</option>
            </select>
          </div>

          <div>
            <Label>FH Contact Email</Label>
            <Input
              type="email"
              value={form.fh_contact_email}
              onChange={(e) =>
                setForm({ ...form, fh_contact_email: e.target.value })
              }
            />
          </div>

          <div>
            <Label>Notes</Label>
            <textarea
              className="w-full rounded-md border px-3 py-2 text-sm"
              rows={3}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>

          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep("product")}>
              Back
            </Button>
            {selectedProduct.source_type === "drop_ship" ? (
              <Button onClick={() => setStep("engraving")}>
                Next: Engraving
              </Button>
            ) : (
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Create Order
              </Button>
            )}
          </div>
        </Card>
      )}

      {/* Step 3: Engraving */}
      {step === "engraving" && selectedProduct && (
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-semibold">Engraving Details</h2>
          <p className="text-sm text-muted-foreground">
            Enter engraving text for the main piece. Companion pieces can be
            configured after order creation.
          </p>

          <div>
            <Label>Line 1 (Decedent Name)</Label>
            <Input
              value={engraving.engraving_line_1}
              onChange={(e) =>
                setEngraving({ ...engraving, engraving_line_1: e.target.value })
              }
            />
          </div>
          <div>
            <Label>Line 2 (Dates)</Label>
            <Input
              value={engraving.engraving_line_2}
              onChange={(e) =>
                setEngraving({ ...engraving, engraving_line_2: e.target.value })
              }
            />
          </div>
          <div>
            <Label>Line 3</Label>
            <Input
              value={engraving.engraving_line_3}
              onChange={(e) =>
                setEngraving({ ...engraving, engraving_line_3: e.target.value })
              }
            />
          </div>
          <div>
            <Label>Line 4</Label>
            <Input
              value={engraving.engraving_line_4}
              onChange={(e) =>
                setEngraving({ ...engraving, engraving_line_4: e.target.value })
              }
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Font</Label>
              <Input
                value={engraving.font_selection}
                onChange={(e) =>
                  setEngraving({
                    ...engraving,
                    font_selection: e.target.value,
                  })
                }
              />
            </div>
            <div>
              <Label>Color</Label>
              <Input
                value={engraving.color_selection}
                onChange={(e) =>
                  setEngraving({
                    ...engraving,
                    color_selection: e.target.value,
                  })
                }
              />
            </div>
          </div>

          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep("details")}>
              Back
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Create Order
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
