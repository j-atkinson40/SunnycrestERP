/**
 * Accounting Reminder Banner — shown when accounting setup was skipped.
 *
 * Session-dismissible: clicking X hides the banner until the next login.
 * Shows a different message if an accountant invite is pending.
 *
 * Aesthetic Arc Session 3 refresh — migrated to Alert primitive.
 * Pre-S3: custom bg-amber-50/border-amber-200/text-amber-900 chrome.
 * Post-S3: uses <Alert variant="warning"> so it inherits the status
 * color family + dismiss affordance + DESIGN_LANGUAGE motion and
 * focus ring from the shared primitive.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plug, Mail } from "lucide-react";
import { usePresetTheme } from "@/contexts/preset-theme-context";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";

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
    <Alert
      variant="warning"
      icon={isPending ? Mail : Plug}
      onDismiss={() => {
        sessionStorage.setItem(DISMISS_KEY, "true");
        setDismissed(true);
      }}
      className="rounded-none border-t-0 border-r-0 border-b border-l-4 px-4 py-2.5"
    >
      {isPending ? (
        <AlertDescription className="font-medium">
          Waiting for{" "}
          <span className="font-semibold">{accountantEmail || "your accountant"}</span>{" "}
          to connect your accounting software.{" "}
          <Link
            to="/onboarding/accounting"
            className="font-semibold underline underline-offset-2 hover:text-status-warning/80"
          >
            Do it yourself
          </Link>
        </AlertDescription>
      ) : (
        <>
          <AlertTitle>Accounting software isn't connected</AlertTitle>
          <AlertDescription>
            Invoices won't sync until connected.{" "}
            <Link
              to="/onboarding/accounting"
              className="font-semibold underline underline-offset-2 hover:text-status-warning/80"
            >
              Connect now
            </Link>
          </AlertDescription>
        </>
      )}
    </Alert>
  );
}
