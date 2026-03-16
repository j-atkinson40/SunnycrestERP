import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  listModuleDefinitionsFlat,
  listVerticalPresets,
  onboardTenant,
  bulkSetTenantModules,
} from "@/services/platform-service";
import type {
  ModuleDefinition,
  VerticalPreset,
} from "@/types/platform";

const STEPS = ["Company Details", "Choose Vertical", "Review Modules", "Summary"];

const CATEGORY_LABELS: Record<string, string> = {
  core: "Core (Always Enabled)",
  business: "Business",
  operations: "Operations",
  manufacturing: "Manufacturing",
  funeral: "Funeral Home",
  cemetery: "Cemetery",
  crematory: "Crematory",
  addon: "Add-ons",
};

const CATEGORY_ORDER = ["core", "business", "operations", "manufacturing", "funeral", "cemetery", "crematory", "addon"];

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

export default function TenantOnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [modules, setModules] = useState<ModuleDefinition[]>([]);
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
  });
  const [slugManual, setSlugManual] = useState(false);

  // Step 2: Vertical
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Step 3: Module selection
  const [enabledKeys, setEnabledKeys] = useState<Set<string>>(new Set());

  const coreKeys = useMemo(
    () => new Set(modules.filter((m) => m.is_core).map((m) => m.key)),
    [modules]
  );

  const moduleMap = useMemo(
    () => Object.fromEntries(modules.map((m) => [m.key, m])),
    [modules]
  );

  const fetchData = useCallback(async () => {
    try {
      const [mods, pres] = await Promise.all([
        listModuleDefinitionsFlat(),
        listVerticalPresets(),
      ]);
      setModules(mods);
      setPresets(pres);
      // Initialize with core keys
      setEnabledKeys(new Set(mods.filter((m) => m.is_core).map((m) => m.key)));
    } catch {
      toast.error("Failed to load module data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-slug from name
  function handleNameChange(name: string) {
    setForm((f) => ({
      ...f,
      name,
      slug: slugManual ? f.slug : slugify(name),
    }));
  }

  // When preset is selected, update enabled modules
  function handleSelectPreset(presetKey: string) {
    setSelectedPreset(presetKey);
    const preset = presets.find((p) => p.key === presetKey);
    if (preset) {
      const newKeys = new Set([
        ...Array.from(coreKeys),
        ...preset.module_keys,
      ]);
      setEnabledKeys(newKeys);
    } else {
      setEnabledKeys(new Set(coreKeys));
    }
  }

  // Toggle a module
  function handleToggleModule(key: string) {
    if (coreKeys.has(key)) return;

    setEnabledKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        // Disabling — check dependents
        const dependents = modules.filter(
          (m) => next.has(m.key) && m.dependencies.includes(key)
        );
        if (dependents.length > 0) {
          toast.error(
            `Cannot disable: ${dependents.map((d) => d.name).join(", ")} depend on it`
          );
          return prev;
        }
        next.delete(key);
      } else {
        // Enabling — auto-enable dependencies
        const mod = moduleMap[key];
        if (mod) {
          for (const dep of mod.dependencies) {
            next.add(dep);
          }
        }
        next.add(key);
      }
      return next;
    });
  }

  // Validation
  function canProceed(): boolean {
    if (step === 0) {
      return !!(
        form.name.trim() &&
        form.slug.trim() &&
        form.admin_email.trim() &&
        form.admin_password.length >= 6
      );
    }
    if (step === 1) return selectedPreset !== null;
    return true;
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const result = await onboardTenant({
        name: form.name,
        slug: form.slug,
        vertical: selectedPreset,
        admin_email: form.admin_email,
        admin_password: form.admin_password,
        admin_first_name: form.admin_first_name,
        admin_last_name: form.admin_last_name,
      });

      // Apply custom module selection
      const nonCoreEnabled = Array.from(enabledKeys).filter(
        (k) => !coreKeys.has(k)
      );
      if (nonCoreEnabled.length > 0) {
        await bulkSetTenantModules(result.tenant_id, Array.from(enabledKeys));
      }

      toast.success(`Tenant "${form.name}" created successfully!`);
      navigate(`/tenants/${result.tenant_id}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to create tenant";
      // Try to extract detail from axios error
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      toast.error(axiosErr.response?.data?.detail || message);
    } finally {
      setSubmitting(false);
    }
  }

  // Group modules by category
  const groupedModules = useMemo(() => {
    const groups: Record<string, ModuleDefinition[]> = {};
    for (const cat of CATEGORY_ORDER) {
      const items = modules.filter((m) => m.category === cat);
      if (items.length > 0) groups[cat] = items;
    }
    return groups;
  }, [modules]);

  const enabledCount = enabledKeys.size;
  const totalCount = modules.length;

  if (loading) {
    return <p className="text-muted-foreground">Loading module configuration...</p>;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Onboard New Tenant</h1>
        <p className="text-muted-foreground">
          Set up a new tenant with their business vertical and module configuration.
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
              {i < step ? "✓" : i + 1}
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

      {/* Step 1: Company Details */}
      {step === 0 && (
        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold">Company Details</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">
                Company Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => handleNameChange(e.target.value)}
                placeholder="Acme Corp"
                className="w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                Slug <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.slug}
                onChange={(e) => {
                  setSlugManual(true);
                  setForm((f) => ({ ...f, slug: e.target.value }));
                }}
                placeholder="acme-corp"
                className="w-full rounded-md border px-3 py-2 text-sm font-mono"
              />
              <p className="mt-1 text-xs text-gray-500">
                Used in URLs: {form.slug || "..."}.yourapp.com
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
      )}

      {/* Step 2: Choose Vertical */}
      {step === 1 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Choose Business Vertical</h2>
          <p className="text-sm text-gray-500">
            Select a preset to pre-configure modules for this tenant&apos;s industry.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {presets.map((preset) => (
              <Card
                key={preset.key}
                className={`cursor-pointer p-4 transition-all hover:shadow-md ${
                  selectedPreset === preset.key
                    ? "ring-2 ring-indigo-500 bg-indigo-50"
                    : "hover:border-gray-300"
                }`}
                onClick={() => handleSelectPreset(preset.key)}
              >
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="font-semibold">{preset.name}</h3>
                  {selectedPreset === preset.key && (
                    <Badge className="bg-indigo-600 text-white">Selected</Badge>
                  )}
                </div>
                <p className="mb-3 text-sm text-gray-500">
                  {preset.description}
                </p>
                <p className="text-xs text-gray-400">
                  {preset.module_keys.length > 0
                    ? `${preset.module_keys.length} modules included`
                    : "Start from scratch"}
                </p>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Review Modules */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Review Modules</h2>
              <p className="text-sm text-gray-500">
                {enabledCount} of {totalCount} modules enabled. Toggle modules
                on/off as needed.
              </p>
            </div>
          </div>
          <div className="space-y-6">
            {CATEGORY_ORDER.map((cat) => {
              const items = groupedModules[cat];
              if (!items) return null;
              return (
                <div key={cat}>
                  <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-500">
                    {CATEGORY_LABELS[cat] || cat}
                  </h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {items.map((m) => {
                      const isEnabled = enabledKeys.has(m.key);
                      const isCore = m.is_core;
                      return (
                        <label
                          key={m.key}
                          className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                            isEnabled
                              ? "border-indigo-200 bg-indigo-50/50"
                              : "border-gray-200 bg-white"
                          } ${isCore ? "opacity-75" : "hover:border-indigo-300"}`}
                        >
                          <input
                            type="checkbox"
                            checked={isEnabled}
                            onChange={() => handleToggleModule(m.key)}
                            disabled={isCore}
                            className="mt-0.5 rounded"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">
                                {m.name}
                              </span>
                              {isCore && (
                                <Badge variant="secondary" className="text-[10px]">
                                  Core
                                </Badge>
                              )}
                            </div>
                            {m.description && (
                              <p className="mt-0.5 text-xs text-gray-500 line-clamp-2">
                                {m.description}
                              </p>
                            )}
                            {m.dependencies.length > 0 && (
                              <p className="mt-1 text-[10px] text-gray-400">
                                Requires: {m.dependencies.join(", ")}
                              </p>
                            )}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 4: Summary */}
      {step === 3 && (
        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold">Review & Create</h2>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm font-medium text-gray-500">Company</p>
                <p className="text-lg font-semibold">{form.name}</p>
                <p className="text-sm text-gray-500 font-mono">{form.slug}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Vertical</p>
                <p className="text-lg font-semibold">
                  {presets.find((p) => p.key === selectedPreset)?.name || "Custom"}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Admin User</p>
                <p>
                  {form.admin_first_name} {form.admin_last_name}
                </p>
                <p className="text-sm text-gray-500">{form.admin_email}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Modules</p>
                <p className="text-lg font-semibold">
                  {enabledCount} enabled
                </p>
                <p className="text-sm text-gray-500">of {totalCount} available</p>
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium text-gray-500">
                Enabled Modules
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Array.from(enabledKeys)
                  .sort()
                  .map((key) => {
                    const mod = moduleMap[key];
                    return (
                      <Badge
                        key={key}
                        variant={mod?.is_core ? "secondary" : "default"}
                        className={
                          mod?.is_core
                            ? ""
                            : "bg-indigo-100 text-indigo-800"
                        }
                      >
                        {mod?.name || key}
                      </Badge>
                    );
                  })}
              </div>
            </div>
          </div>
        </Card>
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
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">
            Step {step + 1} of {STEPS.length}
          </span>
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={!canProceed()}
              className="rounded-md bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="rounded-md bg-green-600 px-6 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create Tenant"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
