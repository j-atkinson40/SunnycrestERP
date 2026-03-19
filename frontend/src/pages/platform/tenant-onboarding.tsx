import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  listVerticalPresets,
  onboardTenant,
} from "@/services/platform-service";
import type { VerticalPreset } from "@/types/platform";
import {
  Factory,
  Heart,
  TreePine,
  Flame,
  CheckCircle2,
  Puzzle,
  ArrowRight,
  Snowflake,
  Sun,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { CardContent } from "@/components/ui/card";

// ── US States ────────────────────────────────────────────────────────────────

const US_STATES = [
  { value: "AL", label: "Alabama" }, { value: "AK", label: "Alaska" },
  { value: "AZ", label: "Arizona" }, { value: "AR", label: "Arkansas" },
  { value: "CA", label: "California" }, { value: "CO", label: "Colorado" },
  { value: "CT", label: "Connecticut" }, { value: "DE", label: "Delaware" },
  { value: "FL", label: "Florida" }, { value: "GA", label: "Georgia" },
  { value: "HI", label: "Hawaii" }, { value: "ID", label: "Idaho" },
  { value: "IL", label: "Illinois" }, { value: "IN", label: "Indiana" },
  { value: "IA", label: "Iowa" }, { value: "KS", label: "Kansas" },
  { value: "KY", label: "Kentucky" }, { value: "LA", label: "Louisiana" },
  { value: "ME", label: "Maine" }, { value: "MD", label: "Maryland" },
  { value: "MA", label: "Massachusetts" }, { value: "MI", label: "Michigan" },
  { value: "MN", label: "Minnesota" }, { value: "MS", label: "Mississippi" },
  { value: "MO", label: "Missouri" }, { value: "MT", label: "Montana" },
  { value: "NE", label: "Nebraska" }, { value: "NV", label: "Nevada" },
  { value: "NH", label: "New Hampshire" }, { value: "NJ", label: "New Jersey" },
  { value: "NM", label: "New Mexico" }, { value: "NY", label: "New York" },
  { value: "NC", label: "North Carolina" }, { value: "ND", label: "North Dakota" },
  { value: "OH", label: "Ohio" }, { value: "OK", label: "Oklahoma" },
  { value: "OR", label: "Oregon" }, { value: "PA", label: "Pennsylvania" },
  { value: "RI", label: "Rhode Island" }, { value: "SC", label: "South Carolina" },
  { value: "SD", label: "South Dakota" }, { value: "TN", label: "Tennessee" },
  { value: "TX", label: "Texas" }, { value: "UT", label: "Utah" },
  { value: "VT", label: "Vermont" }, { value: "VA", label: "Virginia" },
  { value: "WA", label: "Washington" }, { value: "WV", label: "West Virginia" },
  { value: "WI", label: "Wisconsin" }, { value: "WY", label: "Wyoming" },
];

// ── NPCA Certification Options ───────────────────────────────────────────────

const NPCA_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "certified", label: "Certified" },
  { value: "pursuing", label: "Pursuing certification" },
  { value: "wilbert_only", label: "Wilbert standards only" },
  { value: "not_certified", label: "Not certified" },
];

// ── Spring Burials Options ───────────────────────────────────────────────────

const SPRING_BURIALS_OPTIONS = [
  { value: "unknown", label: "Unknown \u2014 ask during onboarding" },
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
];

// ── Preset visual config ─────────────────────────────────────────────────────

const PRESET_ICONS: Record<string, typeof Factory> = {
  manufacturing: Factory,
  funeral_home: Heart,
  cemetery: TreePine,
  crematory: Flame,
};

const PRESET_COLORS: Record<string, { ring: string; bg: string; text: string }> = {
  manufacturing: { ring: "ring-slate-500", bg: "bg-slate-50", text: "text-slate-700" },
  funeral_home: { ring: "ring-stone-500", bg: "bg-stone-50", text: "text-stone-700" },
  cemetery: { ring: "ring-green-700", bg: "bg-green-50", text: "text-green-800" },
  crematory: { ring: "ring-red-800", bg: "bg-red-50", text: "text-red-900" },
};

