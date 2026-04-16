import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import apiClient from "@/lib/api-client";
import {
  Building2,
  MapPin,
  Package,
  ShieldCheck,
  Users,
  Link as LinkIcon,
  Sparkles,
  Upload,
  Rocket,
  ChevronLeft,
  ChevronRight,
  SkipForward,
  Check,
  Plus,
  Trash2,
  Loader2,
  Search,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  Command,
  Globe,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ── Types ────────────────────────────────────────────────────────

interface StepDef {
  key: string;
  label: string;
  icon: LucideIcon;
  skippable: boolean;
}

interface FlowStatus {
  status: string;
  current_step: string;
  completed_steps: string[];
  skipped_steps?: string[];
  visible_steps?: string[];
  percent_complete: number;
  // Existing-data flags (backend populates when endpoints are up-to-date)
  has_existing_orders?: boolean;
  has_existing_crm?: boolean;
  has_existing_users?: boolean;
  has_existing_location?: boolean;
  should_show_import?: boolean;
  existing_order_count?: number;
  existing_crm_count?: number;
  existing_user_count?: number;
  existing_location_count?: number;
}

interface ProgramCard {
  code: string;
  name: string;
  description: string;
  default_enrolled: boolean;
  category: string;
}

interface ComplianceQuestion {
  key: string;
  label: string;
  type: "number" | "boolean";
  hint?: string;
}

interface ComplianceItem {
  key: string;
  label: string;
  category: string;
  description: string;
  frequency?: string;
  triggered_by?: string[];
}

interface DiscoveredFH {
  name: string;
  address: string;
  phone?: string;
  source: string;
  selected: boolean;
}

interface DiscoveredCemetery {
  name: string;
  address: string;
  selected: boolean;
}

interface LocationEntry {
  name: string;
  type: string;
  address: string;
  city: string;
  state: string;
  zip: string;
}

interface TeamInvite {
  email: string;
  name: string;
  role: string;
  location?: string;
}

interface VaultSeedSummary {
  programs_configured: number;
  compliance_items: number;
  funeral_homes_connected: number;
  team_invited: number;
  orders_imported: number;
  time_saved_estimate: string;
}

// ── Step definitions ─────────────────────────────────────────────

const STEPS: StepDef[] = [
  { key: "identity", label: "Your Business", icon: Building2, skippable: false },
  { key: "locations", label: "Locations", icon: MapPin, skippable: true },
  { key: "programs", label: "Programs", icon: Package, skippable: true },
  { key: "compliance", label: "Compliance", icon: ShieldCheck, skippable: true },
  { key: "team", label: "Team", icon: Users, skippable: true },
  { key: "network", label: "Network", icon: LinkIcon, skippable: true },
  { key: "command_bar", label: "Command Bar", icon: Sparkles, skippable: false },
  { key: "import", label: "Import", icon: Upload, skippable: true },
  { key: "complete", label: "Complete", icon: Rocket, skippable: false },
];

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
  "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
  "VA","WA","WV","WI","WY",
];

// ── Main Flow Component ──────────────────────────────────────────

