import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, ExternalLink, CheckCircle, Ban, FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

interface Certificate {
  id: string;
  certificate_number: string;
  status: string;
  order_id: string;
  order_number: string | null;
  deceased_name: string | null;
  funeral_home_name: string | null;
  cemetery_name: string | null;
  product_price: string | null;
  delivered_at: string | null;
  generated_at: string;
  approved_at: string | null;
  approved_by_name: string | null;
  voided_at: string | null;
  voided_by_name: string | null;
  void_reason: string | null;
  sent_at: string | null;
  email_sent_to: string | null;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending_approval: { label: "Pending", color: "bg-amber-100 text-amber-800" },
  approved: { label: "Approved", color: "bg-blue-100 text-blue-800" },
  sent: { label: "Sent", color: "bg-green-100 text-green-800" },
  voided: { label: "Voided", color: "bg-red-100 text-red-800" },
};

function fmtDateTime(iso: string | null) {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  return (
    d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) +
    " " +
    d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
  );
}

function fmtCurrency(n: string | number | null) {
  if (n == null) return "\u2014";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(n)
  );
}

export default function SocialServiceCertificatesPage() {
  const [certs, setCerts] = useState<Certificate[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [voidingId, setVoidingId] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");

  const fetchCerts = useCallback(async () => {
    try {
      const params = statusFilter !== "all" ? { status: statusFilter } : {};
      const res = await apiClient.get<Certificate[]>(
        "/social-service-certificates/all",
        { params }
      );
      setCerts(res.data);
    } catch {
      toast.error("Failed to load certificates");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    setLoading(true);
    fetchCerts();
  }, [fetchCerts]);

  const handleApprove = async (id: string) => {
    setApprovingId(id);
    try {
      await apiClient.post(`/social-service-certificates/${id}/approve`);
      toast.success("Certificate approved and sent");
      fetchCerts();
    } catch {
      toast.error("Failed to approve certificate");
    } finally {
      setApprovingId(null);
    }
  };

  const handleVoid = async (id: string) => {
    if (!voidReason.trim()) {
      toast.error("Please enter a void reason");
      return;
    }
    try {
      await apiClient.post(`/social-service-certificates/${id}/void`, {
        reason: voidReason.trim(),
      });
      toast.success("Certificate voided");
      setVoidingId(null);
      setVoidReason("");
      fetchCerts();
    } catch {
      toast.error("Failed to void certificate");
    }
  };

  const handlePreview = async (id: string) => {
    try {
      const res = await apiClient.get<{ url: string }>(
        `/social-service-certificates/${id}/pdf`
      );
      window.open(res.data.url, "_blank");
    } catch {
      toast.error("Failed to load PDF");
    }
  };

  const pendingCount = certs.filter((c) => c.status === "pending_approval").length;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-6 w-6 text-purple-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Social Service Certificates
            </h1>
            <p className="text-sm text-gray-500">
              Delivery confirmation documents for government benefit program orders
            </p>
          </div>
        </div>
        {pendingCount > 0 && (
          <Badge className="bg-amber-100 text-amber-800 text-sm px-3 py-1">
            {pendingCount} pending approval
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">All Certificates</CardTitle>
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? "all")}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="pending_approval">Pending</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="sent">Sent</SelectItem>
                <SelectItem value="voided">Voided</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12 text-gray-400">
              Loading...
            </div>
          ) : certs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <FileText className="h-10 w-10 mb-2" />
              <p className="text-sm">No certificates found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-gray-500 uppercase tracking-wide">
                    <th className="pb-2 pr-4">Certificate</th>
                    <th className="pb-2 pr-4">Deceased</th>
                    <th className="pb-2 pr-4">Funeral Home</th>
                    <th className="pb-2 pr-4">Cemetery</th>
                    <th className="pb-2 pr-4">Delivered</th>
                    <th className="pb-2 pr-4">Price</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {certs.map((cert) => {
                    const st = STATUS_LABELS[cert.status] ?? {
                      label: cert.status,
                      color: "bg-gray-100 text-gray-800",
                    };
                    return (
                      <tr key={cert.id} className="hover:bg-gray-50">
                        <td className="py-3 pr-4">
                          <span className="font-mono text-xs text-gray-600">
                            {cert.certificate_number}
                          </span>
                        </td>
                        <td className="py-3 pr-4 font-medium text-gray-900">
                          {cert.deceased_name || "\u2014"}
                        </td>
                        <td className="py-3 pr-4 text-gray-700">
                          {cert.funeral_home_name || "\u2014"}
                        </td>
                        <td className="py-3 pr-4 text-gray-700">
                          {cert.cemetery_name || "\u2014"}
                        </td>
                        <td className="py-3 pr-4 text-gray-600 whitespace-nowrap">
                          {fmtDateTime(cert.delivered_at)}
                        </td>
                        <td className="py-3 pr-4 text-gray-700 whitespace-nowrap">
                          {fmtCurrency(cert.product_price)}
                        </td>
                        <td className="py-3 pr-4">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${st.color}`}
                          >
                            {st.label}
                          </span>
                          {cert.status === "sent" && cert.email_sent_to && (
                            <p className="text-[11px] text-gray-400 mt-0.5">
                              {cert.email_sent_to}
                            </p>
                          )}
                          {cert.status === "voided" && cert.void_reason && (
                            <p className="text-[11px] text-red-400 mt-0.5 max-w-[200px] truncate">
                              {cert.void_reason}
                            </p>
                          )}
                        </td>
                        <td className="py-3">
                          {voidingId === cert.id ? (
                            <div className="flex items-center gap-1.5">
                              <input
                                type="text"
                                value={voidReason}
                                onChange={(e) => setVoidReason(e.target.value)}
                                placeholder="Reason..."
                                className="text-xs px-2 py-1 border rounded w-32 focus:outline-none focus:ring-1 focus:ring-purple-400"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleVoid(cert.id);
                                  if (e.key === "Escape") {
                                    setVoidingId(null);
                                    setVoidReason("");
                                  }
                                }}
                                autoFocus
                              />
                              <Button
                                size="sm"
                                variant="destructive"
                                className="h-6 text-xs px-2"
                                onClick={() => handleVoid(cert.id)}
                              >
                                Confirm
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 text-xs px-2"
                                onClick={() => {
                                  setVoidingId(null);
                                  setVoidReason("");
                                }}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 text-xs gap-1"
                                onClick={() => handlePreview(cert.id)}
                              >
                                <ExternalLink className="h-3 w-3" />
                                PDF
                              </Button>
                              {cert.status === "pending_approval" && (
                                <>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 text-xs gap-1 text-green-700 hover:text-green-900"
                                    onClick={() => handleApprove(cert.id)}
                                    disabled={approvingId === cert.id}
                                  >
                                    <CheckCircle className="h-3 w-3" />
                                    {approvingId === cert.id ? "..." : "Approve"}
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 text-xs gap-1 text-red-600 hover:text-red-800"
                                    onClick={() => setVoidingId(cert.id)}
                                  >
                                    <Ban className="h-3 w-3" />
                                    Void
                                  </Button>
                                </>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
