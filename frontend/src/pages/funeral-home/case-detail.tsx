import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { funeralHomeService } from "@/services/funeral-home-service";
import { CremationTab } from "@/components/funeral-home/cremation-tab";
import type {
  FHCase,
  FHCaseStatus,
  FHCaseContact,
  FHServiceItem,
  FHVaultOrder,
  FHObituary,
  FHInvoice,
  FHPayment,
  FHCaseActivity,
  FHPriceListItem,
  FHManufacturerRelationship,
  FHVaultProduct,
  FHDocument,
} from "@/types/funeral-home";
import {
  CASE_STATUS_LABELS,
  CASE_STATUS_COLORS,
  CASE_STATUS_FLOW,
  VAULT_STATUS_LABELS,
  VAULT_STATUS_FLOW,
  DOCUMENT_TYPES,
  DOCUMENT_TYPE_LABELS,
} from "@/types/funeral-home";

const currency = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
const fmtDate = (d?: string) => (d ? new Date(d).toLocaleDateString() : "");
const fmtDateTime = (d?: string) => (d ? new Date(d).toLocaleString() : "");

type Tab =
  | "overview"
  | "deceased"
  | "contacts"
  | "services"
  | "cremation"
  | "vault"
  | "obituary"
  | "documents"
  | "invoice"
  | "activity";

const TAB_LABELS: Record<Tab, string> = {
  overview: "Overview",
  deceased: "Deceased",
  contacts: "Contacts",
  services: "Services",
  cremation: "Cremation",
  vault: "Vault Order",
  obituary: "Obituary",
  documents: "Documents",
  invoice: "Invoice",
  activity: "Activity",
};

const BASE_TABS: Tab[] = [
  "overview",
  "deceased",
  "contacts",
  "services",
  "vault",
  "obituary",
  "documents",
  "invoice",
  "activity",
];

function getTabsForCase(c: FHCase | null): Tab[] {
  if (!c) return BASE_TABS;
  const isCremation = c.disposition_type === "cremation" || c.disposition_type === "direct_cremation";
  if (!isCremation) return BASE_TABS;
  // Insert cremation tab after services
  const tabs = [...BASE_TABS];
  const servicesIdx = tabs.indexOf("services");
  tabs.splice(servicesIdx + 1, 0, "cremation");
  return tabs;
}

// ── Status Timeline ───────────────────────────────────────────

