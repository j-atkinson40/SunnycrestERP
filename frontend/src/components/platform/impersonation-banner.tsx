/**
 * Persistent banner shown at the top of the tenant interface when an
 * impersonation session is active.
 */

import { useCallback, useEffect, useState } from "react";

interface ImpersonationInfo {
  session_id: string;
  tenant_name: string;
  user_name: string;
  expires_at: number; // unix timestamp ms
}

/**
 * Get impersonation info from localStorage (set when impersonation starts).
 */
function getImpersonationInfo(): ImpersonationInfo | null {
  const raw = localStorage.getItem("impersonation_info");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function ImpersonationBanner() {
  const [info, setInfo] = useState<ImpersonationInfo | null>(null);
  const [remaining, setRemaining] = useState("");

  useEffect(() => {
    setInfo(getImpersonationInfo());
  }, []);

  useEffect(() => {
    if (!info) return;
    const interval = setInterval(() => {
      const diff = info.expires_at - Date.now();
      if (diff <= 0) {
        setRemaining("Expired");
        clearInterval(interval);
        return;
      }
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setRemaining(`${mins}:${secs.toString().padStart(2, "0")}`);
    }, 1000);
    return () => clearInterval(interval);
  }, [info]);

  const handleExit = useCallback(() => {
    // Clear impersonation tokens and info
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("impersonation_info");

    // Redirect back to platform admin
    // In production this would go to the admin subdomain
    const adminUrl =
      window.location.hostname === "localhost" ||
      window.location.hostname.endsWith(".localhost")
        ? `${window.location.protocol}//admin.localhost:${window.location.port}`
        : `${window.location.protocol}//admin.${import.meta.env.VITE_APP_DOMAIN || window.location.hostname}`;
    window.location.href = adminUrl;
  }, []);

  if (!info) return null;

  return (
    <div className="fixed top-0 right-0 left-0 z-[100] flex items-center justify-between bg-orange-500 px-4 py-2 text-white shadow-md">
      <div className="flex items-center gap-3 text-sm font-medium">
        <span className="rounded bg-orange-700 px-2 py-0.5 text-xs font-bold uppercase">
          Impersonating
        </span>
        <span>
          {info.user_name} at {info.tenant_name}
        </span>
        <span className="text-orange-200">({remaining} remaining)</span>
      </div>
      <button
        onClick={handleExit}
        className="rounded bg-white px-3 py-1 text-sm font-medium text-orange-600 transition-colors hover:bg-orange-50"
      >
        Exit Impersonation
      </button>
    </div>
  );
}
