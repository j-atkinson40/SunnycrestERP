import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Plus, Loader2, Eye } from "lucide-react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface UrnOrder {
  id: string
  funeral_home_name: string | null
  urn_product_name: string | null
  fulfillment_type: string
  quantity: number
  status: string
  need_by_date: string | null
  delivery_method: string | null
  intake_channel: string
  expected_arrival_date: string | null
  created_at: string
  engraving_jobs: Array<{
    id: string
    piece_label: string
    engraving_line_1: string | null
    proof_status: string
  }>
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  confirmed: "bg-blue-100 text-blue-700",
  engraving_pending: "bg-yellow-100 text-yellow-700",
  proof_pending: "bg-orange-100 text-orange-700",
  awaiting_fh_approval: "bg-purple-100 text-purple-700",
  fh_approved: "bg-green-100 text-green-700",
  fh_changes_requested: "bg-red-100 text-red-700",
  proof_approved: "bg-emerald-100 text-emerald-700",
  fulfilling: "bg-cyan-100 text-cyan-700",
  delivered: "bg-green-200 text-green-800",
  cancelled: "bg-red-200 text-red-800",
}

function statusLabel(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function UrnOrders() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<UrnOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState("")

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (statusFilter) params.set("status", statusFilter)
    apiClient
      .get(`/urns/orders?${params}`)
      .then((r) => setOrders(r.data))
      .catch(() => toast.error("Failed to load orders"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [statusFilter])

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Urn Orders</h1>
        <Button onClick={() => navigate("/urns/orders/new")}>
          <Plus className="mr-2 h-4 w-4" />
          New Order
        </Button>
      </div>

      <div className="flex gap-3">
        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="confirmed">Confirmed</option>
          <option value="engraving_pending">Engraving Pending</option>
          <option value="proof_pending">Proof Pending</option>
          <option value="awaiting_fh_approval">Awaiting FH Approval</option>
          <option value="fh_approved">FH Approved</option>
          <option value="proof_approved">Proof Approved</option>
          <option value="delivered">Delivered</option>
          <option value="cancelled">Cancelled</option>
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
                <TableHead>Order</TableHead>
                <TableHead>Funeral Home</TableHead>
                <TableHead>Product</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Engraving</TableHead>
                <TableHead>Need By</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.map((o) => (
                <TableRow key={o.id}>
                  <TableCell className="font-mono text-xs">
                    {o.id.slice(0, 8)}
                  </TableCell>
                  <TableCell>{o.funeral_home_name || "—"}</TableCell>
                  <TableCell>{o.urn_product_name || "—"}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        o.fulfillment_type === "stocked"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {o.fulfillment_type === "stocked"
                        ? "Stocked"
                        : "Drop Ship"}
                    </Badge>
                  </TableCell>
                  <TableCell>{o.quantity}</TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[o.status] || "bg-gray-100"}`}
                    >
                      {statusLabel(o.status)}
                    </span>
                  </TableCell>
                  <TableCell>
                    {o.engraving_jobs.length > 0 ? (
                      <div className="space-y-1">
                        {o.engraving_jobs.map((j) => (
                          <div key={j.id} className="text-xs">
                            <span className="font-medium">{j.piece_label}</span>
                            :{" "}
                            <span className="text-muted-foreground">
                              {j.engraving_line_1 || "No text"}
                            </span>
                            <Badge
                              variant="outline"
                              className="ml-1 text-[10px]"
                            >
                              {statusLabel(j.proof_status)}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {o.need_by_date
                      ? new Date(o.need_by_date).toLocaleDateString()
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => navigate(`/urns/proof-review/${o.id}`)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {orders.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={9}
                    className="py-8 text-center text-muted-foreground"
                  >
                    No orders found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
