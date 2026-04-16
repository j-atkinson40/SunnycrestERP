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
import {
  Package,
  Plus,
  Loader2,

  Settings2,
  Trash2,
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
}

// ── Main Component ───────────────────────────────────────────────

export default function ProgramsSettings() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [customLines, setCustomLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPrograms() {
      try {
        const [catalogRes, enrolledRes] = await Promise.all([
          apiClient.get<Program[]>("/onboarding-flow/programs/catalog"),
          apiClient.get<{ programs: Program[]; custom_lines: string[] }>("/programs"),
        ]);

        // Merge catalog with enrollment status
        const enrolledCodes = new Set(
          enrolledRes.data.programs
            .filter((p) => p.enrolled)
            .map((p) => p.code),
        );

        const merged = catalogRes.data.map((p) => ({
          ...p,
          enrolled: enrolledCodes.has(p.code),
        }));

        setPrograms(merged);
        setCustomLines(enrolledRes.data.custom_lines ?? []);
      } catch {
        toast.error("Failed to load programs");
      } finally {
        setLoading(false);
      }
    }
    fetchPrograms();
  }, []);

  const toggleProgram = async (code: string, currentlyEnrolled: boolean) => {
    setSaving(code);
    try {
      if (currentlyEnrolled) {
        // Unenroll — for now we re-post all enrollments minus this one
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

  const enrolledPrograms = programs.filter((p) => p.enrolled);
  const availablePrograms = programs.filter((p) => !p.enrolled);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Programs & Products</h1>
        <p className="mt-1 text-muted-foreground">
          Manage your Wilbert program enrollments and custom product lines.
        </p>
      </div>

      {/* Enrolled Programs */}
      <div>
        <h2 className="mb-3 text-lg font-medium">Active Programs</h2>
        {enrolledPrograms.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No programs enrolled yet. Enable programs below to get started.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {enrolledPrograms.map((program) => (
              <Card key={program.code}>
                <CardContent className="flex items-center gap-4 py-4">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground"
                  >
                    <Package className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{program.name}</span>
                      {program.category === "core" && (
                        <Badge variant="secondary" className="text-xs">Core</Badge>
                      )}
                      <Badge className="text-xs">Active</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{program.description}</p>
                    {program.product_count != null && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {program.product_count} products configured
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      <Settings2 className="mr-1 h-3.5 w-3.5" />
                      Configure
                    </Button>
                    {program.category !== "core" && (
                      <Switch
                        checked
                        onCheckedChange={() => toggleProgram(program.code, true)}
                        disabled={saving === program.code}
                      />
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Available Programs */}
      {availablePrograms.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-medium">Available Programs</h2>
          <div className="space-y-3">
            {availablePrograms.map((program) => (
              <Card
                key={program.code}
                className="opacity-75 transition-opacity hover:opacity-100"
              >
                <CardContent className="flex items-center gap-4 py-4">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"
                  >
                    <Package className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <span className="font-medium">{program.name}</span>
                    <p className="text-sm text-muted-foreground">{program.description}</p>
                  </div>
                  <Switch
                    checked={false}
                    onCheckedChange={() => toggleProgram(program.code, false)}
                    disabled={saving === program.code}
                  />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Custom Product Lines */}
      <div>
        <h2 className="mb-3 text-lg font-medium">Custom Product Lines</h2>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Non-Wilbert Product Lines</CardTitle>
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
                <Button variant="ghost" size="sm" onClick={() => removeCustomLine(idx)}>
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
