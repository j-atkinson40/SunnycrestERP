// price-management-email-settings.tsx — Email settings + send history.

import { useCallback, useEffect, useState } from "react";
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
  Save,
  Settings,
  Shield,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EmailSettings {
  id: string;
  sending_mode: string;
  from_name: string | null;
  reply_to_email: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_use_tls: boolean;
  smtp_from_email: string | null;
  smtp_verified: boolean;
  smtp_verified_at: string | null;
  invoice_bcc_email: string | null;
  price_list_bcc_email: string | null;
}

interface EmailSend {
  id: string;
  email_type: string | null;
  to_email: string;
  to_name: string | null;
  subject: string | null;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  attachment_name: string | null;
  created_at: string | null;
}

interface RoundingSettings {
  rounding_mode: string;
  accept_manufacturer_updates: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type TabKey = "email" | "rounding" | "history";

export default function PriceManagementEmailSettingsPage() {
  const [tab, setTab] = useState<TabKey>("email");

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
          <h1 className="text-2xl font-bold">Price Management Settings</h1>
          <p className="text-muted-foreground text-sm mt-1">Email delivery, rounding, and send history.</p>
        </div>
      </div>

      <div className="flex border-b">
        {[
          { key: "email" as TabKey, label: "Email Settings", icon: Mail },
          { key: "rounding" as TabKey, label: "Rounding", icon: Settings },
          { key: "history" as TabKey, label: "Send History", icon: Mail },
        ].map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
                tab === t.key
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "email" && <EmailSettingsTab />}
      {tab === "rounding" && <RoundingTab />}
      {tab === "history" && <SendHistoryTab />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Email Settings Tab
// ---------------------------------------------------------------------------

function EmailSettingsTab() {
  const [settings, setSettings] = useState<EmailSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    apiClient.get("/price-management/settings/email")
      .then((r) => setSettings(r.data))
      .catch(() => toast.error("Failed to load settings"))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const res = await apiClient.put("/price-management/settings/email", {
        sending_mode: settings.sending_mode,
        from_name: settings.from_name,
        reply_to_email: settings.reply_to_email,
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_username: settings.smtp_username,
        smtp_use_tls: settings.smtp_use_tls,
        smtp_from_email: settings.smtp_from_email,
        invoice_bcc_email: settings.invoice_bcc_email,
        price_list_bcc_email: settings.price_list_bcc_email,
      });
      setSettings(res.data);
      toast.success("Settings saved");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await apiClient.post("/price-management/settings/email/verify-smtp");
      if (res.data.success) {
        toast.success("SMTP connection verified");
        setSettings((s) => s ? { ...s, smtp_verified: true } : s);
      } else {
        toast.error(`SMTP verification failed: ${res.data.error || "Unknown error"}`);
      }
    } catch {
      toast.error("SMTP verification failed");
    } finally {
      setVerifying(false);
    }
  };

  if (loading || !settings) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="rounded-xl border bg-white p-5 space-y-4">
        <h3 className="font-semibold text-sm">Sending Mode</h3>
        <div className="flex gap-3">
          {["platform", "smtp"].map((mode) => (
            <button
              key={mode}
              onClick={() => setSettings({ ...settings, sending_mode: mode })}
              className={cn(
                "flex-1 rounded-lg border p-3 text-left transition-all",
                settings.sending_mode === mode
                  ? "border-indigo-400 bg-indigo-50"
                  : "hover:border-gray-300",
              )}
            >
              <p className="font-medium text-sm capitalize">{mode === "platform" ? "Platform (Resend)" : "Custom SMTP"}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {mode === "platform"
                  ? "Send via Bridgeable's email service"
                  : "Use your own SMTP server"}
              </p>
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border bg-white p-5 space-y-4">
        <h3 className="font-semibold text-sm">General</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">From Name</label>
            <Input
              value={settings.from_name || ""}
              onChange={(e) => setSettings({ ...settings, from_name: e.target.value || null })}
              placeholder="Your Company Name"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Reply-to Email</label>
            <Input
              value={settings.reply_to_email || ""}
              onChange={(e) => setSettings({ ...settings, reply_to_email: e.target.value || null })}
              placeholder="billing@company.com"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Invoice BCC</label>
            <Input
              value={settings.invoice_bcc_email || ""}
              onChange={(e) => setSettings({ ...settings, invoice_bcc_email: e.target.value || null })}
              placeholder="accounting@company.com"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Price List BCC</label>
            <Input
              value={settings.price_list_bcc_email || ""}
              onChange={(e) => setSettings({ ...settings, price_list_bcc_email: e.target.value || null })}
              placeholder="sales@company.com"
            />
          </div>
        </div>
      </div>

      {settings.sending_mode === "smtp" && (
        <div className="rounded-xl border bg-white p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm">SMTP Configuration</h3>
            {settings.smtp_verified ? (
              <Badge className="bg-green-100 text-green-700">
                <CheckCircle className="h-3 w-3 mr-1" /> Verified
              </Badge>
            ) : (
              <Badge className="bg-amber-100 text-amber-700">
                <XCircle className="h-3 w-3 mr-1" /> Not verified
              </Badge>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">SMTP Host</label>
              <Input
                value={settings.smtp_host || ""}
                onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value || null })}
                placeholder="smtp.gmail.com"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Port</label>
              <Input
                type="number"
                value={settings.smtp_port}
                onChange={(e) => setSettings({ ...settings, smtp_port: parseInt(e.target.value) || 587 })}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Username</label>
              <Input
                value={settings.smtp_username || ""}
                onChange={(e) => setSettings({ ...settings, smtp_username: e.target.value || null })}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">From Email</label>
              <Input
                value={settings.smtp_from_email || ""}
                onChange={(e) => setSettings({ ...settings, smtp_from_email: e.target.value || null })}
                placeholder="noreply@company.com"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={settings.smtp_use_tls}
              onChange={(e) => setSettings({ ...settings, smtp_use_tls: e.target.checked })}
              className="rounded border-gray-300"
            />
            Use TLS
          </label>
          <Button variant="outline" size="sm" onClick={handleVerify} disabled={verifying}>
            {verifying ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Shield className="h-4 w-4 mr-1.5" />}
            Test Connection
          </Button>
        </div>
      )}

      <Button onClick={handleSave} disabled={saving}>
        {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
        Save Settings
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rounding Tab
// ---------------------------------------------------------------------------

function RoundingTab() {
  const [settings, setSettings] = useState<RoundingSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiClient.get("/price-management/settings/rounding")
      .then((r) => setSettings(r.data))
      .catch(() => toast.error("Failed to load rounding settings"))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await apiClient.put("/price-management/settings/rounding", settings);
      toast.success("Rounding settings saved");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="max-w-md space-y-5">
      <div className="rounded-xl border bg-white p-5 space-y-4">
        <h3 className="font-semibold text-sm">Price Rounding</h3>
        <p className="text-xs text-muted-foreground">
          Applied when calculating price increases. Affects how the final price is rounded.
        </p>
        <select
          value={settings.rounding_mode}
          onChange={(e) => setSettings({ ...settings, rounding_mode: e.target.value })}
          className="w-full rounded-md border px-3 py-2 text-sm"
        >
          <option value="none">No rounding</option>
          <option value="nearest_dollar">Nearest dollar ($X.00)</option>
          <option value="nearest_quarter">Nearest quarter ($X.25, $X.50, ...)</option>
          <option value="nearest_five">Nearest $5</option>
        </select>
      </div>

      <Button onClick={handleSave} disabled={saving}>
        {saving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Save className="h-4 w-4 mr-1.5" />}
        Save
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Send History Tab
// ---------------------------------------------------------------------------

function SendHistoryTab() {
  const [sends, setSends] = useState<EmailSend[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await apiClient.get("/price-management/email-sends");
      setSends(res.data);
    } catch {
      toast.error("Failed to load send history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-4">
      {sends.length === 0 ? (
        <div className="rounded-xl border bg-gray-50 p-10 text-center">
          <Mail className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">No emails sent yet.</p>
        </div>
      ) : (
        <div className="rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-4 py-2.5 font-medium">Recipient</th>
                <th className="text-left px-4 py-2.5 font-medium">Subject</th>
                <th className="text-left px-4 py-2.5 font-medium">Type</th>
                <th className="text-left px-4 py-2.5 font-medium">Status</th>
                <th className="text-left px-4 py-2.5 font-medium">Sent</th>
              </tr>
            </thead>
            <tbody>
              {sends.map((s) => (
                <tr key={s.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <p className="font-medium">{s.to_name || s.to_email}</p>
                    {s.to_name && <p className="text-xs text-muted-foreground">{s.to_email}</p>}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground truncate max-w-xs">
                    {s.subject || "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant="outline" className="text-xs">{s.email_type || "—"}</Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge className={cn(
                      "text-xs",
                      s.status === "sent" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700",
                    )}>
                      {s.status}
                    </Badge>
                    {s.error_message && (
                      <p className="text-[10px] text-red-500 mt-0.5 truncate max-w-32">{s.error_message}</p>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs">
                    {s.sent_at ? new Date(s.sent_at).toLocaleString() : s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
