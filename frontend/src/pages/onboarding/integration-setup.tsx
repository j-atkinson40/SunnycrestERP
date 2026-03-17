import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────

type QBStep = "briefing" | "connect" | "sandbox" | "live";
type SageMode = null | "csv" | "api";

// ── Chart of Accounts placeholder rows ─────────────────────────

const COA_ROWS = [
  { label: "Sales Income", category: "Income", placeholder: "4000 - Sales Revenue" },
  { label: "Accounts Receivable", category: "Asset", placeholder: "1200 - Accounts Receivable" },
  { label: "Concrete Products", category: "Income", placeholder: "4100 - Product Sales" },
  { label: "Vault Sales", category: "Income", placeholder: "4200 - Vault Revenue" },
  { label: "Delivery Revenue", category: "Income", placeholder: "4300 - Delivery Income" },
  { label: "Sales Tax Payable", category: "Liability", placeholder: "2100 - Sales Tax Payable" },
];

// ── QuickBooks Flow ────────────────────────────────────────────

function QuickBooksFlow() {
  const navigate = useNavigate();
  const [step, setStep] = useState<QBStep>("briefing");
  const [acknowledged, setAcknowledged] = useState(false);
  const [connected, setConnected] = useState(false);
  const [testRunning, setTestRunning] = useState(false);
  const [testComplete, setTestComplete] = useState(false);
  const [mappings, setMappings] = useState<Record<string, string>>({});

  const handleConnect = useCallback(() => {
    // Simulate OAuth flow
    setConnected(true);
    toast.success("QuickBooks connected successfully");
    setTimeout(() => setStep("sandbox"), 600);
  }, []);

  const handleTestSync = useCallback(() => {
    setTestRunning(true);
    setTimeout(() => {
      setTestRunning(false);
      setTestComplete(true);
      toast.success("Test sync completed");
    }, 2000);
  }, []);

  const handleGoLive = useCallback(() => {
    setStep("live");
    toast.success("QuickBooks integration is now live!");
  }, []);

  // ── Page 1: Briefing ──────────────────────────────────────────
  if (step === "briefing") {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Here's exactly what the QuickBooks connection does</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            No surprises. Read through these four points before connecting.
          </p>
        </div>

        <div className="grid gap-4">
          {[
            {
              num: 1,
              title: "Customer Sync",
              desc: "New customers created in the platform are pushed to QuickBooks automatically. Existing QuickBooks customers are never modified.",
            },
            {
              num: 2,
              title: "Invoice Sync",
              desc: "When you click 'Send' on an invoice, it creates a matching invoice in QuickBooks with the same line items, amounts, and tax.",
            },
            {
              num: 3,
              title: "Payment Sync",
              desc: "Payments recorded here are posted to QuickBooks and applied to the correct invoice. Your AR stays in sync.",
            },
            {
              num: 4,
              title: "We never modify existing QuickBooks records",
              desc: "The connection is additive only. We create new records but never edit or delete anything already in your QuickBooks file.",
            },
          ].map((item) => (
            <div
              key={item.num}
              className="flex gap-4 rounded-lg border p-4"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                {item.num}
              </span>
              <div>
                <h3 className="text-sm font-semibold">{item.title}</h3>
                <p className="mt-0.5 text-sm text-muted-foreground">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Chart of accounts mapping */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Chart of Accounts Mapping</CardTitle>
            <CardDescription>
              Map platform categories to your QuickBooks accounts. You can change these later.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {COA_ROWS.map((row) => (
                <div key={row.label} className="grid grid-cols-3 items-center gap-3">
                  <div>
                    <p className="text-sm font-medium">{row.label}</p>
                    <p className="text-xs text-muted-foreground">{row.category}</p>
                  </div>
                  <div className="flex items-center justify-center text-muted-foreground">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
                  </div>
                  <select
                    className="h-9 rounded-md border bg-background px-3 text-sm"
                    value={mappings[row.label] || ""}
                    onChange={(e) =>
                      setMappings((m) => ({ ...m, [row.label]: e.target.value }))
                    }
                  >
                    <option value="">{row.placeholder}</option>
                    <option value="custom">Custom Account...</option>
                  </select>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Acknowledge checkbox */}
        <label className="flex items-start gap-3 rounded-lg border p-4 cursor-pointer hover:bg-muted/50 transition-colors">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-input"
          />
          <span className="text-sm">
            I understand how this connection works and what data will be synced to QuickBooks.
          </span>
        </label>

        <div className="flex justify-end">
          <Button disabled={!acknowledged} onClick={() => setStep("connect")}>
            Continue
          </Button>
        </div>
      </div>
    );
  }

  // ── Page 2: Connect ───────────────────────────────────────────
  if (step === "connect") {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Connect to QuickBooks Online</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Click the button below to open Intuit's secure login page.
          </p>
        </div>

        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            {!connected ? (
              <>
                <div className="rounded-xl bg-[#2CA01C]/10 p-4">
                  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#2CA01C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>
                </div>
                <Button size="lg" onClick={handleConnect} className="bg-[#2CA01C] hover:bg-[#228B1B]">
                  Connect QuickBooks
                </Button>
                <p className="text-xs text-muted-foreground text-center max-w-sm">
                  You'll see Intuit's authorization page asking you to select a company file
                  and grant access. We request read/write access for Customers, Invoices, and Payments only.
                </p>
              </>
            ) : (
              <>
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <p className="text-sm font-medium text-green-700">Connected to QuickBooks Online</p>
                <p className="text-xs text-muted-foreground">Company: Sample Business LLC</p>
              </>
            )}
          </CardContent>
        </Card>

        <div className="flex justify-between">
          <Button variant="outline" onClick={() => setStep("briefing")}>Back</Button>
          <Button disabled={!connected} onClick={() => setStep("sandbox")}>
            Continue to Test
          </Button>
        </div>
      </div>
    );
  }

  // ── Page 3: Sandbox Test ──────────────────────────────────────
  if (step === "sandbox") {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Run a Sandbox Test</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            We'll create test records in QuickBooks so you can verify everything looks right before going live.
          </p>
        </div>

        <Card>
          <CardContent className="py-6 space-y-4">
            {!testComplete ? (
              <div className="flex flex-col items-center gap-4">
                <Button
                  size="lg"
                  onClick={handleTestSync}
                  disabled={testRunning}
                >
                  {testRunning ? "Running Test Sync..." : "Run Test Sync"}
                </Button>
                {testRunning && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                    Creating test records in QuickBooks...
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-green-700">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  <span className="text-sm font-medium">Test sync completed successfully</span>
                </div>

                <div className="rounded-lg border divide-y">
                  {[
                    { type: "Customer", name: "Test Customer (Platform Sync)", id: "QB-10042" },
                    { type: "Invoice", name: "INV-TEST-001 ($1,250.00)", id: "QB-10043" },
                    { type: "Payment", name: "PMT-TEST-001 ($500.00)", id: "QB-10044" },
                  ].map((item) => (
                    <div key={item.type} className="flex items-center justify-between px-4 py-3">
                      <div>
                        <p className="text-sm font-medium">{item.type}</p>
                        <p className="text-xs text-muted-foreground">{item.name}</p>
                      </div>
                      <Badge variant="outline" className="font-mono text-xs">
                        {item.id}
                      </Badge>
                    </div>
                  ))}
                </div>

                <p className="text-xs text-muted-foreground">
                  Check your QuickBooks file to confirm these records look correct. Test records are clearly labeled and can be deleted later.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {testComplete && (
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => toast.info("Contact support if something looks wrong.")}>
              Something looks wrong
            </Button>
            <Button onClick={handleGoLive}>
              Test looks correct &mdash; Go Live
            </Button>
          </div>
        )}
      </div>
    );
  }

  // ── Page 4: Live ──────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center gap-4 py-8">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        </div>
        <h2 className="text-xl font-semibold">QuickBooks is connected and live</h2>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          New customers, invoices, and payments will now sync automatically. You can
          manage this connection in Settings at any time.
        </p>
      </div>

      {/* Sync status widget */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Sync Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">Just now</p>
              <p className="text-xs text-muted-foreground">Last Synced</p>
            </div>
            <div>
              <p className="text-2xl font-bold">15 min</p>
              <p className="text-xs text-muted-foreground">Next Sync</p>
            </div>
            <div>
              <p className="text-2xl font-bold">3</p>
              <p className="text-xs text-muted-foreground">Records Synced</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-center gap-3">
        <Button variant="outline" onClick={() => navigate("/admin/settings")}>
          Go to Settings
        </Button>
        <Button onClick={() => navigate("/dashboard")}>
          Back to Dashboard
        </Button>
      </div>
    </div>
  );
}

// ── Sage Flow ──────────────────────────────────────────────────

function SageFlow() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<SageMode>(null);
  const [schedule, setSchedule] = useState("manual");
  const [configured, setConfigured] = useState(false);
  const [assistanceRequested, setAssistanceRequested] = useState(false);

  // ── Mode Selection ────────────────────────────────────────────
  if (mode === null) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Sage Integration</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose how you want to connect to Sage 100.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setMode("csv")}
            className="rounded-lg border-2 p-6 text-left hover:border-primary hover:bg-primary/5 transition-colors"
          >
            <div className="flex items-center gap-2 mb-3">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><polyline points="14 2 14 8 20 8"/></svg>
              <Badge>Recommended</Badge>
            </div>
            <h3 className="text-base font-semibold">CSV Export</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Export data as Sage-formatted CSV files. Simple, reliable, and works with any Sage 100 setup.
            </p>
          </button>

          <button
            type="button"
            onClick={() => setMode("api")}
            className="rounded-lg border-2 p-6 text-left hover:border-primary hover:bg-primary/5 transition-colors"
          >
            <div className="flex items-center gap-2 mb-3">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
              <Badge variant="outline">Advanced</Badge>
            </div>
            <h3 className="text-base font-semibold">API Connection</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Direct API integration for real-time sync. Requires Sage 100 Web Services or a compatible connector.
            </p>
          </button>
        </div>
      </div>
    );
  }

  // ── CSV Configuration ─────────────────────────────────────────
  if (mode === "csv") {
    if (configured) {
      return (
        <div className="space-y-6">
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <h2 className="text-xl font-semibold">Sage CSV Export Configured</h2>
            <p className="text-sm text-muted-foreground text-center max-w-md">
              {schedule === "manual"
                ? "You can generate exports any time from the Sage Exports page."
                : schedule === "daily"
                  ? "Exports will be emailed to your accounting team daily at 7:00 AM."
                  : "Exports will be emailed every Monday at 7:00 AM."}
            </p>
          </div>
          <div className="flex justify-center gap-3">
            <Button variant="outline" onClick={() => navigate("/inventory/sage-exports")}>
              Go to Sage Exports
            </Button>
            <Button onClick={() => navigate("/dashboard")}>
              Back to Dashboard
            </Button>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setMode(null)}>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>
            Back
          </Button>
        </div>

        <div>
          <h2 className="text-xl font-semibold">CSV Export Setup</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Configure how and when Sage-formatted exports are generated.
          </p>
        </div>

        {/* Schedule options */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Export Schedule</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { value: "manual", label: "Manual", desc: "Generate exports on demand from the Sage Exports page." },
              { value: "daily", label: "Daily Email", desc: "Automatically email the export file to your accounting team every morning at 7:00 AM." },
              { value: "weekly", label: "Weekly Email", desc: "Automatically email a summary export every Monday at 7:00 AM." },
            ].map((opt) => (
              <label
                key={opt.value}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-4 cursor-pointer transition-colors",
                  schedule === opt.value ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                )}
              >
                <input
                  type="radio"
                  name="schedule"
                  value={opt.value}
                  checked={schedule === opt.value}
                  onChange={(e) => setSchedule(e.target.value)}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm font-medium">{opt.label}</p>
                  <p className="text-xs text-muted-foreground">{opt.desc}</p>
                </div>
              </label>
            ))}
          </CardContent>
        </Card>

        {/* What the export contains */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">What the Export Contains</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {[
                "Customer records (new and updated)",
                "Invoices with line items and tax",
                "Payments received with invoice application",
                "Inventory transactions (production, adjustments, write-offs)",
                "Vendor bills and purchase orders",
              ].map((item, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                  {item}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={() => toast.info("Sample export downloaded (placeholder)")}
          >
            Download Sample Export
          </Button>
          <Button onClick={() => {
            setConfigured(true);
            toast.success("Sage CSV export configured");
          }}>
            Save Configuration
          </Button>
        </div>
      </div>
    );
  }

  // ── API Connection ────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => setMode(null)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>
          Back
        </Button>
      </div>

      <div>
        <h2 className="text-xl font-semibold">Sage API Connection</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Direct API integration requires additional setup with your Sage administrator.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Technical Requirements</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            {[
              "Sage 100 version 2019 or later",
              "Sage 100 Web Services enabled and accessible",
              "API credentials (provided by your Sage administrator)",
              "Network connectivity between your Sage server and our platform",
              "SSL certificate for secure communication",
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                {item}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {!assistanceRequested ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <p className="text-sm text-muted-foreground text-center max-w-sm">
              Our team will work with your Sage administrator to configure the API connection.
              This typically takes 2-3 business days.
            </p>
            <Button
              size="lg"
              onClick={() => {
                setAssistanceRequested(true);
                toast.success("Setup assistance request submitted");
              }}
            >
              Request Setup Assistance
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <p className="text-sm font-medium">Setup assistance requested</p>
            <p className="text-xs text-muted-foreground text-center max-w-sm">
              Our team will reach out within one business day to coordinate the API setup with your Sage administrator.
            </p>
            <Button variant="outline" onClick={() => navigate("/dashboard")}>
              Back to Dashboard
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────

export default function IntegrationSetupPage() {
  const { type } = useParams<{ type: string }>();
  const navigate = useNavigate();

  if (type !== "quickbooks" && type !== "sage") {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <h2 className="text-xl font-semibold">Unknown Integration</h2>
        <p className="text-sm text-muted-foreground">
          The integration type "{type}" is not recognized.
        </p>
        <Button onClick={() => navigate("/dashboard")}>Back to Dashboard</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <button
          type="button"
          onClick={() => navigate("/dashboard")}
          className="hover:text-foreground transition-colors"
        >
          Dashboard
        </button>
        <span>/</span>
        <button
          type="button"
          onClick={() => navigate("/onboarding")}
          className="hover:text-foreground transition-colors"
        >
          Onboarding
        </button>
        <span>/</span>
        <span className="text-foreground font-medium capitalize">{type}</span>
      </nav>

      {type === "quickbooks" ? <QuickBooksFlow /> : <SageFlow />}
    </div>
  );
}
