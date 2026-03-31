import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  CheckCircle,
  ChevronRight,
  ExternalLink,
  Image,
  Loader2,
  Palette,
  Upload,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BrandingData {
  logo_url: string | null;
  website: string | null;
  detected_logo_url: string | null;
  detected_logo_confidence: number | null;
  detected_primary_color: string | null;
  detected_secondary_color: string | null;
  detected_colors: string[];
}

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
}

const TEMPLATES = [
  {
    key: "professional",
    label: "Professional",
    description: "Classic header band with your brand color, traditional layout.",
  },
  {
    key: "clean_minimal",
    label: "Clean & Minimal",
    description: "White background, colored accents, modern whitespace.",
  },
  {
    key: "modern",
    label: "Modern",
    description: "Bold hero block, accent strip, contemporary style.",
  },
];

const CONTENT_OPTIONS: Array<{
  key: keyof InvoiceSettings;
  label: string;
  description: string;
  group: string;
}> = [
  { key: "show_deceased_name",        label: "Deceased name (RE: Smith, John)", description: "", group: "Customer & service information" },
  { key: "show_cemetery_on_invoice",  label: "Cemetery name",                  description: "", group: "Customer & service information" },
  { key: "show_service_date",         label: "Service date",                   description: "", group: "Customer & service information" },
  { key: "show_order_number",         label: "Order / S/O number",             description: "", group: "Customer & service information" },
  { key: "show_payment_terms",        label: "Payment terms (Net 30 days)",    description: "", group: "Payment information" },
  { key: "show_early_payment_discount", label: "Early payment discount (5%/15 days)", description: "", group: "Payment information" },
  { key: "show_finance_charge_notice",  label: "Finance charge notice (2%/month)", description: "", group: "Payment information" },
  { key: "show_remittance_stub",       label: "Remittance stub (tear-off)",    description: "", group: "Payment information" },
  { key: "show_phone",                label: "Phone number",                   description: "", group: "Your contact information" },
  { key: "show_email",                label: "Email address",                  description: "", group: "Your contact information" },
  { key: "show_website",              label: "Website",                        description: "", group: "Your contact information" },
];

// ---------------------------------------------------------------------------
// Step indicator
// ---------------------------------------------------------------------------

