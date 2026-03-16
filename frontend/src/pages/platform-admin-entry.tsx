/**
 * Entry point for platform admin when subdomains aren't available.
 *
 * Navigating to /platform-admin sets the platform_mode flag and reloads,
 * which causes isPlatformAdmin() to return true and render PlatformApp.
 */

import { useEffect } from "react";
import { enablePlatformMode } from "@/lib/platform";

export default function PlatformAdminEntry() {
  useEffect(() => {
    enablePlatformMode();
    window.location.href = "/dashboard";
  }, []);

  return (
    <div className="flex h-screen items-center justify-center">
      <p className="text-muted-foreground">Redirecting to platform admin...</p>
    </div>
  );
}
