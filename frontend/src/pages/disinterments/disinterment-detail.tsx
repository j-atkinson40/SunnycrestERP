import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import {
  ArrowLeft,
  ClipboardList,
  FileText,
  FileSignature,
  Calendar,
  CheckCircle2,
  Copy,
  Send,
  Loader2,
  XCircle,
  User,
  MapPin,
  Clock,
  Truck,
  DollarSign,
  AlertTriangle,
  Check,
  ExternalLink,
} from "lucide-react";
import {
  CemeteryLocationModal,
  useCemeteryLocation,
} from "@/components/shared/CemeteryLocationModal";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface SignatureStatus {
  party: string;
  status: string;
  signed_at: string | null;
}

interface CaseDetail {
  id: string;
  company_id: string;
  case_number: string;
  status: string;
  decedent_name: string;
  date_of_death: string | null;
  date_of_burial: string | null;
  reason: string | null;
  destination: string | null;
  vault_description: string | null;
  cemetery_id: string | null;
  cemetery_name: string | null;
  cemetery_lot_section: string | null;
  cemetery_lot_space: string | null;
  fulfilling_location_id: string | null;
  fulfilling_location_name: string | null;
  funeral_home_id: string | null;
  funeral_home_name: string | null;
  funeral_director_contact_id: string | null;
  next_of_kin: Array<{
    name: string;
    email: string;
    phone?: string;
    relationship: string;
  }>;
  intake_token: string | null;
  intake_submitted_at: string | null;
  quote_id: string | null;
  accepted_quote_amount: number | null;
  has_hazard_pay: boolean;
  docusign_envelope_id: string | null;
  signatures: SignatureStatus[];
  scheduled_date: string | null;
  assigned_driver_id: string | null;
  assigned_driver_name: string | null;
  assigned_crew: string[];
  rotation_assignment_id: string | null;
  completed_at: string | null;
  invoice_id: string | null;
  created_by_user_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/* ------------------------------------------------------------------ */
/* Stage pipeline config                                               */
/* ------------------------------------------------------------------ */

const STAGES = [
  { key: "intake", label: "Intake", icon: ClipboardList },
  { key: "quote", label: "Quote", icon: DollarSign },
  { key: "signatures", label: "Signatures", icon: FileSignature },
  { key: "scheduling", label: "Scheduling", icon: Calendar },
  { key: "complete", label: "Complete", icon: CheckCircle2 },
] as const;

function stageIndex(status: string): number {
  switch (status) {
    case "intake":
      return 0;
    case "quoted":
    case "quote_accepted":
      return 1;
    case "signatures_pending":
    case "signatures_complete":
      return 2;
    case "scheduled":
      return 3;
    case "complete":
      return 4;
    case "cancelled":
      return -1;
    default:
      return 0;
  }
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function DisintermentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchCase = () => {
    if (!id) return;
    setLoading(true);
    apiClient
      .get(`/disinterments/${id}`)
      .then((r) => setCaseData(r.data))
      .catch(() => toast.error("Failed to load case"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCase();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        Case not found
      </div>
    );
  }

  const currentStage = stageIndex(caseData.status);
  const isCancelled = caseData.status === "cancelled";

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/disinterments")}
          >
            <ArrowLeft className="mr-2 h-4 w-4" /> Back
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{caseData.case_number}</h1>
              <StatusBadge status={caseData.status} />
            </div>
            <p className="text-muted-foreground">{caseData.decedent_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {caseData.intake_token && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const url = `${window.location.origin}/intake/disinterment/${caseData.intake_token}`;
                navigator.clipboard.writeText(url);
                toast.success("Intake link copied");
              }}
            >
              <Copy className="mr-2 h-4 w-4" /> Copy Intake Link
            </Button>
          )}
          {!isCancelled && caseData.status !== "complete" && (
            <CancelButton caseId={caseData.id} onDone={fetchCase} />
          )}
        </div>
      </div>

      {/* Stage Pipeline Visual */}
      {!isCancelled && <StagePipeline currentStage={currentStage} />}