/**
 * Human-readable module labels for the preset confirmation screen.
 * These map the module keys from the preset configuration to
 * business-language names that an admin understands.
 */
const MODULE_LABELS: Record<string, string> = {
  ai_command_bar: "AI Command Bar",
  customers: "Customers & Contacts",
  sales: "Orders & Invoicing",
  driver_delivery: "Delivery Scheduling",
  inventory: "Basic Inventory",
  daily_production_log: "Daily Production Log",
  safety_management: "Safety & OSHA",
  funeral_home: "Case Management, FTC Compliance, Vault Ordering, Family Portal & Invoicing",
  core: "Core Platform",
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

// ── Collapsible Section ──────────────────────────────────────────────────────

function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold hover:bg-muted/50"
      >
        {title}
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {open && <div className="border-t px-4 pb-4 pt-3">{children}</div>}
    </div>
  );
}

// ── Steps ────────────────────────────────────────────────────────────────────

function getSteps(preset: string | null): string[] {
  if (preset === "manufacturing") {
    return ["Company Details", "Choose Vertical", "Configure", "Confirm & Create"];
  }
  return ["Company Details", "Choose Vertical", "Confirm & Create"];
}

// ── Component ────────────────────────────────────────────────────────────────

export default function TenantOnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [presets, setPresets] = useState<VerticalPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Step 1: Company details
  const [form, setForm] = useState({
    name: "",
    slug: "",
    admin_email: "",
    admin_password: "",
    admin_first_name: "Admin",
    admin_last_name: "User",
    website_url: "",
    // New company information fields
    company_legal_name: "",
    facility_address_line1: "",
    facility_address_line2: "",
    facility_city: "",
    facility_state: "",
    facility_zip: "",
    company_phone: "",
    // Platform intelligence fields
    npca_certification_status: "unknown",
    spring_burials_answer: "unknown",
    // Notes
    internal_admin_notes: "",
  });
  const [slugManual, setSlugManual] = useState(false);

  // Step 2: Vertical
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Step 2.5: Manufacturing configuration (legacy — kept for the step flow)
  const [springBurials, setSpringBurials] = useState<boolean | null>(null);

  const STEPS = getSteps(selectedPreset);
  const isManufacturing = selectedPreset === "manufacturing";
  // The "configure" step is step 2 for manufacturing, confirm is step 3
  // For non-manufacturing, confirm is step 2
  const confirmStep = isManufacturing ? 3 : 2;

  const fetchData = useCallback(async () => {
    try {
      const pres = await listVerticalPresets();
      setPresets(pres);
    } catch {
      toast.error("Failed to load preset data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function handleNameChange(name: string) {
    setForm((f) => ({
      ...f,
      name,
      slug: slugManual ? f.slug : slugify(name),
    }));
  }

  function canProceed(): boolean {
    if (step === 0) {
      const baseValid = !!(
        form.name.trim() &&
        form.slug.trim() &&
        form.admin_email.trim() &&
        form.admin_password.length >= 6
      );
      // If manufacturing is already selected, require address fields
      // But we don't know preset yet at step 0, so just require base fields
      return baseValid;
    }
    if (step === 1) return selectedPreset !== null;
    // Manufacturing config step — must answer spring burial question
    if (step === 2 && isManufacturing) return springBurials !== null;
    return true;
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      // Build initial settings from configuration questions
      const initialSettings: Record<string, unknown> = {
        onboarding_questions_completed: true,
      };
      if (isManufacturing) {
        initialSettings.spring_burials_enabled = springBurials === true;
      }

      const result = await onboardTenant({
        name: form.name,
        slug: form.slug,
        vertical: selectedPreset,
        admin_email: form.admin_email,
        admin_password: form.admin_password,
        admin_first_name: form.admin_first_name,
        admin_last_name: form.admin_last_name,
        initial_settings: initialSettings,
        website_url: form.website_url || undefined,
        company_legal_name: form.company_legal_name || undefined,
        facility_address_line1: form.facility_address_line1 || undefined,
        facility_address_line2: form.facility_address_line2 || undefined,
        facility_city: form.facility_city || undefined,
        facility_state: form.facility_state || undefined,
        facility_zip: form.facility_zip || undefined,
        company_phone: form.company_phone || undefined,
        npca_certification_status: form.npca_certification_status !== "unknown" ? form.npca_certification_status : undefined,
        spring_burials_answer: form.spring_burials_answer !== "unknown" ? form.spring_burials_answer : undefined,
        internal_admin_notes: form.internal_admin_notes || undefined,
      });

      // No manual module selection — the backend onboardTenant endpoint
      // reads the preset configuration and activates the correct modules.

      toast.success(`Tenant "${form.name}" created successfully!`);
      navigate(`/tenants/${result.tenant_id}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to create tenant";
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      toast.error(axiosErr.response?.data?.detail || message);
    } finally {
      setSubmitting(false);
    }
  }

  const activePreset = presets.find((p) => p.key === selectedPreset);
  const presetColor = selectedPreset
    ? PRESET_COLORS[selectedPreset] || PRESET_COLORS.manufacturing
    : null;
  const PresetIcon = selectedPreset
    ? PRESET_ICONS[selectedPreset] || Factory
    : Factory;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-indigo-600" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Create New Tenant</h1>
        <p className="text-muted-foreground">
          Set up a new tenant — modules are configured automatically from the
          selected preset.
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                i === step
                  ? "bg-indigo-600 text-white"
                  : i < step
                    ? "bg-indigo-100 text-indigo-700"
                    : "bg-gray-100 text-gray-400"
              }`}
            >
              {i < step ? "\u2713" : i + 1}
            </div>
            <span
              className={`text-sm ${
                i === step ? "font-medium text-gray-900" : "text-gray-500"
              }`}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <div className="mx-2 h-px w-8 bg-gray-200" />
            )}
          </div>
        ))}
      </div>

      {/* ── Step 1: Company Details ── */}
      {step === 0 && (
        <div className="space-y-4">
          {/* Account Setup */}
          <Card className="p-6">
            <h2 className="mb-4 text-lg font-semibold">Account Setup</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Company Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="Acme Vault Co."
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Subdomain <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.slug}
                  onChange={(e) => {
                    setSlugManual(true);
                    setForm((f) => ({ ...f, slug: e.target.value }));
                  }}
                  placeholder="acme-vault"
                  className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                />
                <p className="mt-1 text-xs text-gray-500">
                  {form.slug || "..."}.yourplatform.com
                </p>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Admin Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={form.admin_email}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, admin_email: e.target.value }))
                  }
                  placeholder="admin@company.com"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Admin Password <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={form.admin_password}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, admin_password: e.target.value }))
                  }
                  placeholder="Min 6 characters"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Admin First Name
                </label>
                <input
                  type="text"
                  value={form.admin_first_name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, admin_first_name: e.target.value }))
                  }
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Admin Last Name
                </label>
                <input
                  type="text"
                  value={form.admin_last_name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, admin_last_name: e.target.value }))
                  }
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
            </div>
          </Card>

          {/* Company Information */}
          <Card className="p-6">
            <h2 className="mb-4 text-lg font-semibold">Company Information</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium">
                  Company Legal Name
                </label>
                <input
                  type="text"
                  value={form.company_legal_name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, company_legal_name: e.target.value }))
                  }
                  placeholder="Acme Vault Manufacturing, Inc."
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium">
                  Facility Address Line 1
                </label>
                <input
                  type="text"
                  value={form.facility_address_line1}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, facility_address_line1: e.target.value }))
                  }
                  placeholder="123 Industrial Blvd"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium">
                  Facility Address Line 2
                </label>
                <input
                  type="text"
                  value={form.facility_address_line2}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, facility_address_line2: e.target.value }))
                  }
                  placeholder="Suite 100"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  City
                </label>
                <input
                  type="text"
                  value={form.facility_city}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, facility_city: e.target.value }))
                  }
                  placeholder="Springfield"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    State
                  </label>
                  <select
                    value={form.facility_state}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, facility_state: e.target.value }))
                    }
                    className="w-full rounded-md border px-3 py-2 text-sm"
                  >
                    <option value="">Select state</option>
                    {US_STATES.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Zip Code
                  </label>
                  <input
                    type="text"
                    value={form.facility_zip}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, facility_zip: e.target.value }))
                    }
                    placeholder="12345"
                    className="w-full rounded-md border px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Company Phone
                </label>
                <input
                  type="tel"
                  value={form.company_phone}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, company_phone: e.target.value }))
                  }
                  placeholder="(555) 123-4567"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
            </div>
          </Card>

          {/* Platform Intelligence (collapsible, open by default) */}
          <CollapsibleSection title="Platform Intelligence" defaultOpen={true}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium">
                  Website URL
                </label>
                <input
                  type="url"
                  value={form.website_url}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, website_url: e.target.value }))
                  }
                  placeholder="https://www.example.com"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
                <p className="mt-1 text-xs text-gray-500">
                  We'll scan this to suggest products during onboarding
                </p>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  NPCA Certification Status
                </label>
                <select
                  value={form.npca_certification_status}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, npca_certification_status: e.target.value }))
                  }
                  className="w-full rounded-md border px-3 py-2 text-sm"
                >
                  {NPCA_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  Only relevant for manufacturing presets
                </p>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Spring Burials
                </label>
                <select
                  value={form.spring_burials_answer}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, spring_burials_answer: e.target.value }))
                  }
                  className="w-full rounded-md border px-3 py-2 text-sm"
                >
                  {SPRING_BURIALS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  Only relevant for manufacturing presets
                </p>
              </div>
            </div>
          </CollapsibleSection>

          {/* Notes (collapsible, closed by default) */}
          <CollapsibleSection title="Notes" defaultOpen={false}>
            <div>
              <label className="mb-1 block text-sm font-medium">
                Internal Notes
              </label>
              <textarea
                value={form.internal_admin_notes}
                onChange={(e) =>
                  setForm((f) => ({ ...f, internal_admin_notes: e.target.value }))
                }
                placeholder="Internal notes about this tenant (not visible to tenant)..."
                rows={4}
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
          </CollapsibleSection>
        </div>
      )}

      {/* ── Step 2: Choose Vertical ── */}
      {step === 1 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Choose Business Vertical</h2>
          <p className="text-sm text-gray-500">
            The preset determines which modules are active and how the platform
            is configured. The tenant can enable additional extensions during
            onboarding.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {presets.map((preset) => {
              const colors = PRESET_COLORS[preset.key] || PRESET_COLORS.manufacturing;
              const Icon = PRESET_ICONS[preset.key] || Factory;
              const isSelected = selectedPreset === preset.key;
              return (
                <Card
                  key={preset.key}
                  className={`cursor-pointer p-5 transition-all hover:shadow-md ${
                    isSelected
                      ? `ring-2 ${colors.ring} ${colors.bg}`
                      : "hover:border-gray-300"
                  }`}
                  onClick={() => setSelectedPreset(preset.key)}
                >
                  <div className="mb-3 flex items-center gap-3">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-lg ${colors.bg}`}
                    >
                      <Icon className={`h-5 w-5 ${colors.text}`} />
                    </div>
                    <div>
                      <h3 className="font-semibold">{preset.name}</h3>
                      {isSelected && (
                        <Badge className="mt-0.5 bg-indigo-600 text-white text-[10px]">
                          Selected
                        </Badge>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-gray-500">{preset.description}</p>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Step 2.5: Manufacturing Configuration ── */}
      {step === 2 && isManufacturing && (
        <div className="space-y-6">
          <h2 className="text-lg font-semibold">Configure Manufacturing</h2>
          <div>
            <h3 className="mb-2 text-base font-medium">
              Do you manage spring burials?
            </h3>
            <p className="mb-4 text-sm text-muted-foreground">
              Some cemeteries close in winter — vault orders are held until
              spring when the cemetery opens.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Card
                className={`cursor-pointer transition-all hover:shadow-md ${
                  springBurials === true
                    ? "ring-2 ring-blue-500 bg-blue-50"
                    : "hover:border-gray-300"
                }`}
                onClick={() => setSpringBurials(true)}
              >
                <CardContent className="flex flex-col items-center gap-3 pt-6 pb-4 text-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
                    <Snowflake className="h-6 w-6 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-semibold">Yes, we have spring burials</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Some of our cemeteries close in winter — we hold vaults
                      for spring delivery
                    </p>
                  </div>
                </CardContent>
              </Card>
              <Card
                className={`cursor-pointer transition-all hover:shadow-md ${
                  springBurials === false
                    ? "ring-2 ring-green-500 bg-green-50"
                    : "hover:border-gray-300"
                }`}
                onClick={() => setSpringBurials(false)}
              >
                <CardContent className="flex flex-col items-center gap-3 pt-6 pb-4 text-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
                    <Sun className="h-6 w-6 text-green-600" />
                  </div>
                  <div>
                    <p className="font-semibold">No spring burials</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Our cemeteries stay open year-round
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm & Create ── */}
      {step === confirmStep && activePreset && presetColor && (
        <div className="space-y-6">
          {/* Tenant summary */}
          <Card className="p-6">
            <h2 className="mb-4 text-lg font-semibold">Review & Create</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-gray-500">Company</p>
                <p className="text-lg font-semibold">{form.name}</p>
                <p className="text-sm text-gray-500 font-mono">{form.slug}</p>
                {form.company_legal_name && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Legal: {form.company_legal_name}
                  </p>
                )}
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Vertical</p>
                <div className="mt-1 flex items-center gap-2">
                  <PresetIcon className={`h-4 w-4 ${presetColor.text}`} />
                  <span className="text-lg font-semibold">
                    {activePreset.name}
                  </span>
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Admin User</p>
                <p>
                  {form.admin_first_name} {form.admin_last_name}
                </p>
                <p className="text-sm text-gray-500">{form.admin_email}</p>
              </div>
              {(form.facility_city || form.facility_state) && (
                <div>
                  <p className="text-sm font-medium text-gray-500">Location</p>
                  <p className="text-sm">
                    {[form.facility_address_line1, form.facility_city, form.facility_state, form.facility_zip]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                </div>
              )}
            </div>
          </Card>

          {/* Preset confirmation — what's included */}
          <Card className={`p-6 border-l-4 ${presetColor.ring.replace("ring-", "border-l-")}`}>
            <h3 className="mb-1 text-base font-semibold">
              Here&apos;s what&apos;s included in the {activePreset.name} plan
            </h3>
            <p className="mb-4 text-sm text-gray-500">
              These modules are activated automatically based on the preset. The
              tenant can enable additional extensions during onboarding.
            </p>

            {/* Included by default */}
            <div className="mb-6">
              <h4 className="mb-2 text-sm font-medium text-gray-700">
                Included by default
              </h4>
              <ul className="space-y-2">
                {activePreset.module_keys.map((key) => (
                  <li key={key} className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                    <span className="text-sm">
                      {MODULE_LABELS[key] || key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Available as extensions */}
            <div className="rounded-lg bg-gray-50 p-4">
              <div className="flex items-start gap-2">
                <Puzzle className="mt-0.5 h-4 w-4 text-gray-400 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-gray-700">
                    Available as extensions
                  </p>
                  <p className="mt-1 text-xs text-gray-500">
                    Additional capabilities are available in the Extension
                    Catalog after setup — including{" "}
                    {selectedPreset === "manufacturing"
                      ? "production planning, product line quoting, and advanced reporting"
                      : selectedPreset === "funeral_home"
                        ? "AI obituary builder, pre-need contracts, and cremation workflow"
                        : "additional operational tools and integrations"}
                    .
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Navigation buttons */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className="rounded-md border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Back
        </button>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">
            Step {step + 1} of {STEPS.length}
          </span>
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={!canProceed()}
              className="flex items-center gap-2 rounded-md bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              Next
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="rounded-md bg-green-600 px-8 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create Tenant"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
