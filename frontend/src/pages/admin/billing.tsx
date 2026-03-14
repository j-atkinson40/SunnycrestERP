import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { billingService } from "@/services/billing-service";
import type {
  BillingEvent,
  BillingStats,
  PaginatedBillingEvents,
  PaginatedSubscriptions,
  Subscription,
  SubscriptionPlan,
} from "@/types/billing";
import { toast } from "sonner";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  trialing: "bg-blue-100 text-blue-800",
  past_due: "bg-red-100 text-red-800",
  canceled: "bg-gray-100 text-gray-800",
  unpaid: "bg-orange-100 text-orange-800",
};

export default function BillingPage() {
  const [tab, setTab] = useState<"plans" | "subscriptions" | "events">(
    "plans",
  );
  const [stats, setStats] = useState<BillingStats | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [subs, setSubs] = useState<PaginatedSubscriptions | null>(null);
  const [events, setEvents] = useState<PaginatedBillingEvents | null>(null);
  const [subPage, setSubPage] = useState(1);
  const [eventPage, setEventPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showCreatePlan, setShowCreatePlan] = useState(false);
  const [planForm, setPlanForm] = useState({
    name: "",
    slug: "",
    description: "",
    price_monthly: "0.00",
    price_yearly: "0.00",
    max_users: "",
  });

  const loadStats = async () => {
    try {
      const s = await billingService.getStats();
      setStats(s);
    } catch {
      /* ignore */
    }
  };

  const loadPlans = async () => {
    try {
      setLoading(true);
      const result = await billingService.listPlans(true);
      setPlans(result);
    } catch {
      toast.error("Failed to load plans");
    } finally {
      setLoading(false);
    }
  };

  const loadSubs = async (page = 1) => {
    try {
      setLoading(true);
      const result = await billingService.listSubscriptions({
        page,
        per_page: 20,
      });
      setSubs(result);
      setSubPage(page);
    } catch {
      toast.error("Failed to load subscriptions");
    } finally {
      setLoading(false);
    }
  };

  const loadEvents = async (page = 1) => {
    try {
      setLoading(true);
      const result = await billingService.listEvents({ page, per_page: 20 });
      setEvents(result);
      setEventPage(page);
    } catch {
      toast.error("Failed to load events");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
    loadPlans();
  }, []);

  useEffect(() => {
    if (tab === "subscriptions" && !subs) loadSubs();
    if (tab === "events" && !events) loadEvents();
  }, [tab]);

  const handleCreatePlan = async () => {
    if (!planForm.name || !planForm.slug) {
      toast.error("Name and slug are required");
      return;
    }
    try {
      await billingService.createPlan({
        name: planForm.name,
        slug: planForm.slug,
        description: planForm.description || undefined,
        price_monthly: planForm.price_monthly,
        price_yearly: planForm.price_yearly,
        max_users: planForm.max_users ? parseInt(planForm.max_users) : undefined,
      });
      toast.success("Plan created");
      setShowCreatePlan(false);
      setPlanForm({
        name: "",
        slug: "",
        description: "",
        price_monthly: "0.00",
        price_yearly: "0.00",
        max_users: "",
      });
      loadPlans();
    } catch {
      toast.error("Failed to create plan");
    }
  };

  const handleDeletePlan = async (id: string) => {
    try {
      await billingService.deletePlan(id);
      toast.success("Plan deactivated/deleted");
      loadPlans();
    } catch {
      toast.error("Failed to delete plan");
    }
  };

  const handleCancelSub = async (id: string) => {
    try {
      await billingService.cancelSubscription(id);
      toast.success("Subscription canceled");
      loadSubs(subPage);
      loadStats();
    } catch {
      toast.error("Failed to cancel");
    }
  };

  const handleReactivate = async (id: string) => {
    try {
      await billingService.reactivateSubscription(id);
      toast.success("Subscription reactivated");
      loadSubs(subPage);
      loadStats();
    } catch {
      toast.error("Failed to reactivate");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Billing & Subscriptions</h1>
        <p className="text-muted-foreground">
          Manage plans, subscriptions, and billing events
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-6 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {stats.total_subscriptions}
              </div>
              <p className="text-xs text-muted-foreground">Total</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600">
                {stats.active_subscriptions}
              </div>
              <p className="text-xs text-muted-foreground">Active</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-red-600">
                {stats.past_due}
              </div>
              <p className="text-xs text-muted-foreground">Past Due</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-gray-600">
                {stats.canceled}
              </div>
              <p className="text-xs text-muted-foreground">Canceled</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-blue-600">
                ${stats.mrr}
              </div>
              <p className="text-xs text-muted-foreground">MRR</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                ${stats.total_revenue_30d}
              </div>
              <p className="text-xs text-muted-foreground">Revenue (30d)</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        <Button
          variant={tab === "plans" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("plans")}
        >
          Plans
        </Button>
        <Button
          variant={tab === "subscriptions" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("subscriptions")}
        >
          Subscriptions
        </Button>
        <Button
          variant={tab === "events" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("events")}
        >
          Events
        </Button>
      </div>

      {/* Plans Tab */}
      {tab === "plans" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Subscription Plans</h2>
              <Dialog
                open={showCreatePlan}
                onOpenChange={setShowCreatePlan}
              >
                <DialogTrigger render={<Button size="sm" />}>
                  Add Plan
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>New Subscription Plan</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 pt-2">
                    <div>
                      <Label>Name</Label>
                      <Input
                        value={planForm.name}
                        onChange={(e) =>
                          setPlanForm((f) => ({ ...f, name: e.target.value }))
                        }
                        placeholder="e.g. Professional"
                      />
                    </div>
                    <div>
                      <Label>Slug</Label>
                      <Input
                        value={planForm.slug}
                        onChange={(e) =>
                          setPlanForm((f) => ({ ...f, slug: e.target.value }))
                        }
                        placeholder="e.g. professional"
                      />
                    </div>
                    <div>
                      <Label>Description</Label>
                      <Input
                        value={planForm.description}
                        onChange={(e) =>
                          setPlanForm((f) => ({
                            ...f,
                            description: e.target.value,
                          }))
                        }
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label>Monthly Price</Label>
                        <Input
                          value={planForm.price_monthly}
                          onChange={(e) =>
                            setPlanForm((f) => ({
                              ...f,
                              price_monthly: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div>
                        <Label>Yearly Price</Label>
                        <Input
                          value={planForm.price_yearly}
                          onChange={(e) =>
                            setPlanForm((f) => ({
                              ...f,
                              price_yearly: e.target.value,
                            }))
                          }
                        />
                      </div>
                    </div>
                    <div>
                      <Label>Max Users (optional)</Label>
                      <Input
                        value={planForm.max_users}
                        onChange={(e) =>
                          setPlanForm((f) => ({
                            ...f,
                            max_users: e.target.value,
                          }))
                        }
                        placeholder="Leave blank for unlimited"
                      />
                    </div>
                    <Button onClick={handleCreatePlan} className="w-full">
                      Create Plan
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : plans.length > 0 ? (
              <div className="space-y-2">
                {plans.map((plan) => (
                  <div
                    key={plan.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{plan.name}</span>
                        <Badge variant="outline">{plan.slug}</Badge>
                        {!plan.is_active && (
                          <Badge variant="destructive">Inactive</Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        ${plan.price_monthly}/mo | ${plan.price_yearly}/yr
                        {plan.max_users && ` | Max ${plan.max_users} users`}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDeletePlan(plan.id)}
                    >
                      Delete
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground">
                No plans configured. Create your first plan to start billing.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Subscriptions Tab */}
      {tab === "subscriptions" && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Subscriptions</h2>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : subs && subs.items.length > 0 ? (
              <div className="space-y-2">
                {subs.items.map((sub: Subscription) => (
                  <div
                    key={sub.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {sub.company_name || sub.company_id}
                        </span>
                        <Badge
                          variant="secondary"
                          className={STATUS_COLORS[sub.status] || ""}
                        >
                          {sub.status}
                        </Badge>
                        {sub.plan && (
                          <Badge variant="outline">{sub.plan.name}</Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {sub.billing_interval} | Users: {sub.current_user_count}
                        {sub.current_period_end && (
                          <span>
                            {" "}
                            | Renews:{" "}
                            {new Date(
                              sub.current_period_end,
                            ).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {sub.status === "active" && (
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleCancelSub(sub.id)}
                        >
                          Cancel
                        </Button>
                      )}
                      {(sub.status === "canceled" ||
                        sub.status === "past_due") && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleReactivate(sub.id)}
                        >
                          Reactivate
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
                {subs.total > 20 && (
                  <div className="flex justify-center gap-2 pt-4">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={subPage <= 1}
                      onClick={() => loadSubs(subPage - 1)}
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground py-1">
                      Page {subPage} of {Math.ceil(subs.total / 20)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={subPage >= Math.ceil(subs.total / 20)}
                      onClick={() => loadSubs(subPage + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">No subscriptions yet.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Events Tab */}
      {tab === "events" && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Billing Events</h2>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : events && events.items.length > 0 ? (
              <div className="space-y-2">
                {events.items.map((event: BillingEvent) => (
                  <div
                    key={event.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{event.event_type}</Badge>
                        {event.amount && (
                          <span className="font-medium text-sm">
                            ${event.amount}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(event.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                ))}
                {events.total > 20 && (
                  <div className="flex justify-center gap-2 pt-4">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={eventPage <= 1}
                      onClick={() => loadEvents(eventPage - 1)}
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground py-1">
                      Page {eventPage} of {Math.ceil(events.total / 20)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={eventPage >= Math.ceil(events.total / 20)}
                      onClick={() => loadEvents(eventPage + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">No billing events yet.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
