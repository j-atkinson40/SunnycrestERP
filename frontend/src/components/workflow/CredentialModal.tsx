/**
 * CredentialModal — inline slide-over for connecting / updating an external
 * account credential without navigating away from the workflow canvas.
 *
 * Opens when the user clicks "Connect" or "Update credentials" in the
 * PlaywrightActionConfig section of the step editor.
 */
import { useState } from "react";
import { X, Eye, EyeOff, Shield, CheckCircle, Loader2 } from "lucide-react";
import apiClient from "@/lib/api-client";

interface CredentialField {
  key: string;
  label: string;
  placeholder?: string;
  isPassword?: boolean;
}

const SERVICE_FIELDS: Record<string, { name: string; fields: CredentialField[] }> = {
  uline: {
    name: "Uline",
    fields: [
      { key: "username", label: "Username / Email", placeholder: "you@company.com" },
      { key: "password", label: "Password", isPassword: true },
    ],
  },
  grainger: {
    name: "Grainger",
    fields: [
      { key: "username", label: "Username", placeholder: "username" },
      { key: "password", label: "Password", isPassword: true },
    ],
  },
  staples: {
    name: "Staples Business Advantage",
    fields: [
      { key: "username", label: "Email", placeholder: "you@company.com" },
      { key: "password", label: "Password", isPassword: true },
    ],
  },
};

function getServiceMeta(serviceKey: string) {
  return (
    SERVICE_FIELDS[serviceKey] ?? {
      name: serviceKey,
      fields: [
        { key: "username", label: "Username" },
        { key: "password", label: "Password", isPassword: true },
      ],
    }
  );
}

interface CredentialModalProps {
  serviceKey: string;
  onClose: () => void;
  onSaved: () => void;
}

export default function CredentialModal({
  serviceKey,
  onClose,
  onSaved,
}: CredentialModalProps) {
  const meta = getServiceMeta(serviceKey);
  const [values, setValues] = useState<Record<string, string>>({});
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    const missing = meta.fields.filter((f) => !values[f.key]?.trim());
    if (missing.length > 0) {
      setError(`Please fill in: ${missing.map((f) => f.label).join(", ")}`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiClient.post("/external-accounts", {
        service_name: meta.name,
        service_key: serviceKey,
        credentials: values,
      });
      setSaved(true);
      setTimeout(() => {
        onSaved();
        onClose();
      }, 800);
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setError(msg ?? "Failed to save credentials");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative z-10 w-full max-w-md mx-4 bg-white rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">
              Connect {meta.name}
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Credentials are encrypted with AES-256 and never shown again.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Fields */}
        <div className="px-5 py-4 space-y-4">
          {meta.fields.map((field) => (
            <div key={field.key}>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                {field.label}
              </label>
              <div className="relative">
                <input
                  type={field.isPassword && !visible[field.key] ? "password" : "text"}
                  placeholder={field.placeholder}
                  value={values[field.key] ?? ""}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [field.key]: e.target.value }))
                  }
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-9"
                  autoComplete="off"
                />
                {field.isPassword && (
                  <button
                    type="button"
                    onClick={() =>
                      setVisible((v) => ({ ...v, [field.key]: !v[field.key] }))
                    }
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {visible[field.key] ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}

          {error && (
            <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          {/* Security note */}
          <div className="flex items-start gap-2 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
            <Shield className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-gray-400" />
            <span>
              Credentials are stored encrypted. They are only decrypted at
              automation runtime and are never logged or displayed.
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || saved}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60 transition-colors"
          >
            {saving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : saved ? (
              <CheckCircle className="w-3.5 h-3.5" />
            ) : null}
            {saved ? "Saved!" : saving ? "Saving…" : "Save credentials"}
          </button>
        </div>
      </div>
    </div>
  );
}