export default function OnboardingFlow() {
  const { company, user } = useAuth();
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [flowStatus, setFlowStatus] = useState<FlowStatus | null>(null);

  // Fetch flow status on mount
  useEffect(() => {
    async function fetchStatus() {
      try {
        const { data } = await apiClient.get<FlowStatus>("/onboarding-flow/status");
        setFlowStatus(data);
        setCompletedSteps(new Set(data.completed_steps));
        // Compute step sequence (with import filtered if not needed), then locate current_step
        const visible = data.visible_steps && data.visible_steps.length > 0
          ? data.visible_steps
          : STEPS.map((s) => s.key);
        const filteredSteps = STEPS.filter((s) => visible.includes(s.key));
        const idx = filteredSteps.findIndex((s) => s.key === data.current_step);
        if (idx >= 0) setCurrentStepIndex(idx);
      } catch {
        // Fresh start — stay at step 0
      } finally {
        setLoading(false);
      }
    }
    fetchStatus();
  }, []);

  // Build the visible step sequence based on status flags.
  // When orders already exist, the import step is hidden entirely.
  const visibleStepKeys = flowStatus?.visible_steps && flowStatus.visible_steps.length > 0
    ? flowStatus.visible_steps
    : STEPS.map((s) => s.key);
  const visibleSteps = STEPS.filter((s) => visibleStepKeys.includes(s.key));
  const currentStep = visibleSteps[currentStepIndex] ?? STEPS[currentStepIndex];

  const goNext = useCallback(() => {
    setCompletedSteps((prev) => {
      const next = new Set(prev);
      next.add(currentStep.key);
      return next;
    });
    if (currentStepIndex < visibleSteps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  }, [currentStep.key, currentStepIndex, visibleSteps.length]);

  const goBack = useCallback(() => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  }, [currentStepIndex]);

  const skipStep = useCallback(() => {
    if (currentStepIndex < visibleSteps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  }, [currentStepIndex, visibleSteps.length]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // ── Step Progress Indicator ──────────────────────────────────
  const renderProgress = () => (
    <div className="mx-auto flex max-w-3xl items-center justify-center gap-1 px-4 py-6">
      {visibleSteps.map((step, idx) => {
        const isComplete = completedSteps.has(step.key);
        const isCurrent = idx === currentStepIndex;
        const Icon = step.icon;
        return (
          <div key={step.key} className="flex items-center">
            <button
              type="button"
              onClick={() => {
                if (isComplete || idx <= currentStepIndex) {
                  setCurrentStepIndex(idx);
                }
              }}
              disabled={!isComplete && idx > currentStepIndex}
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-full transition-all",
                isCurrent && "bg-primary text-primary-foreground ring-2 ring-primary/30",
                isComplete && !isCurrent && "bg-green-500 text-white",
                !isComplete && !isCurrent && "bg-muted text-muted-foreground",
                (isComplete || idx <= currentStepIndex) && "cursor-pointer hover:ring-2 hover:ring-primary/20",
              )}
              title={step.label}
            >
              {isComplete && !isCurrent ? (
                <Check className="h-4 w-4" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
            </button>
            {idx < visibleSteps.length - 1 && (
              <div
                className={cn(
                  "mx-0.5 h-0.5 w-4 rounded-full sm:w-8",
                  isComplete ? "bg-green-500" : "bg-muted",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );

  // ── Navigation Buttons ───────────────────────────────────────
  const renderNav = (opts?: { hideSkip?: boolean; hideNext?: boolean; nextLabel?: string }) => (
    <div className="mt-8 flex items-center justify-between">
      <div>
        {currentStepIndex > 0 && currentStep.key !== "complete" && (
          <Button variant="ghost" onClick={goBack}>
            <ChevronLeft className="mr-1 h-4 w-4" />
            Back
          </Button>
        )}
      </div>
      <div className="flex items-center gap-3">
        {currentStep.skippable && !opts?.hideSkip && (
          <Button variant="ghost" onClick={skipStep} className="text-muted-foreground">
            <SkipForward className="mr-1 h-4 w-4" />
            Skip for now
          </Button>
        )}
        {!opts?.hideNext && (
          <Button onClick={goNext}>
            {opts?.nextLabel ?? "Continue"}
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );

  // ── Render Active Step ───────────────────────────────────────
  const renderStep = () => {
    switch (currentStep.key) {
      case "identity":
        return <IdentityStep company={company} user={user} onComplete={goNext} />;
      case "locations":
        return <LocationsStep onComplete={goNext} renderNav={renderNav} />;
      case "programs":
        return <ProgramsStep onComplete={goNext} renderNav={renderNav} />;
      case "compliance":
        return <ComplianceStep onComplete={goNext} renderNav={renderNav} />;
      case "team":
        return <TeamStep onComplete={goNext} renderNav={renderNav} />;
      case "network":
        return <NetworkStep onComplete={goNext} renderNav={renderNav} />;
      case "command_bar":
        return <CommandBarStep onComplete={goNext} />;
      case "import":
        return <ImportStep onComplete={goNext} renderNav={renderNav} />;
      case "complete":
        return <CompleteStep />;
      default:
        return null;
    }
  };

  // Command bar step gets a full-screen treatment
  if (currentStep.key === "command_bar") {
    return (
      <div className="min-h-screen">
        {renderProgress()}
        {renderStep()}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background pb-12">
      {renderProgress()}
      <div className="mx-auto max-w-2xl px-4">
        {renderStep()}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 1: Identity
// ══════════════════════════════════════════════════════════════════

interface IdentityStepProps {
  company: { name: string; id: string } | null;
  user: { first_name?: string; last_name?: string; phone?: string; email?: string } | null;
  onComplete: () => void;
}

function IdentityStep({ company, user, onComplete }: IdentityStepProps) {
  const [companyName, setCompanyName] = useState(company?.name ?? "");
  const [businessType, setBusinessType] = useState("wilbert_licensee");
  const [territoryCode, setTerritoryCode] = useState("");
  const [state, setState] = useState("");
  const [contactName, setContactName] = useState(
    [user?.first_name, user?.last_name].filter(Boolean).join(" ")
  );
  const [contactPhone, setContactPhone] = useState(user?.phone ?? "");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!companyName.trim()) {
      toast.error("Company name is required");
      return;
    }
    if (!state) {
      toast.error("Please select your state");
      return;
    }
    setSaving(true);
    try {
      await apiClient.post("/onboarding-flow/steps/identity", {
        company_name: companyName,
        business_type: businessType,
        wilbert_vault_territory: businessType === "wilbert_licensee" ? territoryCode : undefined,
        state,
        contact_name: contactName,
        contact_phone: contactPhone,
      });
      onComplete();
    } catch {
      toast.error("Failed to save business information");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Tell us about your business</CardTitle>
        <CardDescription>
          This helps us configure everything correctly from day one. Takes about 60 seconds.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="company-name">Company Name</Label>
          <Input
            id="company-name"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Your Company Name"
          />
        </div>

        <div className="space-y-2">
          <Label>Business Type</Label>
          <Select value={businessType} onValueChange={(v) => v && setBusinessType(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="wilbert_licensee">Wilbert Licensee</SelectItem>
              <SelectItem value="manufacturer">Manufacturer (non-Wilbert)</SelectItem>
              <SelectItem value="distributor">Distributor</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {businessType === "wilbert_licensee" && (
          <div className="space-y-2">
            <Label htmlFor="territory">Wilbert Territory Code</Label>
            <Input
              id="territory"
              value={territoryCode}
              onChange={(e) => setTerritoryCode(e.target.value)}
              placeholder="e.g. NY-14"
            />
            <p className="text-xs text-muted-foreground">
              Found on your Wilbert license agreement. We will use this to auto-discover your funeral home network.
            </p>
          </div>
        )}

        <div className="space-y-2">
          <Label>State</Label>
          <Select value={state} onValueChange={(v) => v && setState(v)}>
            <SelectTrigger>
              <SelectValue placeholder="Select state" />
            </SelectTrigger>
            <SelectContent>
              {US_STATES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="contact-name">Primary Contact</Label>
            <Input
              id="contact-name"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              placeholder="Full name"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contact-phone">Phone</Label>
            <Input
              id="contact-phone"
              value={contactPhone}
              onChange={(e) => setContactPhone(e.target.value)}
              placeholder="(555) 555-5555"
            />
          </div>
        </div>

        <div className="flex justify-end pt-4">
          <Button onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Continue
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 2: Locations
// ══════════════════════════════════════════════════════════════════

interface StepProps {
  onComplete: () => void;
  renderNav: (opts?: { hideSkip?: boolean; hideNext?: boolean; nextLabel?: string }) => React.ReactNode;
}

function LocationsStep({ onComplete, renderNav }: StepProps) {
  const [mode, setMode] = useState<"single" | "multiple" | null>(null);
  const [locations, setLocations] = useState<LocationEntry[]>([
    { name: "", type: "plant", address: "", city: "", state: "", zip: "" },
  ]);
  const [saving, setSaving] = useState(false);

  const updateLocation = (index: number, field: keyof LocationEntry, value: string) => {
    setLocations((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addLocation = () => {
    setLocations((prev) => [
      ...prev,
      { name: "", type: "plant", address: "", city: "", state: "", zip: "" },
    ]);
  };

  const removeLocation = (index: number) => {
    if (locations.length > 1) {
      setLocations((prev) => prev.filter((_, i) => i !== index));
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await apiClient.post("/onboarding-flow/steps/locations", {
        mode: mode ?? "single",
        locations,
      });
      onComplete();
    } catch {
      toast.error("Failed to save locations");
    } finally {
      setSaving(false);
    }
  };

  if (!mode) {
    return (
      <>
        <div className="mb-4 text-center">
          <h2 className="text-xl font-semibold">Where do you operate?</h2>
          <p className="mt-1 text-muted-foreground">
            This helps us set up location-based routing and reporting.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => setMode("single")}
            className={cn(
              "flex flex-col items-center gap-3 rounded-xl border-2 border-dashed p-8 transition-all hover:border-primary hover:bg-primary/5",
            )}
          >
            <MapPin className="h-10 w-10 text-primary" />
            <span className="text-lg font-medium">One Location</span>
            <span className="text-sm text-muted-foreground">
              Single plant or facility
            </span>
          </button>
          <button
            type="button"
            onClick={() => setMode("multiple")}
            className={cn(
              "flex flex-col items-center gap-3 rounded-xl border-2 border-dashed p-8 transition-all hover:border-primary hover:bg-primary/5",
            )}
          >
            <Globe className="h-10 w-10 text-primary" />
            <span className="text-lg font-medium">Multiple Locations</span>
            <span className="text-sm text-muted-foreground">
              Several plants or facilities
            </span>
          </button>
        </div>
        {renderNav()}
      </>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-xl">
              {mode === "single" ? "Your Location" : "Your Locations"}
            </CardTitle>
            <CardDescription>
              {mode === "single"
                ? "Enter your primary facility details."
                : "Add each plant or facility you operate."}
            </CardDescription>
          </div>
          {mode === "multiple" && (
            <Button variant="outline" size="sm" onClick={() => setMode(null)}>
              Change
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {locations.map((loc, idx) => (
          <div key={idx} className="space-y-3 rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                {mode === "multiple" ? `Location ${idx + 1}` : "Primary Location"}
              </span>
              {mode === "multiple" && locations.length > 1 && (
                <Button variant="ghost" size="sm" onClick={() => removeLocation(idx)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Name</Label>
                <Input
                  value={loc.name}
                  onChange={(e) => updateLocation(idx, "name", e.target.value)}
                  placeholder="Main Plant"
                />
              </div>
              <div className="space-y-1">
                <Label>Type</Label>
                <Select value={loc.type} onValueChange={(v) => v && updateLocation(idx, "type", v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="plant">Plant</SelectItem>
                    <SelectItem value="warehouse">Warehouse</SelectItem>
                    <SelectItem value="office">Office</SelectItem>
                    <SelectItem value="showroom">Showroom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1">
              <Label>Street Address</Label>
              <Input
                value={loc.address}
                onChange={(e) => updateLocation(idx, "address", e.target.value)}
                placeholder="123 Main St"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label>City</Label>
                <Input
                  value={loc.city}
                  onChange={(e) => updateLocation(idx, "city", e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label>State</Label>
                <Select value={loc.state} onValueChange={(v) => v && updateLocation(idx, "state", v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="ST" />
                  </SelectTrigger>
                  <SelectContent>
                    {US_STATES.map((s) => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>ZIP</Label>
                <Input
                  value={loc.zip}
                  onChange={(e) => updateLocation(idx, "zip", e.target.value)}
                  placeholder="13021"
                />
              </div>
            </div>
          </div>
        ))}

        {mode === "multiple" && (
          <Button variant="outline" className="w-full" onClick={addLocation}>
            <Plus className="mr-2 h-4 w-4" />
            Add Another Location
          </Button>
        )}

        <div className="flex items-center justify-between pt-2">
          <Button variant="ghost" onClick={() => setMode(null)}>
            <ChevronLeft className="mr-1 h-4 w-4" />
            Back
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Continue
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 3: Programs
// ══════════════════════════════════════════════════════════════════

function ProgramsStep({ onComplete, renderNav }: StepProps) {
  const [catalog, setCatalog] = useState<ProgramCard[]>([]);
  const [enrollments, setEnrollments] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [customLines, setCustomLines] = useState<string[]>([]);

  // Platform-native program inline config state
  const [digitalExpanded, setDigitalExpanded] = useState(false);
  const [stationeryExpanded, setStationeryExpanded] = useState(false);
  const [digitalRevVisibility, setDigitalRevVisibility] = useState<"admin_only" | "all_visible" | "off">("admin_only");
  const [stationeryFulfillment, setStationeryFulfillment] = useState<"bridgeable" | "self_fulfill" | "hybrid">("bridgeable");
  const [stationeryLeadTime, setStationeryLeadTime] = useState(5);

  // Vault personalization inline state
  const [vaultPersonalization, setVaultPersonalization] = useState<"yes" | "no" | null>(null);
  const [vaultProofApproval, setVaultProofApproval] = useState<"yes" | "no" | null>(null);

  useEffect(() => {
    async function fetchCatalog() {
      try {
        const { data } = await apiClient.get<ProgramCard[]>("/onboarding-flow/programs/catalog");
        setCatalog(data);
        const defaults: Record<string, boolean> = {};
        for (const p of data) {
          defaults[p.code] = p.default_enrolled;
        }
        setEnrollments(defaults);
      } catch {
        toast.error("Failed to load program catalog");
      } finally {
        setLoading(false);
      }
    }
    fetchCatalog();
  }, []);

  const toggleProgram = (code: string) => {
    setEnrollments((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      const selected = Object.entries(enrollments)
        .filter(([, v]) => v)
        .map(([code]) => ({ code }));
      await apiClient.post("/onboarding-flow/steps/programs", {
        enrollments: selected,
        custom_lines: customLines.filter(Boolean),
        platform_config: {
          digital_products: { revenue_visibility: digitalRevVisibility },
          stationery: {
            fulfillment_path: stationeryFulfillment,
            lead_time_days: stationeryFulfillment === "self_fulfill" ? stationeryLeadTime : undefined,
          },
        },
        vault_personalization: enrollments["vault"]
          ? {
              enabled: vaultPersonalization === "yes",
              family_proof: vaultProofApproval === "yes",
            }
          : undefined,
      });
      onComplete();
    } catch {
      toast.error("Failed to save program selections");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Separate Wilbert programs from platform-native ones
  const wilbertPrograms = catalog.filter((p) =>
    ["vault", "urn", "casket", "monument", "chemical"].includes(p.code)
  );

  return (
    <>
      <div className="mb-6 text-center">
        <h2 className="text-xl font-semibold">Programs & Revenue Streams</h2>
        <p className="mt-1 text-muted-foreground">
          Platform programs are included automatically. Wilbert programs are configured based on your territory.
        </p>
      </div>

      {/* SECTION 1: Included in Your Platform */}
      <div className="mb-6">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Included in Your Platform
        </p>
        <div className="space-y-3">
          {/* Digital Products */}
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">Digital Products</span>
                    <Badge variant="secondary" className="text-xs">Included</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Territory revenue generated automatically. No handling required.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDigitalExpanded(!digitalExpanded)}
                >
                  {digitalExpanded ? "Close" : "Configure"}
                </Button>
              </div>

              {digitalExpanded && (
                <div className="mt-4 space-y-3 rounded-lg border bg-muted/30 p-4">
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Revenue visibility</Label>
                    <div className="space-y-2">
                      {(
                        [
                          { value: "admin_only", label: "Admin only" },
                          { value: "all_visible", label: "All staff with access" },
                          { value: "off", label: "Hide from briefing" },
                        ] as const
                      ).map((opt) => (
                        <label key={opt.value} className="flex items-center gap-2 text-sm">
                          <input
                            type="radio"
                            name="digital-rev-vis"
                            checked={digitalRevVisibility === opt.value}
                            onChange={() => setDigitalRevVisibility(opt.value)}
                            className="h-4 w-4"
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Payout setup can be configured in Settings after onboarding.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Stationery */}
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">Stationery</span>
                    <Badge variant="secondary" className="text-xs">Included</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Fulfillment: Bridgeable handles by default.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setStationeryExpanded(!stationeryExpanded)}
                >
                  {stationeryExpanded ? "Close" : "Configure"}
                </Button>
              </div>

              {stationeryExpanded && (
                <div className="mt-4 space-y-3 rounded-lg border bg-muted/30 p-4">
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Fulfillment path</Label>
                    <div className="space-y-2">
                      {(
                        [
                          { value: "bridgeable", label: "Bridgeable handles fulfillment (recommended)" },
                          { value: "self_fulfill", label: "We fulfill orders ourselves" },
                          { value: "hybrid", label: "Hybrid (choose per order)" },
                        ] as const
                      ).map((opt) => (
                        <label key={opt.value} className="flex items-center gap-2 text-sm">
                          <input
                            type="radio"
                            name="stationery-fulfill"
                            checked={stationeryFulfillment === opt.value}
                            onChange={() => setStationeryFulfillment(opt.value)}
                            className="h-4 w-4"
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                  </div>
                  {stationeryFulfillment === "self_fulfill" && (
                    <div className="space-y-1">
                      <Label className="text-xs">Lead time (business days)</Label>
                      <Input
                        type="number"
                        min={1}
                        className="w-24"
                        value={stationeryLeadTime}
                        onChange={(e) => setStationeryLeadTime(parseInt(e.target.value) || 5)}
                      />
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* SECTION 2: Your Wilbert Programs */}
      <div className="mb-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Your Wilbert Programs
        </p>
        <div className="space-y-3">
          {wilbertPrograms.map((program) => (
            <Card
              key={program.code}
              className={cn(
                "transition-all",
                enrollments[program.code] && "ring-2 ring-primary",
              )}
            >
              <CardContent className="py-4">
                <div className="flex items-center gap-4">
                  <div
                    className={cn(
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                      enrollments[program.code]
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    <Package className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{program.name}</span>
                      {program.category === "core" && (
                        <Badge variant="secondary" className="text-xs">Core</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">{program.description}</p>
                  </div>
                  <Switch
                    checked={enrollments[program.code] ?? false}
                    onCheckedChange={() => toggleProgram(program.code)}
                    disabled={program.category === "core"}
                  />
                </div>

                {/* Vault personalization inline config */}
                {program.code === "vault" && enrollments["vault"] && (
                  <div className="mt-4 space-y-3 rounded-lg border bg-muted/30 p-4">
                    <div className="space-y-2">
                      <Label className="text-sm font-medium">
                        Do you offer vault personalization?
                      </Label>
                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="radio"
                            name="vault-pers"
                            checked={vaultPersonalization === "yes"}
                            onChange={() => setVaultPersonalization("yes")}
                            className="h-4 w-4"
                          />
                          Yes
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="radio"
                            name="vault-pers"
                            checked={vaultPersonalization === "no"}
                            onChange={() => setVaultPersonalization("no")}
                            className="h-4 w-4"
                          />
                          No
                        </label>
                      </div>
                    </div>

                    {vaultPersonalization === "yes" && (
                      <>
                        <div className="space-y-2">
                          <Label className="text-sm font-medium">
                            Does the family approve a proof before production?
                          </Label>
                          <div className="flex items-center gap-4">
                            <label className="flex items-center gap-2 text-sm">
                              <input
                                type="radio"
                                name="vault-proof"
                                checked={vaultProofApproval === "yes"}
                                onChange={() => setVaultProofApproval("yes")}
                                className="h-4 w-4"
                              />
                              Yes
                            </label>
                            <label className="flex items-center gap-2 text-sm">
                              <input
                                type="radio"
                                name="vault-proof"
                                checked={vaultProofApproval === "no"}
                                onChange={() => setVaultProofApproval("no")}
                                className="h-4 w-4"
                              />
                              No
                            </label>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Configure emblem categories and detailed personalization options in Settings.
                        </p>
                      </>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}

          {/* Custom product lines */}
          <div className="pt-2">
            <button
              type="button"
              onClick={() => setCustomLines((prev) => [...prev, ""])}
              className="flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <Plus className="h-4 w-4" />
              Add a non-Wilbert product line
            </button>
            {customLines.map((line, idx) => (
              <div key={idx} className="mt-2 flex items-center gap-2">
                <Input
                  value={line}
                  onChange={(e) => {
                    const updated = [...customLines];
                    updated[idx] = e.target.value;
                    setCustomLines(updated);
                  }}
                  placeholder="e.g. Septic Tanks, Retaining Walls"
                  className="flex-1"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCustomLines((prev) => prev.filter((_, i) => i !== idx))}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-8 flex items-center justify-between">
        {renderNav({ hideNext: true })}
        <Button onClick={handleSubmit} disabled={saving}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Continue
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 4: Compliance
// ══════════════════════════════════════════════════════════════════

function ComplianceStep({ onComplete, renderNav }: StepProps) {
  const [questions, setQuestions] = useState<ComplianceQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string | number | boolean>>({});
  const [enabledItems, setEnabledItems] = useState<Set<string>>(new Set());
  const [allItems, setAllItems] = useState<ComplianceItem[]>([]);
  const [showMasterList, setShowMasterList] = useState(false);
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customLabel, setCustomLabel] = useState("");
  const [customFreq, setCustomFreq] = useState("");
  const [customItems, setCustomItems] = useState<{ label: string; frequency: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const [qRes, mRes] = await Promise.all([
          apiClient.get<ComplianceQuestion[]>("/onboarding-flow/compliance/questions"),
          apiClient.get<ComplianceItem[]>("/onboarding-flow/compliance/master-list"),
        ]);
        setQuestions(qRes.data);
        setAllItems(mRes.data);
      } catch {
        toast.error("Failed to load compliance data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  // When answers change, compute which compliance items are triggered
  useEffect(() => {
    const triggered = new Set<string>();
    for (const item of allItems) {
      if (!item.triggered_by) continue;
      for (const trigger of item.triggered_by) {
        const val = answers[trigger];
        if (typeof val === "boolean" && val) triggered.add(item.key);
        if (typeof val === "number" && val > 0) triggered.add(item.key);
      }
    }
    setEnabledItems(triggered);
  }, [answers, allItems]);

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await apiClient.post("/onboarding-flow/steps/compliance", {
        items: Array.from(enabledItems),
        answers,
        custom_items: customItems,
      });
      onComplete();
    } catch {
      toast.error("Failed to save compliance configuration");
    } finally {
      setSaving(false);
    }
  };

  const addCustomItem = () => {
    if (customLabel.trim()) {
      setCustomItems((prev) => [...prev, { label: customLabel, frequency: customFreq }]);
      setCustomLabel("");
      setCustomFreq("");
      setShowCustomForm(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <>
      <div className="mb-4 text-center">
        <h2 className="text-xl font-semibold">
          Let us protect you from compliance surprises
        </h2>
        <p className="mt-1 text-muted-foreground">
          Answer a few questions and we will automatically configure the right compliance tracking.
        </p>
      </div>

      {/* Smart Questions */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">Quick Questions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {questions.map((q) => (
            <div key={q.key} className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium">{q.label}</span>
                {q.hint && (
                  <p className="text-xs text-muted-foreground">{q.hint}</p>
                )}
              </div>
              {q.type === "boolean" ? (
                <Switch
                  checked={!!answers[q.key]}
                  onCheckedChange={(checked) =>
                    setAnswers((prev) => ({ ...prev, [q.key]: checked }))
                  }
                />
              ) : (
                <Input
                  type="number"
                  min={0}
                  className="w-20 text-center"
                  value={answers[q.key] as number ?? ""}
                  onChange={(e) =>
                    setAnswers((prev) => ({
                      ...prev,
                      [q.key]: parseInt(e.target.value) || 0,
                    }))
                  }
                />
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Enabled items summary */}
      {enabledItems.size > 0 && (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="text-base">
              Compliance Items Configured
              <Badge className="ml-2">{enabledItems.size + customItems.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {allItems
                .filter((item) => enabledItems.has(item.key))
                .map((item) => (
                  <div
                    key={item.key}
                    className="flex items-center gap-2 text-sm"
                  >
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                    <span>{item.label}</span>
                    {item.frequency && (
                      <Badge variant="outline" className="text-xs">
                        {item.frequency}
                      </Badge>
                    )}
                  </div>
                ))}
              {customItems.map((ci, idx) => (
                <div key={`custom-${idx}`} className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-blue-500" />
                  <span>{ci.label}</span>
                  {ci.frequency && (
                    <Badge variant="outline" className="text-xs">{ci.frequency}</Badge>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-auto h-6 w-6 p-0"
                    onClick={() => setCustomItems((prev) => prev.filter((_, i) => i !== idx))}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add more / Add custom */}
      <div className="flex items-center gap-4 text-sm">
        <button
          type="button"
          onClick={() => setShowMasterList(!showMasterList)}
          className="flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <Plus className="h-4 w-4" />
          Add more
        </button>
        <button
          type="button"
          onClick={() => setShowCustomForm(!showCustomForm)}
          className="flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <Plus className="h-4 w-4" />
          Add custom
        </button>
      </div>

      {/* Master list */}
      {showMasterList && (
        <Card className="mt-3">
          <CardContent className="max-h-60 space-y-2 overflow-y-auto py-3">
            {allItems
              .filter((item) => !enabledItems.has(item.key))
              .map((item) => (
                <div
                  key={item.key}
                  className="flex cursor-pointer items-center gap-2 rounded-md p-2 text-sm hover:bg-muted"
                  onClick={() => setEnabledItems((prev) => new Set([...prev, item.key]))}
                >
                  <Plus className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span>{item.label}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {item.category}
                  </span>
                </div>
              ))}
          </CardContent>
        </Card>
      )}

      {/* Custom form */}
      {showCustomForm && (
        <Card className="mt-3">
          <CardContent className="flex items-end gap-3 py-3">
            <div className="flex-1 space-y-1">
              <Label className="text-xs">Item Name</Label>
              <Input
                value={customLabel}
                onChange={(e) => setCustomLabel(e.target.value)}
                placeholder="e.g. Annual fire suppression check"
              />
            </div>
            <div className="w-32 space-y-1">
              <Label className="text-xs">Frequency</Label>
              <Input
                value={customFreq}
                onChange={(e) => setCustomFreq(e.target.value)}
                placeholder="Annual"
              />
            </div>
            <Button size="sm" onClick={addCustomItem} disabled={!customLabel.trim()}>
              Add
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="mt-8 flex items-center justify-between">
        <div>{renderNav({ hideNext: true, hideSkip: true })}</div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onComplete} className="text-muted-foreground">
            <SkipForward className="mr-1 h-4 w-4" />
            Skip for now
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Continue
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 5: Team
// ══════════════════════════════════════════════════════════════════

function TeamStep({ onComplete, renderNav }: StepProps) {
  const [invites, setInvites] = useState<TeamInvite[]>([
    { email: "", name: "", role: "employee" },
  ]);
  const [saving, setSaving] = useState(false);

  const updateInvite = (index: number, field: keyof TeamInvite, value: string) => {
    setInvites((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addInvite = () => {
    setInvites((prev) => [...prev, { email: "", name: "", role: "employee" }]);
  };

  const removeInvite = (index: number) => {
    if (invites.length > 1) {
      setInvites((prev) => prev.filter((_, i) => i !== index));
    }
  };

  const handleSubmit = async () => {
    const valid = invites.filter((inv) => inv.email.trim());
    if (valid.length === 0) {
      onComplete();
      return;
    }
    setSaving(true);
    try {
      await apiClient.post("/onboarding-flow/steps/team", {
        invitations: valid,
      });
      toast.success(`Invited ${valid.length} team member${valid.length > 1 ? "s" : ""}`);
      onComplete();
    } catch {
      toast.error("Failed to send invitations");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="mb-4 text-center">
        <h2 className="text-xl font-semibold">Invite your team</h2>
        <p className="mt-1 text-muted-foreground">
          Add the people who will use Bridgeable day-to-day. You can always add more later.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 py-4">
          {invites.map((inv, idx) => (
            <div key={idx} className="flex items-start gap-3">
              <div className="grid flex-1 grid-cols-3 gap-2">
                <div className="space-y-1">
                  <Label className="text-xs">Name</Label>
                  <Input
                    value={inv.name}
                    onChange={(e) => updateInvite(idx, "name", e.target.value)}
                    placeholder="John Doe"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Email</Label>
                  <Input
                    type="email"
                    value={inv.email}
                    onChange={(e) => updateInvite(idx, "email", e.target.value)}
                    placeholder="john@example.com"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Role</Label>
                  <Select value={inv.role} onValueChange={(v) => v && updateInvite(idx, "role", v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="office">Office Staff</SelectItem>
                      <SelectItem value="employee">Employee</SelectItem>
                      <SelectItem value="driver">Driver</SelectItem>
                      <SelectItem value="production">Production</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {invites.length > 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-5"
                  onClick={() => removeInvite(idx)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          ))}

          <Button variant="outline" className="w-full" onClick={addInvite}>
            <Plus className="mr-2 h-4 w-4" />
            Add Another Person
          </Button>
        </CardContent>
      </Card>

      <div className="mt-8 flex items-center justify-between">
        <div>{renderNav({ hideNext: true, hideSkip: true })}</div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onComplete} className="text-muted-foreground">
            <SkipForward className="mr-1 h-4 w-4" />
            Skip for now
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {invites.some((inv) => inv.email.trim()) ? "Send Invites" : "Continue"}
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 6: Network Discovery
// ══════════════════════════════════════════════════════════════════

function NetworkStep({ onComplete, renderNav }: StepProps) {
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState(false);
  const [funeralHomes, setFuneralHomes] = useState<DiscoveredFH[]>([]);
  const [cemeteries, setCemeteries] = useState<DiscoveredCemetery[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function discover() {
      setDiscovering(true);
      try {
        const { data } = await apiClient.post<{
          funeral_homes: DiscoveredFH[];
          cemeteries: DiscoveredCemetery[];
        }>("/onboarding-flow/network/discover", {});
        setFuneralHomes(data.funeral_homes.map((fh) => ({ ...fh, selected: true })));
        setCemeteries(data.cemeteries.map((c) => ({ ...c, selected: true })));
        setDiscovered(true);
      } catch {
        toast.error("Network discovery failed. You can add connections manually later.");
        setDiscovered(true);
      } finally {
        setDiscovering(false);
      }
    }
    discover();
  }, []);

  const toggleFH = (index: number) => {
    setFuneralHomes((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], selected: !updated[index].selected };
      return updated;
    });
  };

  const toggleCemetery = (index: number) => {
    setCemeteries((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], selected: !updated[index].selected };
      return updated;
    });
  };

  const selectAllFH = () => {
    setFuneralHomes((prev) => prev.map((fh) => ({ ...fh, selected: true })));
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await apiClient.post("/onboarding-flow/steps/network", {
        funeral_homes: funeralHomes.filter((fh) => fh.selected),
        cemeteries: cemeteries.filter((c) => c.selected),
      });
      onComplete();
    } catch {
      toast.error("Failed to save network connections");
    } finally {
      setSaving(false);
    }
  };

  if (discovering) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <div className="relative mb-6">
          <div className="h-16 w-16 animate-ping rounded-full bg-primary/20" />
          <Search className="absolute left-1/2 top-1/2 h-8 w-8 -translate-x-1/2 -translate-y-1/2 text-primary" />
        </div>
        <h2 className="text-xl font-semibold">Discovering your network...</h2>
        <p className="mt-2 text-muted-foreground">
          Searching Wilbert network, NFDA directory, and state licensing databases
        </p>
      </div>
    );
  }

  if (!discovered) return null;

  return (
    <>
      <div className="mb-4 text-center">
        <h2 className="text-xl font-semibold">Connect your funeral home network</h2>
        <p className="mt-1 text-muted-foreground">
          We found {funeralHomes.length} funeral homes and {cemeteries.length} cemeteries in your area.
        </p>
      </div>

      {/* Funeral Homes */}
      {funeralHomes.length > 0 && (
        <Card className="mb-4">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                Funeral Homes ({funeralHomes.filter((f) => f.selected).length} selected)
              </CardTitle>
              <Button variant="outline" size="sm" onClick={selectAllFH}>
                Select All
              </Button>
            </div>
          </CardHeader>
          <CardContent className="max-h-64 space-y-2 overflow-y-auto">
            {funeralHomes.map((fh, idx) => (
              <div
                key={idx}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-all",
                  fh.selected ? "border-primary bg-primary/5" : "border-transparent hover:bg-muted",
                )}
                onClick={() => toggleFH(idx)}
              >
                <div
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded border",
                    fh.selected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground",
                  )}
                >
                  {fh.selected && <Check className="h-3 w-3" />}
                </div>
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium">{fh.name}</span>
                  <p className="truncate text-xs text-muted-foreground">{fh.address}</p>
                </div>
                <Badge variant="outline" className="text-xs">
                  {fh.source}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Cemeteries */}
      {cemeteries.length > 0 && (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="text-base">
              Cemeteries ({cemeteries.filter((c) => c.selected).length} selected)
            </CardTitle>
          </CardHeader>
          <CardContent className="max-h-48 space-y-2 overflow-y-auto">
            {cemeteries.map((cem, idx) => (
              <div
                key={idx}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-all",
                  cem.selected ? "border-primary bg-primary/5" : "border-transparent hover:bg-muted",
                )}
                onClick={() => toggleCemetery(idx)}
              >
                <div
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded border",
                    cem.selected ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground",
                  )}
                >
                  {cem.selected && <Check className="h-3 w-3" />}
                </div>
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium">{cem.name}</span>
                  <p className="truncate text-xs text-muted-foreground">{cem.address}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="mt-8 flex items-center justify-between">
        <div>{renderNav({ hideNext: true, hideSkip: true })}</div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onComplete} className="text-muted-foreground">
            <SkipForward className="mr-1 h-4 w-4" />
            Skip for now
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Continue
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 7: Command Bar
// ══════════════════════════════════════════════════════════════════

function CommandBarStep({ onComplete }: { onComplete: () => void }) {
  const [seconds, setSeconds] = useState(30);
  const [opened, setOpened] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        setOpened(true);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleComplete = async () => {
    try {
      await apiClient.post("/onboarding-flow/steps/command-bar", { completed: true });
    } catch {
      // Non-critical
    }
    onComplete();
  };

  const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
  const modKey = isMac ? "\u2318" : "Ctrl";

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center bg-slate-950 px-4 text-white">
      <div className="text-center">
        <Sparkles className="mx-auto mb-6 h-12 w-12 text-amber-400" />
        <h1 className="text-3xl font-bold">Your command center</h1>
        <p className="mx-auto mt-3 max-w-md text-lg text-slate-300">
          Press{" "}
          <kbd className="rounded-md border border-slate-600 bg-slate-800 px-2 py-1 font-mono text-sm">
            {modKey}+K
          </kbd>{" "}
          from anywhere to search, navigate, or take action using natural language.
        </p>

        <div className="mt-10">
          {!opened ? (
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-6 py-3 text-slate-400">
                <Command className="h-4 w-4" />
                <span>Try it now — press {modKey}+K</span>
              </div>
              <p className="text-sm text-slate-500">
                {seconds > 0
                  ? `Or wait ${seconds}s to continue`
                  : "Ready to continue"}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-xl border border-green-700 bg-green-900/40 px-6 py-3 text-green-400">
                <CheckCircle2 className="h-5 w-5" />
                <span>Nice! You have got the hang of it.</span>
              </div>
            </div>
          )}
        </div>

        <div className="mt-10">
          <Button
            onClick={handleComplete}
            disabled={!opened && seconds > 0}
            variant="secondary"
            className="px-8"
          >
            Continue
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 8: Import
// ══════════════════════════════════════════════════════════════════

function ImportStep({ onComplete, renderNav }: StepProps) {
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [summary, setSummary] = useState<{
    total_rows: number;
    revenue_estimate: string;
    top_products: string[];
    top_customers: string[];
    date_range: string;
  } | null>(null);
  const [saving, setSaving] = useState(false);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) setFile(selected);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setAnalyzing(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post<{
        session_id: string;
        total_rows: number;
        revenue_estimate: string;
        top_products: string[];
        top_customers: string[];
        date_range: string;
      }>("/data-import/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setSessionId(data.session_id);
      setSummary(data);
      setAnalysisComplete(true);
    } catch {
      toast.error("Failed to analyze file. Please check the format and try again.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleImport = async () => {
    if (!sessionId) return;
    setSaving(true);
    try {
      await apiClient.post("/onboarding-flow/steps/import", {
        import_session_id: sessionId,
      });
      toast.success("Data imported successfully");
      onComplete();
    } catch {
      toast.error("Import failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="mb-4 text-center">
        <h2 className="text-xl font-semibold">Do you have historical data to bring in?</h2>
        <p className="mt-1 text-muted-foreground">
          Upload a CSV or Excel file from your current system. We will match products and customers automatically.
        </p>
      </div>

      {!analysisComplete ? (
        <Card>
          <CardContent className="py-6">
            {!file ? (
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                className="flex flex-col items-center gap-4 rounded-xl border-2 border-dashed p-12 text-center transition-colors hover:border-primary/50"
              >
                <FileSpreadsheet className="h-12 w-12 text-muted-foreground" />
                <div>
                  <p className="font-medium">Drop your file here</p>
                  <p className="text-sm text-muted-foreground">CSV or Excel, up to 50MB</p>
                </div>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                  <span className="text-sm font-medium text-primary hover:underline">
                    Or browse files
                  </span>
                </label>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <FileSpreadsheet className="h-8 w-8 text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setFile(null)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
                <Button className="w-full" onClick={handleAnalyze} disabled={analyzing}>
                  {analyzing ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Search className="mr-2 h-4 w-4" />
                      Analyze File
                    </>
                  )}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      ) : summary ? (
        <>
          {/* Business Intelligence Summary */}
          <Card className="mb-4">
            <CardHeader>
              <CardTitle className="text-base">Business Intelligence</CardTitle>
              <CardDescription>Here is what we found in your data</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg bg-muted p-3">
                  <p className="text-xs text-muted-foreground">Total Records</p>
                  <p className="text-lg font-semibold">{summary.total_rows.toLocaleString()}</p>
                </div>
                <div className="rounded-lg bg-muted p-3">
                  <p className="text-xs text-muted-foreground">Revenue Estimate</p>
                  <p className="text-lg font-semibold">{summary.revenue_estimate}</p>
                </div>
                <div className="rounded-lg bg-muted p-3">
                  <p className="text-xs text-muted-foreground">Date Range</p>
                  <p className="text-lg font-semibold">{summary.date_range}</p>
                </div>
                <div className="rounded-lg bg-muted p-3">
                  <p className="text-xs text-muted-foreground">Top Products</p>
                  <p className="text-sm font-medium">
                    {summary.top_products.slice(0, 3).join(", ")}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="mb-4">
            <CardContent className="py-4">
              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 shrink-0 text-amber-500" />
                <p className="text-sm text-muted-foreground">
                  For detailed product and customer matching, visit the{" "}
                  <a href="/onboarding/import-matching" className="font-medium text-primary hover:underline">
                    Import Matching
                  </a>{" "}
                  page after completing setup.
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="flex items-center justify-end gap-3">
            <Button variant="outline" onClick={onComplete}>
              Skip Import
            </Button>
            <Button onClick={handleImport} disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Import Data
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </>
      ) : null}

      {!analysisComplete && renderNav()}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════
// STEP 9: Complete
// ══════════════════════════════════════════════════════════════════

function CompleteStep() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<VaultSeedSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function finalize() {
      try {
        await apiClient.post("/onboarding-flow/steps/complete", {});
        const { data } = await apiClient.get<VaultSeedSummary>("/onboarding-flow/vault-seed-summary");
        setSummary(data);
      } catch {
        // Non-critical — show default summary
      } finally {
        setLoading(false);
      }
    }
    finalize();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="mt-4 text-muted-foreground">Finalizing your setup...</p>
      </div>
    );
  }

  return (
    <div className="text-center">
      <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-100">
        <Rocket className="h-10 w-10 text-green-600" />
      </div>

      <h1 className="text-2xl font-bold">You are all set!</h1>
      <p className="mx-auto mt-2 max-w-md text-muted-foreground">
        Your Bridgeable workspace is configured and ready to go. Here is a summary of what we set up.
      </p>

      {summary && (
        <div className="mx-auto mt-8 grid max-w-lg grid-cols-2 gap-4">
          <Card>
            <CardContent className="py-4 text-center">
              <p className="text-2xl font-bold text-primary">{summary.programs_configured}</p>
              <p className="text-xs text-muted-foreground">Programs Configured</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4 text-center">
              <p className="text-2xl font-bold text-primary">{summary.compliance_items}</p>
              <p className="text-xs text-muted-foreground">Compliance Items</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4 text-center">
              <p className="text-2xl font-bold text-primary">{summary.funeral_homes_connected}</p>
              <p className="text-xs text-muted-foreground">Funeral Homes</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="py-4 text-center">
              <p className="text-2xl font-bold text-primary">{summary.orders_imported}</p>
              <p className="text-xs text-muted-foreground">Orders Imported</p>
            </CardContent>
          </Card>
        </div>
      )}

      {summary?.time_saved_estimate && (
        <p className="mt-6 text-sm text-muted-foreground">
          Estimated time saved: <strong>{summary.time_saved_estimate}</strong>
        </p>
      )}

      <div className="mt-10">
        <Button size="lg" onClick={() => navigate("/")}>
          Enter Bridgeable
          <ChevronRight className="ml-2 h-5 w-5" />
        </Button>
      </div>
    </div>
  );
}
