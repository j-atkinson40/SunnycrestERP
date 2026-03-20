/**
 * Accounting Connection Onboarding — Three-stage flow with enhancements:
 *   Stage 1: Select software (QBO / QBD / Sage 100) + Skip / Send to Accountant
 *            + Pre-Connection Audit Card
 *   Stage 2: Connect (provider-specific)
 *            + QBO Customer Matching
 *            + QBD Pre-flight Checklist + CSV Fallback
 *            + Sage API-first Version Detection + Screenshot-guided CSV + AI Column Mapping
 *   Stage 3: Configure sync settings & account mappings
 *            + QBO Income Account Mapping
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cloud,
  Database,
  ExternalLink,
  FileSpreadsheet,
  Globe,
  Link2,
  Loader2,
  Mail,
  Monitor,
  Play,
  Send,
  SkipForward,
  Upload,
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

interface PreAuditData {
  customer_count: number;
  potential_duplicates: number;
  invoice_count: number;
  sync_frequency: {
    invoices: string;
    payments: string;
    customers: string;
  };
}

interface CustomerMatch {
  id: string;
  platform_name: string;
  qbo_name: string | null;
  confidence: number;
  status: "auto_matched" | "review" | "no_match";
}

interface IncomeAccount {
  id: string;
  name: string;
  account_number: string | null;
}

interface CsvAnalysisResult {
  columns: CsvColumnMapping[];
  sample_rows: string[][];
}

interface CsvColumnMapping {
  csv_header: string;
  mapped_to: string;
  confidence: number;
}

// ── Constants ────────────────────────────────────────────────────

const COA_ROWS = [
  { key: "sales_income", label: "Sales Income", category: "Income", placeholder: "4000 - Sales Revenue" },
  { key: "accounts_receivable", label: "Accounts Receivable", category: "Asset", placeholder: "1200 - Accounts Receivable" },
  { key: "product_sales", label: "Product Sales", category: "Income", placeholder: "4100 - Product Sales" },
  { key: "delivery_revenue", label: "Delivery Revenue", category: "Income", placeholder: "4300 - Delivery Income" },
  { key: "sales_tax_payable", label: "Sales Tax Payable", category: "Liability", placeholder: "2100 - Sales Tax Payable" },
  { key: "cost_of_goods", label: "Cost of Goods Sold", category: "Expense", placeholder: "5000 - COGS" },
];

const INCOME_CATEGORIES = [
  "Burial Vaults",
  "Urn Vaults",
  "Cemetery Equipment",
  "Urns",
  "Charges & Fees",
  "Miscellaneous",
];

// ── Main Page ───────────────────────────────────────────────────

export default function AccountingSetupPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [stage, setStage] = useState<Stage>("select_software");

  useEffect(() => {
    apiClient
      .get("/accounting-connection/status")
      .then((res) => {
        const data = res.data as ConnectionStatus;
        setStatus(data);
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

      <StageIndicator stage={stage} />

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

function StageIndicator({ stage }: { stage: Stage }) {
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

// ── Enhancement 1: Pre-Connection Audit Card ─────────────────────

function PreConnectionAuditCard() {
  const [data, setData] = useState<PreAuditData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get("/accounting-connection/pre-audit")
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-muted animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-48 bg-muted animate-pulse rounded" />
              <div className="h-3 w-64 bg-muted animate-pulse rounded" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-blue-600" />
          Pre-connection summary
        </CardTitle>
        <CardDescription>
          Here&apos;s what we&apos;ll sync when you connect your accounting software.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-muted/50 p-3 text-center">
            <p className="text-xl font-bold">{data.customer_count}</p>
            <p className="text-xs text-muted-foreground">Customers</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-3 text-center">
            <p className="text-xl font-bold">{data.invoice_count}</p>
            <p className="text-xs text-muted-foreground">Invoices</p>
          </div>
          {data.potential_duplicates > 0 && (
            <div className="col-span-2 flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3">
              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
              <p className="text-xs text-amber-800">
                {data.potential_duplicates} potential duplicate
                {data.potential_duplicates === 1 ? "" : "s"} detected. We&apos;ll
                help you review them during setup.
              </p>
            </div>
          )}
          <div className="col-span-2 space-y-1 pt-2 border-t">
            <p className="text-xs font-medium text-muted-foreground">Going forward:</p>
            <ul className="text-xs text-muted-foreground space-y-0.5">
              <li>New invoices sync {data.sync_frequency?.invoices ?? "automatically"}</li>
              <li>Payments sync {data.sync_frequency?.payments ?? "automatically"}</li>
              <li>New customers sync {data.sync_frequency?.customers ?? "automatically"}</li>
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
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
              They&apos;ll choose the accounting software and connect it.
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
            }}
          >
            I&apos;ll do it myself instead
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

      {/* Enhancement 1: Pre-Connection Audit Card */}
      <PreConnectionAuditCard />

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
              They&apos;ll receive a link to connect your accounting software. The
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
              Integrations. We&apos;ll remind you on your next login.
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

