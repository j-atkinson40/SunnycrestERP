import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Building2, ChevronRight, DollarSign, MapPin, Truck } from "lucide-react";
import { cemeteryService } from "@/services/cemetery-service";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import type { Cemetery } from "@/types/customer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/contexts/auth-context";
import { toast } from "sonner";

function equipmentPreviewLabel(
  lowering: boolean,
  grass: boolean,
  tent: boolean,
  chairs: boolean,
): string {
  const canProvide: string[] = [];
  if (!lowering) canProvide.push("lowering device");
  if (!grass) canProvide.push("grass service");
  if (!tent) canProvide.push("tent");
  if (!chairs) canProvide.push("chairs");
  if (canProvide.length === 0) return "No equipment needed";
  if (canProvide.length === 4) return "Full Equipment";
  return canProvide.map((s) => s.replace(/\b\w/g, (c) => c.toUpperCase())).join(" & ");
}

export default function CemeteryProfilePage() {
  const { cemeteryId } = useParams<{ cemeteryId: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("customers.edit");

  const [cemetery, setCemetery] = useState<Cemetery | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Delivery settings form
  const [name, setName] = useState("");
  const [county, setCounty] = useState("");
  const [city, setCity] = useState("");
  const [stateVal, setStateVal] = useState("");
  const [accessNotes, setAccessNotes] = useState("");
  const [taxCountyConfirmed, setTaxCountyConfirmed] = useState(false);
  const [lowering, setLowering] = useState(false);
  const [grass, setGrass] = useState(false);
  const [tent, setTent] = useState(false);
  const [chairs, setChairs] = useState(false);

  // Order history
  const [orders, setOrders] = useState<Array<{
    order_id: string;
    order_number: string;
    customer_name: string | null;
    order_date: string | null;
    scheduled_date: string | null;
    status: string;
    total: number;
  }>>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);

  // Funeral homes
  const [funeralHomes, setFuneralHomes] = useState<Array<{
    customer_id: string;
    customer_name: string;
    order_count: number;
    last_order_date: string | null;
  }>>([]);
  const [fhLoading, setFhLoading] = useState(false);

  // Billing
  const [billingCustomer, setBillingCustomer] = useState<{
    id: string;
    name: string;
    current_balance: number;
  } | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [linkSearch, setLinkSearch] = useState("");
  const [linkResults, setLinkResults] = useState<Array<{ id: string; name: string }>>([]);
  const [linkSearching, setLinkSearching] = useState(false);
  const [showLinkForm, setShowLinkForm] = useState(false);
  const [creatingAccount, setCreatingAccount] = useState(false);

  const load = useCallback(async () => {
    if (!cemeteryId) return;
    setLoading(true);
    try {
      const cem = await cemeteryService.getCemetery(cemeteryId);
      setCemetery(cem);
      setName(cem.name);
      setCounty(cem.county || "");
      setCity(cem.city || "");
      setStateVal(cem.state || "");
      setAccessNotes(cem.access_notes || "");
      setTaxCountyConfirmed(cem.tax_county_confirmed);
      setLowering(cem.cemetery_provides_lowering_device);
      setGrass(cem.cemetery_provides_grass);
      setTent(cem.cemetery_provides_tent);
      setChairs(cem.cemetery_provides_chairs);

      // Load billing customer if linked
      if (cem.customer_id) {
        setBillingLoading(true);
        try {
          const r = await apiClient.get(`/customers/${cem.customer_id}`);
          setBillingCustomer({
            id: r.data.id,
            name: r.data.name,
            current_balance: r.data.current_balance,
          });
        } catch {
          /* non-critical */
        }
        setBillingLoading(false);
      } else {
        setBillingCustomer(null);
      }
    } catch {
      setError("Cemetery not found");
    } finally {
      setLoading(false);
    }
  }, [cemeteryId]);

  useEffect(() => {
    load();
  }, [load]);

  // Load order history and funeral homes after cemetery loads
  useEffect(() => {
    if (!cemeteryId || loading) return;
    setOrdersLoading(true);
    cemeteryService
      .getOrderHistory(cemeteryId)
      .then(setOrders)
      .catch(() => {})
      .finally(() => setOrdersLoading(false));
    setFhLoading(true);
    cemeteryService
      .getFuneralHomes(cemeteryId)
      .then(setFuneralHomes)
      .catch(() => {})
      .finally(() => setFhLoading(false));
  }, [cemeteryId, loading]);

  async function handleSave() {
    if (!cemeteryId) return;
    setSaving(true);
    setError("");
    try {
      await cemeteryService.updateCemetery(cemeteryId, {
        name: name.trim() || undefined,
        county: county.trim() || undefined,
        city: city.trim() || undefined,
        state: stateVal.trim() || undefined,
        access_notes: accessNotes || undefined,
        tax_county_confirmed: taxCountyConfirmed,
        cemetery_provides_lowering_device: lowering,
        cemetery_provides_grass: grass,
        cemetery_provides_tent: tent,
        cemetery_provides_chairs: chairs,
      });
      toast.success("Delivery settings saved");
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to save"));
    } finally {
      setSaving(false);
    }
  }

  // Link search debounce
  useEffect(() => {
    if (!linkSearch.trim()) {
      setLinkResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setLinkSearching(true);
      try {
        const r = await apiClient.get("/customers", {
          params: { search: linkSearch, customer_type: "cemetery", per_page: 8 },
        });
        setLinkResults(
          (r.data.items || []).map((c: { id: string; name: string }) => ({
            id: c.id,
            name: c.name,
          })),
        );
      } catch {
        setLinkResults([]);
      }
      setLinkSearching(false);
    }, 300);
    return () => clearTimeout(t);
  }, [linkSearch]);

  async function handleLinkCustomer(customerId: string) {
    if (!cemeteryId) return;
    try {
      await cemeteryService.linkBillingCustomer(cemeteryId, customerId);
      toast.success("Billing customer linked");
      setShowLinkForm(false);
      setLinkSearch("");
      load();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to link"));
    }
  }

  async function handleCreateAccount() {
    if (!cemeteryId) return;
    setCreatingAccount(true);
    try {
      const result = await cemeteryService.createBillingAccount(cemeteryId);
      toast.success("Billing account created and linked");
      navigate(`/customers/${result.customer_id}`);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to create account"));
    } finally {
      setCreatingAccount(false);
    }
  }

  const previewLabel = equipmentPreviewLabel(lowering, grass, tent, chairs);

  if (loading) {
    return <div className="p-8 text-center text-muted-foreground">Loading...</div>;
  }
  if (error && !cemetery) {
    return <div className="p-8 text-center text-destructive">{error}</div>;
  }
  if (!cemetery) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          to="/settings/cemeteries"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Cemetery Delivery Settings
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{cemetery.name}</h1>
            <p className="text-muted-foreground mt-0.5">
              {[
                cemetery.city,
                cemetery.state,
                cemetery.county ? `${cemetery.county} County` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <Badge variant={cemetery.is_active ? "default" : "secondary"}>
            {cemetery.is_active ? "Active" : "Inactive"}
          </Badge>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Card 1 — Delivery Settings */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Truck className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-semibold">Delivery Settings</h2>
          </div>
          <Separator />

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Cemetery Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!canEdit}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">County</Label>
              <Input
                value={county}
                onChange={(e) => setCounty(e.target.value)}
                placeholder="e.g. Cayuga"
                disabled={!canEdit}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">City</Label>
              <Input
                value={city}
                onChange={(e) => setCity(e.target.value)}
                disabled={!canEdit}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">State</Label>
              <Input
                value={stateVal}
                onChange={(e) => setStateVal(e.target.value)}
                maxLength={2}
                disabled={!canEdit}
              />
            </div>
          </div>

          <div>
            <p className="text-sm font-medium mb-2">Equipment this cemetery provides</p>
            {(
              [
                { key: "lowering", label: "Lowering device", state: lowering, setter: setLowering },
                { key: "grass", label: "Grass service", state: grass, setter: setGrass },
                { key: "tent", label: "Tent", state: tent, setter: setTent },
                { key: "chairs", label: "Chairs", state: chairs, setter: setChairs },
              ] as const
            ).map(({ key, label, state: checked, setter }) => (
              <div key={key} className="flex items-center justify-between py-1.5">
                <Label className="text-sm font-normal">{label}</Label>
                <Switch
                  checked={checked}
                  onCheckedChange={setter}
                  disabled={!canEdit}
                />
              </div>
            ))}
            <div className="mt-2 rounded-md bg-muted px-3 py-2">
              <p className="text-xs text-muted-foreground">When selected on an order we suggest:</p>
              <p className="text-sm font-medium mt-0.5">{previewLabel}</p>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1">
              <Label className="text-xs">Tax County</Label>
              <Badge
                variant="outline"
                className={`text-[10px] ${
                  taxCountyConfirmed
                    ? "border-green-300 text-green-700"
                    : "border-amber-300 text-amber-700"
                }`}
              >
                {taxCountyConfirmed ? "Confirmed" : "Unconfirmed"}
              </Badge>
            </div>
            <Input
              value={county}
              onChange={(e) => setCounty(e.target.value)}
              placeholder="County for tax jurisdiction"
              disabled={!canEdit}
            />
            {canEdit && (
              <label className="mt-1 flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={taxCountyConfirmed}
                  onChange={(e) => setTaxCountyConfirmed(e.target.checked)}
                  className="rounded"
                />
                Confirmed for tax calculation
              </label>
            )}
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Access Notes</Label>
            <textarea
              className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm resize-none placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={accessNotes}
              onChange={(e) => setAccessNotes(e.target.value)}
              placeholder="e.g. Call ahead for gate code."
              disabled={!canEdit}
            />
          </div>

          {canEdit && (
            <Button onClick={handleSave} disabled={saving} className="w-full">
              {saving ? "Saving..." : "Save Delivery Settings"}
            </Button>
          )}
        </Card>

        {/* Card 4 — Billing / Connections */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-semibold">Billing</h2>
          </div>
          <Separator />

          {billingLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : cemetery.customer_id && billingCustomer ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium text-green-800">Billing customer linked</span>
              </div>
              <div className="rounded-md border p-3 space-y-1">
                <p className="text-sm font-medium">{billingCustomer.name}</p>
                <p className="text-xs text-muted-foreground">
                  Balance: ${billingCustomer.current_balance.toFixed(2)}
                </p>
              </div>
              <Link
                to={`/customers/${billingCustomer.id}`}
                className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
              >
                View account <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">No billing relationship set up.</p>
              {canEdit && (
                <>
                  {!showLinkForm ? (
                    <div className="flex flex-col gap-2">
                      <Button variant="outline" size="sm" onClick={() => setShowLinkForm(true)}>
                        Link to existing customer
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCreateAccount}
                        disabled={creatingAccount}
                      >
                        {creatingAccount ? "Creating..." : "Create billing account"}
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label className="text-xs">Search cemetery customers</Label>
                      <Input
                        placeholder="Type to search..."
                        value={linkSearch}
                        onChange={(e) => setLinkSearch(e.target.value)}
                      />
                      {linkSearching && (
                        <p className="text-xs text-muted-foreground">Searching...</p>
                      )}
                      {linkResults.length > 0 && (
                        <div className="rounded-md border max-h-32 overflow-y-auto">
                          {linkResults.map((r) => (
                            <button
                              key={r.id}
                              type="button"
                              className="w-full text-left px-3 py-2 text-sm hover:bg-accent"
                              onClick={() => handleLinkCustomer(r.id)}
                            >
                              {r.name}
                            </button>
                          ))}
                        </div>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowLinkForm(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </Card>

        {/* Card 2 — Order History */}
        <Card className="p-6 lg:col-span-2 space-y-4">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-semibold">Recent Deliveries</h2>
          </div>
          <Separator />
          {ordersLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : orders.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No deliveries recorded yet. Orders will appear here as you use this cemetery.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Order #</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.map((o) => (
                  <TableRow key={o.order_id}>
                    <TableCell className="text-sm text-muted-foreground">
                      {o.scheduled_date
                        ? new Date(o.scheduled_date).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })
                        : o.order_date
                          ? new Date(o.order_date).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                            })
                          : "—"}
                    </TableCell>
                    <TableCell className="text-sm font-medium">
                      {o.customer_name || "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {o.order_number}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize text-xs">
                        {o.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm font-mono">
                      ${o.total.toFixed(2)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>

        {/* Card 3 — Funeral Homes */}
        <Card className="p-6 lg:col-span-2 space-y-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-semibold">Funeral Homes</h2>
            <span className="text-xs text-muted-foreground">who use this cemetery</span>
          </div>
          <Separator />
          {fhLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : funeralHomes.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No funeral home history yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Funeral Home</TableHead>
                  <TableHead>Orders</TableHead>
                  <TableHead>Last Used</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {funeralHomes.map((fh) => (
                  <TableRow key={fh.customer_id}>
                    <TableCell className="font-medium text-sm">{fh.customer_name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {fh.order_count}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {fh.last_order_date
                        ? new Date(fh.last_order_date).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })
                        : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        to={`/customers/${fh.customer_id}`}
                        className="text-xs text-primary hover:underline inline-flex items-center gap-1"
                      >
                        View <ChevronRight className="h-3 w-3" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </div>
    </div>
  );
}
