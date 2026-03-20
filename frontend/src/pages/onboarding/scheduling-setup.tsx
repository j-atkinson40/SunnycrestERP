/**
 * Scheduling Board Setup — 3-question onboarding wizard.
 *
 * 1. Which drivers should appear on the Kanban board? (checkbox list)
 * 2. How do you handle Saturday funeral deliveries? (4 options)
 * 3. How do you handle Sunday funeral deliveries? (2 options)
 */

import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Truck, Calendar, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DriverOption {
  driver_id: string;
  employee_id: string;
  name: string;
}

type SaturdayChoice = "fee" | "spring_only" | "no_charge" | "no_delivery" | null;
type SundayChoice = "surcharge" | "no_delivery" | null;

// ---------------------------------------------------------------------------
// Saturday option definitions
// ---------------------------------------------------------------------------

const SATURDAY_OPTIONS: {
  value: SaturdayChoice;
  label: string;
  desc: string;
  showChargeLink: boolean;
}[] = [
  {
    value: "fee",
    label: "We deliver on Saturdays and charge a Saturday delivery fee",
    desc: "A surcharge is added to all Saturday orders",
    showChargeLink: true,
  },
  {
    value: "spring_only",
    label: "We deliver on Saturdays with a surcharge for spring burials only",
    desc: "The surcharge only applies to orders scheduled from the Spring Burials page — not every Saturday delivery during the spring season",
    showChargeLink: true,
  },
  {
    value: "no_charge",
    label: "We deliver on Saturdays with no extra charge",
    desc: "Saturday orders are scheduled normally",
    showChargeLink: false,
  },
  {
    value: "no_delivery",
    label: "We don't do Saturday deliveries",
    desc: "Saturday orders will show a warning and won't appear on the scheduling board",
    showChargeLink: false,
  },
];

// ---------------------------------------------------------------------------
// Sunday option definitions
// ---------------------------------------------------------------------------

const SUNDAY_OPTIONS: {
  value: SundayChoice;
  label: string;
  desc: string;
  showChargeLink: boolean;
}[] = [
  {
    value: "surcharge",
    label: "We deliver on Sundays with an extra charge",
    desc: "A surcharge is added to Sunday orders",
    showChargeLink: true,
  },
  {
    value: "no_delivery",
    label: "We don't do Sunday deliveries",
    desc: "Sunday orders will show a warning. Monday will be suggested as the next available delivery day.",
    showChargeLink: false,
  },
];

// ---------------------------------------------------------------------------
// Mapping helpers
// ---------------------------------------------------------------------------

function saturdayChoiceToSettings(choice: SaturdayChoice) {
  switch (choice) {
    case "fee":
      return { saturday_delivery_enabled: true, saturday_surcharge_type: "always" as const };
    case "spring_only":
      return { saturday_delivery_enabled: true, saturday_surcharge_type: "spring_burials_only" as const };
    case "no_charge":
      return { saturday_delivery_enabled: true, saturday_surcharge_type: "none" as const };
    case "no_delivery":
      return { saturday_delivery_enabled: false, saturday_surcharge_type: null };
    default:
      return { saturday_delivery_enabled: true, saturday_surcharge_type: null };
  }
}

function settingsToSaturdayChoice(enabled: boolean, surchargeType: string | null): SaturdayChoice {
  if (!enabled) return "no_delivery";
  if (surchargeType === "always") return "fee";
  if (surchargeType === "spring_burials_only") return "spring_only";
  if (surchargeType === "none") return "no_charge";
  return null; // not yet chosen
}

function sundayChoiceToSettings(choice: SundayChoice) {
  switch (choice) {
    case "surcharge":
      return { sunday_delivery_enabled: true, sunday_surcharge_enabled: true };
    case "no_delivery":
      return { sunday_delivery_enabled: false, sunday_surcharge_enabled: false };
    default:
      return { sunday_delivery_enabled: false, sunday_surcharge_enabled: false };
  }
}