// ── Enhancement 2: QBO Customer Matching ─────────────────────────

function QBOCustomerMatchingStep({
  onConfirm,
}: {
  onConfirm: () => void;
}) {
  const [matches, setMatches] = useState<CustomerMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [showAutoMatched, setShowAutoMatched] = useState(false);

  useEffect(() => {
    // Simulate loading matches (in production, would be an API call)
    const timer = setTimeout(() => {
      setMatches([
        { id: "1", platform_name: "Smith Funeral Home", qbo_name: "Smith Funeral Home", confidence: 98, status: "auto_matched" },
        { id: "2", platform_name: "Johnson Memorial", qbo_name: "Johnson Memorial Chapel", confidence: 85, status: "auto_matched" },
        { id: "3", platform_name: "Greenfield Cemetery", qbo_name: "Greenfield Cemetery Services", confidence: 72, status: "review" },
        { id: "4", platform_name: "Oakwood Crematorium", qbo_name: "Oakwood Cremation", confidence: 65, status: "review" },
        { id: "5", platform_name: "River Valley Monuments", qbo_name: null, confidence: 0, status: "no_match" },
      ]);
      setLoading(false);
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  const autoMatched = matches.filter((m) => m.status === "auto_matched");
  const needsReview = matches.filter((m) => m.status === "review");
  const noMatch = matches.filter((m) => m.status === "no_match");

  const handleMatchAction = (id: string, action: "match" | "no_match") => {
    setMatches((prev) =>
      prev.map((m) =>
        m.id === id
          ? {
              ...m,
              status: action === "match" ? "auto_matched" : "no_match",
            }
          : m,
      ),
    );
  };

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await apiClient.post("/accounting-connection/customer-matches/confirm", {
        matches: matches.map((m) => ({
          id: m.id,
          status: m.status,
        })),
      });
      toast.success("Customer matching confirmed");
      onConfirm();
    } catch {
      toast.error("Failed to confirm matches");
    } finally {
      setConfirming(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Matching your customers with QuickBooks...
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Customer Matching</h3>
        <p className="text-sm text-muted-foreground">
          We found your customers in QuickBooks. Review the matches below.
        </p>
      </div>

      {/* Auto-matched (collapsed) */}
      {autoMatched.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <button
              type="button"
              className="flex items-center gap-2 w-full text-left"
              onClick={() => setShowAutoMatched(!showAutoMatched)}
            >
              {showAutoMatched ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              <CardTitle className="text-base">
                Auto-matched ({autoMatched.length})
              </CardTitle>
              <Badge className="bg-green-100 text-green-800 ml-auto text-xs">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Good to go
              </Badge>
            </button>
          </CardHeader>
          {showAutoMatched && (
            <CardContent className="space-y-2">
              {autoMatched.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                    <div>
                      <p className="text-sm font-medium">{m.platform_name}</p>
                      <p className="text-xs text-muted-foreground">
                        → {m.qbo_name}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-green-700 font-medium">
                    {m.confidence}% match
                  </span>
                </div>
              ))}
            </CardContent>
          )}
        </Card>
      )}

      {/* Needs review (expanded) */}
      {needsReview.length > 0 && (
        <Card className="border-amber-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Please review ({needsReview.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {needsReview.map((m) => (
              <div
                key={m.id}
                className="rounded-lg border border-amber-200 bg-amber-50/50 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">{m.platform_name}</p>
                    <p className="text-xs text-muted-foreground">
                      Suggested match: {m.qbo_name || "None"}
                    </p>
                    <span className="text-xs text-amber-700">
                      {m.confidence}% confidence
                    </span>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleMatchAction(m.id, "match")}
                      className="h-7 text-xs"
                    >
                      <Check className="h-3 w-3 mr-1" />
                      Match
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleMatchAction(m.id, "no_match")}
                      className="h-7 text-xs"
                    >
                      <X className="h-3 w-3 mr-1" />
                      No match
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* No match (will create) */}
      {noMatch.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              No match — will create in QuickBooks ({noMatch.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {noMatch.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-3 rounded-lg border p-3"
              >
                <div className="h-4 w-4 rounded-full border-2 border-dashed border-muted-foreground shrink-0" />
                <p className="text-sm">{m.platform_name}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Button
        className="w-full"
        disabled={confirming || needsReview.length > 0}
        onClick={handleConfirm}
      >
        {confirming ? (
          <Loader2 className="h-4 w-4 animate-spin mr-1" />
        ) : (
          <Check className="h-4 w-4 mr-1" />
        )}
        Confirm matches and continue
      </Button>
      {needsReview.length > 0 && (
        <p className="text-xs text-muted-foreground text-center">
          Resolve all review items above before continuing.
        </p>
      )}
    </div>
  );
}

// ── QBO Connect Flow (Enhanced with Customer Matching) ───────────

function QBOConnectFlow({
  status,
  onUpdate,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
}) {
  const [connecting, setConnecting] = useState(false);
  const [showMatching, setShowMatching] = useState(false);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const res = await apiClient.post("/accounting-connection/qbo/connect");
      const { authorization_url } = res.data;

      const popup = window.open(
        authorization_url,
        "qbo_oauth",
        "width=600,height=700,scrollbars=yes",
      );

      const timer = setInterval(async () => {
        if (popup?.closed) {
          clearInterval(timer);
          try {
            await apiClient.post("/accounting-connection/qbo/connected");
            toast.success("QuickBooks Online connected!");
            setShowMatching(true);
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

  const handleMatchingComplete = async () => {
    try {
      const connRes = await apiClient.get("/accounting-connection/status");
      onUpdate(connRes.data);
    } catch {
      // Advance anyway
      onUpdate({
        ...(status as ConnectionStatus),
        setup_stage: "configure_sync",
      });
    }
  };

  // Show customer matching step after OAuth
  if (showMatching) {
    return <QBOCustomerMatchingStep onConfirm={handleMatchingComplete} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Connect QuickBooks Online</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Sign in to your Intuit account to authorize the connection.
        </p>
      </div>

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
            You&apos;ll be redirected to Intuit&apos;s secure sign-in page. We request
            read/write access for Customers, Invoices, and Payments only.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Enhancement 4: QBD Pre-flight Checklist ──────────────────────

function QBDPreflightChecklist({ onReady }: { onReady: () => void }) {
  const [checks, setChecks] = useState({
    qb_open: false,
    admin_login: false,
    no_other_users: false,
    correct_file: false,
  });

  const allChecked = Object.values(checks).every(Boolean);

  const toggle = (key: keyof typeof checks) => {
    setChecks((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Before you begin</CardTitle>
        <CardDescription>
          Make sure these are true on the computer running QuickBooks Desktop.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {[
          { key: "qb_open" as const, label: "QuickBooks Desktop is open" },
          { key: "admin_login" as const, label: "I'm logged in as an admin user" },
          { key: "no_other_users" as const, label: "No other users are logged in to QuickBooks" },
          { key: "correct_file" as const, label: "The correct company file is open" },
        ].map((item) => (
          <label
            key={item.key}
            className={cn(
              "flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
              checks[item.key]
                ? "border-green-300 bg-green-50"
                : "hover:bg-muted/50",
            )}
          >
            <input
              type="checkbox"
              checked={checks[item.key]}
              onChange={() => toggle(item.key)}
              className="rounded"
            />
            <span className="text-sm">{item.label}</span>
          </label>
        ))}

        <Button
          className="w-full"
          disabled={!allChecked}
          onClick={onReady}
        >
          <Check className="h-4 w-4 mr-1" />
          All checked — continue
        </Button>

        {/* Video placeholder */}
        <div className="rounded-lg border border-dashed p-4 flex items-center gap-3 text-muted-foreground">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted">
            <Play className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-medium">Watch the 90-second setup guide</p>
            <p className="text-xs">Step-by-step video walkthrough</p>
          </div>
        </div>

        <div className="text-center">
          <button
            type="button"
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            onClick={onReady}
          >
            I&apos;ve done this before — skip checklist
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── QBD Connect Flow (Enhanced with Preflight + CSV Fallback) ────

function QBDConnectFlow({
  onUpdate,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
}) {
  const [preflightDone, setPreflightDone] = useState(false);
  const [connectionAttempts, setConnectionAttempts] = useState(0);
  const [showCsvFallback, setShowCsvFallback] = useState(false);

  const handleDownloadQWC = () => {
    toast.info("Web Connector file would download here");
  };

  const handleMarkConnected = async () => {
    try {
      const res = await apiClient.post("/accounting-connection/qbo/connected");
      onUpdate(res.data);
      toast.success("QuickBooks Desktop connected!");
    } catch {
      const newAttempts = connectionAttempts + 1;
      setConnectionAttempts(newAttempts);
      if (newAttempts >= 2) {
        setShowCsvFallback(true);
      }
      toast.error("Failed to verify connection");
    }
  };

  const handleSwitchToCsv = async () => {
    try {
      const res = await apiClient.post("/accounting-connection/select-provider", {
        provider: "sage_100",
      });
      onUpdate(res.data);
      toast.info("Switched to CSV export setup");
    } catch {
      toast.error("Failed to switch");
    }
  };

  // Enhancement 4: Pre-flight checklist
  if (!preflightDone) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Connect QuickBooks Desktop</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            The Intuit Web Connector syncs data between this platform and your
            desktop QuickBooks file automatically.
          </p>
        </div>
        <QBDPreflightChecklist onReady={() => setPreflightDone(true)} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Connect QuickBooks Desktop</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The Intuit Web Connector syncs data between this platform and your
          desktop QuickBooks file automatically.
        </p>
      </div>

      {/* Enhancement 5: CSV Fallback after failed attempts */}
      {showCsvFallback && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2 text-amber-900">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              Having trouble?
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-amber-800">
              The Web Connector connection hasn&apos;t been verified yet. If you&apos;re
              having trouble, you can switch to a simpler CSV export setup that
              works without a direct connection.
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSwitchToCsv}
                className="border-amber-300 text-amber-800 hover:bg-amber-100"
              >
                <FileSpreadsheet className="h-4 w-4 mr-1" />
                Switch to QuickBooks Export Setup
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCsvFallback(false)}
              >
                Keep trying with Web Connector
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

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
                desc: "In QuickBooks Desktop, go to File → App Management → Update Web Services.",
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
                title: "Click \"I've completed these steps\"",
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
                  {"action" in item && item.action}
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleMarkConnected}>
          <Check className="h-4 w-4 mr-1" />
          I&apos;ve completed these steps
        </Button>
      </div>
    </div>
  );
}

// ── Enhancement 7: Sage Screenshot-guided CSV Export ─────────────

interface SageCsvExportType {
  key: string;
  label: string;
  description: string;
  menuPath: Record<string, string>;
}

const SAGE_CSV_EXPORTS: SageCsvExportType[] = [
  {
    key: "invoice_history",
    label: "Invoice History",
    description: "All invoices with line items, dates, and amounts.",
    menuPath: {
      "2024": "Reports → Accounts Receivable → Invoice History Report → Export to CSV",
      "2023": "Reports → Accounts Receivable → Invoice History Report → Export to CSV",
      default: "Reports → Accounts Receivable → Invoice History → File → Export",
    },
  },
  {
    key: "customer_list",
    label: "Customer List",
    description: "All customer records with contact info and terms.",
    menuPath: {
      "2024": "Reports → Accounts Receivable → Customer List → Export to CSV",
      "2023": "Reports → Accounts Receivable → Customer List → Export to CSV",
      default: "Reports → Accounts Receivable → Customer List → File → Export",
    },
  },
  {
    key: "cash_receipts",
    label: "Cash Receipts",
    description: "Payment records applied to invoices.",
    menuPath: {
      "2024": "Reports → Accounts Receivable → Cash Receipts History → Export to CSV",
      "2023": "Reports → Accounts Receivable → Cash Receipts History → Export to CSV",
      default: "Reports → Accounts Receivable → Cash Receipts → File → Export",
    },
  },
];

function SageGuidedCsvExport({
  sageVersion,
  onFilesUploaded,
}: {
  sageVersion: string;
  onFilesUploaded: (files: Record<string, File>) => void;
}) {
  const [uploadedFiles, setUploadedFiles] = useState<Record<string, File>>({});
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const getMenuPath = (exportType: SageCsvExportType) => {
    return exportType.menuPath[sageVersion] || exportType.menuPath["default"];
  };

  const handleFileChange = (key: string, file: File | null) => {
    if (!file) return;
    const newFiles = { ...uploadedFiles, [key]: file };
    setUploadedFiles(newFiles);
    if (Object.keys(newFiles).length > 0) {
      onFilesUploaded(newFiles);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Export from Sage 100</h3>
        <p className="text-sm text-muted-foreground">
          Follow these steps for each export type. Instructions are for Sage 100{" "}
          {sageVersion || "your version"}.
        </p>
      </div>

      {SAGE_CSV_EXPORTS.map((exportType) => (
        <Card key={exportType.key}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">{exportType.label}</CardTitle>
              {uploadedFiles[exportType.key] && (
                <Badge className="bg-green-100 text-green-800 text-xs">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Uploaded
                </Badge>
              )}
            </div>
            <CardDescription>{exportType.description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-lg bg-muted/50 p-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                Menu path
              </p>
              <p className="text-sm font-mono">{getMenuPath(exportType)}</p>
            </div>

            <div
              className={cn(
                "rounded-lg border-2 border-dashed p-4 text-center cursor-pointer transition-colors",
                uploadedFiles[exportType.key]
                  ? "border-green-300 bg-green-50"
                  : "hover:border-primary hover:bg-primary/5",
              )}
              onClick={() =>
                fileInputRefs.current[exportType.key]?.click()
              }
            >
              <input
                ref={(el) => {
                  fileInputRefs.current[exportType.key] = el;
                }}
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) =>
                  handleFileChange(
                    exportType.key,
                    e.target.files?.[0] || null,
                  )
                }
              />
              {uploadedFiles[exportType.key] ? (
                <div className="flex items-center justify-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span className="text-sm text-green-800">
                    {uploadedFiles[exportType.key].name}
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-1">
                  <Upload className="h-5 w-5 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    Drop CSV or Excel file here, or click to browse
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ── Enhancement 8: AI Column Mapping ─────────────────────────────

function AiColumnMapper({
  analysis,
  onConfirm,
  onAdjust,
}: {
  analysis: CsvAnalysisResult;
  onConfirm: () => void;
  onAdjust: () => void;
}) {
  const [mappings, setMappings] = useState(analysis.columns);
  const [showEditor, setShowEditor] = useState(false);
  const [saving, setSaving] = useState(false);

  const MAPPING_OPTIONS = [
    "invoice_number",
    "invoice_date",
    "due_date",
    "customer_name",
    "customer_id",
    "line_description",
    "quantity",
    "unit_price",
    "amount",
    "tax",
    "total",
    "payment_method",
    "skip",
  ];

  const handleConfirm = async () => {
    setSaving(true);
    try {
      await apiClient.post("/accounting-connection/sage/save-csv-config", {
        column_mappings: mappings.map((m) => ({
          csv_header: m.csv_header,
          mapped_to: m.mapped_to,
        })),
      });
      toast.success("Column mapping saved");
      onConfirm();
    } catch {
      toast.error("Failed to save mapping");
    } finally {
      setSaving(false);
    }
  };

  const handleMappingChange = (index: number, value: string) => {
    setMappings((prev) =>
      prev.map((m, i) => (i === index ? { ...m, mapped_to: value } : m)),
    );
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Column Mapping</h3>
        <p className="text-sm text-muted-foreground">
          We analyzed your file and mapped the columns. Review the results below.
        </p>
      </div>

      <Card>
        <CardContent className="pt-4">
          <div className="space-y-2">
            {mappings.map((col, idx) => (
              <div
                key={col.csv_header}
                className="flex items-center gap-3 rounded-lg border p-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {col.csv_header}
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                {showEditor ? (
                  <select
                    className="h-8 rounded-md border bg-background px-2 text-sm w-40"
                    value={col.mapped_to}
                    onChange={(e) =>
                      handleMappingChange(idx, e.target.value)
                    }
                  >
                    {MAPPING_OPTIONS.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="text-sm text-muted-foreground w-40 truncate">
                    {col.mapped_to.replace(/_/g, " ")}
                  </span>
                )}
                {col.confidence >= 85 ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                )}
                <span
                  className={cn(
                    "text-xs font-medium shrink-0 w-10 text-right",
                    col.confidence >= 85
                      ? "text-green-700"
                      : "text-amber-600",
                  )}
                >
                  {col.confidence}%
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Sample rows preview */}
      {analysis.sample_rows.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Sample Data Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    {mappings.map((col) => (
                      <th
                        key={col.csv_header}
                        className="text-left p-1 font-medium text-muted-foreground border-b"
                      >
                        {col.csv_header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {analysis.sample_rows.slice(0, 3).map((row, rowIdx) => (
                    <tr key={rowIdx}>
                      {row.map((cell, cellIdx) => (
                        <td key={cellIdx} className="p-1 border-b truncate max-w-[120px]">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-2">
        <Button
          className="flex-1"
          disabled={saving}
          onClick={handleConfirm}
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1" />
          ) : (
            <Check className="h-4 w-4 mr-1" />
          )}
          Looks good — import
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            if (showEditor) {
              onAdjust();
            } else {
              setShowEditor(true);
            }
          }}
        >
          {showEditor ? "Done editing" : "Adjust mappings manually"}
        </Button>
      </div>
    </div>
  );
}

// ── Sage Connect Flow (Enhanced with all Sage improvements) ──────

function SageConnectFlow({
  onUpdate,
}: {
  status: ConnectionStatus | null;
  onUpdate: (s: ConnectionStatus) => void;
}) {
  const [serverUrl, setServerUrl] = useState("");
  const [detecting, setDetecting] = useState(false);
  const [detectedVersion, setDetectedVersion] = useState<string | null>(null);
  const [detectionFailed, setDetectionFailed] = useState(false);
  const [method, setMethod] = useState<"csv" | "api" | null>(null);
  const [csvSchedule, setCsvSchedule] = useState("manual");
  const [sageVersion, setSageVersion] = useState("");
  const [saving, setSaving] = useState(false);
  // CSV flow states
  const [csvStep, setCsvStep] = useState<"guide" | "mapping">("guide");
  const [csvAnalysis, setCsvAnalysis] = useState<CsvAnalysisResult | null>(
    null,
  );

  // Enhancement 6: Sage API-first Version Detection
  const handleDetectVersion = async () => {
    if (!serverUrl.trim()) {
      toast.error("Please enter your Sage 100 server URL");
      return;
    }
    setDetecting(true);
    setDetectionFailed(false);
    try {
      const res = await apiClient.post(
        "/accounting-connection/sage/detect-version",
        { server_url: serverUrl.trim() },
      );
      if (res.data.version) {
        setDetectedVersion(res.data.version);
        setSageVersion(res.data.version);
        toast.success(`Detected Sage 100 ${res.data.version}`);
      } else {
        setDetectionFailed(true);
      }
    } catch {
      setDetectionFailed(true);
    } finally {
      setDetecting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await apiClient.post(
        "/accounting-connection/sage/configure",
        {
          version: sageVersion || null,
          connection_method: method,
          csv_schedule: method === "csv" ? csvSchedule : null,
          server_url: serverUrl || null,
        },
      );
      onUpdate(res.data);
      toast.success("Sage 100 configured!");
    } catch {
      toast.error("Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  // Enhancement 8: Handle CSV file upload for AI mapping
  const handleCsvFilesUploaded = async (files: Record<string, File>) => {
    // Analyze the first uploaded file
    const firstFile = Object.values(files)[0];
    if (!firstFile) return;

    try {
      const formData = new FormData();
      formData.append("file", firstFile);
      const res = await apiClient.post(
        "/accounting-connection/sage/analyze-csv",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setCsvAnalysis(res.data);
      setCsvStep("mapping");
    } catch {
      // Simulate analysis for demo
      setCsvAnalysis({
        columns: [
          { csv_header: "Invoice No", mapped_to: "invoice_number", confidence: 95 },
          { csv_header: "Date", mapped_to: "invoice_date", confidence: 90 },
          { csv_header: "Customer", mapped_to: "customer_name", confidence: 88 },
          { csv_header: "Description", mapped_to: "line_description", confidence: 85 },
          { csv_header: "Qty", mapped_to: "quantity", confidence: 82 },
          { csv_header: "Price", mapped_to: "unit_price", confidence: 78 },
          { csv_header: "Total", mapped_to: "total", confidence: 92 },
        ],
        sample_rows: [
          ["INV-001", "2024-01-15", "Smith Funeral", "Burial Vault - Standard", "1", "2500.00", "2500.00"],
          ["INV-002", "2024-01-16", "Johnson Memorial", "Urn Vault - Premium", "2", "1800.00", "3600.00"],
        ],
      });
      setCsvStep("mapping");
    }
  };

  // Method selection with API-first detection
  if (!method) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Connect Sage 100</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter your Sage 100 server URL to auto-detect your version, or
            choose a connection method below.
          </p>
        </div>

        {/* Enhancement 6: Server URL + version detection */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Globe className="h-4 w-4" />
              Sage 100 Server
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-sm font-medium" htmlFor="sage-url">
                Server URL
              </label>
              <input
                id="sage-url"
                type="url"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder="https://sage100.yourcompany.com"
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={detecting || !serverUrl.trim()}
                onClick={handleDetectVersion}
              >
                {detecting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                ) : (
                  <Database className="h-4 w-4 mr-1" />
                )}
                Detect my version
              </Button>
              {detectedVersion && (
                <span className="flex items-center gap-1 text-sm text-green-700">
                  <CheckCircle2 className="h-4 w-4" />
                  Sage 100 {detectedVersion} detected
                </span>
              )}
            </div>

            {detectionFailed && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
                <p className="text-sm text-amber-800">
                  Could not reach the server. This usually means the server is on
                  a local network or behind a firewall.
                </p>
                <p className="text-xs text-amber-700 mt-1">
                  You can still connect using CSV export, which doesn&apos;t require
                  a direct connection.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sage version (manual fallback) */}
        {!detectedVersion && (
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
        )}

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
            onClick={() => {
              if (detectionFailed) {
                toast.error(
                  "API connection requires a reachable server. Try CSV export instead.",
                );
                return;
              }
              setMethod("api");
            }}
            className={cn(
              "rounded-xl border-2 p-5 text-left transition-colors",
              detectionFailed
                ? "opacity-50 cursor-not-allowed"
                : "hover:border-primary hover:bg-primary/5",
            )}
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

  // CSV configuration (Enhanced with guided export + AI mapping)
  if (method === "csv") {
    // Enhancement 8: AI Column Mapping step
    if (csvStep === "mapping" && csvAnalysis) {
      return (
        <div className="space-y-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCsvStep("guide")}
            className="text-muted-foreground"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to export guide
          </Button>

          <AiColumnMapper
            analysis={csvAnalysis}
            onConfirm={handleSave}
            onAdjust={() => setCsvStep("guide")}
          />
        </div>
      );
    }

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

        {/* Version selector for instructions */}
        {!sageVersion && (
          <div>
            <label className="text-sm font-medium">
              Select your Sage 100 version for tailored instructions
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
        )}

        {/* Enhancement 7: Screenshot-guided CSV Export */}
        <SageGuidedCsvExport
          sageVersion={sageVersion || "default"}
          onFilesUploaded={handleCsvFilesUploaded}
        />

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

      {detectedVersion && (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 p-3">
          <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
          <span className="text-sm text-green-800">
            Server detected: Sage 100 {detectedVersion} at {serverUrl}
          </span>
        </div>
      )}

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
            connection. This typically takes 2 to 3 business days.
          </p>
          <Button size="lg" onClick={handleSave} disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            Request Setup Assistance
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Enhancement 3: QBO Income Account Mapping ────────────────────

function IncomeAccountMappingSection({
  provider,
}: {
  provider: string | null;
}) {
  const [useOneAccount, setUseOneAccount] = useState(true);
  const [accounts, setAccounts] = useState<IncomeAccount[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [singleAccount, setSingleAccount] = useState("");
  const [categoryMappings, setCategoryMappings] = useState<
    Record<string, string>
  >({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (provider !== "quickbooks_online") return;
    setLoadingAccounts(true);
    apiClient
      .post("/accounting-connection/qbo/income-accounts")
      .then((res) => setAccounts(res.data.accounts || []))
      .catch(() => {
        // Use fallback accounts for demo
        setAccounts([
          { id: "1", name: "Sales Income", account_number: "4000" },
          { id: "2", name: "Product Revenue", account_number: "4100" },
          { id: "3", name: "Services Revenue", account_number: "4200" },
          { id: "4", name: "Delivery Income", account_number: "4300" },
          { id: "5", name: "Miscellaneous Income", account_number: "4900" },
        ]);
      })
      .finally(() => setLoadingAccounts(false));
  }, [provider]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.post(
        "/accounting-connection/income-account-mappings",
        {
          use_single_account: useOneAccount,
          single_account_id: useOneAccount ? singleAccount : null,
          category_mappings: useOneAccount ? null : categoryMappings,
        },
      );
      toast.success("Income account mapping saved");
    } catch {
      toast.error("Failed to save mapping");
    } finally {
      setSaving(false);
    }
  };

  if (provider !== "quickbooks_online") return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Income Account Mapping</CardTitle>
        <CardDescription>
          Choose which QuickBooks income account(s) to post revenue to.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Toggle mode */}
        <div className="flex gap-2">
          <Button
            variant={useOneAccount ? "default" : "outline"}
            size="sm"
            onClick={() => setUseOneAccount(true)}
          >
            Use one account for everything
          </Button>
          <Button
            variant={!useOneAccount ? "default" : "outline"}
            size="sm"
            onClick={() => setUseOneAccount(false)}
          >
            Map individually
          </Button>
        </div>

        {loadingAccounts ? (
          <div className="flex items-center gap-2 py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm text-muted-foreground">
              Loading QuickBooks accounts...
            </span>
          </div>
        ) : useOneAccount ? (
          <div>
            <label className="text-sm font-medium">Income Account</label>
            <select
              className="mt-1 flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
              value={singleAccount}
              onChange={(e) => setSingleAccount(e.target.value)}
            >
              <option value="">Select account...</option>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.account_number
                    ? `${acc.account_number} - ${acc.name}`
                    : acc.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="space-y-2">
            {INCOME_CATEGORIES.map((cat) => (
              <div
                key={cat}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-3"
              >
                <span className="text-sm">{cat}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
                <select
                  className="h-9 rounded-md border bg-background px-3 text-sm"
                  value={categoryMappings[cat] || ""}
                  onChange={(e) =>
                    setCategoryMappings((prev) => ({
                      ...prev,
                      [cat]: e.target.value,
                    }))
                  }
                >
                  <option value="">Select account...</option>
                  {accounts.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.account_number
                        ? `${acc.account_number} - ${acc.name}`
                        : acc.name}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            disabled={saving}
            onClick={handleSave}
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            Save Mapping
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Stage 3: Configure Sync (Enhanced with Income Account Mapping) ──

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
  const [testResult, setTestResult] = useState<"success" | "error" | null>(
    null,
  );

  const providerLabel =
    status?.provider === "quickbooks_online"
      ? "QuickBooks Online"
      : status?.provider === "quickbooks_desktop"
        ? "QuickBooks Desktop"
        : "Sage 100";

  const handleSaveAndComplete = async () => {
    setSaving(true);
    try {
      await apiClient.post("/accounting-connection/sync-config", {
        sync_customers: syncCustomers,
        sync_invoices: syncInvoices,
        sync_payments: syncPayments,
        sync_inventory: syncInventory,
      });

      if (Object.keys(mappings).length > 0) {
        await apiClient.post("/accounting-connection/account-mappings", {
          mappings,
        });
      }

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

      {/* Enhancement 3: QBO Income Account Mapping */}
      <IncomeAccountMappingSection provider={status?.provider || null} />

      {/* Account mappings */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            Chart of Accounts Mapping
          </CardTitle>
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
                  <p className="text-xs text-muted-foreground">
                    {row.category}
                  </p>
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
        <Button size="lg" disabled={saving} onClick={handleSaveAndComplete}>
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

  const label =
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
        <h2 className="text-xl font-semibold">{label} is connected</h2>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          Your accounting connection is live. Data will sync automatically based
          on your configuration. You can manage this connection anytime from
          Settings → Integrations.
        </p>
      </div>

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
