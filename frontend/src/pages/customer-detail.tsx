import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangleIcon, CreditCard, MapPin, PlusIcon, Trash2Icon, Wrench } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { customerService } from "@/services/customer-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  BalanceAdjustment,
  CreditCheckResult,
  Customer,
  CustomerContact,
  CustomerNote,
} from "@/types/customer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { RecordPaymentDialog } from "@/components/record-payment-dialog";
import ContactListCRM from "@/components/crm/ContactList";

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge variant="default">Active</Badge>;
    case "hold":
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
        >
          Hold
        </Badge>
      );
    case "suspended":
      return <Badge variant="destructive">Suspended</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function noteTypeBadge(type: string) {
  const colors: Record<string, string> = {
    call: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    email:
      "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    visit:
      "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    credit:
      "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
    general: "",
  };
  return (
    <Badge variant="secondary" className={colors[type] || ""}>
      {type}
    </Badge>
  );
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function CustomerDetailPage() {
  const { customerId } = useParams<{ customerId: string }>();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("customers.edit");
  const canDelete = hasPermission("customers.delete");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Customer fields
  const [name, setName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [contactName, setContactName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [fax, setFax] = useState("");
  const [website, setWebsite] = useState("");
  const [taxExempt, setTaxExempt] = useState(false);
  const [taxId, setTaxId] = useState("");
  const [accountStatus, setAccountStatus] = useState("active");
  const [isActive, setIsActive] = useState(true);
  const [currentBalance, setCurrentBalance] = useState(0);
  const [creditBalance, setCreditBalance] = useState(0);

  // Shipping address
  const [addressLine1, setAddressLine1] = useState("");
  const [addressLine2, setAddressLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [country, setCountry] = useState("US");

  // Billing address
  const [billingLine1, setBillingLine1] = useState("");
  const [billingLine2, setBillingLine2] = useState("");
  const [billingCity, setBillingCity] = useState("");
  const [billingState, setBillingState] = useState("");
  const [billingZip, setBillingZip] = useState("");
  const [billingCountry, setBillingCountry] = useState("US");

  // Charge account
  const [creditLimit, setCreditLimit] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");

  // Sage
  const [sageCustomerId, setSageCustomerId] = useState("");

  // CRM link
  const [masterCompanyId, setMasterCompanyId] = useState<string | null>(null);

  // Classification
  const [customerType, setCustomerType] = useState<string | null>(null);
  const [classificationConfidence, setClassificationConfidence] = useState<number | null>(null);
  const [classificationMethod, setClassificationMethod] = useState<string | null>(null);
  const [classificationReasoning, setClassificationReasoning] = useState<string | null>(null);

  // Funeral home order preferences
  const [prefersplacer, setPrefersplacer] = useState(false);
  const [preferredConfirmationMethod, setPreferredConfirmationMethod] = useState<string>("");
  const [invoiceDeliveryPreference, setInvoiceDeliveryPreference] = useState<string>("statement_only");
  const [preferencesSaving, setPreferencesSaving] = useState(false);

  // Notes
  const [customerNotes, setCustomerNotes] = useState("");

  // Contacts
  const [contacts, setContacts] = useState<CustomerContact[]>([]);
  const [contactDialogOpen, setContactDialogOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<CustomerContact | null>(
    null,
  );
  const [contactForm, setContactForm] = useState({
    name: "",
    title: "",
    email: "",
    phone: "",
    is_primary: false,
  });
  const [contactError, setContactError] = useState("");

  // Notes feed
  const [notes, setNotes] = useState<CustomerNote[]>([]);
  const [notesTotal, setNotesTotal] = useState(0);
  const [notesPage, setNotesPage] = useState(1);
  const [newNoteType, setNewNoteType] = useState("general");
  const [newNoteContent, setNewNoteContent] = useState("");

  // Credit check widget
  const [creditCheckAmount, setCreditCheckAmount] = useState("");
  const [creditCheckResult, setCreditCheckResult] =
    useState<CreditCheckResult | null>(null);
  const [creditCheckLoading, setCreditCheckLoading] = useState(false);

  // Payment dialog (invoice-level payment recording)
  const [invoicePaymentDialogOpen, setInvoicePaymentDialogOpen] = useState(false);

  // Balance adjustments
  const [adjustments, setAdjustments] = useState<BalanceAdjustment[]>([]);
  const [adjustmentsTotal, setAdjustmentsTotal] = useState(0);
  const [adjustmentsPage, setAdjustmentsPage] = useState(1);
  const [adjustmentDialogOpen, setAdjustmentDialogOpen] = useState(false);
  const [adjustmentForm, setAdjustmentForm] = useState({
    adjustment_type: "charge" as "charge" | "payment",
    amount: "",
    description: "",
    reference_number: "",
  });
  const [adjustmentError, setAdjustmentError] = useState("");

  const loadData = useCallback(async () => {
    if (!customerId) return;
    try {
      setLoading(true);
      const customer: Customer =
        await customerService.getCustomer(customerId);

      setName(customer.name);
      setAccountNumber(customer.account_number || "");
      setContactName(customer.contact_name || "");
      setEmail(customer.email || "");
      setPhone(customer.phone || "");
      setFax(customer.fax || "");
      setWebsite(customer.website || "");
      setTaxExempt(customer.tax_exempt);
      setTaxId(customer.tax_id || "");
      setAccountStatus(customer.account_status);
      setIsActive(customer.is_active);
      setCurrentBalance(customer.current_balance);
      setCreditBalance(Number(customer.credit_balance ?? 0));

      setAddressLine1(customer.address_line1 || "");
      setAddressLine2(customer.address_line2 || "");
      setCity(customer.city || "");
      setState(customer.state || "");
      setZipCode(customer.zip_code || "");
      setCountry(customer.country || "US");

      setBillingLine1(customer.billing_address_line1 || "");
      setBillingLine2(customer.billing_address_line2 || "");
      setBillingCity(customer.billing_city || "");
      setBillingState(customer.billing_state || "");
      setBillingZip(customer.billing_zip || "");
      setBillingCountry(customer.billing_country || "US");

      setCreditLimit(
        customer.credit_limit !== null ? String(customer.credit_limit) : "",
      );
      setPaymentTerms(customer.payment_terms || "");
      setSageCustomerId(customer.sage_customer_id || "");
      setMasterCompanyId(customer.master_company_id || null);
      setCustomerNotes(customer.notes || "");
      setCustomerType(customer.customer_type ?? null);
      setClassificationConfidence(customer.classification_confidence ?? null);
      setClassificationMethod(customer.classification_method ?? null);
      setClassificationReasoning(customer.classification_reasoning ?? null);
      setPrefersplacer(customer.prefers_placer ?? false);
      setPreferredConfirmationMethod(customer.preferred_confirmation_method ?? "");
      setInvoiceDeliveryPreference(customer.invoice_delivery_preference ?? "statement_only");

      setContacts(customer.contacts || []);
      setNotes(customer.recent_notes || []);
    } catch {
      setError("Failed to load customer");
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  const loadNotes = useCallback(async () => {
    if (!customerId) return;
    try {
      const data = await customerService.getNotes(customerId, notesPage, 20);
      setNotes(data.items);
      setNotesTotal(data.total);
    } catch {
      // Non-critical
    }
  }, [customerId, notesPage]);

  const loadAdjustments = useCallback(async () => {
    if (!customerId) return;
    try {
      const data = await customerService.getAdjustments(
        customerId,
        adjustmentsPage,
        20,
      );
      setAdjustments(data.items);
      setAdjustmentsTotal(data.total);
    } catch {
      // Non-critical
    }
  }, [customerId, adjustmentsPage]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!loading) loadNotes();
  }, [loadNotes, loading]);

  useEffect(() => {
    if (!loading) loadAdjustments();
  }, [loadAdjustments, loading]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) return;
    setError("");
    setSaving(true);
    try {
      await customerService.updateCustomer(customerId, {
        name,
        account_number: accountNumber.trim() || undefined,
        contact_name: contactName.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        fax: fax.trim() || undefined,
        website: website.trim() || undefined,
        tax_exempt: taxExempt,
        tax_id: taxId.trim() || undefined,
        account_status: accountStatus,
        address_line1: addressLine1.trim() || undefined,
        address_line2: addressLine2.trim() || undefined,
        city: city.trim() || undefined,
        state: state.trim() || undefined,
        zip_code: zipCode.trim() || undefined,
        country: country.trim() || undefined,
        billing_address_line1: billingLine1.trim() || undefined,
        billing_address_line2: billingLine2.trim() || undefined,
        billing_city: billingCity.trim() || undefined,
        billing_state: billingState.trim() || undefined,
        billing_zip: billingZip.trim() || undefined,
        billing_country: billingCountry.trim() || undefined,
        credit_limit: creditLimit.trim()
          ? parseFloat(creditLimit)
          : undefined,
        payment_terms: paymentTerms.trim() || undefined,
        sage_customer_id: sageCustomerId.trim() || undefined,
        notes: customerNotes.trim() || undefined,
      });
      toast.success("Customer saved");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to save customer"));
    } finally {
      setSaving(false);
    }
  }

  function copyShippingToBilling() {
    setBillingLine1(addressLine1);
    setBillingLine2(addressLine2);
    setBillingCity(city);
    setBillingState(state);
    setBillingZip(zipCode);
    setBillingCountry(country);
  }

  // ------- Credit check -------

  async function handleCreditCheck() {
    if (!customerId || !creditCheckAmount.trim()) return;
    setCreditCheckLoading(true);
    setCreditCheckResult(null);
    try {
      const result = await customerService.checkCredit(
        customerId,
        parseFloat(creditCheckAmount),
      );
      setCreditCheckResult(result);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Credit check failed"));
    } finally {
      setCreditCheckLoading(false);
    }
  }

  // ------- Balance adjustment handlers -------

  function openAdjustmentDialog(type: "charge" | "payment") {
    setAdjustmentForm({
      adjustment_type: type,
      amount: "",
      description: "",
      reference_number: "",
    });
    setAdjustmentError("");
    setAdjustmentDialogOpen(true);
  }

  async function handleCreateAdjustment() {
    if (!customerId || !adjustmentForm.amount.trim()) return;
    setAdjustmentError("");
    try {
      await customerService.createAdjustment(customerId, {
        adjustment_type: adjustmentForm.adjustment_type,
        amount: parseFloat(adjustmentForm.amount),
        description: adjustmentForm.description.trim() || undefined,
        reference_number: adjustmentForm.reference_number.trim() || undefined,
      });
      setAdjustmentDialogOpen(false);
      toast.success(
        adjustmentForm.adjustment_type === "charge"
          ? "Charge recorded"
          : "Payment recorded",
      );
      // Reload everything to reflect balance + status changes
      loadData();
      loadAdjustments();
      loadNotes();
    } catch (err: unknown) {
      setAdjustmentError(
        getApiErrorMessage(err, "Failed to record adjustment"),
      );
    }
  }

  // ------- Contact handlers -------

  function openAddContact() {
    setEditingContact(null);
    setContactForm({
      name: "",
      title: "",
      email: "",
      phone: "",
      is_primary: false,
    });
    setContactError("");
    setContactDialogOpen(true);
  }

  function openEditContact(contact: CustomerContact) {
    setEditingContact(contact);
    setContactForm({
      name: contact.name,
      title: contact.title || "",
      email: contact.email || "",
      phone: contact.phone || "",
      is_primary: contact.is_primary,
    });
    setContactError("");
    setContactDialogOpen(true);
  }

  async function handleSaveContact() {
    if (!customerId) return;
    setContactError("");
    try {
      if (editingContact) {
        const updated = await customerService.updateContact(
          customerId,
          editingContact.id,
          {
            name: contactForm.name,
            title: contactForm.title.trim() || undefined,
            email: contactForm.email.trim() || undefined,
            phone: contactForm.phone.trim() || undefined,
            is_primary: contactForm.is_primary,
          },
        );
        setContacts(
          contacts.map((c) => (c.id === updated.id ? updated : c)),
        );
        toast.success("Contact updated");
      } else {
        const created = await customerService.createContact(customerId, {
          name: contactForm.name,
          title: contactForm.title.trim() || undefined,
          email: contactForm.email.trim() || undefined,
          phone: contactForm.phone.trim() || undefined,
          is_primary: contactForm.is_primary,
        });
        setContacts([...contacts, created]);
        toast.success("Contact added");
      }
      setContactDialogOpen(false);
    } catch (err: unknown) {
      setContactError(getApiErrorMessage(err, "Failed to save contact"));
    }
  }

  async function handleDeleteContact(contactId: string) {
    if (!customerId) return;
    try {
      await customerService.deleteContact(customerId, contactId);
      setContacts(contacts.filter((c) => c.id !== contactId));
      toast.success("Contact removed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to remove contact"));
    }
  }

  // ------- Note handlers -------

  async function handleAddNote() {
    if (!customerId || !newNoteContent.trim()) return;
    try {
      const note = await customerService.createNote(customerId, {
        note_type: newNoteType,
        content: newNoteContent.trim(),
      });
      setNotes([note, ...notes]);
      setNotesTotal(notesTotal + 1);
      setNewNoteContent("");
      setNewNoteType("general");
      toast.success("Note added");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to add note"));
    }
  }

  // ------- Funeral home preferences -------

  async function handlePlacerToggle(newValue: boolean) {
    if (!customerId) return;
    setPrefersplacer(newValue);
    try {
      await customerService.updateCustomer(customerId, { prefers_placer: newValue });
      toast.success(newValue ? "Vault placer preference enabled" : "Vault placer preference disabled");
    } catch (err: unknown) {
      setPrefersplacer(!newValue); // revert
      toast.error(getApiErrorMessage(err, "Failed to save preference"));
    }
  }

  async function handleSavePreferences() {
    if (!customerId) return;
    setPreferencesSaving(true);
    try {
      await customerService.updateCustomer(customerId, {
        preferred_confirmation_method: preferredConfirmationMethod || null,
        invoice_delivery_preference: invoiceDeliveryPreference,
      });
      toast.success("Preferences saved");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to save preferences"));
    } finally {
      setPreferencesSaving(false);
    }
  }

  // ------- Deactivate -------

  async function handleDeactivate() {
    if (!customerId) return;
    try {
      await customerService.deleteCustomer(customerId);
      setIsActive(false);
      toast.success("Customer deactivated");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to deactivate customer"));
    }
  }

  // Calculated available credit
  const availableCredit = creditLimit.trim()
    ? parseFloat(creditLimit) - currentBalance
    : null;

  // Over-limit check
  const isOverLimit =
    creditLimit.trim() && currentBalance > parseFloat(creditLimit);
  const overLimitAmount = isOverLimit
    ? currentBalance - parseFloat(creditLimit)
    : 0;

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold">Customer Details</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  const notesTotalPages = Math.ceil(notesTotal / 20);
  const adjustmentsTotalPages = Math.ceil(adjustmentsTotal / 20);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-bold">{name || "Customer Details"}</h1>
          {statusBadge(accountStatus)}
          {!isActive && <Badge variant="destructive">Inactive</Badge>}
          {/* Customer type badge */}
          {customerType && customerType !== "unknown" && (
            <Badge variant="outline" className="capitalize text-xs">
              {customerType.replace("_", " ")}
            </Badge>
          )}
          {/* Classification confidence */}
          {classificationConfidence !== null && (
            <span
              className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${
                classificationConfidence >= 0.85
                  ? "bg-green-50 text-green-700 border-green-200"
                  : classificationConfidence >= 0.70
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : "bg-red-50 text-red-600 border-red-200"
              }`}
              title={`Classification method: ${classificationMethod ?? "unknown"}${classificationReasoning ? ` — ${classificationReasoning}` : ""}`}
            >
              {Math.round(classificationConfidence * 100)}% confidence
              {(customerType === "unknown" || classificationConfidence < 0.75) && (
                <a
                  href="/settings/data/customer-types"
                  className="ml-1 underline"
                  onClick={(e) => { e.preventDefault(); window.location.href = "/settings/data/customer-types"; }}
                >
                  [Change type]
                </a>
              )}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {canDelete && isActive && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDeactivate}
            >
              Deactivate
            </Button>
          )}
          <Link
            to="/customers"
            className="text-sm text-muted-foreground hover:underline"
          >
            ← Back to Customers
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Over-Limit Warning Banner */}
      {isOverLimit && (
        <div className="flex items-center gap-3 rounded-md border border-red-300 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950">
          <AlertTriangleIcon className="size-5 shrink-0 text-red-600 dark:text-red-400" />
          <div>
            <p className="font-medium text-red-800 dark:text-red-200">
              Over Credit Limit
            </p>
            <p className="text-sm text-red-700 dark:text-red-300">
              This customer is over their credit limit by{" "}
              {formatCurrency(overLimitAmount)}. Balance:{" "}
              {formatCurrency(currentBalance)}, Limit:{" "}
              {formatCurrency(parseFloat(creditLimit))}.
            </p>
          </div>
        </div>
      )}

      {/* Credit Balance Banner */}
      {creditBalance > 0 && (
        <div className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800 flex items-center gap-2">
          <span className="text-green-600 font-bold">$</span>
          <span>
            <strong>{formatCurrency(creditBalance)}</strong> credit on account — will apply to next invoice
          </span>
        </div>
      )}

      {/* Account Summary */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">Status</p>
          <div className="mt-1">{statusBadge(accountStatus)}</div>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">Balance</p>
          <p
            className={`mt-1 text-lg font-bold ${isOverLimit ? "text-destructive" : ""}`}
          >
            {formatCurrency(currentBalance)}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">Credit Limit</p>
          <p className="mt-1 text-lg font-bold">
            {creditLimit.trim()
              ? formatCurrency(parseFloat(creditLimit))
              : "None"}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">Available Credit</p>
          <p
            className={`mt-1 text-lg font-bold ${
              availableCredit !== null && availableCredit < 0
                ? "text-destructive"
                : ""
            }`}
          >
            {availableCredit !== null
              ? formatCurrency(availableCredit)
              : "N/A"}
          </p>
        </Card>
      </div>

      {/* Credit Check Widget */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Check Credit</Label>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={creditCheckAmount}
              onChange={(e) => {
                setCreditCheckAmount(e.target.value);
                setCreditCheckResult(null);
              }}
              placeholder="Amount"
              className="w-32"
            />
          </div>
          <Button
            type="button"
            variant="outline"
            size="default"
            onClick={handleCreditCheck}
            disabled={
              !creditCheckAmount.trim() ||
              creditCheckLoading ||
              parseFloat(creditCheckAmount) <= 0
            }
          >
            {creditCheckLoading ? "Checking..." : "Check"}
          </Button>
          {creditCheckResult && (
            <div
              className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
                creditCheckResult.allowed
                  ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
                  : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
              }`}
            >
              <span className="font-medium">
                {creditCheckResult.allowed ? "✓ Allowed" : "✗ Denied"}
              </span>
              {creditCheckResult.available_credit !== null && (
                <span>
                  — Available: {formatCurrency(creditCheckResult.available_credit)}
                </span>
              )}
              {creditCheckResult.credit_limit === null && (
                <span>— No credit limit set</span>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Cemetery Delivery Settings link */}
      {customerType === "cemetery" && (
        <Card className="p-4">
          <div className="flex items-start gap-3">
            <MapPin className="size-5 text-muted-foreground mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-sm">Delivery Settings</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Configure which equipment this cemetery provides to ensure orders are pre-filled correctly.
              </p>
            </div>
            <Link
              to="/settings/cemeteries"
              className="text-sm text-primary hover:underline shrink-0"
            >
              Open Cemetery Settings →
            </Link>
          </div>
        </Card>
      )}

      {/* Order Preferences — funeral home customers only */}
      {customerType === "funeral_home" && (
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-1">
            <Wrench className="size-4 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Order Preferences</h2>
          </div>
          <p className="text-xs text-muted-foreground mb-4">
            Preferences auto-applied when creating orders for this funeral home.
          </p>
          <Separator className="mb-5" />

          {/* Vault Placer toggle */}
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <p className="text-sm font-medium">Vault placer</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Automatically add a vault placer to every order that includes a lowering device.
                  When enabled, the placer is added at $0.00 and marked as a funeral home preference.
                </p>
              </div>
              <Switch
                checked={prefersplacer}
                onCheckedChange={handlePlacerToggle}
                disabled={!canEdit}
              />
            </div>

            <Separator />

            {/* Confirmation method */}
            <div className="space-y-2">
              <p className="text-sm font-medium">Preferred confirmation method</p>
              <p className="text-xs text-muted-foreground">
                How does this funeral home prefer to confirm orders?
              </p>
              <div className="space-y-2 mt-2">
                {[
                  { value: "", label: "No preference" },
                  { value: "phone", label: "Phone" },
                  { value: "email", label: "Email" },
                  { value: "text", label: "Text" },
                  { value: "any", label: "Any method" },
                ].map(({ value, label }) => (
                  <label key={value} className="flex items-center gap-2.5 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="confirmation_method"
                      value={value}
                      checked={preferredConfirmationMethod === value}
                      onChange={() => setPreferredConfirmationMethod(value)}
                      disabled={!canEdit}
                      className="size-4"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>

            <Separator />

            {/* Invoice delivery preference */}
            <div className="space-y-2">
              <p className="text-sm font-medium">Invoice delivery</p>
              <p className="text-xs text-muted-foreground">
                When should invoices be sent to this funeral home?
              </p>
              <div className="space-y-2 mt-2">
                {[
                  { value: "statement_only", label: "Statement only", description: "Invoices appear on the monthly statement — no individual emails" },
                  { value: "invoice_immediately", label: "Email invoice immediately", description: "Send a PDF invoice by email when each order is approved" },
                  { value: "both", label: "Both", description: "Email the invoice and include it on the monthly statement" },
                ].map(({ value, label, description }) => (
                  <label key={value} className="flex items-start gap-2.5 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="invoice_delivery_preference"
                      value={value}
                      checked={invoiceDeliveryPreference === value}
                      onChange={() => setInvoiceDeliveryPreference(value)}
                      disabled={!canEdit}
                      className="size-4 mt-0.5"
                    />
                    <span>
                      <span className="font-medium">{label}</span>
                      <span className="block text-xs text-muted-foreground">{description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {canEdit && (
              <div className="pt-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleSavePreferences}
                  disabled={preferencesSaving}
                >
                  {preferencesSaving ? "Saving..." : "Save preferences"}
                </Button>
              </div>
            )}
          </div>
        </Card>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Customer Info */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Customer Information</h2>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Customer Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={!canEdit}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Account #</Label>
                <Input
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Contact Name</Label>
                <Input
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>Fax</Label>
                <Input
                  value={fax}
                  onChange={(e) => setFax(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>Website</Label>
                <Input
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={taxExempt}
                  onChange={(e) => setTaxExempt(e.target.checked)}
                  disabled={!canEdit}
                  className="size-4 rounded border-input"
                />
                Tax Exempt
              </label>
              <div className="space-y-2">
                <Label>Tax ID</Label>
                <Input
                  value={taxId}
                  onChange={(e) => setTaxId(e.target.value)}
                  disabled={!canEdit}
                  placeholder="e.g. EIN"
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Shipping Address */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Shipping Address</h2>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Address Line 1</Label>
              <Input
                value={addressLine1}
                onChange={(e) => setAddressLine1(e.target.value)}
                disabled={!canEdit}
              />
            </div>
            <div className="space-y-2">
              <Label>Address Line 2</Label>
              <Input
                value={addressLine2}
                onChange={(e) => setAddressLine2(e.target.value)}
                disabled={!canEdit}
              />
            </div>
            <div className="grid grid-cols-4 gap-4">
              <div className="space-y-2 col-span-2">
                <Label>City</Label>
                <Input
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>State</Label>
                <Input
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>ZIP</Label>
                <Input
                  value={zipCode}
                  onChange={(e) => setZipCode(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
            <div className="space-y-2 max-w-[200px]">
              <Label>Country</Label>
              <Input
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                disabled={!canEdit}
              />
            </div>
          </div>
        </Card>

        {/* Billing Address */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Billing Address</h2>
            {canEdit && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={copyShippingToBilling}
              >
                Copy from Shipping
              </Button>
            )}
          </div>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Address Line 1</Label>
              <Input
                value={billingLine1}
                onChange={(e) => setBillingLine1(e.target.value)}
                disabled={!canEdit}
              />
            </div>
            <div className="space-y-2">
              <Label>Address Line 2</Label>
              <Input
                value={billingLine2}
                onChange={(e) => setBillingLine2(e.target.value)}
                disabled={!canEdit}
              />
            </div>
            <div className="grid grid-cols-4 gap-4">
              <div className="space-y-2 col-span-2">
                <Label>City</Label>
                <Input
                  value={billingCity}
                  onChange={(e) => setBillingCity(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>State</Label>
                <Input
                  value={billingState}
                  onChange={(e) => setBillingState(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>ZIP</Label>
                <Input
                  value={billingZip}
                  onChange={(e) => setBillingZip(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
            <div className="space-y-2 max-w-[200px]">
              <Label>Country</Label>
              <Input
                value={billingCountry}
                onChange={(e) => setBillingCountry(e.target.value)}
                disabled={!canEdit}
              />
            </div>
          </div>
        </Card>

        {/* Charge Account */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Charge Account</h2>
          <Separator className="my-4" />
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Credit Limit</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={creditLimit}
                onChange={(e) => setCreditLimit(e.target.value)}
                disabled={!canEdit}
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <Label>Payment Terms</Label>
              <Input
                value={paymentTerms}
                onChange={(e) => setPaymentTerms(e.target.value)}
                disabled={!canEdit}
                placeholder="e.g. Net 30"
              />
            </div>
            <div className="space-y-2">
              <Label>Account Status</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                value={accountStatus}
                onChange={(e) => setAccountStatus(e.target.value)}
                disabled={!canEdit}
              >
                <option value="active">Active</option>
                <option value="hold">On Hold</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Notes (general field) */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Internal Notes</h2>
          <Separator className="my-4" />
          <textarea
            value={customerNotes}
            onChange={(e) => setCustomerNotes(e.target.value)}
            disabled={!canEdit}
            rows={3}
            className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
            placeholder="Internal notes about this customer..."
          />
        </Card>

        {/* Sage Integration */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Sage Integration</h2>
          <Separator className="my-4" />
          <div className="space-y-2 max-w-sm">
            <Label>Sage Customer ID</Label>
            <Input
              value={sageCustomerId}
              onChange={(e) => setSageCustomerId(e.target.value)}
              disabled={!canEdit}
              placeholder="e.g. CUST-12345"
            />
            <p className="text-xs text-muted-foreground">
              Links this customer to their record in Sage accounting.
            </p>
          </div>
        </Card>

        {canEdit && (
          <div className="flex justify-end">
            <Button type="submit" disabled={saving || !name.trim()}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        )}
      </form>

      {/* Balance Adjustments */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Balance Adjustments</h2>
          {canEdit && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => openAdjustmentDialog("charge")}
              >
                Record Charge
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => openAdjustmentDialog("payment")}
              >
                Balance Adjustment
              </Button>
              <Button
                size="sm"
                onClick={() => setInvoicePaymentDialogOpen(true)}
              >
                <CreditCard className="w-4 h-4 mr-1.5" />
                Record Payment
              </Button>
            </div>
          )}
        </div>
        <Separator className="my-4" />

        {/* Adjustment dialog */}
        <Dialog
          open={adjustmentDialogOpen}
          onOpenChange={setAdjustmentDialogOpen}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                Record{" "}
                {adjustmentForm.adjustment_type === "charge"
                  ? "Charge"
                  : "Payment"}
              </DialogTitle>
              <DialogDescription>
                {adjustmentForm.adjustment_type === "charge"
                  ? "Add a charge to this customer's balance."
                  : "Record a payment received from this customer."}
              </DialogDescription>
            </DialogHeader>
            {adjustmentError && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {adjustmentError}
              </div>
            )}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Amount</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={adjustmentForm.amount}
                  onChange={(e) =>
                    setAdjustmentForm({
                      ...adjustmentForm,
                      amount: e.target.value,
                    })
                  }
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Input
                  value={adjustmentForm.description}
                  onChange={(e) =>
                    setAdjustmentForm({
                      ...adjustmentForm,
                      description: e.target.value,
                    })
                  }
                  placeholder={
                    adjustmentForm.adjustment_type === "charge"
                      ? "e.g. Invoice #1234"
                      : "e.g. Check #5678"
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Reference # (optional)</Label>
                <Input
                  value={adjustmentForm.reference_number}
                  onChange={(e) =>
                    setAdjustmentForm({
                      ...adjustmentForm,
                      reference_number: e.target.value,
                    })
                  }
                  placeholder="e.g. INV-001, CHK-5678"
                />
              </div>
              {adjustmentForm.adjustment_type === "charge" &&
                creditLimit.trim() && (
                  <div className="rounded-md bg-muted p-3 text-sm">
                    <p className="text-muted-foreground">
                      Current balance: {formatCurrency(currentBalance)} /{" "}
                      {formatCurrency(parseFloat(creditLimit))} limit
                    </p>
                    {adjustmentForm.amount.trim() &&
                      parseFloat(adjustmentForm.amount) > 0 && (
                        <p
                          className={
                            currentBalance +
                              parseFloat(adjustmentForm.amount) >
                            parseFloat(creditLimit)
                              ? "text-destructive font-medium mt-1"
                              : "text-green-700 dark:text-green-400 mt-1"
                          }
                        >
                          After charge:{" "}
                          {formatCurrency(
                            currentBalance +
                              parseFloat(adjustmentForm.amount),
                          )}{" "}
                          {currentBalance +
                            parseFloat(adjustmentForm.amount) >
                          parseFloat(creditLimit)
                            ? "— exceeds limit!"
                            : "— within limit"}
                        </p>
                      )}
                  </div>
                )}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setAdjustmentDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateAdjustment}
                disabled={
                  !adjustmentForm.amount.trim() ||
                  parseFloat(adjustmentForm.amount) <= 0
                }
              >
                {adjustmentForm.adjustment_type === "charge"
                  ? "Record Charge"
                  : "Record Payment"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Adjustments table */}
        {adjustments.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No balance adjustments recorded yet.
          </p>
        ) : (
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium">Date</th>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                  <th className="px-3 py-2 text-left font-medium">
                    Description
                  </th>
                  <th className="px-3 py-2 text-left font-medium">Ref #</th>
                  <th className="px-3 py-2 text-left font-medium">By</th>
                </tr>
              </thead>
              <tbody>
                {adjustments.map((adj) => (
                  <tr key={adj.id} className="border-b last:border-0">
                    <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
                      {formatDate(adj.created_at)}
                    </td>
                    <td className="px-3 py-2">
                      <Badge
                        variant="secondary"
                        className={
                          adj.adjustment_type === "charge"
                            ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                            : "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                        }
                      >
                        {adj.adjustment_type}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {adj.adjustment_type === "charge" ? "+" : "−"}
                      {formatCurrency(adj.amount)}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {adj.description || "—"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {adj.reference_number || "—"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {adj.created_by_name || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Adjustments pagination */}
        {adjustmentsTotalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={adjustmentsPage <= 1}
              onClick={() => setAdjustmentsPage(adjustmentsPage - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {adjustmentsPage} of {adjustmentsTotalPages}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={adjustmentsPage >= adjustmentsTotalPages}
              onClick={() => setAdjustmentsPage(adjustmentsPage + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </Card>

      {/* Contacts Section */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Contacts</h2>
          {canEdit && (
            <>
              <Button variant="outline" size="sm" onClick={openAddContact}>
                <PlusIcon className="mr-1 size-4" />
                Add Contact
              </Button>
              <Dialog
                open={contactDialogOpen}
                onOpenChange={setContactDialogOpen}
              >
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>
                      {editingContact ? "Edit Contact" : "Add Contact"}
                    </DialogTitle>
                    <DialogDescription>
                      {editingContact
                        ? "Update the contact details."
                        : "Add a new contact for this customer."}
                    </DialogDescription>
                  </DialogHeader>
                  {contactError && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {contactError}
                    </div>
                  )}
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Name</Label>
                      <Input
                        value={contactForm.name}
                        onChange={(e) =>
                          setContactForm({
                            ...contactForm,
                            name: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Title</Label>
                      <Input
                        value={contactForm.title}
                        onChange={(e) =>
                          setContactForm({
                            ...contactForm,
                            title: e.target.value,
                          })
                        }
                        placeholder="e.g. Purchasing Manager"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Email</Label>
                        <Input
                          type="email"
                          value={contactForm.email}
                          onChange={(e) =>
                            setContactForm({
                              ...contactForm,
                              email: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Phone</Label>
                        <Input
                          value={contactForm.phone}
                          onChange={(e) =>
                            setContactForm({
                              ...contactForm,
                              phone: e.target.value,
                            })
                          }
                        />
                      </div>
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={contactForm.is_primary}
                        onChange={(e) =>
                          setContactForm({
                            ...contactForm,
                            is_primary: e.target.checked,
                          })
                        }
                        className="size-4 rounded border-input"
                      />
                      Primary contact
                    </label>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setContactDialogOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleSaveContact}
                      disabled={!contactForm.name.trim()}
                    >
                      {editingContact ? "Update" : "Add"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </>
          )}
        </div>
        <Separator className="my-4" />
        {contacts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No contacts added yet.
          </p>
        ) : (
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium">Name</th>
                  <th className="px-3 py-2 text-left font-medium">Title</th>
                  <th className="px-3 py-2 text-left font-medium">Email</th>
                  <th className="px-3 py-2 text-left font-medium">Phone</th>
                  <th className="px-3 py-2 text-right font-medium w-20"></th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => (
                  <tr key={contact.id} className="border-b last:border-0">
                    <td className="px-3 py-2 font-medium">
                      {contact.name}
                      {contact.is_primary && (
                        <Badge variant="default" className="ml-2 text-xs">
                          Primary
                        </Badge>
                      )}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {contact.title || "—"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {contact.email || "—"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {contact.phone || "—"}
                    </td>
                    <td className="px-3 py-2 text-right space-x-1">
                      {canEdit && (
                        <>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditContact(contact)}
                          >
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            onClick={() => handleDeleteContact(contact.id)}
                          >
                            <Trash2Icon className="size-3.5 text-destructive" />
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* CRM Contacts (from company_entities) */}
      {masterCompanyId && (
        <Card className="p-6">
          <ContactListCRM
            masterCompanyId={masterCompanyId}
            companyName={name}
            allowEdit={canEdit}
            compact
          />
        </Card>
      )}

      {/* Activity Notes */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Activity Notes</h2>
        <Separator className="my-4" />

        {/* Add note */}
        {canEdit && (
          <div className="mb-4 space-y-3 rounded-md border p-4">
            <div className="flex items-center gap-2">
              <Label className="text-sm">Type</Label>
              <select
                className="flex h-8 rounded-md border border-input bg-transparent px-2 py-1 text-sm"
                value={newNoteType}
                onChange={(e) => setNewNoteType(e.target.value)}
              >
                <option value="general">General</option>
                <option value="call">Call</option>
                <option value="email">Email</option>
                <option value="visit">Visit</option>
                <option value="credit">Credit</option>
              </select>
            </div>
            <textarea
              value={newNoteContent}
              onChange={(e) => setNewNoteContent(e.target.value)}
              rows={2}
              className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              placeholder="Add a note..."
            />
            <div className="flex justify-end">
              <Button
                type="button"
                size="sm"
                onClick={handleAddNote}
                disabled={!newNoteContent.trim()}
              >
                Add Note
              </Button>
            </div>
          </div>
        )}

        {/* Notes feed */}
        {notes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No notes yet.</p>
        ) : (
          <div className="space-y-3">
            {notes.map((note) => (
              <div key={note.id} className="rounded-md border p-3">
                <div className="flex items-center gap-2 mb-1">
                  {noteTypeBadge(note.note_type)}
                  <span className="text-xs text-muted-foreground">
                    {formatDate(note.created_at)}
                  </span>
                  {note.created_by_name && (
                    <span className="text-xs text-muted-foreground">
                      by {note.created_by_name}
                    </span>
                  )}
                </div>
                <p className="text-sm whitespace-pre-wrap">{note.content}</p>
              </div>
            ))}
          </div>
        )}

        {/* Notes pagination */}
        {notesTotalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={notesPage <= 1}
              onClick={() => setNotesPage(notesPage - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {notesPage} of {notesTotalPages}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={notesPage >= notesTotalPages}
              onClick={() => setNotesPage(notesPage + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </Card>

      {/* Invoice payment dialog */}
      {customerId && (
        <RecordPaymentDialog
          open={invoicePaymentDialogOpen}
          onClose={() => setInvoicePaymentDialogOpen(false)}
          onSuccess={() => {
            loadData();
            setInvoicePaymentDialogOpen(false);
          }}
          customerId={customerId}
          customerName={name}
        />
      )}
    </div>
  );
}