function settingsToSundayChoice(enabled: boolean, surcharge: boolean): SundayChoice {
  if (enabled && surcharge) return "surcharge";
  if (!enabled) return "no_delivery";
  return null;
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function SchedulingSetupPage() {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [loadingDrivers, setLoadingDrivers] = useState(true);
  const [loadingConfig, setLoadingConfig] = useState(true);

  // Driver state
  const [drivers, setDrivers] = useState<DriverOption[]>([]);
  const [selectedDriverIds, setSelectedDriverIds] = useState<Set<string>>(new Set());

  // Saturday state
  const [saturdayChoice, setSaturdayChoice] = useState<SaturdayChoice>(null);

  // Sunday state
  const [sundayChoice, setSundayChoice] = useState<SundayChoice>(null);

  // Load drivers + existing config in parallel
  useEffect(() => {
    apiClient
      .get("/tenant-onboarding/scheduling-board/drivers")
      .then(({ data }) => {
        const driverList: DriverOption[] = data.drivers ?? [];
        setDrivers(driverList);
        // Pre-check all drivers by default (will be overridden if config exists)
        setSelectedDriverIds(new Set(driverList.map((d) => d.driver_id)));
      })
      .catch(() => {})
      .finally(() => setLoadingDrivers(false));

    apiClient
      .get("/tenant-onboarding/scheduling-board/config")
      .then(({ data }) => {
        if (data.configured) {
          // Restore driver selection
          const saved: string[] = data.kanban_driver_ids ?? [];
          if (saved.length > 0) {
            setSelectedDriverIds(new Set(saved));
          }
          // Restore Saturday choice
          const satChoice = settingsToSaturdayChoice(
            data.saturday_delivery_enabled ?? true,
            data.saturday_surcharge_type ?? null,
          );
          setSaturdayChoice(satChoice);
          // Restore Sunday choice
          const sunChoice = settingsToSundayChoice(
            data.sunday_delivery_enabled ?? false,
            data.sunday_surcharge_enabled ?? false,
          );
          setSundayChoice(sunChoice);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingConfig(false));
  }, []);

  const toggleDriver = (driverId: string) => {
    setSelectedDriverIds((prev) => {
      const next = new Set(prev);
      if (next.has(driverId)) next.delete(driverId);
      else next.add(driverId);
      return next;
    });
  };

  // Completion: Saturday + Sunday required, drivers optional
  const canSave = saturdayChoice !== null && sundayChoice !== null;

  const handleSave = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      const sat = saturdayChoiceToSettings(saturdayChoice);
      const sun = sundayChoiceToSettings(sundayChoice);
      await apiClient.post("/tenant-onboarding/scheduling-board/configure", {
        kanban_driver_ids: Array.from(selectedDriverIds),
        ...sat,
        ...sun,
      });
      toast.success("Scheduling board configured");
      navigate("/onboarding");
    } catch {
      toast.error("Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  const loading = loadingDrivers || loadingConfig;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate("/onboarding")}
          className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to onboarding
        </button>
        <h1 className="text-2xl font-bold text-gray-900">
          Set up your scheduling board
        </h1>
        <p className="mt-1 text-gray-500">
          Configure your scheduling board drivers and weekend delivery settings.
        </p>
      </div>

      <div className="space-y-10">
        {/* Question 1 — Driver selection */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Truck className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                Which drivers should appear on your scheduling board?
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Select the drivers who will have their own lane on the Kanban
                scheduling board.
              </p>
            </div>
          </div>

          <div className="ml-12">
            {drivers.length === 0 ? (
              /* Empty state */
              <div className="rounded-lg border border-dashed border-gray-300 p-5 text-center">
                <p className="text-sm text-gray-500 mb-2">
                  No drivers set up yet.
                </p>
                <Link
                  to="/onboarding/team"
                  className="text-sm font-medium text-blue-600 hover:text-blue-700"
                >
                  + Add your drivers first &rarr;
                </Link>
                <p className="mt-2 text-xs text-gray-400">
                  You can also set up drivers later and add them to the board
                  from Settings.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {drivers.map((drv) => (
                  <label
                    key={drv.driver_id}
                    className={cn(
                      "flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                      selectedDriverIds.has(drv.driver_id)
                        ? "border-blue-200 bg-blue-50/40"
                        : "hover:bg-gray-50",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={selectedDriverIds.has(drv.driver_id)}
                      onChange={() => toggleDriver(drv.driver_id)}
                      className="rounded"
                    />
                    <span className="text-sm font-medium text-gray-900">
                      {drv.name}
                    </span>
                  </label>
                ))}
                <Link
                  to="/onboarding/team"
                  className="inline-flex items-center gap-1 mt-1 text-xs text-blue-600 hover:text-blue-700"
                >
                  + Add a driver first &rarr;
                </Link>
              </div>
            )}
          </div>
        </section>

        {/* Question 2 — Saturday handling */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <Calendar className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                How do you handle Saturday funeral deliveries?
              </h2>
            </div>
          </div>
          <div className="ml-12 space-y-2">
            {SATURDAY_OPTIONS.map((opt) => (
              <div key={opt.value}>
                <label
                  className={cn(
                    "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                    saturdayChoice === opt.value
                      ? "border-blue-500 bg-blue-50/50"
                      : "hover:bg-gray-50",
                  )}
                >
                  <input
                    type="radio"
                    name="saturday"
                    checked={saturdayChoice === opt.value}
                    onChange={() => setSaturdayChoice(opt.value)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="font-medium text-gray-900 text-sm">
                      {opt.label}
                    </div>
                    <div className="text-xs text-gray-500">{opt.desc}</div>
                  </div>
                </label>
                {opt.showChargeLink && saturdayChoice === opt.value && (
                  <p className="ml-7 mt-1 text-xs text-blue-600">
                    Configure the surcharge amount in{" "}
                    <Link
                      to="/settings/charges?highlight=saturday_surcharge"
                      className="underline hover:text-blue-700"
                    >
                      Charge Library &rarr;
                    </Link>
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Question 3 — Sunday handling */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-50 text-violet-600">
              <Sun className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                How do you handle Sunday funeral deliveries?
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Sunday funerals are rare but do happen. This setting affects your
                scheduling board's 3-day view and how drivers see their upcoming
                orders.
              </p>
            </div>
          </div>
          <div className="ml-12 space-y-2">
            {SUNDAY_OPTIONS.map((opt) => (
              <div key={opt.value}>
                <label
                  className={cn(
                    "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                    sundayChoice === opt.value
                      ? "border-blue-500 bg-blue-50/50"
                      : "hover:bg-gray-50",
                  )}
                >
                  <input
                    type="radio"
                    name="sunday"
                    checked={sundayChoice === opt.value}
                    onChange={() => setSundayChoice(opt.value)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="font-medium text-gray-900 text-sm">
                      {opt.label}
                    </div>
                    <div className="text-xs text-gray-500">{opt.desc}</div>
                  </div>
                </label>
                {opt.showChargeLink && sundayChoice === opt.value && (
                  <p className="ml-7 mt-1 text-xs text-blue-600">
                    Configure the surcharge amount in{" "}
                    <Link
                      to="/settings/charges?highlight=sunday_surcharge"
                      className="underline hover:text-blue-700"
                    >
                      Charge Library &rarr;
                    </Link>
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Footer */}
      <div className="mt-8 flex items-center justify-between">
        <button
          onClick={() => navigate("/onboarding")}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <div className="flex items-center gap-3">
          {!canSave && (
            <span className="text-xs text-gray-400">
              Answer Saturday and Sunday questions to continue
            </span>
          )}
          <Button onClick={handleSave} disabled={saving || !canSave}>
            {saving ? "Saving..." : "Save and continue"}
            {!saving && <ArrowRight className="ml-2 h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
