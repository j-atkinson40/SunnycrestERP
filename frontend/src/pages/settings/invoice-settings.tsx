import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ExternalLink, Loader2, Palette, Save } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface InvoiceSettings {
  template_key: string;
  show_deceased_name: boolean;
  show_payment_terms: boolean;
  show_early_payment_discount: boolean;
  show_finance_charge_notice: boolean;
  show_cemetery_on_invoice: boolean;
  show_service_date: boolean;
  show_order_number: boolean;
  show_phone: boolean;
  show_email: boolean;
  show_website: boolean;
  show_remittance_stub: boolean;
  primary_color: string;
  secondary_color: string;
  remit_to_name: string | null;
  remit_to_address: string | null;
  custom_footer_text: string | null;
}

const TEMPLATES = [
  { key: "professional",  label: "Professional" },
  { key: "clean_minimal", label: "Clean & Minimal" },
  { key: "modern",        label: "Modern" },
];

const DEFAULT_DELIVERY_OPTIONS = [
  { value: "statement_only",       label: "Statement only",          description: "Include invoices on monthly statement — no individual emails" },
  { value: "invoice_immediately",  label: "Email invoice immediately", description: "Send PDF by email when each order is approved" },
  { value: "both",                 label: "Both",                    description: "Email immediately and include on monthly statement" },
];