function StatusTimeline({ current }: { current: FHCaseStatus }) {
  const idx = CASE_STATUS_FLOW.indexOf(current);
  return (
    <div className="flex items-center gap-1">
      {CASE_STATUS_FLOW.map((s, i) => {
        const done = i <= idx;
        const isCurrent = s === current;
        return (
          <div key={s} className="flex items-center gap-1">
            <div
              className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-bold transition-colors",
                done
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground",
                isCurrent && "ring-2 ring-primary/50",
              )}
              title={CASE_STATUS_LABELS[s]}
            >
              {i + 1}
            </div>
            {i < CASE_STATUS_FLOW.length - 1 && (
              <div
                className={cn(
                  "h-0.5 w-4",
                  i < idx ? "bg-primary" : "bg-muted",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Vault Status Timeline ─────────────────────────────────────

function VaultTimeline({ current }: { current: string }) {
  const idx = VAULT_STATUS_FLOW.indexOf(current);
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {VAULT_STATUS_FLOW.map((s, i) => {
        const done = i <= idx;
        return (
          <div key={s} className="flex items-center gap-1">
            <div
              className={cn(
                "h-3 w-3 rounded-full transition-colors",
                done ? "bg-green-500" : "bg-muted",
              )}
              title={VAULT_STATUS_LABELS[s] ?? s}
            />
            {i < VAULT_STATUS_FLOW.length - 1 && (
              <div className={cn("h-0.5 w-3", i < idx ? "bg-green-500" : "bg-muted")} />
            )}
          </div>
        );
      })}
      <span className="ml-2 text-xs text-muted-foreground">
        {VAULT_STATUS_LABELS[current] ?? current}
      </span>
    </div>
  );
}

// ── OVERVIEW TAB ──────────────────────────────────────────────

function OverviewTab({
  c,
  onAction,
}: {
  c: FHCase;
  onAction: (tab: Tab) => void;
}) {
  const vaultDanger =
    c.vault_order &&
    c.vault_order.status !== "delivered" &&
    c.service_date &&
    daysBetween(new Date(), new Date(c.service_date)) <= 1;
  const vaultWarning =
    c.vault_order &&
    c.vault_order.status !== "delivered" &&
    c.service_date &&
    daysBetween(new Date(), new Date(c.service_date)) <= 3 &&
    !vaultDanger;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Key Dates */}
      <Card>
        <CardHeader>
          <CardTitle>Key Dates</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <InfoRow label="Date of Death" value={fmtDate(c.deceased_date_of_death)} />
          <InfoRow label="Service" value={c.service_date ? `${fmtDate(c.service_date)} ${c.service_time ?? ""}` : "Not scheduled"} />
          <InfoRow label="Service Location" value={c.service_location ?? "—"} />
          {c.visitation_date && (
            <>
              <InfoRow label="Visitation" value={`${fmtDate(c.visitation_date)} ${c.visitation_start_time ?? ""} - ${c.visitation_end_time ?? ""}`} />
              <InfoRow label="Visitation Location" value={c.visitation_location ?? "—"} />
            </>
          )}
          {c.disposition_date && (
            <InfoRow label="Disposition" value={`${fmtDate(c.disposition_date)} at ${c.disposition_location ?? "—"}`} />
          )}
        </CardContent>
      </Card>

      {/* Primary Contact */}
      <Card>
        <CardHeader>
          <CardTitle>Primary Contact</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {c.primary_contact ? (
            <>
              <InfoRow label="Name" value={`${c.primary_contact.first_name} ${c.primary_contact.last_name}`} />
              <InfoRow label="Phone" value={c.primary_contact.phone_primary ?? "—"} />
              <InfoRow label="Email" value={c.primary_contact.email ?? "—"} />
              <InfoRow label="Relationship" value={c.primary_contact.relationship_to_deceased ?? "—"} />
            </>
          ) : (
            <p className="text-muted-foreground">No primary contact</p>
          )}
        </CardContent>
      </Card>

      {/* Vault Status */}
      <Card className={cn(vaultDanger && "border-red-300 bg-red-50", vaultWarning && "border-amber-300 bg-amber-50")}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Vault Status
            {vaultDanger && <span className="text-xs font-normal text-red-700">URGENT</span>}
            {vaultWarning && <span className="text-xs font-normal text-amber-700">At Risk</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {c.vault_order ? (
            <>
              <InfoRow label="Product" value={c.vault_order.vault_product_name ?? "—"} />
              <VaultTimeline current={c.vault_order.status} />
              <InfoRow label="Requested" value={fmtDate(c.vault_order.requested_delivery_date)} />
              <InfoRow label="Confirmed" value={fmtDate(c.vault_order.confirmed_delivery_date)} />
            </>
          ) : (
            <div className="space-y-2">
              <p className="text-muted-foreground">No vault order</p>
              <Button size="sm" variant="outline" onClick={() => onAction("vault")}>
                Order Vault
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Obituary */}
      <Card>
        <CardHeader>
          <CardTitle>Obituary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {c.obituary ? (
            <>
              <Badge variant="outline">{c.obituary.status}</Badge>
              <p className="text-muted-foreground line-clamp-3">
                {c.obituary.content?.slice(0, 150) ?? "No content yet"}
              </p>
            </>
          ) : (
            <div className="space-y-2">
              <p className="text-muted-foreground">No obituary</p>
              <Button size="sm" variant="outline" onClick={() => onAction("obituary")}>
                Generate Obituary
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Invoice */}
      <Card>
        <CardHeader>
          <CardTitle>Invoice</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {c.invoice ? (
            <>
              <InfoRow label="Total" value={currency(c.invoice.total_amount)} />
              <InfoRow label="Paid" value={currency(c.invoice.amount_paid)} />
              <InfoRow label="Balance Due" value={currency(c.invoice.balance_due)} />
            </>
          ) : (
            <p className="text-muted-foreground">No invoice generated</p>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => onAction("contacts")}>
            Add Contact
          </Button>
          <Button size="sm" variant="outline" onClick={() => onAction("services")}>
            Select Services
          </Button>
          <Button size="sm" variant="outline" onClick={() => onAction("vault")}>
            Order Vault
          </Button>
          <Button size="sm" variant="outline" onClick={() => onAction("obituary")}>
            Generate Obituary
          </Button>
          <Button size="sm" variant="outline" onClick={() => onAction("invoice")}>
            Create Invoice
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ── DECEASED TAB ──────────────────────────────────────────────

function DeceasedTab({ c, onSave }: { c: FHCase; onSave: (data: Record<string, unknown>) => void }) {
  const [form, setForm] = useState({
    deceased_first_name: c.deceased_first_name,
    deceased_middle_name: c.deceased_middle_name ?? "",
    deceased_last_name: c.deceased_last_name,
    deceased_date_of_birth: c.deceased_date_of_birth ?? "",
    deceased_date_of_death: c.deceased_date_of_death,
    deceased_place_of_death: c.deceased_place_of_death ?? "",
    deceased_place_of_death_name: c.deceased_place_of_death_name ?? "",
    deceased_place_of_death_city: c.deceased_place_of_death_city ?? "",
    deceased_place_of_death_state: c.deceased_place_of_death_state ?? "",
    deceased_gender: c.deceased_gender ?? "",
    deceased_age_at_death: c.deceased_age_at_death?.toString() ?? "",
    deceased_ssn_last_four: c.deceased_ssn_last_four ?? "",
    deceased_veteran: c.deceased_veteran,
    disposition_type: c.disposition_type ?? "",
    disposition_date: c.disposition_date ?? "",
    disposition_location: c.disposition_location ?? "",
    disposition_city: c.disposition_city ?? "",
    disposition_state: c.disposition_state ?? "",
    service_type: c.service_type ?? "",
    service_date: c.service_date ?? "",
    service_time: c.service_time ?? "",
    service_location: c.service_location ?? "",
    visitation_date: c.visitation_date ?? "",
    visitation_start_time: c.visitation_start_time ?? "",
    visitation_end_time: c.visitation_end_time ?? "",
    visitation_location: c.visitation_location ?? "",
  });
  const [saving, setSaving] = useState(false);

  const set = (key: string, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    const data: Record<string, unknown> = { ...form };
    if (form.deceased_age_at_death) data.deceased_age_at_death = Number(form.deceased_age_at_death);
    else data.deceased_age_at_death = undefined;
    onSave(data);
    setSaving(false);
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <Card>
        <CardHeader><CardTitle>Personal Information</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="First Name" value={form.deceased_first_name} onChange={(v) => set("deceased_first_name", v)} />
            <Field label="Middle Name" value={form.deceased_middle_name} onChange={(v) => set("deceased_middle_name", v)} />
            <Field label="Last Name" value={form.deceased_last_name} onChange={(v) => set("deceased_last_name", v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Date of Birth" type="date" value={form.deceased_date_of_birth} onChange={(v) => set("deceased_date_of_birth", v)} />
            <Field label="Date of Death" type="date" value={form.deceased_date_of_death} onChange={(v) => set("deceased_date_of_death", v)} />
            <Field label="Age at Death" type="number" value={form.deceased_age_at_death} onChange={(v) => set("deceased_age_at_death", v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Gender</Label>
              <select value={form.deceased_gender} onChange={(e) => set("deceased_gender", e.target.value)} className="w-full rounded-md border border-input px-3 py-2 text-sm">
                <option value="">Select...</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            <Field label="SSN Last 4" value={form.deceased_ssn_last_four} onChange={(v) => set("deceased_ssn_last_four", v.replace(/\D/g, "").slice(0, 4))} />
            <div className="space-y-2">
              <Label>Veteran</Label>
              <div className="pt-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.deceased_veteran} onChange={(e) => set("deceased_veteran", e.target.checked)} className="h-4 w-4 rounded border-gray-300" />
                  <span className="text-sm">Yes</span>
                </label>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Place of Death</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Place / Facility" value={form.deceased_place_of_death_name} onChange={(v) => set("deceased_place_of_death_name", v)} />
            <Field label="Address" value={form.deceased_place_of_death} onChange={(v) => set("deceased_place_of_death", v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="City" value={form.deceased_place_of_death_city} onChange={(v) => set("deceased_place_of_death_city", v)} />
            <Field label="State" value={form.deceased_place_of_death_state} onChange={(v) => set("deceased_place_of_death_state", v)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Service Details</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Service Type</Label>
              <select value={form.service_type} onChange={(e) => set("service_type", e.target.value)} className="w-full rounded-md border border-input px-3 py-2 text-sm">
                <option value="">Select...</option>
                <option value="traditional">Traditional</option>
                <option value="memorial">Memorial</option>
                <option value="graveside">Graveside</option>
                <option value="celebration_of_life">Celebration of Life</option>
                <option value="direct_burial">Direct Burial</option>
                <option value="direct_cremation">Direct Cremation</option>
              </select>
            </div>
            <Field label="Service Date" type="date" value={form.service_date} onChange={(v) => set("service_date", v)} />
            <Field label="Service Time" type="time" value={form.service_time} onChange={(v) => set("service_time", v)} />
          </div>
          <Field label="Service Location" value={form.service_location} onChange={(v) => set("service_location", v)} />
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Visitation Date" type="date" value={form.visitation_date} onChange={(v) => set("visitation_date", v)} />
            <Field label="Start Time" type="time" value={form.visitation_start_time} onChange={(v) => set("visitation_start_time", v)} />
            <Field label="End Time" type="time" value={form.visitation_end_time} onChange={(v) => set("visitation_end_time", v)} />
          </div>
          <Field label="Visitation Location" value={form.visitation_location} onChange={(v) => set("visitation_location", v)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Disposition</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>Disposition Type</Label>
              <select value={form.disposition_type} onChange={(e) => set("disposition_type", e.target.value)} className="w-full rounded-md border border-input px-3 py-2 text-sm">
                <option value="">Select...</option>
                <option value="burial">Burial</option>
                <option value="cremation">Cremation</option>
                <option value="entombment">Entombment</option>
                <option value="donation">Donation</option>
              </select>
            </div>
            <Field label="Date" type="date" value={form.disposition_date} onChange={(v) => set("disposition_date", v)} />
            <Field label="Location" value={form.disposition_location} onChange={(v) => set("disposition_location", v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="City" value={form.disposition_city} onChange={(v) => set("disposition_city", v)} />
            <Field label="State" value={form.disposition_state} onChange={(v) => set("disposition_state", v)} />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save Changes"}</Button>
      </div>
    </div>
  );
}

// ── CONTACTS TAB ──────────────────────────────────────────────

function ContactsTab({ caseId }: { caseId: string }) {
  const [contacts, setContacts] = useState<FHCaseContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ first_name: "", last_name: "", phone_primary: "", email: "", relationship_to_deceased: "", contact_type: "family" });

  const load = useCallback(async () => {
    try {
      const data = await funeralHomeService.listContacts(caseId);
      setContacts(data);
    } catch {
      toast.error("Failed to load contacts");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    try {
      await funeralHomeService.addContact(caseId, formData);
      toast.success("Contact added");
      setShowForm(false);
      setFormData({ first_name: "", last_name: "", phone_primary: "", email: "", relationship_to_deceased: "", contact_type: "family" });
      load();
    } catch {
      toast.error("Failed to add contact");
    }
  };

  const handleInvite = async (contactId: string) => {
    try {
      const result = await funeralHomeService.sendPortalInvite(caseId, contactId);
      toast.success(result.message);
      load();
    } catch {
      toast.error("Failed to send portal invite");
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading contacts...</p>;

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Contacts ({contacts.length})</h3>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "Add Contact"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardContent className="space-y-4 pt-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="First Name" value={formData.first_name} onChange={(v) => setFormData((p) => ({ ...p, first_name: v }))} />
              <Field label="Last Name" value={formData.last_name} onChange={(v) => setFormData((p) => ({ ...p, last_name: v }))} />
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Phone" value={formData.phone_primary} onChange={(v) => setFormData((p) => ({ ...p, phone_primary: v }))} />
              <Field label="Email" value={formData.email} onChange={(v) => setFormData((p) => ({ ...p, email: v }))} />
              <Field label="Relationship" value={formData.relationship_to_deceased} onChange={(v) => setFormData((p) => ({ ...p, relationship_to_deceased: v }))} />
            </div>
            <Button onClick={handleAdd} disabled={!formData.first_name || !formData.last_name}>Save Contact</Button>
          </CardContent>
        </Card>
      )}

      {contacts.map((ct) => (
        <Card key={ct.id}>
          <CardContent className="flex items-center justify-between gap-4 pt-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{ct.first_name} {ct.last_name}</span>
                <Badge variant="outline">{ct.contact_type}</Badge>
                {ct.is_primary && <Badge variant="secondary">Primary</Badge>}
              </div>
              <div className="text-sm text-muted-foreground">
                {ct.phone_primary && <span className="mr-4">{ct.phone_primary}</span>}
                {ct.email && <span className="mr-4">{ct.email}</span>}
                {ct.relationship_to_deceased && <span>{ct.relationship_to_deceased}</span>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {ct.portal_invite_sent_at ? (
                <span className="text-xs text-green-600">Invite sent {fmtDate(ct.portal_invite_sent_at)}</span>
              ) : (
                <Button size="sm" variant="outline" onClick={() => handleInvite(ct.id)}>
                  Send Portal Invite
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}

      {contacts.length === 0 && !showForm && (
        <p className="text-center text-muted-foreground py-8">No contacts yet. Add one above.</p>
      )}
    </div>
  );
}

// ── SERVICES TAB ──────────────────────────────────────────────

function ServicesTab({ caseId }: { caseId: string }) {
  const [services, setServices] = useState<FHServiceItem[]>([]);
  const [priceList, setPriceList] = useState<FHPriceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showPriceList, setShowPriceList] = useState(false);
  const [showCustom, setShowCustom] = useState(false);
  const [customForm, setCustomForm] = useState({ service_name: "", service_category: "other", quantity: "1", unit_price: "" });

  const load = useCallback(async () => {
    try {
      const [svc, pl] = await Promise.all([
        funeralHomeService.listServices(caseId),
        funeralHomeService.listPriceList(),
      ]);
      setServices(svc);
      setPriceList(pl);
    } catch {
      toast.error("Failed to load services");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const grouped = services.reduce<Record<string, FHServiceItem[]>>((acc, s) => {
    const cat = s.service_category || "Other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(s);
    return acc;
  }, {});

  const subtotal = services
    .filter((s) => s.is_selected)
    .reduce((sum, s) => sum + s.extended_price, 0);

  const handleAddFromPriceList = async (item: FHPriceListItem) => {
    try {
      await funeralHomeService.addService(caseId, {
        service_name: item.item_name,
        service_category: item.category,
        service_code: item.item_code,
        quantity: 1,
        unit_price: item.unit_price,
        is_required: item.is_required_by_law,
        is_selected: true,
      });
      toast.success(`Added ${item.item_name}`);
      load();
    } catch {
      toast.error("Failed to add service");
    }
  };

  const handleAddCustom = async () => {
    try {
      await funeralHomeService.addService(caseId, {
        service_name: customForm.service_name,
        service_category: customForm.service_category,
        quantity: Number(customForm.quantity) || 1,
        unit_price: Number(customForm.unit_price) || 0,
        is_selected: true,
      });
      toast.success("Custom item added");
      setShowCustom(false);
      setCustomForm({ service_name: "", service_category: "other", quantity: "1", unit_price: "" });
      load();
    } catch {
      toast.error("Failed to add custom item");
    }
  };

  const handleRemove = async (serviceId: string) => {
    try {
      await funeralHomeService.removeService(caseId, serviceId);
      toast.success("Service removed");
      load();
    } catch {
      toast.error("Failed to remove service");
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading services...</p>;

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Selected Services</h3>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setShowPriceList(!showPriceList)}>
            {showPriceList ? "Hide Price List" : "Add from Price List"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setShowCustom(!showCustom)}>
            Add Custom Item
          </Button>
        </div>
      </div>

      {showCustom && (
        <Card>
          <CardContent className="space-y-4 pt-4">
            <div className="grid gap-4 sm:grid-cols-4">
              <Field label="Name" value={customForm.service_name} onChange={(v) => setCustomForm((p) => ({ ...p, service_name: v }))} />
              <Field label="Category" value={customForm.service_category} onChange={(v) => setCustomForm((p) => ({ ...p, service_category: v }))} />
              <Field label="Qty" type="number" value={customForm.quantity} onChange={(v) => setCustomForm((p) => ({ ...p, quantity: v }))} />
              <Field label="Unit Price" type="number" value={customForm.unit_price} onChange={(v) => setCustomForm((p) => ({ ...p, unit_price: v }))} />
            </div>
            <Button size="sm" onClick={handleAddCustom} disabled={!customForm.service_name}>Add</Button>
          </CardContent>
        </Card>
      )}

      {showPriceList && (
        <Card>
          <CardHeader><CardTitle>General Price List</CardTitle></CardHeader>
          <CardContent className="max-h-64 overflow-y-auto space-y-1">
            {priceList.filter((p) => p.is_active).map((item) => (
              <div key={item.id} className="flex items-center justify-between py-1.5 border-b last:border-0">
                <div>
                  <span className="text-sm font-medium">{item.item_name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{item.category}</span>
                  {item.is_ftc_required_disclosure && <Badge variant="outline" className="ml-2">FTC</Badge>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm">{currency(item.unit_price)}</span>
                  <Button size="sm" variant="outline" onClick={() => handleAddFromPriceList(item)}>Add</Button>
                </div>
              </div>
            ))}
            {priceList.length === 0 && <p className="text-sm text-muted-foreground">No price list items.</p>}
          </CardContent>
        </Card>
      )}

      {Object.entries(grouped).map(([category, items]) => (
        <Card key={category}>
          <CardHeader><CardTitle className="text-sm">{category}</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {items.map((s) => (
                <div key={s.id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className={cn(!s.is_selected && "line-through text-muted-foreground")}>{s.service_name}</span>
                    {s.is_required && <Badge variant="secondary">Required</Badge>}
                    {s.service_code && <span className="text-xs text-muted-foreground">({s.service_code})</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-muted-foreground">{s.quantity} x {currency(s.unit_price)}</span>
                    <span className="font-medium">{currency(s.extended_price)}</span>
                    {!s.is_required && (
                      <button onClick={() => handleRemove(s.id)} className="text-red-500 hover:text-red-700 text-xs">Remove</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}

      {services.length > 0 && (
        <div className="text-right text-lg font-semibold">
          Subtotal: {currency(subtotal)}
        </div>
      )}

      {services.length === 0 && (
        <p className="text-center text-muted-foreground py-8">No services selected yet.</p>
      )}
    </div>
  );
}

// ── VAULT ORDER TAB ───────────────────────────────────────────

function VaultTab({ caseId, existingOrder }: { caseId: string; existingOrder?: FHVaultOrder }) {
  const [vaultOrder, setVaultOrder] = useState<FHVaultOrder | undefined>(existingOrder);
  const [manufacturers, setManufacturers] = useState<FHManufacturerRelationship[]>([]);
  const [catalog, setCatalog] = useState<FHVaultProduct[]>([]);
  const [selectedMfr, setSelectedMfr] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<FHVaultProduct | null>(null);
  const [orderForm, setOrderForm] = useState({ requested_delivery_date: "", delivery_address: "", delivery_contact_name: "", delivery_contact_phone: "", special_instructions: "" });
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [vo, mfrs] = await Promise.all([
        funeralHomeService.getVaultOrder(caseId),
        funeralHomeService.getManufacturers(),
      ]);
      if (vo) setVaultOrder(vo);
      setManufacturers(mfrs);
    } catch {
      toast.error("Failed to load vault data");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const loadCatalog = async (mfrId: string) => {
    setSelectedMfr(mfrId);
    try {
      const products = await funeralHomeService.getManufacturerCatalog(mfrId);
      setCatalog(products);
    } catch {
      toast.error("Failed to load catalog");
    }
  };

  const handleSubmit = async () => {
    if (!selectedProduct || !selectedMfr) return;
    try {
      const order = await funeralHomeService.submitVaultOrder(caseId, {
        manufacturer_tenant_id: selectedMfr,
        vault_product_id: selectedProduct.id,
        vault_product_name: selectedProduct.product_name,
        vault_product_sku: selectedProduct.sku,
        quantity: 1,
        unit_price: selectedProduct.unit_price,
        ...orderForm,
      });
      setVaultOrder(order);
      toast.success("Vault order submitted");
    } catch {
      toast.error("Failed to submit vault order");
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const updated = await funeralHomeService.syncVaultStatus(caseId);
      setVaultOrder(updated);
      toast.success("Vault status synced");
    } catch {
      toast.error("Failed to sync vault status");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading vault data...</p>;

  if (vaultOrder) {
    return (
      <div className="space-y-4 max-w-3xl">
        <Card>
          <CardHeader><CardTitle>Vault Order Details</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <InfoRow label="Order #" value={vaultOrder.order_number ?? "—"} />
            <InfoRow label="Product" value={vaultOrder.vault_product_name ?? "—"} />
            <InfoRow label="SKU" value={vaultOrder.vault_product_sku ?? "—"} />
            <InfoRow label="Quantity" value={String(vaultOrder.quantity)} />
            {vaultOrder.unit_price !== undefined && (
              <InfoRow label="Price" value={currency(vaultOrder.unit_price)} />
            )}
            <div className="pt-2">
              <VaultTimeline current={vaultOrder.status} />
            </div>
            <InfoRow label="Requested Delivery" value={fmtDate(vaultOrder.requested_delivery_date)} />
            <InfoRow label="Confirmed Delivery" value={fmtDate(vaultOrder.confirmed_delivery_date)} />
            <InfoRow label="Delivery Address" value={vaultOrder.delivery_address ?? "—"} />
            <InfoRow label="Contact" value={vaultOrder.delivery_contact_name ?? "—"} />
            {vaultOrder.special_instructions && (
              <InfoRow label="Instructions" value={vaultOrder.special_instructions} />
            )}
            {vaultOrder.delivery_status_last_updated_at && (
              <InfoRow label="Last Synced" value={fmtDateTime(vaultOrder.delivery_status_last_updated_at)} />
            )}
          </CardContent>
        </Card>
        <Button variant="outline" onClick={handleSync} disabled={syncing}>
          {syncing ? "Syncing..." : "Sync Status"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <h3 className="font-semibold">Order a Vault</h3>

      <div className="space-y-2">
        <Label>Manufacturer</Label>
        <select value={selectedMfr} onChange={(e) => loadCatalog(e.target.value)} className="w-full rounded-md border border-input px-3 py-2 text-sm">
          <option value="">Select manufacturer...</option>
          {manufacturers.map((m) => (
            <option key={m.id} value={m.manufacturer_tenant_id}>
              {m.manufacturer_name ?? m.manufacturer_tenant_id}
            </option>
          ))}
        </select>
      </div>

      {catalog.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {catalog.map((p) => (
            <Card
              key={p.id}
              className={cn(
                "cursor-pointer transition-all",
                selectedProduct?.id === p.id && "ring-2 ring-primary",
              )}
              onClick={() => setSelectedProduct(p)}
            >
              <CardContent className="pt-4 space-y-1">
                <p className="font-medium">{p.product_name}</p>
                <p className="text-xs text-muted-foreground">SKU: {p.sku}</p>
                {p.description && <p className="text-xs text-muted-foreground">{p.description}</p>}
                <p className="text-sm font-semibold">{currency(p.unit_price)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {selectedProduct && (
        <Card>
          <CardHeader><CardTitle>Delivery Details</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Field label="Requested Delivery Date" type="date" value={orderForm.requested_delivery_date} onChange={(v) => setOrderForm((p) => ({ ...p, requested_delivery_date: v }))} />
            <Field label="Delivery Address" value={orderForm.delivery_address} onChange={(v) => setOrderForm((p) => ({ ...p, delivery_address: v }))} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Contact Name" value={orderForm.delivery_contact_name} onChange={(v) => setOrderForm((p) => ({ ...p, delivery_contact_name: v }))} />
              <Field label="Contact Phone" value={orderForm.delivery_contact_phone} onChange={(v) => setOrderForm((p) => ({ ...p, delivery_contact_phone: v }))} />
            </div>
            <div className="space-y-2">
              <Label>Special Instructions</Label>
              <textarea value={orderForm.special_instructions} onChange={(e) => setOrderForm((p) => ({ ...p, special_instructions: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
            </div>
            <Button onClick={handleSubmit}>Submit Vault Order</Button>
          </CardContent>
        </Card>
      )}

      {manufacturers.length === 0 && (
        <p className="text-center text-muted-foreground py-8">
          No manufacturer relationships configured. Contact your administrator.
        </p>
      )}
    </div>
  );
}

// ── OBITUARY TAB ──────────────────────────────────────────────

function ObituaryTab({ caseId, existing }: { caseId: string; existing?: FHObituary }) {
  const [obituary, setObituary] = useState<FHObituary | undefined>(existing);
  const [loading, setLoading] = useState(!existing);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [content, setContent] = useState(existing?.content ?? "");
  const [publishLocation, setPublishLocation] = useState("");

  // AI generation form
  const [bioForm, setBioForm] = useState({
    surviving_family: "",
    education: "",
    career: "",
    military_service: "",
    hobbies: "",
    faith: "",
    accomplishments: "",
    special_memories: "",
    tone: "warm",
  });

  useEffect(() => {
    if (!existing) {
      funeralHomeService.getObituary(caseId).then((o) => {
        if (o) {
          setObituary(o);
          setContent(o.content ?? "");
        }
      }).catch(() => {}).finally(() => setLoading(false));
    }
  }, [caseId, existing]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const obit = await funeralHomeService.generateObituary(caseId, bioForm);
      setObituary(obit);
      setContent(obit.content ?? "");
      toast.success("Obituary generated");
    } catch {
      toast.error("Failed to generate obituary");
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await funeralHomeService.saveObituary(caseId, { content });
      setObituary(updated);
      toast.success("Obituary saved");
    } catch {
      toast.error("Failed to save obituary");
    } finally {
      setSaving(false);
    }
  };

  const handleSendForApproval = async () => {
    try {
      const updated = await funeralHomeService.sendObituaryForApproval(caseId);
      setObituary(updated);
      toast.success("Sent for family approval");
    } catch {
      toast.error("Failed to send for approval");
    }
  };

  const handlePublish = async () => {
    if (!publishLocation.trim()) return;
    try {
      const updated = await funeralHomeService.markObituaryPublished(caseId, [
        ...(obituary?.published_locations ?? []),
        publishLocation.trim(),
      ]);
      setObituary(updated);
      setPublishLocation("");
      toast.success("Marked as published");
    } catch {
      toast.error("Failed to update publication");
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading obituary...</p>;

  if (!obituary) {
    return (
      <div className="space-y-4 max-w-3xl">
        <h3 className="font-semibold">Generate Obituary</h3>
        <p className="text-sm text-muted-foreground">
          Provide biographical details and our AI will draft a respectful obituary.
        </p>
        <Card>
          <CardContent className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>Surviving Family</Label>
              <textarea value={bioForm.surviving_family} onChange={(e) => setBioForm((p) => ({ ...p, surviving_family: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" placeholder="Spouse, children, grandchildren..." />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Education</Label>
                <textarea value={bioForm.education} onChange={(e) => setBioForm((p) => ({ ...p, education: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
              </div>
              <div className="space-y-2">
                <Label>Career</Label>
                <textarea value={bioForm.career} onChange={(e) => setBioForm((p) => ({ ...p, career: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Military Service</Label>
                <textarea value={bioForm.military_service} onChange={(e) => setBioForm((p) => ({ ...p, military_service: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
              </div>
              <div className="space-y-2">
                <Label>Hobbies & Interests</Label>
                <textarea value={bioForm.hobbies} onChange={(e) => setBioForm((p) => ({ ...p, hobbies: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Faith / Church</Label>
                <textarea value={bioForm.faith} onChange={(e) => setBioForm((p) => ({ ...p, faith: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
              </div>
              <div className="space-y-2">
                <Label>Accomplishments</Label>
                <textarea value={bioForm.accomplishments} onChange={(e) => setBioForm((p) => ({ ...p, accomplishments: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Special Memories</Label>
              <textarea value={bioForm.special_memories} onChange={(e) => setBioForm((p) => ({ ...p, special_memories: e.target.value }))} rows={2} className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none" />
            </div>
            <div className="space-y-2">
              <Label>Tone</Label>
              <select value={bioForm.tone} onChange={(e) => setBioForm((p) => ({ ...p, tone: e.target.value }))} className="w-full rounded-md border border-input px-3 py-2 text-sm">
                <option value="warm">Warm & Personal</option>
                <option value="formal">Formal & Traditional</option>
                <option value="celebratory">Celebratory</option>
                <option value="simple">Simple & Brief</option>
              </select>
            </div>
            <Button onClick={handleGenerate} disabled={generating}>
              {generating ? "Generating..." : "Generate with AI"}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center gap-3">
        <h3 className="font-semibold">Obituary</h3>
        <Badge variant="outline">{obituary.status}</Badge>
        <span className="text-xs text-muted-foreground">v{obituary.version}</span>
      </div>

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={12}
        className="w-full rounded-md border border-input px-4 py-3 text-sm leading-relaxed resize-y"
      />

      <div className="flex flex-wrap gap-2">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Draft"}
        </Button>
        {obituary.status === "draft" && (
          <Button variant="outline" onClick={handleSendForApproval}>
            Send for Family Approval
          </Button>
        )}
        {obituary.status === "approved" && (
          <div className="flex items-center gap-2">
            <Input
              placeholder="Publication location"
              value={publishLocation}
              onChange={(e) => setPublishLocation(e.target.value)}
              className="w-48"
            />
            <Button variant="outline" onClick={handlePublish}>Mark Published</Button>
          </div>
        )}
      </div>

      {obituary.family_approved_at && (
        <Card>
          <CardContent className="pt-4 text-sm">
            <p className="text-green-700">Family approved on {fmtDate(obituary.family_approved_at)}</p>
            {obituary.family_approval_notes && (
              <p className="text-muted-foreground mt-1">{obituary.family_approval_notes}</p>
            )}
          </CardContent>
        </Card>
      )}

      {obituary.published_locations && obituary.published_locations.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Published Locations</CardTitle></CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {obituary.published_locations.map((loc, i) => (
                <li key={i} className="text-muted-foreground">{loc}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── DOCUMENTS TAB ─────────────────────────────────────────────

function DocumentsTab({ caseId }: { caseId: string }) {
  const [documents, setDocuments] = useState<FHDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ document_type: "other", document_name: "", file_url: "" });

  const load = useCallback(async () => {
    try {
      const data = await funeralHomeService.listDocuments(caseId);
      setDocuments(data as FHDocument[]);
    } catch {
      toast.error("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const handleUpload = async () => {
    try {
      await funeralHomeService.uploadDocument(caseId, form);
      toast.success("Document uploaded");
      setShowForm(false);
      setForm({ document_type: "other", document_name: "", file_url: "" });
      load();
    } catch {
      toast.error("Failed to upload document");
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading documents...</p>;

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Documents ({documents.length})</h3>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "Upload Document"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardContent className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>Document Type</Label>
              <select value={form.document_type} onChange={(e) => setForm((p) => ({ ...p, document_type: e.target.value }))} className="w-full rounded-md border border-input px-3 py-2 text-sm">
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t} value={t}>{DOCUMENT_TYPE_LABELS[t]}</option>
                ))}
              </select>
            </div>
            <Field label="Document Name" value={form.document_name} onChange={(v) => setForm((p) => ({ ...p, document_name: v }))} />
            <Field label="File URL" value={form.file_url} onChange={(v) => setForm((p) => ({ ...p, file_url: v }))} />
            <Button onClick={handleUpload} disabled={!form.document_name || !form.file_url}>Upload</Button>
          </CardContent>
        </Card>
      )}

      {documents.map((doc) => (
        <Card key={doc.id}>
          <CardContent className="flex items-center justify-between pt-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline">{DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type}</Badge>
                <span className="font-medium text-sm">{doc.document_name}</span>
              </div>
              <p className="text-xs text-muted-foreground">Uploaded {fmtDate(doc.created_at)}</p>
            </div>
            <a href={doc.file_url} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline">
              Download
            </a>
          </CardContent>
        </Card>
      ))}

      {documents.length === 0 && !showForm && (
        <p className="text-center text-muted-foreground py-8">No documents uploaded yet.</p>
      )}
    </div>
  );
}

// ── INVOICE TAB ───────────────────────────────────────────────

function InvoiceTab({ caseId, existing }: { caseId: string; existing?: FHInvoice }) {
  const [invoice, setInvoice] = useState<FHInvoice | undefined>(existing);
  const [payments, setPayments] = useState<FHPayment[]>([]);
  const [loading, setLoading] = useState(!existing);
  const [generating, setGenerating] = useState(false);
  const [showPayment, setShowPayment] = useState(false);
  const [sendEmail, setSendEmail] = useState("");
  const [paymentForm, setPaymentForm] = useState({ payment_date: new Date().toISOString().slice(0, 10), amount: "", payment_method: "check", reference_number: "", notes: "" });

  const load = useCallback(async () => {
    try {
      const [inv, pmts] = await Promise.all([
        funeralHomeService.getInvoice(caseId),
        funeralHomeService.getPayments(caseId),
      ]);
      if (inv) setInvoice(inv);
      setPayments(pmts);
    } catch {
      // ignore if no invoice
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { if (!existing) load(); }, [existing, load]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const inv = await funeralHomeService.generateInvoice(caseId);
      setInvoice(inv);
      toast.success("Invoice generated");
    } catch {
      toast.error("Failed to generate invoice");
    } finally {
      setGenerating(false);
    }
  };

  const handleSend = async () => {
    if (!sendEmail.trim()) return;
    try {
      const result = await funeralHomeService.sendInvoice(caseId, sendEmail.trim());
      toast.success(result.message);
      setSendEmail("");
      load();
    } catch {
      toast.error("Failed to send invoice");
    }
  };

  const handleRecordPayment = async () => {
    try {
      await funeralHomeService.recordPayment(caseId, {
        ...paymentForm,
        amount: Number(paymentForm.amount),
      });
      toast.success("Payment recorded");
      setShowPayment(false);
      setPaymentForm({ payment_date: new Date().toISOString().slice(0, 10), amount: "", payment_method: "check", reference_number: "", notes: "" });
      load();
    } catch {
      toast.error("Failed to record payment");
    }
  };

  const handleVoid = async () => {
    if (!confirm("Are you sure you want to void this invoice?")) return;
    try {
      await funeralHomeService.voidInvoice(caseId);
      toast.success("Invoice voided");
      load();
    } catch {
      toast.error("Failed to void invoice");
    }
  };

  if (loading) return <p className="text-muted-foreground">Loading invoice...</p>;

  if (!invoice) {
    return (
      <div className="space-y-4 max-w-3xl">
        <p className="text-muted-foreground">No invoice has been generated for this case.</p>
        <Button onClick={handleGenerate} disabled={generating}>
          {generating ? "Generating..." : "Generate Invoice from Services"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Invoice #{invoice.invoice_number}
            <Badge variant="outline">{invoice.status}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <InfoRow label="Subtotal" value={currency(invoice.subtotal)} />
          <InfoRow label="Tax" value={currency(invoice.tax_amount)} />
          <div className="border-t pt-2">
            <InfoRow label="Total" value={currency(invoice.total_amount)} />
            <InfoRow label="Paid" value={currency(invoice.amount_paid)} />
            <InfoRow label="Balance Due" value={currency(invoice.balance_due)} bold />
          </div>
          {invoice.due_date && <InfoRow label="Due Date" value={fmtDate(invoice.due_date)} />}
          {invoice.sent_at && <InfoRow label="Sent" value={`${fmtDateTime(invoice.sent_at)} to ${invoice.sent_to_email ?? ""}`} />}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <div className="flex gap-2">
          <Input placeholder="Email address" value={sendEmail} onChange={(e) => setSendEmail(e.target.value)} className="w-48" />
          <Button variant="outline" onClick={handleSend}>Send Invoice</Button>
        </div>
        <Button variant="outline" onClick={() => setShowPayment(!showPayment)}>
          Record Payment
        </Button>
        {invoice.status !== "voided" && (
          <Button variant="destructive" onClick={handleVoid}>Void</Button>
        )}
      </div>

      {showPayment && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Record Payment</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Date" type="date" value={paymentForm.payment_date} onChange={(v) => setPaymentForm((p) => ({ ...p, payment_date: v }))} />
              <Field label="Amount" type="number" value={paymentForm.amount} onChange={(v) => setPaymentForm((p) => ({ ...p, amount: v }))} />
              <div className="space-y-2">
                <Label>Method</Label>
                <select value={paymentForm.payment_method} onChange={(e) => setPaymentForm((p) => ({ ...p, payment_method: e.target.value }))} className="w-full rounded-md border border-input px-3 py-2 text-sm">
                  <option value="check">Check</option>
                  <option value="cash">Cash</option>
                  <option value="credit_card">Credit Card</option>
                  <option value="insurance">Insurance</option>
                  <option value="wire">Wire Transfer</option>
                </select>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Reference #" value={paymentForm.reference_number} onChange={(v) => setPaymentForm((p) => ({ ...p, reference_number: v }))} />
              <Field label="Notes" value={paymentForm.notes} onChange={(v) => setPaymentForm((p) => ({ ...p, notes: v }))} />
            </div>
            <Button onClick={handleRecordPayment} disabled={!paymentForm.amount}>Save Payment</Button>
          </CardContent>
        </Card>
      )}

      {payments.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Payment History</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              {payments.map((p) => (
                <div key={p.id} className="flex items-center justify-between border-b pb-2 last:border-0">
                  <div>
                    <span className="font-medium">{currency(p.amount)}</span>
                    <span className="ml-2 text-muted-foreground">{p.payment_method}</span>
                    {p.reference_number && <span className="ml-2 text-muted-foreground">Ref: {p.reference_number}</span>}
                  </div>
                  <span className="text-xs text-muted-foreground">{fmtDate(p.payment_date)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── ACTIVITY TAB ──────────────────────────────────────────────

function ActivityTab({ caseId }: { caseId: string }) {
  const [activities, setActivities] = useState<FHCaseActivity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    funeralHomeService
      .getCaseActivity(caseId)
      .then((resp) => setActivities(resp.items))
      .catch(() => toast.error("Failed to load activity"))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (loading) return <p className="text-muted-foreground">Loading activity...</p>;

  return (
    <div className="space-y-3 max-w-3xl">
      {activities.length === 0 && (
        <p className="text-center text-muted-foreground py-8">No activity recorded.</p>
      )}
      {activities.map((a) => (
        <div key={a.id} className="flex gap-3 text-sm">
          <div className="flex flex-col items-center">
            <div className="h-2.5 w-2.5 rounded-full bg-primary mt-1.5" />
            <div className="flex-1 w-px bg-muted" />
          </div>
          <div className="pb-4">
            <div className="flex items-center gap-2">
              <Badge variant="outline">{a.activity_type}</Badge>
              {a.performed_by && (
                <span className="text-xs text-muted-foreground">by {a.performed_by}</span>
              )}
            </div>
            <p className="mt-1">{a.description}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{fmtDateTime(a.created_at)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── MAIN CASE DETAIL PAGE ─────────────────────────────────────

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState<FHCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");
  const fetchCase = useCallback(async () => {
    if (!id) return;
    try {
      const data = await funeralHomeService.getCase(id);
      setCaseData(data);
    } catch {
      toast.error("Failed to load case");
      navigate("/cases");
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    fetchCase();
  }, [fetchCase]);

  const handleUpdateCase = async (data: Record<string, unknown>) => {
    if (!id) return;
    try {
      const updated = await funeralHomeService.updateCase(id, data);
      setCaseData(updated);
      toast.success("Case updated");
    } catch {
      toast.error("Failed to update case");
    }
  };

  const handleStatusChange = async (status: string) => {
    if (!id) return;
    try {
      const updated = await funeralHomeService.updateCaseStatus(id, status);
      setCaseData(updated);
      toast.success(`Status changed to ${CASE_STATUS_LABELS[status as FHCaseStatus] ?? status}`);
    } catch {
      toast.error("Failed to change status");
    }
  };

  if (loading || !caseData) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading case...</p>
      </div>
    );
  }

  const c = caseData;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">
                {c.deceased_last_name}, {c.deceased_first_name}
                {c.deceased_middle_name ? ` ${c.deceased_middle_name}` : ""}
              </h1>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                  CASE_STATUS_COLORS[c.status],
                )}
              >
                {CASE_STATUS_LABELS[c.status]}
              </span>
            </div>
            <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
              <span>Case {c.case_number}</span>
              {c.assigned_director_name && <span>Director: {c.assigned_director_name}</span>}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value=""
              onChange={(e) => {
                if (e.target.value) handleStatusChange(e.target.value);
              }}
              className="rounded-md border border-input px-3 py-1.5 text-sm"
            >
              <option value="">Change Status...</option>
              {CASE_STATUS_FLOW.map((s) => (
                <option key={s} value={s} disabled={s === c.status}>
                  {CASE_STATUS_LABELS[s]}
                </option>
              ))}
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        <StatusTimeline current={c.status} />
      </div>

      {/* Tabs */}
      <div className="border-b">
        <div className="flex gap-1 overflow-x-auto -mb-px">
          {getTabsForCase(c).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
                tab === t
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted",
              )}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {tab === "overview" && <OverviewTab c={c} onAction={setTab} />}
      {tab === "deceased" && <DeceasedTab c={c} onSave={handleUpdateCase} />}
      {tab === "contacts" && <ContactsTab caseId={c.id} />}
      {tab === "services" && <ServicesTab caseId={c.id} />}
      {tab === "cremation" && <CremationTab caseData={c} onUpdate={fetchCase} />}
      {tab === "vault" && <VaultTab caseId={c.id} existingOrder={c.vault_order} />}
      {tab === "obituary" && <ObituaryTab caseId={c.id} existing={c.obituary} />}
      {tab === "documents" && <DocumentsTab caseId={c.id} />}
      {tab === "invoice" && <InvoiceTab caseId={c.id} existing={c.invoice} />}
      {tab === "activity" && <ActivityTab caseId={c.id} />}
    </div>
  );
}

// ── Shared Components ─────────────────────────────────────────

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function InfoRow({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn(bold && "font-semibold")}>{value || "—"}</span>
    </div>
  );
}

function daysBetween(a: Date, b: Date) {
  return Math.ceil((b.getTime() - a.getTime()) / (1000 * 60 * 60 * 24));
}
