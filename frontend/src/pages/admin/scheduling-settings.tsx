/**
 * Scheduling Board Settings — Post-onboarding settings page.
 *
 * Manage Kanban driver lanes and weekend delivery preferences.
 * Changes save immediately on toggle (no batch save).
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Truck, Calendar, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
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
// Mapping helpers (same as onboarding page)
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
  return null;
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
// Saturday / Sunday option definitions
// ---------------------------------------------------------------------------

const SATURDAY_OPTIONS: {
  value: NonNullable<SaturdayChoice>;
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
    desc: "The surcharge only applies during spring burial season",
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

const SUNDAY_OPTIONS: {
  value: NonNullable<SundayChoice>;
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
// Page Component
// ---------------------------------------------------------------------------

export default function SchedulingSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [drivers, setDrivers] = useState<DriverOption[]>([]);
  const [selectedDriverIds, setSelectedDriverIds] = useState<Set<string>>(new Set());
  const [saturdayChoice, setSaturdayChoice] = useState<SaturdayChoice>(null);
  const [sundayChoice, setSundayChoice] = useState<SundayChoice>(null);

  useEffect(() => {
    Promise.all([
      apiClient.get("/tenant-onboarding/scheduling-board/drivers"),
      apiClient.get("/tenant-onboarding/scheduling-board/config"),
    ])
      .then(([driversRes, configRes]) => {
        const driverList: DriverOption[] = driversRes.data.drivers ?? [];
        setDrivers(driverList);

        const config = configRes.data;
        const savedIds: string[] = config.kanban_driver_ids ?? [];
        setSelectedDriverIds(
          savedIds.length > 0
            ? new Set(savedIds)
            : new Set(driverList.map((d) => d.driver_id)),
        );

        setSaturdayChoice(
          settingsToSaturdayChoice(
            config.saturday_delivery_enabled ?? true,
            config.saturday_surcharge_type ?? null,
          ),
        );
        setSundayChoice(
          settingsToSundayChoice(
            config.sunday_delivery_enabled ?? false,
            config.sunday_surcharge_enabled ?? false,
          ),
        );
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Immediate save helper
  const saveAll = async (
    driverIds: Set<string>,
    sat: SaturdayChoice,
    sun: SundayChoice,
  ) => {
    try {
      const satSettings = saturdayChoiceToSettings(sat);
      const sunSettings = sundayChoiceToSettings(sun);
      await apiClient.post("/tenant-onboarding/scheduling-board/configure", {
        kanban_driver_ids: Array.from(driverIds),
        ...satSettings,
        ...sunSettings,
      });
      toast.success("Setting updated");
    } catch {
      toast.error("Failed to save setting");
    }
  };

  const handleToggleDriver = (driverId: string) => {
    setSelectedDriverIds((prev) => {
      const next = new Set(prev);
      if (next.has(driverId)) next.delete(driverId);
      else next.add(driverId);
      saveAll(next, saturdayChoice, sundayChoice);
      return next;
    });
  };

  const handleSaturdayChange = (choice: SaturdayChoice) => {
    setSaturdayChoice(choice);
    saveAll(selectedDriverIds, choice, sundayChoice);
  };

  const handleSundayChange = (choice: SundayChoice) => {
    setSundayChoice(choice);
    saveAll(selectedDriverIds, saturdayChoice, choice);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Scheduling Board Settings
        </h1>
        <p className="mt-1 text-gray-500">
          Manage your scheduling board driver lanes and weekend delivery
          preferences. Changes take effect immediately.
        </p>
      </div>

      <div className="space-y-10">
        {/* Scheduling Board Drivers */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Truck className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                Scheduling Board Drivers
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Select which drivers have their own lane on the Kanban
                scheduling board.
              </p>
            </div>
          </div>

          <div className="ml-12">
            {drivers.length === 0 ? (
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
                      onChange={() => handleToggleDriver(drv.driver_id)}
                      className="rounded"
                    />
                    <span className="text-sm font-medium text-gray-900">
                      {drv.name}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Saturday Handling */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <Calendar className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                Saturday Deliveries
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
                    onChange={() => handleSaturdayChange(opt.value)}
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

        {/* Sunday Handling */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-50 text-violet-600">
              <Sun className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                Sunday Deliveries
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
                    onChange={() => handleSundayChange(opt.value)}
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
    </div>
  );
}
