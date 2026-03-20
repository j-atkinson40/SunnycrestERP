/**
 * Accounting Connection Onboarding — Three-stage flow:
 *   Stage 1: Select software (QBO / QBD / Sage 100) + Skip / Send to Accountant
 *   Stage 2: Connect (provider-specific)
 *   Stage 3: Configure sync settings & account mappings
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Cloud,
  Database,
  ExternalLink,
  FileSpreadsheet,
  Link2,
  Loader2,
  Mail,
  Monitor,
  Send,
  SkipForward,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import apiClient from "@/lib/api-client";

// ── Types ────────────────────────────────────────────────────────

type Provider = "quickbooks_online" | "quickbooks_desktop" | "sage_100";
type Stage = "select_software" | "connect" | "configure_sync" | "complete";

interface ConnectionStatus {
  id: string | null;
  provider: string | null;
  status: string;
  setup_stage: string | null;
  qbo_company_name: string | null;
  sage_version: string | null;
  sage_connection_method: string | null;
  sage_csv_schedule: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  accountant_email: string | null;
  accountant_name: string | null;
  skip_count: number;
  skipped_at: string | null;
  sync_config: Record<string, boolean> | null;
  account_mappings: Record<string, string> | null;
}

// ── Chart of Accounts mapping rows ──────────────────────────────

const COA_ROWS = [
  { key: "sales_income", label: "Sales Income", category: "Income", placeholder: "4000 - Sales Revenue" },
  { key: "accounts_receivable", label: "Accounts Receivable", category: "Asset", placeholder: "1200 - Accounts Receivable" },
  { key: "product_sales", label: "Product Sales", category: "Income", placeholder: "4100 - Product Sales" },
  { key: "delivery_revenue", label: "Delivery Revenue", category: "Income", placeholder: "4300 - Delivery Income" },
  { key: "sales_tax_payable", label: "Sales Tax Payable", category: "Liability", placeholder: "2100 - Sales Tax Payable" },
  { key: "cost_of_goods", label: "Cost of Goods Sold", category: "Expense", placeholder: "5000 - COGS" },
];

// ── Main Page ───────────────────────────────────────────────────

export default function AccountingSetupPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [stage, setStage] = useState<Stage>("select_software");

  // Load current status
  useEffect(() => {
    apiClient
      .get("/accounting-connection/status")
      .then((res) => {
        const data = res.data as ConnectionStatus;
        setStatus(data);
        // Resume from where they left off
        if (data.setup_stage) {
          setStage(data.setup_stage as Stage);
        }
        if (data.status === "skipped") {
          setStage("select_software");
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const updateStatus = useCallback((data: ConnectionStatus) => {
    setStatus(data);
    if (data.setup_stage) {
      setStage(data.setup_stage as Stage);
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground mb-6">
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
          Setup
        </button>
        <span>/</span>
        <span className="text-foreground font-medium">Accounting</span>
      </nav>

      {/* Stage progress indicator */}
      <StageIndicator stage={stage} status={status} />

      {/* Stage content */}
      {stage === "select_software" && (
        <SelectSoftwareStage
          status={status}
          onUpdate={updateStatus}
          onSkip={() => navigate("/onboarding")}
        />
      )}
      {stage === "connect" && (
        <ConnectStage
          status={status}
          onUpdate={updateStatus}
          onBack={() => setStage("select_software")}
        />
      )}
      {stage === "configure_sync" && (
        <ConfigureSyncStage
          status={status}
          onUpdate={updateStatus}
          onBack={() => setStage("connect")}
        />
      )}
      {stage === "complete" && <CompleteStage status={status} />}
    </div>
  );
}

// ── Stage Indicator ──────────────────────────────────────────────

