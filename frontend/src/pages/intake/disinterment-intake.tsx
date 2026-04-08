import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  User,
  MapPin,
  FileText,
  Phone,
  Users,
  Send,
  Plus,
  X,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface TokenInfo {
  case_number: string;
  status: string;
  already_submitted: boolean;
  company_name: string | null;
}

interface NextOfKin {
  name: string;
  email: string;
  phone: string;
  relationship: string;
}

interface FormData {
  decedent_name: string;
  date_of_death: string;
  date_of_burial: string;
  vault_description: string;
  cemetery_name: string;
  cemetery_city: string;
  cemetery_state: string;
  cemetery_lot_section: string;
  cemetery_lot_space: string;
  reason: string;
  destination: string;
  funeral_director_name: string;
  funeral_director_email: string;
  funeral_director_phone: string;
  funeral_home_name: string;
  next_of_kin: NextOfKin[];
}

/* ------------------------------------------------------------------ */
/* Steps config                                                        */
/* ------------------------------------------------------------------ */

const STEPS = [
  { key: "decedent", label: "Decedent", icon: User },
  { key: "cemetery", label: "Cemetery", icon: MapPin },
  { key: "reason", label: "Reason & Destination", icon: FileText },
  { key: "contact", label: "Funeral Director", icon: Phone },
  { key: "nok", label: "Next of Kin", icon: Users },
  { key: "confirm", label: "Confirm", icon: Send },
] as const;

