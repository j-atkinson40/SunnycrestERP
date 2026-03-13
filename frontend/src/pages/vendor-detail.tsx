import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { vendorService } from "@/services/vendor-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { Vendor, VendorContact, VendorNote } from "@/types/vendor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge variant="default">Active</Badge>;
    case "on_hold":
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
        >
          On Hold
        </Badge>
      );
    case "inactive":
      return <Badge variant="destructive">Inactive</Badge>;
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
    general: "",
  };
  return (
    <Badge variant="secondary" className={colors[type] || ""}>
      {type}
    </Badge>
  );
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

export default function VendorDetailPage() {
  const { vendorId } = useParams<{ vendorId: string }>();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("vendors.edit");
  const canDelete = hasPermission("vendors.delete");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Vendor fields
  const [name, setName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [contactName, setContactName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [fax, setFax] = useState("");
  const [website, setWebsite] = useState("");
  const [taxId, setTaxId] = useState("");
  const [vendorStatus, setVendorStatus] = useState("active");
  const [isActive, setIsActive] = useState(true);

  // Address
  const [addressLine1, setAddressLine1] = useState("");
  const [addressLine2, setAddressLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [country, setCountry] = useState("US");

  // Purchasing info
  const [paymentTerms, setPaymentTerms] = useState("");
  const [leadTimeDays, setLeadTimeDays] = useState("");
  const [minimumOrder, setMinimumOrder] = useState("");

  // Sage
  const [sageVendorId, setSageVendorId] = useState("");

  // General notes
  const [vendorNotes, setVendorNotes] = useState("");

  // Contacts
  const [contacts, setContacts] = useState<VendorContact[]>([]);
  const [contactDialogOpen, setContactDialogOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<VendorContact | null>(
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
  const [notes, setNotes] = useState<VendorNote[]>([]);
  const [notesTotal, setNotesTotal] = useState(0);
  const [notesPage, setNotesPage] = useState(1);
  const [newNoteType, setNewNoteType] = useState("general");
  const [newNoteContent, setNewNoteContent] = useState("");

  // Tabs
  const [activeTab, setActiveTab] = useState<
    "details" | "contacts" | "notes"
  >("details");

  const loadData = useCallback(async () => {
    if (!vendorId) return;
    try {
      setLoading(true);
      const vendor: Vendor = await vendorService.getVendor(vendorId);

      setName(vendor.name);
      setAccountNumber(vendor.account_number || "");
      setContactName(vendor.contact_name || "");
      setEmail(vendor.email || "");
      setPhone(vendor.phone || "");
      setFax(vendor.fax || "");
      setWebsite(vendor.website || "");
      setTaxId(vendor.tax_id || "");
      setVendorStatus(vendor.vendor_status);
      setIsActive(vendor.is_active);

      setAddressLine1(vendor.address_line1 || "");
      setAddressLine2(vendor.address_line2 || "");
      setCity(vendor.city || "");
      setState(vendor.state || "");
      setZipCode(vendor.zip_code || "");
      setCountry(vendor.country || "US");

      setPaymentTerms(vendor.payment_terms || "");
      setLeadTimeDays(
        vendor.lead_time_days !== null ? String(vendor.lead_time_days) : "",
      );
      setMinimumOrder(
        vendor.minimum_order !== null ? String(vendor.minimum_order) : "",
      );

      setSageVendorId(vendor.sage_vendor_id || "");
      setVendorNotes(vendor.notes || "");

      setContacts(vendor.contacts);
      setNotes(vendor.recent_notes);
    } finally {
      setLoading(false);
    }
  }, [vendorId]);

  const loadNotes = useCallback(async () => {
    if (!vendorId) return;
    try {
      const data = await vendorService.getNotes(vendorId, notesPage, 20);
      setNotes(data.items);
      setNotesTotal(data.total);
    } catch {
      // non-critical
    }
  }, [vendorId, notesPage]);

  const loadContacts = useCallback(async () => {
    if (!vendorId) return;
    try {
      const data = await vendorService.getContacts(vendorId);
      setContacts(data);
    } catch {
      // non-critical
    }
  }, [vendorId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (activeTab === "notes") loadNotes();
  }, [activeTab, loadNotes]);

  async function handleSave() {
    if (!vendorId) return;
    setSaving(true);
    setError("");
    try {
      await vendorService.updateVendor(vendorId, {
        name,
        account_number: accountNumber.trim() || undefined,
        contact_name: contactName.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        fax: fax.trim() || undefined,
        website: website.trim() || undefined,
        tax_id: taxId.trim() || undefined,
        vendor_status: vendorStatus,
        address_line1: addressLine1.trim() || undefined,
        address_line2: addressLine2.trim() || undefined,
        city: city.trim() || undefined,
        state: state.trim() || undefined,
        zip_code: zipCode.trim() || undefined,
        country: country.trim() || undefined,
        payment_terms: paymentTerms.trim() || undefined,
        lead_time_days: leadTimeDays.trim()
          ? parseInt(leadTimeDays)
          : undefined,
        minimum_order: minimumOrder.trim()
          ? parseFloat(minimumOrder)
          : undefined,
        sage_vendor_id: sageVendorId.trim() || undefined,
        notes: vendorNotes.trim() || undefined,
      });
      toast.success("Vendor updated");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to update vendor"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate() {
    if (!vendorId) return;
    try {
      await vendorService.deleteVendor(vendorId);
      setIsActive(false);
      toast.success("Vendor deactivated");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to deactivate vendor"));
    }
  }

  // ---- Contacts ----

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

  function openEditContact(c: VendorContact) {
    setEditingContact(c);
    setContactForm({
      name: c.name,
      title: c.title || "",
      email: c.email || "",
      phone: c.phone || "",
      is_primary: c.is_primary,
    });
    setContactError("");
    setContactDialogOpen(true);
  }

  async function handleSaveContact() {
    if (!vendorId) return;
    setContactError("");
    try {
      if (editingContact) {
        await vendorService.updateContact(vendorId, editingContact.id, {
          name: contactForm.name,
          title: contactForm.title.trim() || undefined,
          email: contactForm.email.trim() || undefined,
          phone: contactForm.phone.trim() || undefined,
          is_primary: contactForm.is_primary,
        });
        toast.success("Contact updated");
      } else {
        await vendorService.createContact(vendorId, {
          name: contactForm.name,
          title: contactForm.title.trim() || undefined,
          email: contactForm.email.trim() || undefined,
          phone: contactForm.phone.trim() || undefined,
          is_primary: contactForm.is_primary,
        });
        toast.success("Contact added");
      }
      setContactDialogOpen(false);
      loadContacts();
    } catch (err: unknown) {
      setContactError(getApiErrorMessage(err, "Failed to save contact"));
    }
  }

  async function handleDeleteContact(contactId: string) {
    if (!vendorId) return;
    try {
      await vendorService.deleteContact(vendorId, contactId);
      toast.success("Contact removed");
      loadContacts();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete contact"));
    }
  }

  // ---- Notes ----

  async function handleAddNote() {
    if (!vendorId || !newNoteContent.trim()) return;
    try {
      await vendorService.createNote(vendorId, {
        note_type: newNoteType,
        content: newNoteContent.trim(),
      });
      setNewNoteContent("");
      toast.success("Note added");
      loadNotes();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to add note"));
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading vendor...</p>
      </div>
    );
  }

  const notesTotalPages = Math.ceil(notesTotal / 20);

  const tabs = [
    { key: "details" as const, label: "Details" },
    { key: "contacts" as const, label: `Contacts (${contacts.length})` },
    { key: "notes" as const, label: "Notes" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Link to="/vendors" className="hover:underline">
              Vendors
            </Link>
            <span>/</span>
            <span>{name}</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{name}</h1>
            {statusBadge(vendorStatus)}
            {!isActive && <Badge variant="destructive">Inactive</Badge>}
          </div>
          {accountNumber && (
            <p className="text-muted-foreground">
              Account #{accountNumber}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {canDelete && isActive && (
            <Button variant="destructive" size="sm" onClick={handleDeactivate}>
              Deactivate
            </Button>
          )}
          {canEdit && (
            <Button onClick={handleSave} disabled={saving || !name.trim()}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Details Tab */}
      {activeTab === "details" && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Core Info */}
          <Card className="p-6 space-y-4">
            <h2 className="text-lg font-semibold">Vendor Info</h2>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>Vendor Name</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Account #</Label>
                  <Input
                    value={accountNumber}
                    onChange={(e) => setAccountNumber(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Status</Label>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                    value={vendorStatus}
                    onChange={(e) => setVendorStatus(e.target.value)}
                    disabled={!canEdit}
                  >
                    <option value="active">Active</option>
                    <option value="on_hold">On Hold</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
              </div>
              <div className="space-y-1">
                <Label>Contact Name</Label>
                <Input
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Phone</Label>
                  <Input
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Fax</Label>
                  <Input
                    value={fax}
                    onChange={(e) => setFax(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Website</Label>
                  <Input
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
              </div>
            </div>
          </Card>

          {/* Address */}
          <Card className="p-6 space-y-4">
            <h2 className="text-lg font-semibold">Address</h2>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>Address Line 1</Label>
                <Input
                  value={addressLine1}
                  onChange={(e) => setAddressLine1(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-1">
                <Label>Address Line 2</Label>
                <Input
                  value={addressLine2}
                  onChange={(e) => setAddressLine2(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1">
                  <Label>City</Label>
                  <Input
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label>State</Label>
                  <Input
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Zip Code</Label>
                  <Input
                    value={zipCode}
                    onChange={(e) => setZipCode(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Country</Label>
                <Input
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
          </Card>

          {/* Purchasing Info */}
          <Card className="p-6 space-y-4">
            <h2 className="text-lg font-semibold">Purchasing Info</h2>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Payment Terms</Label>
                  <Input
                    value={paymentTerms}
                    onChange={(e) => setPaymentTerms(e.target.value)}
                    disabled={!canEdit}
                    placeholder="e.g. Net 30"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Lead Time (days)</Label>
                  <Input
                    type="number"
                    min="0"
                    value={leadTimeDays}
                    onChange={(e) => setLeadTimeDays(e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Minimum Order ($)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={minimumOrder}
                  onChange={(e) => setMinimumOrder(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <Separator />
              <div className="space-y-1">
                <Label>Tax ID / EIN</Label>
                <Input
                  value={taxId}
                  onChange={(e) => setTaxId(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
              <div className="space-y-1">
                <Label>Sage Vendor ID</Label>
                <Input
                  value={sageVendorId}
                  onChange={(e) => setSageVendorId(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
          </Card>

          {/* Notes field */}
          <Card className="p-6 space-y-4">
            <h2 className="text-lg font-semibold">General Notes</h2>
            <textarea
              className="flex min-h-[120px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
              value={vendorNotes}
              onChange={(e) => setVendorNotes(e.target.value)}
              disabled={!canEdit}
              placeholder="Internal notes about this vendor..."
            />
          </Card>
        </div>
      )}

      {/* Contacts Tab */}
      {activeTab === "contacts" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              Contacts ({contacts.length})
            </h2>
            {canEdit && (
              <Button size="sm" onClick={openAddContact}>
                <PlusIcon className="mr-1 size-4" />
                Add Contact
              </Button>
            )}
          </div>
          {contacts.length === 0 ? (
            <Card className="p-6 text-center text-muted-foreground">
              No contacts yet
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {contacts.map((c) => (
                <Card key={c.id} className="p-4 space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium">{c.name}</p>
                      {c.title && (
                        <p className="text-sm text-muted-foreground">
                          {c.title}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      {c.is_primary && (
                        <Badge variant="default" className="text-xs">
                          Primary
                        </Badge>
                      )}
                      {canEdit && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="size-8 p-0 text-destructive"
                          onClick={() => handleDeleteContact(c.id)}
                        >
                          <Trash2Icon className="size-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                  {c.email && (
                    <p className="text-sm text-muted-foreground">{c.email}</p>
                  )}
                  {c.phone && (
                    <p className="text-sm text-muted-foreground">{c.phone}</p>
                  )}
                  {canEdit && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEditContact(c)}
                    >
                      Edit
                    </Button>
                  )}
                </Card>
              ))}
            </div>
          )}

          {/* Contact Dialog */}
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
                    ? "Update this contact's information."
                    : "Add a new contact for this vendor."}
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
                      setContactForm({ ...contactForm, name: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Title</Label>
                  <Input
                    value={contactForm.title}
                    onChange={(e) =>
                      setContactForm({ ...contactForm, title: e.target.value })
                    }
                    placeholder="e.g. Account Manager"
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
                  {editingContact ? "Update" : "Add Contact"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}

      {/* Notes Tab */}
      {activeTab === "notes" && (
        <div className="space-y-6">
          {/* Add note form */}
          {canEdit && (
            <Card className="p-4 space-y-3">
              <div className="flex items-center gap-2">
                <select
                  className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={newNoteType}
                  onChange={(e) => setNewNoteType(e.target.value)}
                >
                  <option value="general">General</option>
                  <option value="call">Call</option>
                  <option value="email">Email</option>
                  <option value="visit">Visit</option>
                </select>
              </div>
              <textarea
                className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                value={newNoteContent}
                onChange={(e) => setNewNoteContent(e.target.value)}
                placeholder="Add a note..."
              />
              <div className="flex justify-end">
                <Button
                  size="sm"
                  onClick={handleAddNote}
                  disabled={!newNoteContent.trim()}
                >
                  Add Note
                </Button>
              </div>
            </Card>
          )}

          {/* Notes list */}
          {notes.length === 0 ? (
            <Card className="p-6 text-center text-muted-foreground">
              No notes yet
            </Card>
          ) : (
            <div className="space-y-3">
              {notes.map((note) => (
                <Card key={note.id} className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {noteTypeBadge(note.note_type)}
                      <span className="text-xs text-muted-foreground">
                        {formatDate(note.created_at)}
                      </span>
                    </div>
                    {note.created_by_name && (
                      <span className="text-xs text-muted-foreground">
                        by {note.created_by_name}
                      </span>
                    )}
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{note.content}</p>
                </Card>
              ))}
            </div>
          )}

          {/* Notes pagination */}
          {notesTotalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
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
                variant="outline"
                size="sm"
                disabled={notesPage >= notesTotalPages}
                onClick={() => setNotesPage(notesPage + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
