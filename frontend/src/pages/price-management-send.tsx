// price-management-send.tsx — Send price list PDF to recipients via email.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  ChevronLeft,
  Loader2,
  Mail,
  Plus,
  Send,
  Trash2,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PriceVersion {
  id: string;
  version_number: number;
  label: string | null;
  status: string;
  effective_date: string | null;
}

interface Recipient {
  email: string;
  name: string;
}

interface SendResult {
  email: string;
  success: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PriceManagementSendPage() {
  const [searchParams] = useSearchParams();
  const versionParam = searchParams.get("version");

  const [versions, setVersions] = useState<PriceVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState(versionParam || "");
  const [recipients, setRecipients] = useState<Recipient[]>([{ email: "", name: "" }]);
  const [customMessage, setCustomMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [results, setResults] = useState<SendResult[] | null>(null);
  const [loading, setLoading] = useState(true);

  const loadVersions = useCallback(async () => {
    try {
      const res = await apiClient.get("/price-management/versions");
      setVersions(res.data);
    } catch {
      toast.error("Failed to load versions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadVersions(); }, [loadVersions]);

  const addRecipient = () => setRecipients([...recipients, { email: "", name: "" }]);

  const removeRecipient = (idx: number) => {
    if (recipients.length === 1) return;
    setRecipients(recipients.filter((_, i) => i !== idx));
  };

  const updateRecipient = (idx: number, field: "email" | "name", value: string) => {
    const updated = [...recipients];
    updated[idx] = { ...updated[idx], [field]: value };
    setRecipients(updated);
  };

  const handleSend = async () => {
    const validRecipients = recipients.filter((r) => r.email.trim());
    if (!selectedVersionId) {
      toast.error("Select a version");
      return;
    }
    if (validRecipients.length === 0) {
      toast.error("Add at least one recipient");
      return;
    }

    setSending(true);
    setResults(null);
    try {
      const res = await apiClient.post("/price-management/send-price-list", {
        version_id: selectedVersionId,
        recipients: validRecipients,
        custom_message: customMessage || undefined,
      });
      setResults(res.data.results);
      const sent = res.data.sent;
      const total = res.data.total;
      if (sent === total) {
        toast.success(`Price list sent to ${sent} recipient${sent !== 1 ? "s" : ""}`);
      } else {
        toast.warning(`Sent to ${sent}/${total} recipients`);
      }
    } catch {
      toast.error("Send failed");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  const selectedVersion = versions.find((v) => v.id === selectedVersionId);

  return (
    <div className="space-y-6 p-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Link to="/price-management">
          <Button variant="ghost" size="sm">
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Send Price List</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Email a price list PDF to customers and contacts.
          </p>
        </div>
      </div>

      {/* Version picker */}
      <div className="rounded-xl border bg-white p-5 space-y-3">
        <label className="text-xs font-medium text-muted-foreground block">Price List Version</label>
        <select
          value={selectedVersionId}
          onChange={(e) => setSelectedVersionId(e.target.value)}
          className="w-full rounded-md border px-3 py-2 text-sm"
        >
          <option value="">Select a version...</option>
          {versions.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label || `Version ${v.version_number}`} — {v.status} — {v.effective_date || "no date"}
            </option>
          ))}
        </select>
        {selectedVersion && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">{selectedVersion.status}</Badge>
            <span>Effective: {selectedVersion.effective_date || "—"}</span>
          </div>
        )}
      </div>

      {/* Recipients */}
      <div className="rounded-xl border bg-white p-5 space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-muted-foreground">Recipients</label>
          <Button variant="ghost" size="sm" onClick={addRecipient}>
            <Plus className="h-4 w-4 mr-1" />
            Add
          </Button>
        </div>
        {recipients.map((r, idx) => (
          <div key={idx} className="flex gap-2 items-center">
            <Input
              placeholder="Email address"
              value={r.email}
              onChange={(e) => updateRecipient(idx, "email", e.target.value)}
              className="flex-1"
            />
            <Input
              placeholder="Name (optional)"
              value={r.name}
              onChange={(e) => updateRecipient(idx, "name", e.target.value)}
              className="flex-1"
            />
            {recipients.length > 1 && (
              <Button variant="ghost" size="sm" onClick={() => removeRecipient(idx)}>
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            )}
          </div>
        ))}
      </div>

      {/* Custom message */}
      <div className="rounded-xl border bg-white p-5 space-y-3">
        <label className="text-xs font-medium text-muted-foreground block">Custom Message (optional)</label>
        <textarea
          value={customMessage}
          onChange={(e) => setCustomMessage(e.target.value)}
          placeholder="Add a personal note to the email..."
          rows={3}
          className="w-full rounded-md border px-3 py-2 text-sm resize-none"
        />
      </div>

      <Button onClick={handleSend} disabled={sending} className="w-full">
        {sending ? (
          <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
        ) : (
          <Send className="h-4 w-4 mr-1.5" />
        )}
        Send Price List
      </Button>

      {/* Results */}
      {results && (
        <div className="rounded-xl border bg-white p-5 space-y-2">
          <h3 className="font-semibold text-sm">Send Results</h3>
          {results.map((r, idx) => (
            <div key={idx} className="flex items-center gap-2 text-sm">
              {r.success ? (
                <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500 shrink-0" />
              )}
              <span className={cn(r.success ? "" : "text-red-600")}>{r.email}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