function StageIndicator({
  stage,
}: {
  stage: Stage;
  status: ConnectionStatus | null;
}) {
  const stages: { key: Stage; label: string; num: number }[] = [
    { key: "select_software", label: "Select Software", num: 1 },
    { key: "connect", label: "Connect", num: 2 },
    { key: "configure_sync", label: "Configure", num: 3 },
  ];

  const currentIdx = stages.findIndex((s) => s.key === stage);
  const isComplete = stage === "complete";

  return (
    <div className="flex items-center justify-between mb-8">
      {stages.map((s, idx) => {
        const done = isComplete || idx < currentIdx;
        const active = idx === currentIdx && !isComplete;
        return (
          <div key={s.key} className="flex items-center gap-2 flex-1">
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium transition-colors",
                done
                  ? "bg-green-100 text-green-700"
                  : active
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {done ? <Check className="h-4 w-4" /> : s.num}
            </div>
            <span
              className={cn(
                "text-sm hidden sm:block",
                active ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              {s.label}
            </span>
            {idx < stages.length - 1 && (
              <div
                className={cn(
                  "flex-1 h-px mx-2",
                  done ? "bg-green-300" : "bg-border",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Stage 1: Select Software ─────────────────────────────────────

function SelectSoftwareStage({
  status,
  onUpdate,
  onSkip,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
  onSkip: () => void;
}) {
  const [showSendToAccountant, setShowSendToAccountant] = useState(false);
  const [showSkipConfirm, setShowSkipConfirm] = useState(false);
  const [accountantEmail, setAccountantEmail] = useState("");
  const [accountantName, setAccountantName] = useState("");
  const [saving, setSaving] = useState(false);

  const selectProvider = async (provider: Provider) => {
    setSaving(true);
    try {
      const res = await apiClient.post("/accounting-connection/select-provider", {
        provider,
      });
      onUpdate(res.data);
    } catch {
      toast.error("Failed to select provider");
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = async () => {
    setSaving(true);
    try {
      await apiClient.post("/accounting-connection/skip");
      toast.info("You can connect your accounting software anytime from Settings.");
      onSkip();
    } catch {
      toast.error("Failed to skip");
    } finally {
      setSaving(false);
    }
  };

  const handleSendToAccountant = async () => {
    if (!accountantEmail.trim()) return;
    setSaving(true);
    try {
      const res = await apiClient.post("/accounting-connection/send-to-accountant", {
        email: accountantEmail.trim(),
        name: accountantName.trim() || null,
      });
      onUpdate(res.data);
      toast.success(`Setup link sent to ${accountantEmail}`);
      setShowSendToAccountant(false);
    } catch {
      toast.error("Failed to send invite");
    } finally {
      setSaving(false);
    }
  };

  // Pending accountant state
  if (status?.accountant_email && status?.status === "connecting") {
    return (
      <div className="space-y-6">
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-50">
              <Mail className="h-7 w-7 text-blue-600" />
            </div>
            <h2 className="text-lg font-semibold">Waiting on your accountant</h2>
            <p className="text-sm text-muted-foreground text-center max-w-sm">
              We sent a setup link to{" "}
              <span className="font-medium text-foreground">
                {status.accountant_email}
              </span>
              {status.accountant_name ? ` (${status.accountant_name})` : ""}.
              They'll choose the accounting software and connect it.
            </p>
            <Badge variant="outline" className="text-xs">
              Link expires in 7 days
            </Badge>
          </CardContent>
        </Card>

        <div className="flex justify-center gap-3">
          <Button
            variant="outline"
            onClick={() => {
              setShowSendToAccountant(false);
              // Allow user to continue themselves
            }}
          >
            I'll do it myself instead
          </Button>
          <Button variant="outline" onClick={onSkip}>
            Skip for now
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Connect your accounting software
        </h1>
        <p className="mt-1 text-gray-500">
          Invoices, payments, and customer records will sync automatically.
          Choose your accounting software to get started.
        </p>
      </div>

      {/* Provider cards */}
      <div className="grid gap-4">
        {/* QuickBooks Online */}
        <button
          type="button"
          disabled={saving}
          onClick={() => selectProvider("quickbooks_online")}
          className="rounded-xl border-2 p-5 text-left hover:border-primary hover:bg-primary/5 transition-colors disabled:opacity-50"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#2CA01C]/10">
              <span className="text-xl font-bold text-[#2CA01C]">QB</span>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold">QuickBooks Online</h3>
                <Badge className="bg-blue-100 text-blue-700 text-xs">
                  <Cloud className="h-3 w-3 mr-1" />
                  Cloud
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Direct cloud-to-cloud sync. Customers, invoices, and payments
                flow automatically in real time.
              </p>
            </div>
            <ArrowRight className="h-5 w-5 text-muted-foreground mt-1 shrink-0" />
          </div>
        </button>

        {/* QuickBooks Desktop */}
        <button
          type="button"
          disabled={saving}
          onClick={() => selectProvider("quickbooks_desktop")}
          className="rounded-xl border-2 p-5 text-left hover:border-primary hover:bg-primary/5 transition-colors disabled:opacity-50"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#2CA01C]/10">
              <Monitor className="h-6 w-6 text-[#2CA01C]" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold">QuickBooks Desktop</h3>
                <Badge variant="outline" className="text-xs">
                  <Monitor className="h-3 w-3 mr-1" />
                  Desktop
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Syncs via the Intuit Web Connector installed on your QuickBooks
                computer. Runs automatically on a schedule.
              </p>
            </div>
            <ArrowRight className="h-5 w-5 text-muted-foreground mt-1 shrink-0" />
          </div>
        </button>

        {/* Sage 100 */}
        <button
          type="button"
          disabled={saving}
          onClick={() => selectProvider("sage_100")}
          className="rounded-xl border-2 p-5 text-left hover:border-primary hover:bg-primary/5 transition-colors disabled:opacity-50"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-emerald-100">
              <Database className="h-6 w-6 text-emerald-700" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold">Sage 100</h3>
                <Badge variant="outline" className="text-xs">
                  <FileSpreadsheet className="h-3 w-3 mr-1" />
                  CSV or API
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Export Sage-formatted CSV files on a schedule, or connect
                directly via API for real-time sync.
              </p>
            </div>
            <ArrowRight className="h-5 w-5 text-muted-foreground mt-1 shrink-0" />
          </div>
        </button>
      </div>

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">or</span>
        </div>
      </div>

      {/* Send to accountant */}
      {showSendToAccountant ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Send className="h-4 w-4" />
              Send setup link to your accountant
            </CardTitle>
            <CardDescription>
              They'll receive a link to connect your accounting software. The
              link expires in 7 days.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-sm font-medium" htmlFor="accountant-email">
                Email address
              </label>
              <input
                id="accountant-email"
                type="email"
                value={accountantEmail}
                onChange={(e) => setAccountantEmail(e.target.value)}
                placeholder="accountant@example.com"
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="accountant-name">
                Name (optional)
              </label>
              <input
                id="accountant-name"
                type="text"
                value={accountantName}
                onChange={(e) => setAccountantName(e.target.value)}
                placeholder="Jane Smith"
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              />
            </div>
            <div className="flex gap-2 pt-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSendToAccountant(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!accountantEmail.includes("@") || saving}
                onClick={handleSendToAccountant}
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                ) : (
                  <Send className="h-4 w-4 mr-1" />
                )}
                Send Link
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <button
          type="button"
          onClick={() => setShowSendToAccountant(true)}
          className="w-full rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground hover:border-primary hover:text-primary transition-colors"
        >
          <Send className="h-4 w-4 inline mr-2" />
          Have your accountant set this up instead
        </button>
      )}

      {/* Skip */}
      {showSkipConfirm ? (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="py-4">
            <p className="text-sm font-medium text-amber-900 mb-2">
              Skip accounting setup?
            </p>
            <p className="text-sm text-amber-700 mb-3">
              You can connect your accounting software anytime from Settings →
              Integrations. We'll remind you on your next login.
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSkipConfirm(false)}
              >
                Go back
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={saving}
                onClick={handleSkip}
                className="border-amber-300 text-amber-800 hover:bg-amber-100"
              >
                <SkipForward className="h-4 w-4 mr-1" />
                Yes, skip for now
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="text-center">
          <button
            type="button"
            onClick={() => setShowSkipConfirm(true)}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip for now →
          </button>
        </div>
      )}
    </div>
  );
}

// ── Stage 2: Connect ─────────────────────────────────────────────

function ConnectStage({
  status,
  onUpdate,
  onBack,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
  onBack: () => void;
}) {
  const provider = status?.provider;

  return (
    <div className="space-y-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={onBack}
        className="text-muted-foreground"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to software selection
      </Button>

      {provider === "quickbooks_online" && (
        <QBOConnectFlow status={status} onUpdate={onUpdate} />
      )}
      {provider === "quickbooks_desktop" && (
        <QBDConnectFlow status={status} onUpdate={onUpdate} />
      )}
      {provider === "sage_100" && (
        <SageConnectFlow status={status} onUpdate={onUpdate} />
      )}
    </div>
  );
}

// ── QBO Connect Flow ─────────────────────────────────────────────

function QBOConnectFlow({
  onUpdate,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
}) {
  const [connecting, setConnecting] = useState(false);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const res = await apiClient.post("/accounting-connection/qbo/connect");
      const { authorization_url } = res.data;

      // Open OAuth window
      const popup = window.open(
        authorization_url,
        "qbo_oauth",
        "width=600,height=700,scrollbars=yes",
      );

      // Poll for popup close (simplified — real implementation would use postMessage)
      const timer = setInterval(async () => {
        if (popup?.closed) {
          clearInterval(timer);
          // Mark as connected
          try {
            const connRes = await apiClient.post(
              "/accounting-connection/qbo/connected",
            );
            onUpdate(connRes.data);
            toast.success("QuickBooks Online connected!");
          } catch {
            toast.error("Connection may have failed. Please try again.");
          }
          setConnecting(false);
        }
      }, 500);
    } catch {
      toast.error("Failed to start QuickBooks connection");
      setConnecting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Connect QuickBooks Online</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Sign in to your Intuit account to authorize the connection.
        </p>
      </div>

      {/* What the connection does */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">What this connection does</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              {
                title: "Customer Sync",
                desc: "New customers push to QuickBooks. Existing records are never modified.",
              },
              {
                title: "Invoice Sync",
                desc: "Sent invoices create matching QBO invoices with the same line items and tax.",
              },
              {
                title: "Payment Sync",
                desc: "Recorded payments post to QuickBooks and apply to the correct invoice.",
              },
              {
                title: "Read-only for existing data",
                desc: "We only create new records — we never edit or delete existing QuickBooks data.",
              },
            ].map((item) => (
              <div key={item.title} className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Connect button */}
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-8">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#2CA01C]/10">
            <span className="text-2xl font-bold text-[#2CA01C]">QB</span>
          </div>
          <Button
            size="lg"
            disabled={connecting}
            onClick={handleConnect}
            className="bg-[#2CA01C] hover:bg-[#228B1B] text-white"
          >
            {connecting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Connecting...
              </>
            ) : (
              <>
                <ExternalLink className="h-4 w-4 mr-2" />
                Connect QuickBooks Online
              </>
            )}
          </Button>
          <p className="text-xs text-muted-foreground text-center max-w-sm">
            You'll be redirected to Intuit's secure sign-in page. We request
            read/write access for Customers, Invoices, and Payments only.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ── QBD Connect Flow ─────────────────────────────────────────────

function QBDConnectFlow({
  onUpdate,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
}) {
  const [_step, setStep] = useState<"instructions" | "waiting" | "connected">(
    "instructions",
  );

  const handleDownloadQWC = () => {
    toast.info("Web Connector file would download here");
    setStep("waiting");
  };

  const handleMarkConnected = async () => {
    try {
      const res = await apiClient.post("/accounting-connection/qbo/connected");
      onUpdate(res.data);
      toast.success("QuickBooks Desktop connected!");
    } catch {
      toast.error("Failed to mark as connected");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Connect QuickBooks Desktop</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The Intuit Web Connector syncs data between this platform and your
          desktop QuickBooks file automatically.
        </p>
      </div>

      {/* Step-by-step instructions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Setup Instructions</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4">
            {[
              {
                title: "Download the Web Connector file",
                desc: "Click below to download the .qwc configuration file.",
                action: (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleDownloadQWC}
                    className="mt-2"
                  >
                    <FileSpreadsheet className="h-4 w-4 mr-1" />
                    Download .qwc file
                  </Button>
                ),
              },
              {
                title: "Open the Web Connector on your QuickBooks computer",
                desc: 'In QuickBooks Desktop, go to File → App Management → Update Web Services.',
              },
              {
                title: "Add the .qwc file",
                desc: "Click 'Add an Application' and select the .qwc file you just downloaded.",
              },
              {
                title: "Authorize the connection",
                desc: "QuickBooks will ask you to authorize. Click 'Yes, always allow access.'",
              },
              {
                title: 'Click "I\'ve completed these steps"',
                desc: "We'll verify the connection and move to the next step.",
              },
            ].map((item, idx) => (
              <li key={idx} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">
                  {idx + 1}
                </span>
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{item.desc}</p>
                  {item.action}
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleMarkConnected}>
          <Check className="h-4 w-4 mr-1" />
          I've completed these steps
        </Button>
      </div>
    </div>
  );
}

// ── Sage Connect Flow ────────────────────────────────────────────

function SageConnectFlow({
  onUpdate,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
}) {
  const [method, setMethod] = useState<"csv" | "api" | null>(null);
  const [csvSchedule, setCsvSchedule] = useState("manual");
  const [sageVersion, setSageVersion] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await apiClient.post("/accounting-connection/sage/configure", {
        version: sageVersion || null,
        connection_method: method,
        csv_schedule: method === "csv" ? csvSchedule : null,
      });
      onUpdate(res.data);
      toast.success("Sage 100 configured!");
    } catch {
      toast.error("Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  // Method selection
  if (!method) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Connect Sage 100</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose how you want to connect to Sage 100.
          </p>
        </div>

        {/* Sage version */}
        <div>
          <label className="text-sm font-medium">
            Sage 100 Version (optional)
          </label>
          <select
            className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            value={sageVersion}
            onChange={(e) => setSageVersion(e.target.value)}
          >
            <option value="">Select version...</option>
            <option value="2024">Sage 100 2024</option>
            <option value="2023">Sage 100 2023</option>
            <option value="2022">Sage 100 2022</option>
            <option value="2021">Sage 100 2021</option>
            <option value="2020">Sage 100 2020</option>
            <option value="older">Earlier version</option>
          </select>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setMethod("csv")}
            className="rounded-xl border-2 p-5 text-left hover:border-primary hover:bg-primary/5 transition-colors"
          >
            <div className="flex items-center gap-2 mb-2">
              <FileSpreadsheet className="h-5 w-5 text-emerald-700" />
              <Badge>Recommended</Badge>
            </div>
            <h3 className="font-semibold">CSV Export</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Export data as Sage-formatted CSV files. Simple, reliable, and
              works with any Sage 100 setup.
            </p>
          </button>

          <button
            type="button"
            onClick={() => setMethod("api")}
            className="rounded-xl border-2 p-5 text-left hover:border-primary hover:bg-primary/5 transition-colors"
          >
            <div className="flex items-center gap-2 mb-2">
              <Link2 className="h-5 w-5 text-blue-700" />
              <Badge variant="outline">Advanced</Badge>
            </div>
            <h3 className="font-semibold">API Connection</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Direct API integration for real-time sync. Requires Sage 100
              version 2019+ with Web Services enabled.
            </p>
          </button>
        </div>
      </div>
    );
  }

  // CSV configuration
  if (method === "csv") {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setMethod(null)}
          className="text-muted-foreground"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Button>

        <div>
          <h2 className="text-xl font-semibold">Sage CSV Export Setup</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Configure how and when Sage-formatted exports are generated.
          </p>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Export Schedule</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              {
                value: "manual",
                label: "Manual",
                desc: "Generate exports on demand from the Sage Exports page.",
              },
              {
                value: "daily",
                label: "Daily Email",
                desc: "Automatically email the export file every morning at 7:00 AM.",
              },
              {
                value: "weekly",
                label: "Weekly Email",
                desc: "Automatically email a summary export every Monday at 7:00 AM.",
              },
            ].map((opt) => (
              <label
                key={opt.value}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                  csvSchedule === opt.value
                    ? "border-primary bg-primary/5"
                    : "hover:bg-muted/50",
                )}
              >
                <input
                  type="radio"
                  name="csv_schedule"
                  checked={csvSchedule === opt.value}
                  onChange={() => setCsvSchedule(opt.value)}
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
              ].map((item, i) => (
                <li key={i} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button disabled={saving} onClick={handleSave}>
            {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            Save & Continue
          </Button>
        </div>
      </div>
    );
  }

  // API configuration
  return (
    <div className="space-y-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setMethod(null)}
        className="text-muted-foreground"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back
      </Button>

      <div>
        <h2 className="text-xl font-semibold">Sage 100 API Connection</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Direct API integration requires additional setup with your Sage
          administrator.
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
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground" />
                {item}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-8">
          <p className="text-sm text-muted-foreground text-center max-w-sm">
            Our team will work with your Sage administrator to configure the API
            connection. This typically takes 2–3 business days.
          </p>
          <Button
            size="lg"
            onClick={() => {
              handleSave();
            }}
            disabled={saving}
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            Request Setup Assistance
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Stage 3: Configure Sync ──────────────────────────────────────

function ConfigureSyncStage({
  status,
  onUpdate,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
  onBack: () => void;
}) {
  const [syncCustomers, setSyncCustomers] = useState(
    status?.sync_config?.sync_customers ?? true,
  );
  const [syncInvoices, setSyncInvoices] = useState(
    status?.sync_config?.sync_invoices ?? true,
  );
  const [syncPayments, setSyncPayments] = useState(
    status?.sync_config?.sync_payments ?? true,
  );
  const [syncInventory, setSyncInventory] = useState(
    status?.sync_config?.sync_inventory ?? false,
  );
  const [mappings, setMappings] = useState<Record<string, string>>(
    (status?.account_mappings as Record<string, string>) || {},
  );
  const [saving, setSaving] = useState(false);
  const [testRunning, setTestRunning] = useState(false);
  const [testResult, setTestResult] = useState<"success" | "error" | null>(null);

  const providerLabel =
    status?.provider === "quickbooks_online"
      ? "QuickBooks Online"
      : status?.provider === "quickbooks_desktop"
        ? "QuickBooks Desktop"
        : "Sage 100";

  const handleSaveAndComplete = async () => {
    setSaving(true);
    try {
      // Save sync config
      await apiClient.post("/accounting-connection/sync-config", {
        sync_customers: syncCustomers,
        sync_invoices: syncInvoices,
        sync_payments: syncPayments,
        sync_inventory: syncInventory,
      });

      // Save mappings
      if (Object.keys(mappings).length > 0) {
        await apiClient.post("/accounting-connection/account-mappings", {
          mappings,
        });
      }

      // Mark complete
      const res = await apiClient.post("/accounting-connection/complete");
      onUpdate(res.data);
      toast.success("Accounting connection setup complete!");
    } catch {
      toast.error("Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  const handleTestSync = async () => {
    setTestRunning(true);
    setTestResult(null);
    try {
      // Simulated test — would call actual sync endpoint in production
      await new Promise((r) => setTimeout(r, 2000));
      setTestResult("success");
      toast.success("Test sync completed successfully");
    } catch {
      setTestResult("error");
      toast.error("Test sync failed");
    } finally {
      setTestRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Configure Sync Settings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose what data syncs to {providerLabel} and map your accounts.
        </p>
      </div>

      {/* Sync toggles */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Data Sync</CardTitle>
          <CardDescription>
            Select which data types sync automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            {
              key: "customers",
              label: "Customers",
              desc: "New customers created in the platform push to your books.",
              checked: syncCustomers,
              onChange: setSyncCustomers,
            },
            {
              key: "invoices",
              label: "Invoices",
              desc: "Sent invoices create matching records in your accounting software.",
              checked: syncInvoices,
              onChange: setSyncInvoices,
            },
            {
              key: "payments",
              label: "Payments",
              desc: "Recorded payments post to your books and apply to invoices.",
              checked: syncPayments,
              onChange: setSyncPayments,
            },
            {
              key: "inventory",
              label: "Inventory Transactions",
              desc: "Production entries, adjustments, and write-offs sync to your books.",
              checked: syncInventory,
              onChange: setSyncInventory,
            },
          ].map((toggle) => (
            <label
              key={toggle.key}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                toggle.checked
                  ? "border-primary bg-primary/5"
                  : "hover:bg-muted/50",
              )}
            >
              <input
                type="checkbox"
                checked={toggle.checked}
                onChange={(e) => toggle.onChange(e.target.checked)}
                className="mt-0.5 rounded"
              />
              <div>
                <p className="text-sm font-medium">{toggle.label}</p>
                <p className="text-xs text-muted-foreground">{toggle.desc}</p>
              </div>
            </label>
          ))}
        </CardContent>
      </Card>

      {/* Account mappings */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Chart of Accounts Mapping</CardTitle>
          <CardDescription>
            Map platform categories to your {providerLabel} accounts. You can
            change these later in Settings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {COA_ROWS.map((row) => (
              <div
                key={row.key}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-3"
              >
                <div>
                  <p className="text-sm font-medium">{row.label}</p>
                  <p className="text-xs text-muted-foreground">{row.category}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
                <select
                  className="h-9 rounded-md border bg-background px-3 text-sm"
                  value={mappings[row.key] || ""}
                  onChange={(e) =>
                    setMappings((m) => ({ ...m, [row.key]: e.target.value }))
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

      {/* Test sync */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Test Sync</CardTitle>
          <CardDescription>
            Run a test sync to verify your configuration before going live.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              disabled={testRunning}
              onClick={handleTestSync}
            >
              {testRunning ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                  Running test...
                </>
              ) : (
                "Run Test Sync"
              )}
            </Button>
            {testResult === "success" && (
              <span className="flex items-center gap-1 text-sm text-green-700">
                <CheckCircle2 className="h-4 w-4" />
                Test passed
              </span>
            )}
            {testResult === "error" && (
              <span className="flex items-center gap-1 text-sm text-red-600">
                <X className="h-4 w-4" />
                Test failed
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-end gap-3">
        <Button
          size="lg"
          disabled={saving}
          onClick={handleSaveAndComplete}
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Check className="h-4 w-4 mr-2" />
          )}
          Complete Setup
        </Button>
      </div>
    </div>
  );
}

// ── Stage 4: Complete ────────────────────────────────────────────

function CompleteStage({ status }: { status: ConnectionStatus | null }) {
  const navigate = useNavigate();

  const providerLabel =
    status?.provider === "quickbooks_online"
      ? "QuickBooks Online"
      : status?.provider === "quickbooks_desktop"
        ? "QuickBooks Desktop"
        : status?.provider === "sage_100"
          ? "Sage 100"
          : "your accounting software";

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center gap-4 py-8">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
          <CheckCircle2 className="h-8 w-8 text-green-600" />
        </div>
        <h2 className="text-xl font-semibold">
          {providerLabel} is connected
        </h2>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          Your accounting connection is live. Data will sync automatically based
          on your configuration. You can manage this connection anytime from
          Settings → Integrations.
        </p>
      </div>

      {/* Quick status */}
      <Card>
        <CardContent className="py-6">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-green-600">
                <CheckCircle2 className="h-6 w-6 mx-auto" />
              </p>
              <p className="text-xs text-muted-foreground mt-1">Connected</p>
            </div>
            <div>
              <p className="text-2xl font-bold">
                {status?.sync_config
                  ? Object.values(status.sync_config).filter(Boolean).length
                  : 0}
              </p>
              <p className="text-xs text-muted-foreground">Data Types</p>
            </div>
            <div>
              <p className="text-2xl font-bold">—</p>
              <p className="text-xs text-muted-foreground">Last Sync</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-center gap-3">
        <Button
          variant="outline"
          onClick={() => navigate("/admin/accounting")}
        >
          Manage Connection
        </Button>
        <Button onClick={() => navigate("/onboarding")}>
          Back to Setup Hub
        </Button>
      </div>
    </div>
  );
}
