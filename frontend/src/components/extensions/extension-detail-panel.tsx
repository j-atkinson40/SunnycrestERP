import { useEffect, useState } from "react";
import { Check, Clock, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { extensionService } from "@/services/extension-service";
import { getExtensionIcon } from "./extension-icons";
import type { ExtensionDetail } from "@/types/extension";
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  type ExtensionCategory,
} from "@/types/extension";

// ── Setup form from JSON Schema ──

function SetupForm({
  schema,
  values,
  onChange,
}: {
  schema: Record<string, unknown>;
  values: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
}) {
  const properties =
    (schema as { properties?: Record<string, Record<string, unknown>> })
      .properties || {};

  const setValue = (key: string, val: unknown) => {
    onChange({ ...values, [key]: val });
  };

  return (
    <div className="space-y-4">
      {Object.entries(properties).map(([key, prop]) => {
        const type = prop.type as string;
        const title = (prop.title || key) as string;
        const enumVals = prop.enum as string[] | undefined;

        if (type === "boolean") {
          return (
            <label key={key} className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={
                  (values[key] as boolean) ?? (prop.default as boolean) ?? false
                }
                onChange={(e) => setValue(key, e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <span className="text-sm text-gray-700">{title}</span>
            </label>
          );
        }

        if (type === "string" && enumVals) {
          return (
            <div key={key} className="space-y-1">
              <label className="text-sm font-medium text-gray-700">
                {title}
              </label>
              <select
                value={
                  (values[key] as string) ?? (prop.default as string) ?? ""
                }
                onChange={(e) => setValue(key, e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                {enumVals.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          );
        }

        return (
          <div key={key} className="space-y-1">
            <label className="text-sm font-medium text-gray-700">
              {title}
            </label>
            <input
              type="text"
              value={(values[key] as string) ?? ""}
              onChange={(e) => setValue(key, e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        );
      })}
    </div>
  );
}

// ── Detail Panel ──

interface ExtensionDetailPanelProps {
  extensionKey: string;
  onClose: () => void;
  onInstallChange: () => void;
}

export function ExtensionDetailPanel({
  extensionKey,
  onClose,
  onInstallChange,
}: ExtensionDetailPanelProps) {
  const { isAdmin, refreshUser } = useAuth();
  const [detail, setDetail] = useState<ExtensionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [disabling, setDisabling] = useState(false);
  const [notifying, setNotifying] = useState(false);
  const [setupSchema, setSetupSchema] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [setupValues, setSetupValues] = useState<Record<string, unknown>>({});

  useEffect(() => {
    setLoading(true);
    extensionService
      .getDetail(extensionKey)
      .then(setDetail)
      .catch(() => toast.error("Failed to load extension details"))
      .finally(() => setLoading(false));
  }, [extensionKey]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleInstall = async () => {
    if (!detail) return;
    setInstalling(true);
    try {
      const result = await extensionService.install(detail.extension_key);
      if (result.setup_config_schema) {
        setSetupSchema(result.setup_config_schema);
        toast.info("Complete setup to activate this extension");
      } else {
        toast.success(result.message);
        await refreshUser();
        onInstallChange();
        const updated = await extensionService.getDetail(extensionKey);
        setDetail(updated);
      }
    } catch {
      toast.error("Failed to install extension");
    } finally {
      setInstalling(false);
    }
  };

  const handleConfigure = async () => {
    if (!detail) return;
    setInstalling(true);
    try {
      const result = await extensionService.configure(
        detail.extension_key,
        setupValues,
      );
      toast.success(result.message);
      setSetupSchema(null);
      await refreshUser();
      onInstallChange();
      const updated = await extensionService.getDetail(extensionKey);
      setDetail(updated);
    } catch {
      toast.error("Failed to configure extension");
    } finally {
      setInstalling(false);
    }
  };

  const handleDisable = async () => {
    if (!detail) return;
    setDisabling(true);
    try {
      await extensionService.disable(detail.extension_key);
      toast.success(`${detail.name} has been disabled`);
      await refreshUser();
      onInstallChange();
      const updated = await extensionService.getDetail(extensionKey);
      setDetail(updated);
    } catch {
      toast.error("Failed to disable extension");
    } finally {
      setDisabling(false);
    }
  };

  const handleNotify = async () => {
    if (!detail) return;
    setNotifying(true);
    try {
      const result = await extensionService.notifyMe(detail.extension_key);
      toast.success(result.message);
      setDetail({ ...detail, notify_me_count: result.notify_me_count });
    } catch {
      toast.error("Failed to register interest");
    } finally {
      setNotifying(false);
    }
  };

  const Icon = detail ? getExtensionIcon(detail.extension_key) : null;
  const isInstalled = detail?.installed && detail?.install_status === "active";
  const isComingSoon = detail?.status === "coming_soon";

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/30" onClick={onClose} />

      {/* Panel */}
      <div className="w-full max-w-lg bg-white shadow-xl animate-in slide-in-from-right overflow-y-auto">
        {loading ? (
          <div className="p-6 flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
          </div>
        ) : !detail ? null : (
          <div className="relative">
            {/* Header */}
            <div className="sticky top-0 bg-white border-b px-6 py-4 z-10">
              <div className="flex items-start gap-4">
                {Icon && (
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-gray-700">
                    <Icon className="h-6 w-6" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-lg font-bold text-gray-900">
                      {detail.name}
                    </h2>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                      v{detail.version}
                    </span>
                  </div>
                  {detail.tagline && (
                    <p className="mt-0.5 text-sm text-gray-500">
                      {detail.tagline}
                    </p>
                  )}
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    {detail.applicable_verticals
                      .filter((v) => v !== "all")
                      .map((v) => (
                        <span
                          key={v}
                          className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500"
                        >
                          {v.replace(/_/g, " ")}
                        </span>
                      ))}
                    <span
                      className={cn(
                        "text-xs px-2 py-0.5 rounded-full font-medium",
                        CATEGORY_COLORS[
                          detail.category as ExtensionCategory
                        ] || "bg-gray-100 text-gray-700",
                      )}
                    >
                      {CATEGORY_LABELS[
                        detail.category as ExtensionCategory
                      ] || detail.category}
                    </span>
                    {detail.access_model === "included" &&
                      detail.status === "active" && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
                          Included
                        </span>
                      )}
                    {detail.access_model === "paid_addon" &&
                      detail.addon_price_monthly && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 font-medium">
                          ${detail.addon_price_monthly}/mo
                        </span>
                      )}
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <X className="h-5 w-5 text-gray-400" />
                </button>
              </div>

              {/* Primary action */}
              <div className="mt-4">
                {isAdmin &&
                  !detail.installed &&
                  detail.status === "active" &&
                  detail.access_model === "included" && (
                    <button
                      onClick={handleInstall}
                      disabled={installing}
                      className="w-full px-4 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                    >
                      {installing ? (
                        <span className="flex items-center justify-center gap-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                          Enabling...
                        </span>
                      ) : (
                        "Enable"
                      )}
                    </button>
                  )}

                {isAdmin &&
                  !detail.installed &&
                  detail.status === "active" &&
                  detail.access_model === "paid_addon" && (
                    <button
                      onClick={handleInstall}
                      disabled={installing}
                      className="w-full px-4 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                    >
                      {installing ? (
                        <span className="flex items-center justify-center gap-2">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                          Adding...
                        </span>
                      ) : (
                        `Add for $${detail.addon_price_monthly ?? 0}/mo`
                      )}
                    </button>
                  )}

                {isAdmin &&
                  !detail.installed &&
                  detail.access_model === "plan_required" && (
                    <button className="w-full px-4 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors">
                      Upgrade to Enable
                    </button>
                  )}

                {isAdmin && detail.install_status === "pending_setup" && (
                  <button
                    onClick={() => {
                      if (detail.setup_config_schema) {
                        setSetupSchema(detail.setup_config_schema);
                      }
                    }}
                    className="w-full px-4 py-2.5 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 transition-colors"
                  >
                    Complete Setup
                  </button>
                )}

                {isInstalled && (
                  <div className="flex items-center justify-center gap-2 py-2.5 bg-green-50 text-green-700 rounded-lg font-medium">
                    <Check className="h-5 w-5" />
                    Installed
                  </div>
                )}

                {isComingSoon && (
                  <button
                    onClick={handleNotify}
                    disabled={notifying}
                    className="w-full px-4 py-2.5 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 transition-colors"
                  >
                    {notifying
                      ? "Registering..."
                      : "Notify Me When Available"}
                  </button>
                )}
              </div>
            </div>

            {/* Body */}
            <div className="px-6 py-6 space-y-6">
              {/* Social proof */}
              {isComingSoon && detail.notify_me_count > 3 && (
                <div className="text-sm text-gray-500 flex items-center gap-1.5">
                  <span className="font-medium text-gray-700">
                    {detail.notify_me_count}
                  </span>
                  teams have requested this
                </div>
              )}

              {/* What it does */}
              {detail.description && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">
                    What it does
                  </h3>
                  <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                    {detail.description}
                  </p>
                </div>
              )}

              {/* What you get */}
              {detail.feature_bullets.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">
                    What you get
                  </h3>
                  <ul className="space-y-2">
                    {detail.feature_bullets.map((bullet, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm text-gray-600"
                      >
                        <Check className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                        {bullet}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Works with */}
              {detail.module_key && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-900">
                    Works with
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 font-medium">
                      {detail.module_key.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
              )}

              {/* Setup time */}
              {detail.setup_required && (
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Clock className="h-4 w-4" />
                  <span>Setup time: ~2 minutes</span>
                </div>
              )}

              {/* Installed info + disable */}
              {isInstalled && detail.enabled_at && (
                <div className="pt-4 border-t space-y-3">
                  <p className="text-sm text-gray-500">
                    Installed on{" "}
                    {new Date(detail.enabled_at).toLocaleDateString()}
                  </p>
                  {isAdmin && (
                    <button
                      onClick={handleDisable}
                      disabled={disabling}
                      className="text-sm text-red-500 hover:text-red-700 transition-colors"
                    >
                      {disabling ? "Disabling..." : "Disable extension"}
                    </button>
                  )}
                </div>
              )}

              {/* Customer requested */}
              {detail.is_customer_requested && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
                  Built from a customer request
                </div>
              )}
            </div>

            {/* Setup overlay */}
            {setupSchema && (
              <div className="absolute inset-0 bg-white z-10 overflow-y-auto">
                <div className="p-6 space-y-4">
                  <h3 className="text-lg font-bold">Set up {detail.name}</h3>
                  <p className="text-sm text-gray-500">
                    Configure this extension before activation.
                  </p>
                  <SetupForm
                    schema={setupSchema}
                    values={setupValues}
                    onChange={setSetupValues}
                  />
                  <div className="flex gap-3">
                    <button
                      onClick={handleConfigure}
                      disabled={installing}
                      className="flex-1 px-4 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                    >
                      {installing ? "Saving..." : "Enable Extension"}
                    </button>
                    <button
                      onClick={() => setSetupSchema(null)}
                      className="px-4 py-2.5 border rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
