import { useEffect, useState } from "react";
import { toast } from "sonner";

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
import { Switch } from "@/components/ui/switch";
import apiClient from "@/lib/api-client";
import ProgramSettingsPanel from "@/components/programs/ProgramSettingsPanel";
import {
  Package,
  Plus,
  Loader2,
  Settings2,
  Trash2,
  Sparkles,
  FileText,
  AlertCircle,
  ChevronRight,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────

interface Program {
  code: string;
  name: string;
  description: string;
  category: string;
  enrolled: boolean;
  territory_code?: string;
  product_count?: number;
  enrollment_id?: string;
}

interface PlatformProgramStatus {
  code: string;
  config_complete: boolean;
  attention_message?: string;
}

// ── Main Component ───────────────────────────────────────────────

export default function ProgramsSettings() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [customLines, setCustomLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [openPanelCode, setOpenPanelCode] = useState<string | null>(null);
  const [platformStatus, setPlatformStatus] = useState<Record<string, PlatformProgramStatus>>({});

  useEffect(() => {
    async function fetchPrograms() {
      try {
        const [catalogRes, enrolledRes] = await Promise.all([
          apiClient.get<Program[]>("/onboarding-flow/programs/catalog"),
          apiClient.get<{ programs: Program[]; custom_lines: string[] }>("/programs"),
        ]);

        // Merge catalog with enrollment status
        const enrolledMap = new Map(
          enrolledRes.data.programs
            .filter((p) => p.enrolled)
            .map((p) => [p.code, p]),
        );

        const merged = catalogRes.data.map((p) => ({
          ...p,
          enrolled: enrolledMap.has(p.code),
          enrollment_id: enrolledMap.get(p.code)?.enrollment_id,
        }));

        setPrograms(merged);
        setCustomLines(enrolledRes.data.custom_lines ?? []);
      } catch {
        toast.error("Failed to load programs");
      } finally {
        setLoading(false);
      }
    }

    async function fetchPlatformStatus() {
      try {
        const { data } = await apiClient.get<PlatformProgramStatus[]>(
          "/programs/platform-status"
        );
        const map: Record<string, PlatformProgramStatus> = {};
        for (const s of data) {
          map[s.code] = s;
        }
        setPlatformStatus(map);
      } catch {
        // Non-critical
      }
    }

    fetchPrograms();
    fetchPlatformStatus();
  }, []);

  const toggleProgram = async (code: string, currentlyEnrolled: boolean) => {
    setSaving(code);
    try {
      if (currentlyEnrolled) {
        const enrollments = programs
          .filter((p) => p.enrolled && p.code !== code)
          .map((p) => ({ code: p.code }));
        await apiClient.post("/onboarding-flow/steps/programs", {
          enrollments,
          custom_lines: customLines.filter(Boolean),
        });
      } else {
        await apiClient.post(`/programs/${code}/enroll`, {});
      }

      setPrograms((prev) =>
        prev.map((p) =>
          p.code === code ? { ...p, enrolled: !currentlyEnrolled } : p,
        ),
      );
      toast.success(
        currentlyEnrolled
          ? `Removed ${programs.find((p) => p.code === code)?.name}`
          : `Enrolled in ${programs.find((p) => p.code === code)?.name}`,
      );
    } catch {
      toast.error("Failed to update program");
    } finally {
      setSaving(null);
    }
  };

  const addCustomLine = () => {
    setCustomLines((prev) => [...prev, ""]);
  };

  const updateCustomLine = (index: number, value: string) => {
    setCustomLines((prev) => {
      const updated = [...prev];
      updated[index] = value;
      return updated;
    });
  };

  const removeCustomLine = (index: number) => {
    setCustomLines((prev) => prev.filter((_, i) => i !== index));
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Separate program categories
  const wilbertPrograms = programs.filter((p) =>
    ["vault", "urn", "casket", "monument", "chemical"].includes(p.code)
  );
  const enrolledWilbert = wilbertPrograms.filter((p) => p.enrolled);
  const availableWilbert = wilbertPrograms.filter((p) => !p.enrolled);

  const digitalStatus = platformStatus["digital_products"];
  const stationeryStatus = platformStatus["stationery"];

  // If a panel is open, show it
  if (openPanelCode) {
    const program = programs.find((p) => p.code === openPanelCode);
    return (
      <div className="space-y-6 p-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpenPanelCode(null)}
        >
          <ChevronRight className="mr-1 h-4 w-4 rotate-180" />
          Back to Programs
        </Button>
        <ProgramSettingsPanel
          programCode={openPanelCode}
          enrollmentId={program?.enrollment_id ?? openPanelCode}
          mode="settings"
          onClose={() => setOpenPanelCode(null)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Programs & Products</h1>
        <p className="mt-1 text-muted-foreground">
          Manage your platform programs, Wilbert program enrollments, and custom product lines.
        </p>
      </div>

      {/* SECTION 1: Included in Your Platform */}
      <div>
        <h2 className="mb-3 text-lg font-medium">Included in Your Platform</h2>
        <div className="space-y-3">
          {/* Digital Products */}
          <Card>
            <CardContent className="flex items-center gap-4 py-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Sparkles className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Digital Products</span>
                  <Badge variant="secondary" className="text-xs">
                    Included
                  </Badge>
                  {digitalStatus && !digitalStatus.config_complete && (
                    <Badge
                      variant="outline"
                      className="border-amber-300 bg-amber-50 text-xs text-amber-700 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
                    >
                      <AlertCircle className="mr-1 h-3 w-3" />
                      {digitalStatus.attention_message ?? "Bank account not connected"}
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  Territory revenue generated automatically. No handling required.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOpenPanelCode("digital_products")}
              >
                <Settings2 className="mr-1 h-3.5 w-3.5" />
                Settings
              </Button>
            </CardContent>
          </Card>

          {/* Stationery */}
          <Card>
            <CardContent className="flex items-center gap-4 py-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Stationery</span>
                  <Badge variant="secondary" className="text-xs">
                    Included
                  </Badge>
                  {stationeryStatus && !stationeryStatus.config_complete && (
                    <Badge
                      variant="outline"
                      className="border-amber-300 bg-amber-50 text-xs text-amber-700 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
                    >
                      <AlertCircle className="mr-1 h-3 w-3" />
                      {stationeryStatus.attention_message ?? "Fulfillment contact not set"}
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  Personalized stationery products for funeral homes.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOpenPanelCode("stationery")}
              >
                <Settings2 className="mr-1 h-3.5 w-3.5" />
                Settings
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* SECTION 2: Your Wilbert Programs */}
      <div>
        <h2 className="mb-3 text-lg font-medium">Your Wilbert Programs</h2>

        {/* Enrolled */}
        {enrolledWilbert.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No Wilbert programs enrolled yet. Enable programs below to get started.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {enrolledWilbert.map((program) => (
              <Card key={program.code}>
                <CardContent className="flex items-center gap-4 py-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                    <Package className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{program.name}</span>
                      {program.category === "core" && (
                        <Badge variant="secondary" className="text-xs">
                          Core
                        </Badge>
                      )}
                      <Badge className="text-xs">Active</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {program.description}
                    </p>
                    {program.product_count != null && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {program.product_count} products configured
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setOpenPanelCode(program.code)}
                    >
                      <Settings2 className="mr-1 h-3.5 w-3.5" />
                      Settings
                    </Button>
                    {program.category !== "core" && (
                      <Switch
                        checked
                        onCheckedChange={() =>
                          toggleProgram(program.code, true)
                        }
                        disabled={saving === program.code}
                      />
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Available */}
        {availableWilbert.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              Available Programs
            </h3>
            <div className="space-y-3">
              {availableWilbert.map((program) => (
                <Card
                  key={program.code}
                  className="opacity-75 transition-opacity hover:opacity-100"
                >
                  <CardContent className="flex items-center gap-4 py-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                      <Package className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <span className="font-medium">{program.name}</span>
                      <p className="text-sm text-muted-foreground">
                        {program.description}
                      </p>
                    </div>
                    <Switch
                      checked={false}
                      onCheckedChange={() =>
                        toggleProgram(program.code, false)
                      }
                      disabled={saving === program.code}
                    />
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Custom Product Lines */}
      <div>
        <h2 className="mb-3 text-lg font-medium">Custom Product Lines</h2>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Non-Wilbert Product Lines
            </CardTitle>
            <CardDescription>
              Add product lines outside of the Wilbert program catalog.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {customLines.map((line, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <Input
                  value={line}
                  onChange={(e) => updateCustomLine(idx, e.target.value)}
                  placeholder="e.g. Septic Tanks, Retaining Walls"
                  className="flex-1"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeCustomLine(idx)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}

            {customLines.length === 0 && (
              <p className="py-4 text-center text-sm text-muted-foreground">
                No custom product lines added.
              </p>
            )}

            <Button variant="outline" className="w-full" onClick={addCustomLine}>
              <Plus className="mr-2 h-4 w-4" />
              Add Product Line
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