/* ------------------------------------------------------------------ */
/* API helpers — no auth, raw fetch                                    */
/* ------------------------------------------------------------------ */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}/api/v1${path}`);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function DisintermentIntakePage() {
  const { token } = useParams<{ token: string }>();
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [caseNumber, setCaseNumber] = useState("");

  const [form, setForm] = useState<FormData>({
    decedent_name: "",
    date_of_death: "",
    date_of_burial: "",
    vault_description: "",
    cemetery_name: "",
    cemetery_city: "",
    cemetery_state: "",
    cemetery_lot_section: "",
    cemetery_lot_space: "",
    reason: "",
    destination: "",
    funeral_director_name: "",
    funeral_director_email: "",
    funeral_director_phone: "",
    funeral_home_name: "",
    next_of_kin: [{ name: "", email: "", phone: "", relationship: "" }],
  });

  useEffect(() => {
    if (!token) {
      setError("Invalid intake link");
      setLoading(false);
      return;
    }
    apiGet<TokenInfo>(`/intake/${token}`)
      .then((data) => {
        if (data.already_submitted) {
          setSubmitted(true);
          setCaseNumber(data.case_number);
        }
        setTokenInfo(data);
      })
      .catch(() => setError("This intake link is invalid or has expired."))
      .finally(() => setLoading(false));
  }, [token]);

  const updateForm = (updates: Partial<FormData>) =>
    setForm((prev) => ({ ...prev, ...updates }));

  const updateNok = (index: number, updates: Partial<NextOfKin>) => {
    const nok = [...form.next_of_kin];
    nok[index] = { ...nok[index], ...updates };
    setForm((prev) => ({ ...prev, next_of_kin: nok }));
  };

  const addNok = () => {
    setForm((prev) => ({
      ...prev,
      next_of_kin: [
        ...prev.next_of_kin,
        { name: "", email: "", phone: "", relationship: "" },
      ],
    }));
  };

  const removeNok = (index: number) => {
    if (form.next_of_kin.length <= 1) return;
    setForm((prev) => ({
      ...prev,
      next_of_kin: prev.next_of_kin.filter((_, i) => i !== index),
    }));
  };

  const canAdvance = (): boolean => {
    switch (step) {
      case 0:
        return !!form.decedent_name.trim();
      case 1:
        return true; // cemetery info optional
      case 2:
        return !!form.reason.trim() && !!form.destination.trim();
      case 3:
        return (
          !!form.funeral_director_name.trim() &&
          !!form.funeral_director_email.trim()
        );
      case 4:
        return form.next_of_kin.some((k) => k.name.trim() && k.email.trim());
      case 5:
        return true;
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        date_of_death: form.date_of_death || null,
        date_of_burial: form.date_of_burial || null,
        next_of_kin: form.next_of_kin.filter((k) => k.name.trim()),
        confirmed_accurate: true,
      };
      const result = await apiPost<{ case_number: string; message: string }>(
        `/intake/${token}`,
        payload
      );
      setCaseNumber(result.case_number);
      setSubmitted(true);
    } catch {
      toast.error("Failed to submit. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  // Loading / error states
  if (loading) {
    return (
      <PublicShell>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </PublicShell>
    );
  }

  if (error) {
    return (
      <PublicShell>
        <Card className="max-w-md mx-auto mt-12">
          <CardContent className="py-12 text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-red-400" />
            <h2 className="text-lg font-semibold mb-2">Invalid Link</h2>
            <p className="text-gray-500">{error}</p>
          </CardContent>
        </Card>
      </PublicShell>
    );
  }

  if (submitted) {
    return (
      <PublicShell companyName={tokenInfo?.company_name}>
        <Card className="max-w-md mx-auto mt-12">
          <CardContent className="py-12 text-center">
            <CheckCircle2 className="mx-auto mb-4 h-12 w-12 text-green-500" />
            <h2 className="text-lg font-semibold mb-2">
              Intake Submitted Successfully
            </h2>
            <p className="text-gray-500 mb-4">
              Case <strong>{caseNumber}</strong> has been received. We will
              review the information and be in touch to confirm the quote and
              next steps.
            </p>
          </CardContent>
        </Card>
      </PublicShell>
    );
  }

  const StepIcon = STEPS[step].icon;

  return (
    <PublicShell companyName={tokenInfo?.company_name}>
      <div className="max-w-2xl mx-auto mt-6 space-y-6">
        {/* Step indicator */}
        <div className="flex items-center justify-between px-2">
          {STEPS.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.key} className="flex items-center">
                <div
                  className={`flex items-center justify-center h-8 w-8 rounded-full text-xs font-medium transition-colors ${
                    i === step
                      ? "bg-blue-600 text-white"
                      : i < step
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {i < step ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={`mx-1 h-px w-4 sm:w-8 ${
                      i < step ? "bg-green-300" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Step content */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <StepIcon className="h-5 w-5 text-blue-600" />
              {STEPS[step].label}
            </CardTitle>
            <p className="text-sm text-gray-500">
              Case {tokenInfo?.case_number}
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {step === 0 && (
              <DecedentStep form={form} updateForm={updateForm} />
            )}
            {step === 1 && (
              <CemeteryStep form={form} updateForm={updateForm} />
            )}
            {step === 2 && (
              <ReasonStep form={form} updateForm={updateForm} />
            )}
            {step === 3 && (
              <ContactStep form={form} updateForm={updateForm} />
            )}
            {step === 4 && (
              <NokStep
                form={form}
                updateNok={updateNok}
                addNok={addNok}
                removeNok={removeNok}
              />
            )}
            {step === 5 && <ConfirmStep form={form} />}
          </CardContent>
        </Card>

        {/* Navigation buttons */}
        <div className="flex justify-between">
          <Button
            variant="outline"
            onClick={() => setStep(step - 1)}
            disabled={step === 0}
          >
            <ChevronLeft className="mr-2 h-4 w-4" /> Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button
              onClick={() => setStep(step + 1)}
              disabled={!canAdvance()}
            >
              Next <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={submitting}
              className="bg-green-600 hover:bg-green-700"
            >
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Submit Intake
            </Button>
          )}
        </div>
      </div>
    </PublicShell>
  );
}

/* ------------------------------------------------------------------ */
/* Public Shell (no auth header)                                       */
/* ------------------------------------------------------------------ */

function PublicShell({
  children,
  companyName,
}: {
  children: React.ReactNode;
  companyName?: string | null;
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <FileText className="h-6 w-6 text-blue-600" />
          <div>
            <h1 className="font-semibold text-lg">
              Disinterment Intake Form
            </h1>
            {companyName && (
              <p className="text-sm text-gray-500">{companyName}</p>
            )}
          </div>
        </div>
      </header>
      <main className="px-4 pb-12">{children}</main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Step Components                                                     */
/* ------------------------------------------------------------------ */

function DecedentStep({
  form,
  updateForm,
}: {
  form: FormData;
  updateForm: (u: Partial<FormData>) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Label>
          Decedent Name <span className="text-red-500">*</span>
        </Label>
        <Input
          value={form.decedent_name}
          onChange={(e) => updateForm({ decedent_name: e.target.value })}
          placeholder="Full name of the deceased"
        />
      </div>
      <div>
        <Label>Date of Death</Label>
        <Input
          type="date"
          value={form.date_of_death}
          onChange={(e) => updateForm({ date_of_death: e.target.value })}
        />
      </div>
      <div>
        <Label>Date of Burial</Label>
        <Input
          type="date"
          value={form.date_of_burial}
          onChange={(e) => updateForm({ date_of_burial: e.target.value })}
        />
      </div>
      <div className="sm:col-span-2">
        <Label>Vault Description</Label>
        <Input
          value={form.vault_description}
          onChange={(e) => updateForm({ vault_description: e.target.value })}
          placeholder="Type, material, condition if known"
        />
      </div>
    </div>
  );
}

function CemeteryStep({
  form,
  updateForm,
}: {
  form: FormData;
  updateForm: (u: Partial<FormData>) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Label>Cemetery Name</Label>
        <Input
          value={form.cemetery_name}
          onChange={(e) => updateForm({ cemetery_name: e.target.value })}
          placeholder="Name of cemetery"
        />
      </div>
      <div>
        <Label>City</Label>
        <Input
          value={form.cemetery_city}
          onChange={(e) => updateForm({ cemetery_city: e.target.value })}
        />
      </div>
      <div>
        <Label>State</Label>
        <Input
          value={form.cemetery_state}
          onChange={(e) => updateForm({ cemetery_state: e.target.value })}
          placeholder="e.g. NY"
        />
      </div>
      <div>
        <Label>Lot/Section</Label>
        <Input
          value={form.cemetery_lot_section}
          onChange={(e) =>
            updateForm({ cemetery_lot_section: e.target.value })
          }
        />
      </div>
      <div>
        <Label>Lot/Space</Label>
        <Input
          value={form.cemetery_lot_space}
          onChange={(e) =>
            updateForm({ cemetery_lot_space: e.target.value })
          }
        />
      </div>
    </div>
  );
}

function ReasonStep({
  form,
  updateForm,
}: {
  form: FormData;
  updateForm: (u: Partial<FormData>) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <Label>
          Reason for Disinterment <span className="text-red-500">*</span>
        </Label>
        <Textarea
          value={form.reason}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateForm({ reason: e.target.value })}
          placeholder="e.g. Relocation to family plot, transfer to another cemetery..."
          rows={3}
        />
      </div>
      <div>
        <Label>
          Destination <span className="text-red-500">*</span>
        </Label>
        <Textarea
          value={form.destination}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateForm({ destination: e.target.value })}
          placeholder="Where the remains will be transferred to (cemetery name, address, etc.)"
          rows={3}
        />
      </div>
    </div>
  );
}

function ContactStep({
  form,
  updateForm,
}: {
  form: FormData;
  updateForm: (u: Partial<FormData>) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <Label>
          Funeral Home Name
        </Label>
        <Input
          value={form.funeral_home_name}
          onChange={(e) => updateForm({ funeral_home_name: e.target.value })}
          placeholder="Name of funeral home"
        />
      </div>
      <div className="sm:col-span-2">
        <Label>
          Funeral Director Name <span className="text-red-500">*</span>
        </Label>
        <Input
          value={form.funeral_director_name}
          onChange={(e) =>
            updateForm({ funeral_director_name: e.target.value })
          }
          placeholder="Full name"
        />
      </div>
      <div>
        <Label>
          Email <span className="text-red-500">*</span>
        </Label>
        <Input
          type="email"
          value={form.funeral_director_email}
          onChange={(e) =>
            updateForm({ funeral_director_email: e.target.value })
          }
          placeholder="director@funeralhome.com"
        />
      </div>
      <div>
        <Label>Phone</Label>
        <Input
          type="tel"
          value={form.funeral_director_phone}
          onChange={(e) =>
            updateForm({ funeral_director_phone: e.target.value })
          }
          placeholder="(555) 123-4567"
        />
      </div>
    </div>
  );
}

function NokStep({
  form,
  updateNok,
  addNok,
  removeNok,
}: {
  form: FormData;
  updateNok: (i: number, u: Partial<NextOfKin>) => void;
  addNok: () => void;
  removeNok: (i: number) => void;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        Provide at least one next-of-kin who will need to authorize the
        disinterment.
      </p>
      {form.next_of_kin.map((k, i) => (
        <div
          key={i}
          className="rounded-lg border p-4 space-y-3 relative"
        >
          {form.next_of_kin.length > 1 && (
            <button
              onClick={() => removeNok(i)}
              className="absolute top-2 right-2 text-gray-400 hover:text-red-500"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label>
                Name <span className="text-red-500">*</span>
              </Label>
              <Input
                value={k.name}
                onChange={(e) => updateNok(i, { name: e.target.value })}
                placeholder="Full name"
              />
            </div>
            <div>
              <Label>Relationship</Label>
              <Input
                value={k.relationship}
                onChange={(e) =>
                  updateNok(i, { relationship: e.target.value })
                }
                placeholder="e.g. Spouse, Child"
              />
            </div>
            <div>
              <Label>
                Email <span className="text-red-500">*</span>
              </Label>
              <Input
                type="email"
                value={k.email}
                onChange={(e) => updateNok(i, { email: e.target.value })}
                placeholder="email@example.com"
              />
            </div>
            <div>
              <Label>Phone</Label>
              <Input
                type="tel"
                value={k.phone}
                onChange={(e) => updateNok(i, { phone: e.target.value })}
                placeholder="(555) 123-4567"
              />
            </div>
          </div>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={addNok}>
        <Plus className="mr-2 h-4 w-4" /> Add Another
      </Button>
    </div>
  );
}

function ConfirmStep({ form }: { form: FormData }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        Please review the information below before submitting.
      </p>

      <Section title="Decedent">
        <Row label="Name" value={form.decedent_name} />
        <Row label="Date of Death" value={form.date_of_death || "—"} />
        <Row label="Date of Burial" value={form.date_of_burial || "—"} />
        <Row label="Vault" value={form.vault_description || "—"} />
      </Section>

      <Section title="Cemetery">
        <Row label="Name" value={form.cemetery_name || "—"} />
        <Row
          label="Location"
          value={
            [form.cemetery_city, form.cemetery_state]
              .filter(Boolean)
              .join(", ") || "—"
          }
        />
        <Row label="Lot/Section" value={form.cemetery_lot_section || "—"} />
        <Row label="Lot/Space" value={form.cemetery_lot_space || "—"} />
      </Section>

      <Section title="Reason & Destination">
        <Row label="Reason" value={form.reason} />
        <Row label="Destination" value={form.destination} />
      </Section>

      <Section title="Funeral Director">
        <Row label="Name" value={form.funeral_director_name} />
        <Row label="Email" value={form.funeral_director_email} />
        <Row label="Phone" value={form.funeral_director_phone || "—"} />
        <Row label="Funeral Home" value={form.funeral_home_name || "—"} />
      </Section>

      <Section title="Next of Kin">
        {form.next_of_kin
          .filter((k) => k.name.trim())
          .map((k, i) => (
            <div key={i} className="text-sm">
              <span className="font-medium">{k.name}</span>
              {k.relationship && (
                <span className="text-gray-500"> ({k.relationship})</span>
              )}
              <span className="text-gray-500"> — {k.email}</span>
            </div>
          ))}
      </Section>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Confirm step helpers                                                */
/* ------------------------------------------------------------------ */

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border p-3 space-y-1">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-right max-w-[60%]">{value}</span>
    </div>
  );
}
