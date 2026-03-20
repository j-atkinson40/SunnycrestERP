/**
 * Accounting Reminder Banner — shown when accounting setup was skipped.
 *
 * Session-dismissible: clicking X hides the banner until the next login.
 * Shows a different message if an accountant invite is pending.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X, Plug, Mail } from "lucide-react";
import { usePresetTheme } from "@/contexts/preset-theme-context";

const DISMISS_KEY = "accounting_banner_dismissed";

export function AccountingReminderBanner() {
  const { tenantSettings } = usePresetTheme();
  const [dismissed, setDismissed] = useState(true);

  const connectionStatus = tenantSettings.accounting_connection_status as
    | string
    | undefined;
  const accountantEmail = tenantSettings.accounting_accountant_email as
    | string
    | undefined;

  useEffect(() => {
    // Show if skipped or pending_accountant and not dismissed this session
    const shouldShow =
      connectionStatus === "skipped" || connectionStatus === "pending_accountant";
    const wasDismissed = sessionStorage.getItem(DISMISS_KEY) === "true";
    setDismissed(!shouldShow || wasDismissed);
  }, [connectionStatus]);

  if (dismissed) return null;

  const isPending = connectionStatus === "pending_accountant";

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-2 text-sm text-amber-900 min-w-0">
        {isPending ? (
          <>
            <Mail className="h-4 w-4 shrink-0 text-amber-600" />
            <span>
              Waiting for{" "}
              <span className="font-medium">{accountantEmail || "your accountant"}</span>{" "}
              to connect your accounting software.{" "}
              <Link
                to="/onboarding/accounting"
                className="font-medium underline hover:text-amber-700"
              >
                Do it yourself
              </Link>
            </span>
          </>
        ) : (
          <>
            <Plug className="h-4 w-4 shrink-0 text-amber-600" />
            <span>
              Your accounting software isn't connected yet. Invoices won't sync
              until it is.{" "}
              <Link
                to="/onboarding/accounting"
                className="font-medium underline hover:text-amber-700"
              >
                Connect now
              </Link>
            </span>
          </>
        )}
      </div>
      <button
        type="button"
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, "true");
          setDismissed(true);
        }}
        className="shrink-0 text-amber-600 hover:text-amber-800 transition-colors"
        aria-label="Dismiss banner"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
