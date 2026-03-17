import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { extensionService } from "@/services/extension-service";
import type { ExtensionCatalogItem, ExtensionCategory } from "@/types/extension";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/types/extension";

export default function ExtensionInstalledPage() {
  const { isAdmin, refreshUser } = useAuth();
  const [extensions, setExtensions] = useState<ExtensionCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [disablingKey, setDisablingKey] = useState<string | null>(null);
  const [confirmDisable, setConfirmDisable] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await extensionService.listInstalled();
      setExtensions(data);
    } catch {
      toast.error("Failed to load installed extensions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDisable = async (ext: ExtensionCatalogItem) => {
    setDisablingKey(ext.extension_key);
    try {
      await extensionService.disable(ext.extension_key);
      toast.success(`${ext.name} has been disabled`);
      await refreshUser();
      load();
    } catch {
      toast.error("Failed to disable extension");
    } finally {
      setDisablingKey(null);
      setConfirmDisable(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Installed Extensions</h1>
          <p className="text-gray-500 mt-1">
            {extensions.length} extension{extensions.length !== 1 ? "s" : ""} active
          </p>
        </div>
        <Link
          to="/extensions"
          className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
        >
          Browse Catalog
        </Link>
      </div>

      {extensions.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <p className="text-gray-500">No extensions installed yet.</p>
          <Link
            to="/extensions"
            className="inline-block px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
          >
            Browse the Extension Catalog
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {extensions.map((ext) => (
            <div
              key={ext.extension_key}
              className="border rounded-lg p-4 bg-white flex items-start justify-between gap-4"
            >
              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-semibold text-gray-900">{ext.name}</h3>
                  <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", CATEGORY_COLORS[ext.category as ExtensionCategory] || "bg-gray-100 text-gray-700")}>
                    {CATEGORY_LABELS[ext.category as ExtensionCategory] || ext.category}
                  </span>
                  <span className="text-xs text-gray-400">v{ext.version_at_install || ext.version}</span>
                  {ext.install_status === "pending_setup" && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                      Setup Required
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500">{ext.tagline}</p>
                {ext.enabled_at && (
                  <p className="text-xs text-gray-400">
                    Installed on {new Date(ext.enabled_at).toLocaleDateString()}
                  </p>
                )}
              </div>

              {isAdmin && (
                <div className="shrink-0 flex items-center gap-2">
                  {ext.install_status === "pending_setup" && (
                    <Link
                      to={`/extensions?setup=${ext.extension_key}`}
                      className="px-3 py-1.5 bg-amber-500 text-white text-sm rounded-md hover:bg-amber-600 transition-colors"
                    >
                      Configure
                    </Link>
                  )}
                  {confirmDisable === ext.extension_key ? (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDisable(ext)}
                        disabled={disablingKey === ext.extension_key}
                        className="px-3 py-1.5 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 disabled:opacity-50 transition-colors"
                      >
                        {disablingKey === ext.extension_key ? "..." : "Confirm"}
                      </button>
                      <button
                        onClick={() => setConfirmDisable(null)}
                        className="px-3 py-1.5 border text-sm rounded-md hover:bg-gray-50 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDisable(ext.extension_key)}
                      className="px-3 py-1.5 text-sm text-gray-500 hover:text-red-600 border rounded-md hover:border-red-200 transition-colors"
                    >
                      Disable
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
