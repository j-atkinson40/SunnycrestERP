import { useEffect, useState } from "react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface EligibleCustomer {
  id: string;
  name: string;
  outstanding_balance: number;
  last_statement_date: string | null;
}

interface StatementRunItem {
  id: string;
  customer_name: string;
  opening_balance: number;
  total_invoices: number;
  total_payments: number;
  closing_balance: number;
  delivery_status: string;
}

interface StatementRun {
  id: string;
  month: number;
  year: number;
  status: string;
  created_at: string;
  item_count: number;
  total_amount: number;
  items?: StatementRunItem[];
}

function fmtCurrency(n: number | string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n));
}

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString();
}

function statusBadge(status: string) {
  switch (status) {
    case "completed":
    case "sent":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </Badge>
      );
    case "running":
    case "generating":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </Badge>
      );
    case "draft":
    case "ready":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </Badge>
      );
    case "failed":
      return (
        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          Failed
        </Badge>
      );
    default:
      return (
        <Badge className="bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {status}
        </Badge>
      );
  }
}

function deliveryBadge(status: string) {
  switch (status) {
    case "delivered":
    case "sent":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Sent
        </Badge>
      );
    case "pending":
      return (
        <Badge className="bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          Pending
        </Badge>
      );
    case "failed":
      return (
        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          Failed
        </Badge>
      );
    default:
      return (
        <Badge className="bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {status || "Pending"}
        </Badge>
      );
  }
}

export default function StatementsPage() {
  const [activeTab, setActiveTab] = useState<"current" | "history">("current");
  const [eligibleCustomers, setEligibleCustomers] = useState<EligibleCustomer[]>([]);
  const [currentRun, setCurrentRun] = useState<StatementRun | null>(null);
  const [history, setHistory] = useState<StatementRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);

  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();

  async function fetchData() {
    setLoading(true);
    try {
      const [eligibleRes, currentRes, historyRes] = await Promise.all([
        apiClient.get("/api/v1/statements/eligible-customers").catch(() => ({ data: [] })),
        apiClient.get("/api/v1/statements/runs/current").catch(() => ({ data: null })),
        apiClient.get("/api/v1/statements/runs/history").catch(() => ({ data: [] })),
      ]);
      setEligibleCustomers(eligibleRes.data || []);
      setCurrentRun(currentRes.data || null);
      setHistory(Array.isArray(historyRes.data) ? historyRes.data : []);
    } catch {
      toast.error("Failed to load statement data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    try {
      await apiClient.post("/api/v1/statements/runs", {
        month: currentMonth,
        year: currentYear,
      });
      toast.success("Statement run started");
      await fetchData();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response: { data: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast.error(msg || "Failed to generate statements");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSendAll() {
    if (!currentRun) return;
    setSending(true);
    try {
      await apiClient.post(`/api/v1/statements/runs/${currentRun.id}/send`);
      toast.success("Statements sent");
      await fetchData();
    } catch {
      toast.error("Failed to send statements");
    } finally {
      setSending(false);
    }
  }

  const totalOutstanding = eligibleCustomers.reduce(
    (sum, c) => sum + (c.outstanding_balance || 0),
    0
  );
  const lastRunDate =
    history.length > 0 ? history[0].created_at : null;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Monthly Statements</h1>
          <p className="text-sm text-muted-foreground">
            Generate and send monthly statements to customers
          </p>
        </div>
        <Button onClick={handleGenerate} disabled={generating}>
          {generating ? "Generating..." : "Generate Statements"}
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Eligible Customers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{eligibleCustomers.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Last Run Date
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtDate(lastRunDate)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Outstanding Balance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtCurrency(totalOutstanding)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-2 border-b pb-2">
        <button
          className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
            activeTab === "current"
              ? "bg-white dark:bg-gray-900 border border-b-0 text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("current")}
        >
          Current Run
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
            activeTab === "history"
              ? "bg-white dark:bg-gray-900 border border-b-0 text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("history")}
        >
          History
        </button>
      </div>

      {/* Tab Content */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          Loading...
        </div>
      ) : activeTab === "current" ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>
              {currentRun
                ? `Statement Run - ${currentRun.month}/${currentRun.year}`
                : "No Active Run"}
            </CardTitle>
            {currentRun &&
              (currentRun.status === "ready" || currentRun.status === "completed") && (
                <Button
                  onClick={handleSendAll}
                  disabled={sending}
                  variant="outline"
                >
                  {sending ? "Sending..." : "Send All"}
                </Button>
              )}
          </CardHeader>
          <CardContent>
            {currentRun && currentRun.items && currentRun.items.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer</TableHead>
                    <TableHead className="text-right">Opening Balance</TableHead>
                    <TableHead className="text-right">Invoices</TableHead>
                    <TableHead className="text-right">Payments</TableHead>
                    <TableHead className="text-right">Closing Balance</TableHead>
                    <TableHead>Delivery</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {currentRun.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {item.customer_name}
                      </TableCell>
                      <TableCell className="text-right">
                        {fmtCurrency(item.opening_balance)}
                      </TableCell>
                      <TableCell className="text-right">
                        {fmtCurrency(item.total_invoices)}
                      </TableCell>
                      <TableCell className="text-right">
                        {fmtCurrency(item.total_payments)}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {fmtCurrency(item.closing_balance)}
                      </TableCell>
                      <TableCell>{deliveryBadge(item.delivery_status)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : currentRun ? (
              <p className="py-8 text-center text-muted-foreground">
                Run is {currentRun.status} - {statusBadge(currentRun.status)}
              </p>
            ) : (
              <p className="py-8 text-center text-muted-foreground">
                No statement run in progress. Click "Generate Statements" to start.
              </p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Run History</CardTitle>
          </CardHeader>
          <CardContent>
            {history.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Period</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Statements</TableHead>
                    <TableHead className="text-right">Total Amount</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="font-medium">
                        {run.month}/{run.year}
                      </TableCell>
                      <TableCell>{statusBadge(run.status)}</TableCell>
                      <TableCell className="text-right">{run.item_count}</TableCell>
                      <TableCell className="text-right">
                        {fmtCurrency(run.total_amount)}
                      </TableCell>
                      <TableCell>{fmtDate(run.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="py-8 text-center text-muted-foreground">
                No statement runs yet.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