const CONTENT_OPTIONS: Array<{
  key: keyof InvoiceSettings;
  label: string;
  group: string;
}> = [
  { key: "show_deceased_name",          label: "Deceased name (RE: Smith, John)", group: "Customer & service information" },
  { key: "show_cemetery_on_invoice",    label: "Cemetery name",                  group: "Customer & service information" },
  { key: "show_service_date",           label: "Service date",                   group: "Customer & service information" },
  { key: "show_order_number",           label: "Order / S/O number",             group: "Customer & service information" },
  { key: "show_payment_terms",          label: "Payment terms",                  group: "Payment information" },
  { key: "show_early_payment_discount", label: "Early payment discount",         group: "Payment information" },
  { key: "show_finance_charge_notice",  label: "Finance charge notice",          group: "Payment information" },
  { key: "show_remittance_stub",        label: "Remittance stub (tear-off)",     group: "Payment information" },
  { key: "show_phone",                  label: "Phone number",                   group: "Contact information" },
  { key: "show_email",                  label: "Email address",                  group: "Contact information" },
  { key: "show_website",                label: "Website",                        group: "Contact information" },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function InvoiceSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<InvoiceSettings>({
    template_key: "professional",
    show_deceased_name: true,
    show_payment_terms: true,
    show_early_payment_discount: true,
    show_finance_charge_notice: true,
    show_cemetery_on_invoice: true,
    show_service_date: true,
    show_order_number: true,
    show_phone: true,
    show_email: true,
    show_website: false,
    show_remittance_stub: false,
    primary_color: "#1B4F8A",
    secondary_color: "#2D9B8A",
    remit_to_name: null,
    remit_to_address: null,
    custom_footer_text: null,
  });
  const [defaultDelivery, setDefaultDelivery] = useState("statement_only");
  const [previewKey, setPreviewKey] = useState(0);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);
  const previewBlobRef = useRef<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await apiClient.get("/sales/invoice-settings");
        setSettings((s) => ({ ...s, ...res.data }));
      } catch (err) {
        toast.error(getApiErrorMessage(err, "Failed to load invoice settings"));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Debounce preview refresh on any settings change
  useEffect(() => {
    if (loading) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setPreviewKey((k) => k + 1), 1200);
  }, [settings, loading]);

  // Fetch preview PDF as blob whenever previewKey changes
  useEffect(() => {
    if (loading) return;
    const params = new URLSearchParams({
      template: settings.template_key,
      format: "pdf",
      options: JSON.stringify(settings),
    });
    apiClient
      .get(`/sales/invoice-templates/preview?${params.toString()}`, { responseType: "blob" })
      .then((res) => {
        const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
        if (previewBlobRef.current) URL.revokeObjectURL(previewBlobRef.current);
        previewBlobRef.current = url;
        setPreviewBlobUrl(url);
      })
      .catch(() => {});
  }, [previewKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggle = useCallback((key: keyof InvoiceSettings) => {
    setSettings((s) => ({ ...s, [key]: !s[key as keyof typeof s] }));
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await apiClient.patch("/sales/invoice-settings", settings);
      toast.success("Invoice settings saved");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save"));
    } finally {
      setSaving(false);
    }
  }, [settings]);

  const groupedOptions = CONTENT_OPTIONS.reduce<Record<string, typeof CONTENT_OPTIONS>>(
    (acc, opt) => {
      if (!acc[opt.group]) acc[opt.group] = [];
      acc[opt.group].push(opt);
      return acc;
    },
    {}
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 max-w-6xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Invoice &amp; Statement Settings</h1>
          <p className="text-muted-foreground mt-1">
            Configure what appears on invoices and monthly statements.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/onboarding/branding">
            <Button variant="outline" size="sm">
              <Palette className="w-4 h-4 mr-1.5" />
              Change template
            </Button>
          </Link>
          <Button onClick={handleSave} disabled={saving}>
            <Save className="w-4 h-4 mr-1.5" />
            {saving ? "Saving..." : "Save settings"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Left column: controls */}
        <div className="space-y-5">

          {/* Template */}
          <Card className="p-4">
            <h2 className="font-semibold mb-3">Template</h2>
            <div className="space-y-2">
              {TEMPLATES.map((t) => (
                <label key={t.key} className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="radio"
                    name="template_key"
                    value={t.key}
                    checked={settings.template_key === t.key}
                    onChange={() => setSettings((s) => ({ ...s, template_key: t.key }))}
                    className="size-4"
                  />
                  <span className="text-sm">{t.label}</span>
                </label>
              ))}
            </div>
          </Card>

          {/* Colors */}
          <Card className="p-4">
            <h2 className="font-semibold mb-3">Brand Colors</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Primary</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={settings.primary_color}
                    onChange={(e) => setSettings((s) => ({ ...s, primary_color: e.target.value }))}
                    className="h-9 w-14 rounded border cursor-pointer"
                  />
                  <span className="text-sm font-mono text-muted-foreground">{settings.primary_color}</span>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Secondary</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={settings.secondary_color}
                    onChange={(e) => setSettings((s) => ({ ...s, secondary_color: e.target.value }))}
                    className="h-9 w-14 rounded border cursor-pointer"
                  />
                  <span className="text-sm font-mono text-muted-foreground">{settings.secondary_color}</span>
                </div>
              </div>
            </div>
          </Card>

          {/* Content options */}
          {Object.entries(groupedOptions).map(([group, opts]) => (
            <Card key={group} className="p-4">
              <h2 className="font-semibold mb-3">{group}</h2>
              <div className="space-y-2.5">
                {opts.map((opt) => (
                  <label key={opt.key} className="flex items-center gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={Boolean(settings[opt.key])}
                      onChange={() => handleToggle(opt.key)}
                      className="size-4 rounded"
                    />
                    <span className="text-sm">{opt.label}</span>
                  </label>
                ))}
              </div>
            </Card>
          ))}

          {/* Default delivery preference */}
          <Card className="p-4">
            <h2 className="font-semibold mb-1">Default invoice delivery</h2>
            <p className="text-xs text-muted-foreground mb-3">
              Applied to new customers. Individual customer preferences override this.
            </p>
            <div className="space-y-2">
              {DEFAULT_DELIVERY_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-start gap-2.5 cursor-pointer">
                  <input
                    type="radio"
                    name="default_delivery"
                    value={opt.value}
                    checked={defaultDelivery === opt.value}
                    onChange={() => setDefaultDelivery(opt.value)}
                    className="size-4 mt-0.5"
                  />
                  <span>
                    <span className="text-sm font-medium">{opt.label}</span>
                    <span className="block text-xs text-muted-foreground">{opt.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </Card>

          {/* Remit-to + footer */}
          <Card className="p-4">
            <h2 className="font-semibold mb-3">Footer &amp; Remit-to</h2>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Remit-to name (optional)</label>
                <input
                  type="text"
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  placeholder="Leave blank to use company name"
                  value={settings.remit_to_name || ""}
                  onChange={(e) => setSettings((s) => ({ ...s, remit_to_name: e.target.value || null }))}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Custom footer text (optional)</label>
                <textarea
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm resize-none"
                  rows={2}
                  placeholder="e.g. Thank you for your business."
                  value={settings.custom_footer_text || ""}
                  onChange={(e) => setSettings((s) => ({ ...s, custom_footer_text: e.target.value || null }))}
                />
              </div>
            </div>
          </Card>

          <Separator />

          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving}>
              <Save className="w-4 h-4 mr-1.5" />
              {saving ? "Saving..." : "Save settings"}
            </Button>
            <a href={previewBlobUrl ?? "#"} target="_blank" rel="noreferrer">
              <Button variant="outline" disabled={!previewBlobUrl}>
                <ExternalLink className="w-4 h-4 mr-1.5" />
                Preview invoice PDF
              </Button>
            </a>
          </div>
        </div>

        {/* Right column: live preview */}
        <div className="sticky top-4 space-y-2">
          <div className="text-sm font-medium text-muted-foreground">Live preview</div>
          <div className="rounded-lg border overflow-hidden bg-muted" style={{ height: 700 }}>
            {previewBlobUrl ? (
              <iframe
                key={previewBlobUrl}
                src={previewBlobUrl}
                className="w-full h-full border-0"
                title="Invoice preview"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin" />
              </div>
            )}
          </div>
          <a
            href={previewBlobUrl ?? "#"}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground justify-end"
          >
            <ExternalLink className="w-3 h-3" />
            Open full size
          </a>
        </div>
      </div>
    </div>
  );
}
