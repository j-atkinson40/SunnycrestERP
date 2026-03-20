export interface AccountingError {
  title: string;
  plain: string;
  cause: string;
  action: string;
  actionLabel: string;
  actionRoute: string;
}

export const ACCOUNTING_ERRORS: Record<string, AccountingError> = {
  // QBO errors
  QBO_3200: {
    title: "QuickBooks session expired",
    plain: "Your QuickBooks authorization has expired.",
    cause: "This happens when you haven't used the connection in a while or changed your QuickBooks password.",
    action: "Reconnect to QuickBooks — it only takes 30 seconds.",
    actionLabel: "Reconnect to QuickBooks →",
    actionRoute: "/onboarding/accounting",
  },
  QBO_DUPLICATE_INVOICE: {
    title: "Invoice already exists in QuickBooks",
    plain: "Invoice #[invoice_number] already exists in QuickBooks.",
    cause: "This invoice may have been created manually in QuickBooks before the sync was set up.",
    action: "You can link the existing QuickBooks invoice to this one, or delete the duplicate in QuickBooks.",
    actionLabel: "Resolve duplicate →",
    actionRoute: "/admin/accounting",
  },
  QBO_ACCOUNT_NOT_FOUND: {
    title: "Income account not found",
    plain: "The income account this invoice was mapped to no longer exists in QuickBooks.",
    cause: "Someone may have deleted or renamed the account in QuickBooks.",
    action: "Update your account mapping to use an existing QuickBooks account.",
    actionLabel: "Update account mapping →",
    actionRoute: "/admin/accounting",
  },
  QBO_CUSTOMER_NOT_FOUND: {
    title: "Customer not found in QuickBooks",
    plain: "[customer_name] exists in your platform but not in QuickBooks.",
    cause: "The customer may have been deleted in QuickBooks, or the sync hasn't created them yet.",
    action: "Sync your customers now to push this customer to QuickBooks.",
    actionLabel: "Sync customers now →",
    actionRoute: "/admin/accounting",
  },
  // QBD errors
  QBD_NOT_RUNNING: {
    title: "QuickBooks Desktop is not running",
    plain: "The Web Connector can't sync because QuickBooks Desktop isn't open.",
    cause: "QuickBooks must be running when the Web Connector syncs.",
    action: "Open QuickBooks Desktop on your computer and run the Web Connector sync again.",
    actionLabel: "Check Web Connector status →",
    actionRoute: "/admin/accounting",
  },
  QBD_WRONG_FILE: {
    title: "Wrong QuickBooks company file",
    plain: "The Web Connector is connected to a different QuickBooks company file.",
    cause: "QuickBooks Desktop was open with a different company file when the sync ran.",
    action: "Open the correct QuickBooks company file and run the sync again.",
    actionLabel: "View setup instructions →",
    actionRoute: "/admin/accounting",
  },
  QBD_PERMISSION_DENIED: {
    title: "QuickBooks permission denied",
    plain: "QuickBooks rejected the connection — insufficient permissions.",
    cause: "The QuickBooks user account used during setup may not have admin rights.",
    action: "Log into QuickBooks as an administrator and re-add the .qwc connection file.",
    actionLabel: "Download new .qwc file →",
    actionRoute: "/admin/accounting",
  },
  // Sage errors
  SAGE_CONNECTION_REFUSED: {
    title: "Cannot reach your Sage 100 server",
    plain: "We couldn't connect to your Sage 100 server at [server_url].",
    cause: "Your Sage server may be behind a firewall, on a local network only, or the URL may be incorrect.",
    action: "Check the server URL with your IT person, or switch to CSV export which works without a direct connection.",
    actionLabel: "Switch to CSV export →",
    actionRoute: "/onboarding/accounting",
  },
  SAGE_INVALID_CREDENTIALS: {
    title: "Sage 100 credentials incorrect",
    plain: "The client ID or client secret you entered is incorrect.",
    cause: "These credentials come from the Sage 100 Operations API setup in your Sage admin console.",
    action: "Check your Sage 100 Operations API settings and re-enter the credentials.",
    actionLabel: "Try again →",
    actionRoute: "/onboarding/accounting",
  },
  SAGE_CSV_WRONG_FORMAT: {
    title: "This doesn't look like a Sage 100 export",
    plain: "We couldn't find the expected columns in your uploaded file.",
    cause: "The file may be a different report than expected, or exported in the wrong format.",
    action: "Make sure you're exporting the Invoice History report in CSV or Excel format.",
    actionLabel: "View export instructions →",
    actionRoute: "/admin/accounting",
  },
  // Generic
  UNKNOWN: {
    title: "Something went wrong",
    plain: "An unexpected error occurred during the accounting sync.",
    cause: "This is usually temporary.",
    action: "Try again in a few minutes. If it keeps happening contact support with error code: [error_code].",
    actionLabel: "Contact support →",
    actionRoute: "/support",
  },
};

export function interpolateError(
  template: string,
  context: Record<string, string>,
): string {
  return template.replace(
    /\[(\w+)\]/g,
    (match, key: string) => context[key] || match,
  );
}

export function getAccountingError(
  errorCode: string,
  context: Record<string, string> = {},
): AccountingError {
  const error = ACCOUNTING_ERRORS[errorCode] || ACCOUNTING_ERRORS["UNKNOWN"];
  return {
    ...error,
    plain: interpolateError(error.plain, {
      ...context,
      error_code: errorCode,
    }),
    action: interpolateError(error.action, {
      ...context,
      error_code: errorCode,
    }),
  };
}