function StepDots({ step }: { step: number }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {["Logo & Colors", "Template", "Content"].map((label, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
              i < step
                ? "bg-green-500 text-white"
                : i === step
                ? "bg-primary text-white"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {i < step ? <CheckCircle className="w-4 h-4" /> : i + 1}
          </div>
          <span
            className={`text-sm ${i === step ? "font-semibold text-foreground" : "text-muted-foreground"}`}
          >
            {label}
          </span>
          {i < 2 && <ChevronRight className="w-4 h-4 text-muted-foreground" />}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Color swatch
// ---------------------------------------------------------------------------

function ColorSwatch({
  color,
  selected,
  onClick,
}: {
  color: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-8 h-8 rounded-full border-2 transition-all ${
        selected ? "border-foreground scale-110" : "border-transparent"
      }`}
      style={{ backgroundColor: color }}
      title={color}
    />
  );
}

// ---------------------------------------------------------------------------
// Template card
// ---------------------------------------------------------------------------

function TemplateCard({
  template,
  selected,
  onSelect,
}: {
  template: (typeof TEMPLATES)[0];
  selected: boolean;
  onSelect: () => void;
}) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    // Lazy load preview URL
    const url = `/api/v1/sales/invoices/template-preview?template=${template.key}&format=pdf`;
    setPdfUrl(url);
  }, [template.key]);

  return (
    <>
      <Card
        className={`flex flex-col overflow-hidden cursor-pointer transition-all ${
          selected ? "ring-2 ring-primary" : "hover:ring-1 hover:ring-border"
        }`}
      >
        {/* PDF preview iframe */}
        <div
          className="relative bg-muted border-b"
          style={{ height: 280 }}
          onClick={() => setModalOpen(true)}
          title="Click to view full size"
        >
          {pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              title={`${template.label} preview`}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          )}
          <div className="absolute bottom-1 right-1 opacity-60 hover:opacity-100">
            <ExternalLink className="w-3.5 h-3.5 text-muted-foreground" />
          </div>
        </div>

        <div className="p-4 flex flex-col gap-2 flex-1">
          <div className="font-semibold text-sm">{template.label}</div>
          <p className="text-xs text-muted-foreground flex-1">{template.description}</p>
          <Button
            size="sm"
            variant={selected ? "default" : "outline"}
            onClick={onSelect}
            className="w-full mt-1"
          >
            {selected ? "Selected" : "Select this template"}
          </Button>
        </div>
      </Card>

      {/* Full-size modal */}
      {modalOpen && pdfUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
          onClick={() => setModalOpen(false)}
        >
          <div
            className="bg-white rounded-lg overflow-hidden shadow-2xl"
            style={{ width: "min(90vw, 900px)", height: "min(90vh, 1100px)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-2 border-b">
              <span className="font-medium text-sm">{template.label} — Preview</span>
              <Button variant="ghost" size="sm" onClick={() => setModalOpen(false)}>Close</Button>
            </div>
            <iframe src={pdfUrl} className="w-full border-0" style={{ height: "calc(100% - 40px)" }} title="Full preview" />
          </div>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CompanyBrandingPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Branding data
  const [branding, setBranding] = useState<BrandingData | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [primaryColor, setPrimaryColor] = useState("#1B4F8A");
  const [secondaryColor, setSecondaryColor] = useState("#2D9B8A");
  const [uploadingLogo, setUploadingLogo] = useState(false);

  // Template + settings
  const [templateKey, setTemplateKey] = useState("professional");
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
  });
  const [previewKey, setPreviewKey] = useState(0); // increment to force iframe reload
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load branding data
  useEffect(() => {
    async function load() {
      try {
        const [brandRes, settingsRes] = await Promise.all([
          apiClient.get("/sales/company/branding"),
          apiClient.get("/sales/invoice-settings"),
        ]);
        const b: BrandingData = brandRes.data;
        setBranding(b);
        setLogoUrl(b.logo_url || b.detected_logo_url || null);
        const s: InvoiceSettings = settingsRes.data;
        setSettings(s);
        setTemplateKey(s.template_key || "professional");
        setPrimaryColor(b.detected_primary_color || s.primary_color || "#1B4F8A");
        setSecondaryColor(b.detected_secondary_color || s.secondary_color || "#2D9B8A");
      } catch (err) {
        toast.error(getApiErrorMessage(err, "Failed to load branding settings"));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Debounce preview refresh on settings change
  useEffect(() => {
    if (step !== 2) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setPreviewKey((k) => k + 1), 1000);
  }, [settings, step]);

  const handleLogoUpload = useCallback(async (file: File) => {
    setUploadingLogo(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiClient.post("/sales/company/logo-upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setLogoUrl(res.data.logo_url);
      toast.success("Logo uploaded");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Upload failed"));
    } finally {
      setUploadingLogo(false);
    }
  }, []);

  const handleConfirmDetectedLogo = useCallback(async () => {
    if (!branding?.detected_logo_url) return;
    try {
      await apiClient.patch("/sales/company/branding", {
        logo_url: branding.detected_logo_url,
      });
      setLogoUrl(branding.detected_logo_url);
      toast.success("Logo confirmed");
      setStep(1);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save logo"));
    }
  }, [branding]);

  const handleSaveLogoAndColors = useCallback(async () => {
    setSaving(true);
    try {
      await apiClient.patch("/sales/company/branding", {
        logo_url: logoUrl,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
      });
      setStep(1);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save branding"));
    } finally {
      setSaving(false);
    }
  }, [logoUrl, primaryColor, secondaryColor]);

  const handleSelectTemplate = useCallback((key: string) => {
    setTemplateKey(key);
    setSettings((s) => ({ ...s, template_key: key }));
    setStep(2);
  }, []);

  const handleToggleSetting = useCallback((key: keyof InvoiceSettings) => {
    setSettings((s) => ({ ...s, [key]: !s[key as keyof typeof s] }));
  }, []);

  const handleSaveAndFinish = useCallback(async () => {
    setSaving(true);
    try {
      await apiClient.patch("/sales/invoice-settings", {
        ...settings,
        template_key: templateKey,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
      });
      // Mark checklist item complete
      await apiClient.patch("/tenant-onboarding/checklist/items/company_branding", {
        status: "completed",
      });
      toast.success("Invoice template saved!");
      navigate("/onboarding");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save settings"));
    } finally {
      setSaving(false);
    }
  }, [settings, templateKey, primaryColor, secondaryColor, navigate]);

  // Build preview URL for live preview in step 2
  const previewUrl = `/api/v1/sales/invoices/template-preview?template=${templateKey}&format=pdf&options=${encodeURIComponent(
    JSON.stringify({
      ...settings,
      template_key: templateKey,
      primary_color: primaryColor,
      secondary_color: secondaryColor,
    })
  )}&_k=${previewKey}`;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const detectedColors = branding?.detected_colors || [];
  const hasDetectedLogo = Boolean(branding?.detected_logo_url);

  // Group content options
  const optionGroups = CONTENT_OPTIONS.reduce<Record<string, typeof CONTENT_OPTIONS>>(
    (acc, opt) => {
      if (!acc[opt.group]) acc[opt.group] = [];
      acc[opt.group].push(opt);
      return acc;
    },
    {}
  );

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Breadcrumb */}
      <Link to="/onboarding" className="text-sm text-muted-foreground hover:underline">
        &larr; Onboarding
      </Link>

      <div>
        <h1 className="text-2xl font-bold">Set up your brand</h1>
        <p className="text-muted-foreground mt-1">
          We'll use your logo and colors to generate professional invoice templates.
        </p>
      </div>

      <StepDots step={step} />

      {/* ── STEP 0: Logo & Colors ───────────────────────────────────── */}
      {step === 0 && (
        <div className="space-y-6 max-w-2xl">
          {/* Logo section */}
          <Card className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <Image className="w-4 h-4 text-muted-foreground" />
              <h2 className="font-semibold">Your Logo</h2>
            </div>

            {hasDetectedLogo ? (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  We found this image on your website. Is this your logo?
                </p>
                <div className="rounded-lg border bg-muted/30 flex items-center justify-center p-6">
                  <img
                    src={branding!.detected_logo_url!}
                    alt="Detected logo"
                    className="max-h-24 max-w-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Found on your website
                  {branding?.detected_logo_confidence
                    ? ` (${Math.round(branding.detected_logo_confidence * 100)}% confidence)`
                    : ""}
                </p>
                <div className="flex gap-2">
                  <Button onClick={handleConfirmDetectedLogo}>
                    Yes, use this logo
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    No, upload a different one
                  </Button>
                </div>
              </div>
            ) : logoUrl ? (
              <div className="space-y-4">
                <div className="rounded-lg border bg-muted/30 flex items-center justify-center p-6">
                  <img
                    src={logoUrl}
                    alt="Company logo"
                    className="max-h-24 max-w-full object-contain"
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="w-4 h-4 mr-1.5" />
                    Replace logo
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Upload your logo. PNG, JPG, or SVG recommended.
                </p>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full rounded-lg border-2 border-dashed border-muted-foreground/30 hover:border-primary/50 p-8 flex flex-col items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Upload className="w-6 h-6" />
                  <span className="text-sm font-medium">Click to upload logo</span>
                  <span className="text-xs">PNG, JPG, SVG, WebP · Max 5MB</span>
                </button>
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.svg,.webp"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) await handleLogoUpload(file);
                e.target.value = "";
              }}
            />
          </Card>

          {/* Color section */}
          <Card className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <Palette className="w-4 h-4 text-muted-foreground" />
              <h2 className="font-semibold">Brand Colors</h2>
            </div>

            {detectedColors.length > 0 ? (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  We detected these colors from your website:
                </p>
                <div className="flex flex-wrap gap-2">
                  {detectedColors.map((c) => (
                    <ColorSwatch
                      key={c}
                      color={c}
                      selected={primaryColor === c}
                      onClick={() => setPrimaryColor(c)}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            <div className="grid grid-cols-2 gap-4 mt-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Primary color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="h-9 w-16 rounded border cursor-pointer"
                  />
                  <span className="text-sm text-muted-foreground font-mono">
                    {primaryColor}
                  </span>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Secondary color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    className="h-9 w-16 rounded border cursor-pointer"
                  />
                  <span className="text-sm text-muted-foreground font-mono">
                    {secondaryColor}
                  </span>
                </div>
              </div>
            </div>
          </Card>

          <div className="flex gap-2">
            <Button onClick={handleSaveLogoAndColors} disabled={saving}>
              {saving ? "Saving..." : "Continue"}
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
            <Button variant="ghost" onClick={() => setStep(1)}>
              Skip for now
            </Button>
          </div>
        </div>
      )}

      {/* ── STEP 1: Template Selection ──────────────────────────────── */}
      {step === 1 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold">Choose your invoice style</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Select a template. You can customize the content in the next step.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4">
            {TEMPLATES.map((t) => (
              <TemplateCard
                key={t.key}
                template={t}
                selected={templateKey === t.key}
                onSelect={() => handleSelectTemplate(t.key)}
              />
            ))}
          </div>

          {/* Back */}
          <Button variant="ghost" onClick={() => setStep(0)}>
            &larr; Back
          </Button>
        </div>
      )}

      {/* ── STEP 2: Content Customization ──────────────────────────── */}
      {step === 2 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold">Customize your invoice</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Configure what appears on invoices and statements sent to funeral homes.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Left: checkboxes */}
            <div className="space-y-6">
              {Object.entries(optionGroups).map(([group, opts]) => (
                <Card key={group} className="p-4">
                  <h3 className="text-sm font-semibold mb-3">{group}</h3>
                  <div className="space-y-2.5">
                    {opts.map((opt) => (
                      <label
                        key={opt.key}
                        className="flex items-center gap-2.5 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={Boolean(settings[opt.key])}
                          onChange={() => handleToggleSetting(opt.key)}
                          className="size-4 rounded"
                        />
                        <span className="text-sm">{opt.label}</span>
                      </label>
                    ))}
                  </div>
                </Card>
              ))}

              <div className="flex gap-2">
                <Button onClick={handleSaveAndFinish} disabled={saving}>
                  {saving ? "Saving..." : "Save and finish"}
                  <CheckCircle className="w-4 h-4 ml-1.5" />
                </Button>
                <Button variant="ghost" onClick={() => setStep(1)}>
                  &larr; Back
                </Button>
              </div>
            </div>

            {/* Right: live preview */}
            <div className="sticky top-4 space-y-2">
              <div className="text-sm font-medium text-muted-foreground">
                Live preview
              </div>
              <div className="rounded-lg border overflow-hidden bg-muted" style={{ height: 600 }}>
                <iframe
                  key={previewUrl}
                  src={previewUrl}
                  className="w-full h-full border-0"
                  title="Invoice preview"
                />
              </div>
              <div className="flex justify-end">
                <a
                  href={previewUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                >
                  <ExternalLink className="w-3 h-3" />
                  Open full size
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
