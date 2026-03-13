import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { customerService } from "@/services/customer-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  CustomerListItem,
  CustomerStats,
} from "@/types/customer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge variant="default">Active</Badge>;
    case "hold":
      return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">Hold</Badge>;
    case "suspended":
      return <Badge variant="destructive">Suspended</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function CustomersPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("customers.create");

  // Customer list state
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);

  // Stats
  const [stats, setStats] = useState<CustomerStats | null>(null);

  // Create customer dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newCustomer, setNewCustomer] = useState({
    name: "",
    account_number: "",
    contact_name: "",
    email: "",
    phone: "",
    city: "",
    state: "",
    payment_terms: "",
    credit_limit: "",
  });
  const [createError, setCreateError] = useState("");

  const loadCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await customerService.getCustomers(
        page,
        20,
        search || undefined,
        filterStatus || undefined,
        includeInactive,
      );
      setCustomers(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus, includeInactive]);

  const loadStats = useCallback(async () => {
    try {
      const data = await customerService.getStats();
      setStats(data);
    } catch {
      // Stats may fail — non-critical
    }
  }, []);

  useEffect(() => {
    loadCustomers();
  }, [loadCustomers]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  async function handleCreateCustomer() {
    setCreateError("");
    try {
      await customerService.createCustomer({
        name: newCustomer.name,
        account_number: newCustomer.account_number.trim() || undefined,
        contact_name: newCustomer.contact_name.trim() || undefined,
        email: newCustomer.email.trim() || undefined,
        phone: newCustomer.phone.trim() || undefined,
        city: newCustomer.city.trim() || undefined,
        state: newCustomer.state.trim() || undefined,
        payment_terms: newCustomer.payment_terms.trim() || undefined,
        credit_limit: newCustomer.credit_limit.trim()
          ? parseFloat(newCustomer.credit_limit)
          : undefined,
      });
      setCreateOpen(false);
      setNewCustomer({
        name: "",
        account_number: "",
        contact_name: "",
        email: "",
        phone: "",
        city: "",
        state: "",
        payment_terms: "",
        credit_limit: "",
      });
      toast.success("Customer created");
      loadCustomers();
      loadStats();
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create customer"));
    }
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Customers</h1>
          <p className="text-muted-foreground">{total} total customers</p>
        </div>
        {canCreate && (
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger render={<Button />}>Add Customer</DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Customer</DialogTitle>
                <DialogDescription>
                  Add a new customer to the database.
                </DialogDescription>
              </DialogHeader>
              {createError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {createError}
                </div>
              )}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Customer Name</Label>
                  <Input
                    value={newCustomer.name}
                    onChange={(e) =>
                      setNewCustomer({ ...newCustomer, name: e.target.value })
                    }
                    placeholder="e.g. Smith Landscaping"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Account #</Label>
                    <Input
                      value={newCustomer.account_number}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          account_number: e.target.value,
                        })
                      }
                      placeholder="e.g. CUST-001"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Contact Name</Label>
                    <Input
                      value={newCustomer.contact_name}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          contact_name: e.target.value,
                        })
                      }
                      placeholder="e.g. John Smith"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input
                      type="email"
                      value={newCustomer.email}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          email: e.target.value,
                        })
                      }
                      placeholder="john@example.com"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Phone</Label>
                    <Input
                      value={newCustomer.phone}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          phone: e.target.value,
                        })
                      }
                      placeholder="(555) 123-4567"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>City</Label>
                    <Input
                      value={newCustomer.city}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          city: e.target.value,
                        })
                      }
                      placeholder="e.g. Springfield"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>State</Label>
                    <Input
                      value={newCustomer.state}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          state: e.target.value,
                        })
                      }
                      placeholder="e.g. IL"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Payment Terms</Label>
                    <Input
                      value={newCustomer.payment_terms}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          payment_terms: e.target.value,
                        })
                      }
                      placeholder="e.g. Net 30"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Credit Limit</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={newCustomer.credit_limit}
                      onChange={(e) =>
                        setNewCustomer({
                          ...newCustomer,
                          credit_limit: e.target.value,
                        })
                      }
                      placeholder="0.00"
                    />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setCreateOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateCustomer}
                  disabled={!newCustomer.name.trim()}
                >
                  Create Customer
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Customers</p>
            <p className="text-2xl font-bold">{stats.total_customers}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Active</p>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.active_customers}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">On Hold</p>
            <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {stats.on_hold}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Over Limit</p>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.over_limit_count}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Outstanding</p>
            <p className="text-2xl font-bold">{formatCurrency(stats.total_outstanding)}</p>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search customers..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="hold">On Hold</option>
          <option value="suspended">Suspended</option>
        </select>
        <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => {
              setIncludeInactive(e.target.checked);
              setPage(1);
            }}
            className="size-4 rounded border-input"
          />
          Include inactive
        </label>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Account #</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>City / State</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Balance</TableHead>
              <TableHead>Terms</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : customers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No customers found
                </TableCell>
              </TableRow>
            ) : (
              customers.map((customer) => (
                <TableRow key={customer.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/customers/${customer.id}`}
                      className="hover:underline"
                    >
                      {customer.name}
                    </Link>
                    {!customer.is_active && (
                      <Badge variant="destructive" className="ml-2">
                        Inactive
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {customer.account_number || "—"}
                  </TableCell>
                  <TableCell>
                    <div>{customer.contact_name || "—"}</div>
                    {customer.email && (
                      <div className="text-xs text-muted-foreground">
                        {customer.email}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {customer.city && customer.state
                      ? `${customer.city}, ${customer.state}`
                      : customer.city || customer.state || "—"}
                  </TableCell>
                  <TableCell>{statusBadge(customer.account_status)}</TableCell>
                  <TableCell className="text-right font-mono">
                    {customer.credit_limit !== null &&
                    customer.current_balance > customer.credit_limit ? (
                      <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400">
                        <AlertTriangle className="size-3.5" />
                        {formatCurrency(customer.current_balance)}
                      </span>
                    ) : (
                      formatCurrency(customer.current_balance)
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {customer.payment_terms || "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