      {isCancelled && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex items-center gap-3 p-4">
            <XCircle className="h-5 w-5 text-destructive" />
            <span className="font-medium text-destructive">
              This case has been cancelled.
            </span>
          </CardContent>
        </Card>
      )}

      {/* Stage Content */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column: Active stage card */}
        <div className="lg:col-span-2 space-y-6">
          {currentStage === 0 && (
            <IntakeStage caseData={caseData} onUpdate={fetchCase} />
          )}
          {currentStage === 1 && (
            <QuoteStage caseData={caseData} onUpdate={fetchCase} />
          )}
          {currentStage === 2 && (
            <SignaturesStage caseData={caseData} onUpdate={fetchCase} />
          )}
          {currentStage === 3 && (
            <SchedulingStage caseData={caseData} onUpdate={fetchCase} />
          )}
          {currentStage === 4 && <CompleteStage caseData={caseData} />}
        </div>

        {/* Right column: Summary sidebar */}
        <div className="space-y-4">
          <CaseSummary caseData={caseData} />
          <NextOfKinCard nok={caseData.next_of_kin} />
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Status Badge                                                        */
/* ------------------------------------------------------------------ */

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    intake: "bg-blue-50 text-blue-700 border-blue-200",
    quoted: "bg-amber-50 text-amber-700 border-amber-200",
    quote_accepted: "bg-orange-50 text-orange-700 border-orange-200",
    signatures_pending: "bg-purple-50 text-purple-700 border-purple-200",
    signatures_complete: "bg-indigo-50 text-indigo-700 border-indigo-200",
    scheduled: "bg-emerald-50 text-emerald-700 border-emerald-200",
    complete: "bg-green-50 text-green-700 border-green-200",
    cancelled: "bg-gray-50 text-gray-500 border-gray-200",
  };
  return (
    <Badge variant="outline" className={colors[status] || ""}>
      {status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
    </Badge>
  );
}

/* ------------------------------------------------------------------ */
/* Stage Pipeline Visual                                               */
/* ------------------------------------------------------------------ */

function StagePipeline({ currentStage }: { currentStage: number }) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto">
      {STAGES.map((stage, i) => {
        const Icon = stage.icon;
        const isActive = i === currentStage;
        const isDone = i < currentStage;
        return (
          <div key={stage.key} className="flex items-center">
            <div
              className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                isDone
                  ? "bg-green-50 text-green-700"
                  : isActive
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {isDone ? (
                <Check className="h-4 w-4" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
              <span className="hidden sm:inline">{stage.label}</span>
            </div>
            {i < STAGES.length - 1 && (
              <div
                className={`mx-1 h-px w-6 ${
                  i < currentStage ? "bg-green-300" : "bg-border"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stage 1: Intake                                                     */
/* ------------------------------------------------------------------ */

function IntakeStage({
  caseData,
  onUpdate,
}: {
  caseData: CaseDetail;
  onUpdate: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    decedent_name: caseData.decedent_name,
    date_of_death: caseData.date_of_death || "",
    date_of_burial: caseData.date_of_burial || "",
    reason: caseData.reason || "",
    destination: caseData.destination || "",
    vault_description: caseData.vault_description || "",
    cemetery_lot_section: caseData.cemetery_lot_section || "",
    cemetery_lot_space: caseData.cemetery_lot_space || "",
  });

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/disinterments/${caseData.id}/intake`, form);
      toast.success("Intake updated");
      setEditing(false);
      onUpdate();
    } catch {
      toast.error("Failed to update");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <ClipboardList className="h-5 w-5 text-blue-600" />
            Intake Review
          </CardTitle>
          {!editing && (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              Edit
            </Button>
          )}
        </div>
        {caseData.intake_submitted_at && (
          <p className="text-sm text-muted-foreground">
            Intake submitted{" "}
            {new Date(caseData.intake_submitted_at).toLocaleString()}
          </p>
        )}
        {!caseData.intake_submitted_at && (
          <p className="text-sm text-amber-600">
            Awaiting intake form submission from funeral director
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {editing ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label>Decedent Name</Label>
                <Input
                  value={form.decedent_name}
                  onChange={(e) =>
                    setForm({ ...form, decedent_name: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Date of Death</Label>
                <Input
                  type="date"
                  value={form.date_of_death}
                  onChange={(e) =>
                    setForm({ ...form, date_of_death: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Date of Burial</Label>
                <Input
                  type="date"
                  value={form.date_of_burial}
                  onChange={(e) =>
                    setForm({ ...form, date_of_burial: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Vault Description</Label>
                <Input
                  value={form.vault_description}
                  onChange={(e) =>
                    setForm({ ...form, vault_description: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Lot/Section</Label>
                <Input
                  value={form.cemetery_lot_section}
                  onChange={(e) =>
                    setForm({ ...form, cemetery_lot_section: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Lot/Space</Label>
                <Input
                  value={form.cemetery_lot_space}
                  onChange={(e) =>
                    setForm({ ...form, cemetery_lot_space: e.target.value })
                  }
                />
              </div>
            </div>
            <div>
              <Label>Reason for Disinterment</Label>
              <Textarea
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                rows={2}
              />
            </div>
            <div>
              <Label>Destination</Label>
              <Textarea
                value={form.destination}
                onChange={(e) =>
                  setForm({ ...form, destination: e.target.value })
                }
                rows={2}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                onClick={() => setEditing(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Check className="mr-2 h-4 w-4" />
                )}
                Save
              </Button>
            </div>
          </>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <InfoRow label="Decedent" value={caseData.decedent_name} />
            <InfoRow
              label="Date of Death"
              value={
                caseData.date_of_death
                  ? new Date(caseData.date_of_death).toLocaleDateString()
                  : null
              }
            />
            <InfoRow
              label="Date of Burial"
              value={
                caseData.date_of_burial
                  ? new Date(caseData.date_of_burial).toLocaleDateString()
                  : null
              }
            />
            <InfoRow label="Vault" value={caseData.vault_description} />
            <InfoRow label="Lot/Section" value={caseData.cemetery_lot_section} />
            <InfoRow label="Lot/Space" value={caseData.cemetery_lot_space} />
            <InfoRow label="Reason" value={caseData.reason} span2 />
            <InfoRow label="Destination" value={caseData.destination} span2 />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Stage 2: Quote                                                      */
/* ------------------------------------------------------------------ */

function QuoteStage({
  caseData,
  onUpdate,
}: {
  caseData: CaseDetail;
  onUpdate: () => void;
}) {
  const [quoteAmount, setQuoteAmount] = useState(
    caseData.accepted_quote_amount?.toString() || ""
  );
  const [hasHazard, setHasHazard] = useState(caseData.has_hazard_pay);
  const [accepting, setAccepting] = useState(false);

  const isAccepted = caseData.status === "quote_accepted";

  const handleAccept = async () => {
    const amount = parseFloat(quoteAmount);
    if (!amount || amount <= 0) {
      toast.error("Enter a valid quote amount");
      return;
    }
    setAccepting(true);
    try {
      await apiClient.post(`/disinterments/${caseData.id}/accept-quote`, null, {
        params: {
          quote_id: caseData.quote_id || caseData.id,
          quote_amount: amount,
          has_hazard_pay: hasHazard,
        },
      });
      toast.success("Quote accepted");
      onUpdate();
    } catch {
      toast.error("Failed to accept quote");
    } finally {
      setAccepting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DollarSign className="h-5 w-5 text-amber-600" />
          Quote
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isAccepted ? (
          <div className="rounded-md bg-green-50 border border-green-200 p-4">
            <div className="flex items-center gap-2 text-green-700 font-medium">
              <CheckCircle2 className="h-5 w-5" />
              Quote Accepted
            </div>
            <p className="mt-2 text-2xl font-bold text-green-800">
              ${Number(caseData.accepted_quote_amount || 0).toFixed(2)}
            </p>
            {caseData.has_hazard_pay && (
              <Badge className="mt-2 bg-amber-100 text-amber-700 border-amber-300">
                <AlertTriangle className="mr-1 h-3 w-3" /> Hazard Pay
              </Badge>
            )}
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              Enter the quote amount and accept to advance to the signatures
              stage.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label>Quote Amount ($)</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={quoteAmount}
                  onChange={(e) => setQuoteAmount(e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="flex items-center gap-3 pt-6">
                <Switch
                  checked={hasHazard}
                  onCheckedChange={setHasHazard}
                  id="hazard"
                />
                <Label
                  htmlFor="hazard"
                  className="text-amber-600 font-medium"
                >
                  Hazard Pay
                </Label>
              </div>
            </div>
            <Button
              onClick={handleAccept}
              disabled={accepting || !quoteAmount}
            >
              {accepting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Check className="mr-2 h-4 w-4" />
              )}
              Accept Quote
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Stage 3: Signatures                                                 */
/* ------------------------------------------------------------------ */

function SignaturesStage({
  caseData,
  onUpdate,
}: {
  caseData: CaseDetail;
  onUpdate: () => void;
}) {
  const [sending, setSending] = useState(false);
  const allSigned =
    caseData.signatures.length > 0 &&
    caseData.signatures.every((s) => s.status === "signed");

  const handleSend = async () => {
    setSending(true);
    try {
      await apiClient.post(`/disinterments/${caseData.id}/send-signatures`);
      toast.success("Sent for signatures via DocuSign");
      onUpdate();
    } catch {
      toast.error("Failed to send for signatures");
    } finally {
      setSending(false);
    }
  };

  const sigPartyLabels: Record<string, string> = {
    funeral_home: "Funeral Home",
    cemetery: "Cemetery",
    next_of_kin: "Next of Kin",
    manufacturer: "Manufacturer",
  };

  const sigStatusColors: Record<string, string> = {
    not_sent: "bg-gray-50 text-gray-500 border-gray-200",
    sent: "bg-blue-50 text-blue-700 border-blue-200",
    signed: "bg-green-50 text-green-700 border-green-200",
    declined: "bg-red-50 text-red-700 border-red-200",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileSignature className="h-5 w-5 text-purple-600" />
          Signatures
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {caseData.status === "quote_accepted" && !caseData.docusign_envelope_id && (
          <>
            <p className="text-sm text-muted-foreground">
              Send the disinterment authorization form to all 4 required
              signers via DocuSign.
            </p>
            <Button onClick={handleSend} disabled={sending}>
              {sending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Send for Signatures
            </Button>
          </>
        )}

        {caseData.signatures.length > 0 && (
          <div className="space-y-3">
            {caseData.signatures.map((sig) => (
              <div
                key={sig.party}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div className="flex items-center gap-3">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">
                    {sigPartyLabels[sig.party] || sig.party}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={sigStatusColors[sig.status] || ""}
                  >
                    {sig.status === "signed" && (
                      <Check className="mr-1 h-3 w-3" />
                    )}
                    {sig.status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </Badge>
                  {sig.signed_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(sig.signed_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {allSigned && (
          <div className="rounded-md bg-green-50 border border-green-200 p-3 text-sm text-green-700 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            All signatures complete — ready for scheduling
          </div>
        )}

        {caseData.docusign_envelope_id && (
          <p className="text-xs text-muted-foreground">
            Envelope ID: {caseData.docusign_envelope_id}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Stage 4: Scheduling                                                 */
/* ------------------------------------------------------------------ */

function SchedulingStage({
  caseData,
  onUpdate,
}: {
  caseData: CaseDetail;
  onUpdate: () => void;
}) {
  const [date, setDate] = useState(caseData.scheduled_date || "");
  const [driverId, setDriverId] = useState(caseData.assigned_driver_id || "");
  const [crew, setCrew] = useState(caseData.assigned_crew?.join(", ") || "");
  const [scheduling, setScheduling] = useState(false);
  const [completing, setCompleting] = useState(false);

  const isScheduled = caseData.status === "scheduled";

  // Cemetery location check
  const cemLoc = useCemeteryLocation(caseData.cemetery_id);

  const handleSchedule = async () => {
    if (!date) {
      toast.error("Select a date");
      return;
    }

    // Check cemetery location first
    if (cemLoc.needsMapping && caseData.cemetery_id) {
      cemLoc.openModal();
      return;
    }

    setScheduling(true);
    try {
      await apiClient.post(`/disinterments/${caseData.id}/schedule`, {
        scheduled_date: date,
        assigned_driver_id: driverId || null,
        assigned_crew: crew
          ? crew.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
      });
      toast.success("Disinterment scheduled");
      onUpdate();
    } catch {
      toast.error("Failed to schedule");
    } finally {
      setScheduling(false);
    }
  };

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await apiClient.post(`/disinterments/${caseData.id}/complete`);
      toast.success("Case completed — invoice generated");
      onUpdate();
    } catch {
      toast.error("Failed to complete case");
    } finally {
      setCompleting(false);
    }
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-emerald-600" />
            Scheduling
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isScheduled ? (
            <>
              <div className="rounded-md bg-emerald-50 border border-emerald-200 p-4">
                <p className="font-medium text-emerald-700">
                  Scheduled for{" "}
                  {caseData.scheduled_date
                    ? new Date(
                        caseData.scheduled_date + "T12:00:00"
                      ).toLocaleDateString()
                    : "—"}
                </p>
                {caseData.assigned_driver_name && (
                  <p className="text-sm text-emerald-600 mt-1">
                    <Truck className="inline mr-1 h-3.5 w-3.5" />
                    Driver: {caseData.assigned_driver_name}
                  </p>
                )}
                {caseData.assigned_crew.length > 0 && (
                  <p className="text-sm text-emerald-600 mt-1">
                    Crew: {caseData.assigned_crew.join(", ")}
                  </p>
                )}
              </div>
              <Button onClick={handleComplete} disabled={completing}>
                {completing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                )}
                Mark Complete
              </Button>
            </>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label>Scheduled Date</Label>
                  <Input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                  />
                </div>
                <div>
                  <Label>Driver ID (optional)</Label>
                  <Input
                    value={driverId}
                    onChange={(e) => setDriverId(e.target.value)}
                    placeholder="Driver user ID"
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label>Crew (comma-separated IDs, optional)</Label>
                  <Input
                    value={crew}
                    onChange={(e) => setCrew(e.target.value)}
                    placeholder="user-id-1, user-id-2"
                  />
                </div>
              </div>
              <Button onClick={handleSchedule} disabled={scheduling || !date}>
                {scheduling ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Calendar className="mr-2 h-4 w-4" />
                )}
                Schedule Disinterment
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {/* Cemetery Location Modal */}
      {caseData.cemetery_id && caseData.cemetery_name && (
        <CemeteryLocationModal
          open={cemLoc.modalOpen}
          cemeteryId={caseData.cemetery_id}
          cemeteryName={caseData.cemetery_name}
          onConfirm={(locationId) => {
            cemLoc.onConfirm(locationId);
            // Re-try scheduling after location set
            handleSchedule();
          }}
          onDismiss={cemLoc.closeModal}
        />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Stage 5: Complete                                                   */
/* ------------------------------------------------------------------ */

function CompleteStage({ caseData }: { caseData: CaseDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          Completed
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md bg-green-50 border border-green-200 p-4 space-y-2">
          <p className="font-medium text-green-700">
            Disinterment completed{" "}
            {caseData.completed_at
              ? new Date(caseData.completed_at).toLocaleString()
              : ""}
          </p>
          {caseData.invoice_id && (
            <p className="text-sm text-green-600 flex items-center gap-1">
              <FileText className="h-3.5 w-3.5" />
              Invoice generated —{" "}
              <a
                href={`/ar/invoices/${caseData.invoice_id}`}
                className="underline hover:text-green-800"
              >
                View Invoice
                <ExternalLink className="inline ml-1 h-3 w-3" />
              </a>
            </p>
          )}
          {caseData.scheduled_date && (
            <p className="text-sm text-green-600">
              Performed on{" "}
              {new Date(
                caseData.scheduled_date + "T12:00:00"
              ).toLocaleDateString()}
            </p>
          )}
          {caseData.assigned_driver_name && (
            <p className="text-sm text-green-600">
              Driver: {caseData.assigned_driver_name}
            </p>
          )}
          {caseData.has_hazard_pay && (
            <Badge className="bg-amber-100 text-amber-700 border-amber-300">
              <AlertTriangle className="mr-1 h-3 w-3" /> Hazard Pay Applied
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Case Summary Sidebar                                                */
/* ------------------------------------------------------------------ */

function CaseSummary({ caseData }: { caseData: CaseDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Case Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <InfoRow label="Case #" value={caseData.case_number} />
        <InfoRow label="Decedent" value={caseData.decedent_name} />
        <InfoRow
          label="Cemetery"
          value={caseData.cemetery_name}
          icon={<MapPin className="h-3.5 w-3.5" />}
        />
        {caseData.fulfilling_location_name && (
          <InfoRow label="Location" value={caseData.fulfilling_location_name} />
        )}
        <InfoRow
          label="Funeral Home"
          value={caseData.funeral_home_name}
          icon={<User className="h-3.5 w-3.5" />}
        />
        {caseData.accepted_quote_amount != null && (
          <InfoRow
            label="Quote"
            value={`$${Number(caseData.accepted_quote_amount).toFixed(2)}`}
            icon={<DollarSign className="h-3.5 w-3.5" />}
          />
        )}
        {caseData.scheduled_date && (
          <InfoRow
            label="Scheduled"
            value={new Date(
              caseData.scheduled_date + "T12:00:00"
            ).toLocaleDateString()}
            icon={<Calendar className="h-3.5 w-3.5" />}
          />
        )}
        <InfoRow
          label="Created"
          value={
            caseData.created_at
              ? new Date(caseData.created_at).toLocaleDateString()
              : null
          }
          icon={<Clock className="h-3.5 w-3.5" />}
        />
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Next of Kin Card                                                    */
/* ------------------------------------------------------------------ */

function NextOfKinCard({
  nok,
}: {
  nok: Array<{
    name: string;
    email: string;
    phone?: string;
    relationship: string;
  }>;
}) {
  if (!nok || nok.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Next of Kin</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {nok.map((k, i) => (
          <div key={i} className="rounded-md border p-3 space-y-1 text-sm">
            <p className="font-medium">{k.name}</p>
            <p className="text-muted-foreground">{k.relationship}</p>
            <p className="text-muted-foreground">{k.email}</p>
            {k.phone && (
              <p className="text-muted-foreground">{k.phone}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Cancel Button                                                       */
/* ------------------------------------------------------------------ */

function CancelButton({
  caseId,
  onDone,
}: {
  caseId: string;
  onDone: () => void;
}) {
  const [cancelling, setCancelling] = useState(false);

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel this case?")) return;
    setCancelling(true);
    try {
      await apiClient.post(`/disinterments/${caseId}/cancel`);
      toast.success("Case cancelled");
      onDone();
    } catch {
      toast.error("Failed to cancel");
    } finally {
      setCancelling(false);
    }
  };

  return (
    <Button
      variant="outline"
      size="sm"
      className="text-destructive border-destructive/30 hover:bg-destructive/5"
      onClick={handleCancel}
      disabled={cancelling}
    >
      <XCircle className="mr-2 h-4 w-4" />
      {cancelling ? "Cancelling..." : "Cancel Case"}
    </Button>
  );
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function InfoRow({
  label,
  value,
  icon,
  span2,
}: {
  label: string;
  value: string | null | undefined;
  icon?: React.ReactNode;
  span2?: boolean;
}) {
  return (
    <div className={span2 ? "sm:col-span-2" : ""}>
      <p className="text-xs text-muted-foreground flex items-center gap-1">
        {icon}
        {label}
      </p>
      <p className="font-medium">{value || "—"}</p>
    </div>
  );
}
