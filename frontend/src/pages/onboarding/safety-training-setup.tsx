import { useState, useEffect } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  Upload,
  Check,
  ClipboardList,
  Loader2,
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { completeChecklistItem } from "@/services/onboarding-service";

// ── Types ──

interface FacilityDetails {
  company_name: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  assembly_point: string;
  severe_weather_shelter: string;
  evacuation_map_locations: string;
  fire_wardens: string[];
  loto_device_location: string;
  sds_locations: string[];
  ppe_replacement_location: string;
  electrical_panel_locations: string[];
  earplug_dispenser_location: string;
  first_aid_kit_locations: string[];
  first_aid_trained_employees: string[];
  ladder_storage_location: string;
  confined_spaces: string[];
  confined_space_permit_issuer: string;
  crane_rated_capacity: string;
  pedestrian_walkway_description: string;
  // N/A flags
  overhead_crane_not_applicable: boolean;
  confined_spaces_not_applicable: boolean;
  forklift_not_applicable: boolean;
  electrical_panels_not_applicable: boolean;
  [key: string]: string | string[] | boolean;
}

const EMPTY_DETAILS: FacilityDetails = {
  company_name: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  assembly_point: "",
  severe_weather_shelter: "",
  evacuation_map_locations: "",
  fire_wardens: [""],
  loto_device_location: "",
  sds_locations: [""],
  ppe_replacement_location: "",
  electrical_panel_locations: [""],
  earplug_dispenser_location: "",
  first_aid_kit_locations: [""],
  first_aid_trained_employees: [""],
  ladder_storage_location: "",
  confined_spaces: [""],
  confined_space_permit_issuer: "",
  crane_rated_capacity: "",
  pedestrian_walkway_description: "",
  overhead_crane_not_applicable: false,
  confined_spaces_not_applicable: false,
  forklift_not_applicable: false,
  electrical_panels_not_applicable: false,
};

const SINGLE_FIELDS = [
  "company_name", "emergency_contact_name", "emergency_contact_phone",
  "assembly_point", "severe_weather_shelter", "evacuation_map_locations",
  "loto_device_location", "ppe_replacement_location",
  "earplug_dispenser_location", "ladder_storage_location",
  "confined_space_permit_issuer", "crane_rated_capacity",
  "pedestrian_walkway_description",
] as const;

const MULTI_FIELDS = [
  "fire_wardens", "sds_locations", "electrical_panel_locations",
  "first_aid_kit_locations", "first_aid_trained_employees", "confined_spaces",
] as const;

// Map of N/A flags to the fields they resolve
const NA_RESOLVES: Record<string, string[]> = {
  overhead_crane_not_applicable: ["crane_rated_capacity"],
  confined_spaces_not_applicable: ["confined_spaces", "confined_space_permit_issuer"],
  forklift_not_applicable: ["pedestrian_walkway_description"],
  electrical_panels_not_applicable: ["electrical_panel_locations"],
};

function countFilled(d: FacilityDetails): number {
  // Collect fields resolved by N/A flags
  const resolvedByNA = new Set<string>();
  for (const [flag, fields] of Object.entries(NA_RESOLVES)) {
    if (d[flag]) {
      for (const f of fields) resolvedByNA.add(f);
    }
  }

  let count = 0;
  for (const k of SINGLE_FIELDS) {
    if (resolvedByNA.has(k)) { count++; continue; }
    const v = d[k];
    if (typeof v === "string" && v.trim()) count++;
  }
  for (const k of MULTI_FIELDS) {
    if (resolvedByNA.has(k)) { count++; continue; }
    const v = d[k];
    if (Array.isArray(v) && v.some((s: string) => s.trim())) count++;
  }
  return count;
}

const TOTAL_FIELDS = SINGLE_FIELDS.length + MULTI_FIELDS.length; // 19

// ── Component ──

export default function SafetyTrainingSetupPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const isOnboarding = location.pathname.startsWith("/onboarding");

  const [stage, setStage] = useState<1 | "2a" | "2b" | "2.5" | 3>(1);
  const [details, setDetails] = useState<FacilityDetails>({ ...EMPTY_DETAILS });
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState<string[]>([]);
  const [skipped, setSkipped] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // Preview state (Stage 2.5)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [fieldsFilled, setFieldsFilled] = useState<string[]>([]);
  const [fieldsPlaceholder, setFieldsPlaceholder] = useState<string[]>([]);

  // Load existing facility details
  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get("/safety/training/facility-details");
        if (res.data.facility_details && Object.keys(res.data.facility_details).length > 0) {
          setDetails((prev) => ({ ...prev, ...res.data.facility_details }));
        }
        // If already set up, go to stage 3 summary
        if (res.data.setup_complete) {
          setStage(3);
        }
      } catch {
        // Use defaults
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Multi-value field helpers
  const addMultiValue = (field: keyof FacilityDetails) => {
    setDetails((prev) => ({
      ...prev,
      [field]: [...(prev[field] as string[]), ""],
    }));
  };

  const updateMultiValue = (field: keyof FacilityDetails, index: number, value: string) => {
    setDetails((prev) => {
      const arr = [...(prev[field] as string[])];
      arr[index] = value;
      return { ...prev, [field]: arr };
    });
  };

  const removeMultiValue = (field: keyof FacilityDetails, index: number) => {
    setDetails((prev) => {
      const arr = [...(prev[field] as string[])];
      if (arr.length > 1) arr.splice(index, 1);
      return { ...prev, [field]: arr };
    });
  };

  // Save facility details
  const saveDetails = async () => {
    try {
      await apiClient.put("/safety/training/facility-details", {
        facility_details: details,
      });
    } catch {
      toast.error("Failed to save facility details");
    }
  };

  // Generate personalized PDFs
  const handleGenerate = async () => {
    setGenerating(true);
    setGenerated([]);
    setSkipped([]);
    try {
      await saveDetails();
      const res = await apiClient.post("/safety/training/generate-personalized-pdfs");
      setGenerated(res.data.generated || []);
      setSkipped(res.data.skipped || []);
      setStage(3);
    } catch {
      toast.error("Failed to generate documents");
    } finally {
      setGenerating(false);
    }
  };

  // Complete setup
  const handleComplete = async () => {
    setSaving(true);
    try {
      await apiClient.post("/safety/training/complete-setup");
      if (isOnboarding) {
        await completeChecklistItem("setup_safety_training").catch(() => {});
        navigate("/onboarding");
      } else {
        toast.success("Safety training setup complete");
      }
    } catch {
      toast.error("Failed to complete setup");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  const filled = countFilled(details);
  const pct = Math.round((filled / TOTAL_FIELDS) * 100);

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      {/* Header */}
      <div>
        {isOnboarding && (
          <Link
            to="/onboarding"
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
          >
            <ArrowLeft className="h-4 w-4" /> Back to onboarding
          </Link>
        )}
        <h1 className="text-xl font-bold text-gray-900">
          Safety Training Program
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Choose your training documents and personalize them with your facility
          details.
        </p>
      </div>

      {/* ═══ STAGE 1 — CHOOSE APPROACH ═══ */}
      {stage === 1 && (
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-gray-900">
            How would you like to set up your safety training program?
          </h2>

          <Card
            className="cursor-pointer hover:ring-2 hover:ring-blue-200 transition-all"
            onClick={() => setStage("2a")}
          >
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <ClipboardList className="h-8 w-8 text-blue-600 shrink-0 mt-1" />
                <div>
                  <h3 className="text-base font-semibold text-gray-900">
                    Use the built-in training templates
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    12 OSHA-compliant training documents, one for each month.
                    We'll personalize them with your facility details —
                    locations, contacts, and equipment specifics.
                  </p>
                  <p className="text-xs text-gray-400 mt-2">
                    Best for getting started quickly · ~10 minutes
                  </p>
                  <Button size="sm" className="mt-3 gap-1">
                    Use built-in templates <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:ring-2 hover:ring-blue-200 transition-all"
            onClick={() => setStage("2b")}
          >
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <Upload className="h-8 w-8 text-green-600 shrink-0 mt-1" />
                <div>
                  <h3 className="text-base font-semibold text-gray-900">
                    Upload your own training documents
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    You have existing safety programs. Upload them and we'll use
                    your documents for each monthly training topic.
                  </p>
                  <p className="text-xs text-gray-400 mt-2">
                    Best for companies with established safety programs · ~5
                    minutes
                  </p>
                  <Button size="sm" variant="outline" className="mt-3 gap-1">
                    Upload my documents <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <p className="text-sm text-gray-400 text-center">
            Or{" "}
            <Link
              to="/settings/safety/training-documents"
              className="text-blue-600 hover:underline"
            >
              set up individually
            </Link>{" "}
            — mix and match templates and your own documents.
          </p>
        </div>
      )}

      {/* ═══ STAGE 2a — FACILITY DETAILS FORM ═══ */}
      {stage === "2a" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">
                Tell us about your facility
              </h2>
              <p className="text-sm text-gray-500">
                We'll use this to personalize all 12 training documents.
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-gray-700">
                {filled} of {TOTAL_FIELDS} filled
              </p>
              <div className="w-32 h-1.5 bg-gray-200 rounded-full mt-1">
                <div
                  className="h-full bg-green-500 rounded-full transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          </div>

          {/* Section 1 — Shared info */}
          <Card>
            <CardContent className="p-5 space-y-4">
              <h3 className="text-sm font-semibold text-gray-800">
                Shared Information
              </h3>
              <p className="text-xs text-gray-400">
                Used in multiple training documents — you're entering it once.
              </p>

              <FieldRow label="Company name" value={details.company_name} onChange={(v) => setDetails((d) => ({ ...d, company_name: v }))} placeholder="Sunnycrest Precast" />
              <FieldRow label="Emergency contact name" value={details.emergency_contact_name} onChange={(v) => setDetails((d) => ({ ...d, emergency_contact_name: v }))} placeholder="Dave Martinez" />
              <FieldRow label="Emergency contact phone" value={details.emergency_contact_phone} onChange={(v) => setDetails((d) => ({ ...d, emergency_contact_phone: v }))} placeholder="(315) 555-0142" />
              <FieldRow label="Emergency assembly point" value={details.assembly_point} onChange={(v) => setDetails((d) => ({ ...d, assembly_point: v }))} placeholder="North parking lot near the main gate" />
              <FieldRow label="Severe weather shelter" value={details.severe_weather_shelter} onChange={(v) => setDetails((d) => ({ ...d, severe_weather_shelter: v }))} placeholder="Interior break room, northwest corner" />
              <FieldRow label="Evacuation route maps posted at" value={details.evacuation_map_locations} onChange={(v) => setDetails((d) => ({ ...d, evacuation_map_locations: v }))} placeholder="Main entrance, break room, production floor" />

              <MultiFieldRow label="Fire wardens" values={details.fire_wardens} onChange={(i, v) => updateMultiValue("fire_wardens", i, v)} onAdd={() => addMultiValue("fire_wardens")} onRemove={(i) => removeMultiValue("fire_wardens", i)} placeholder="Dave Martinez" />
            </CardContent>
          </Card>

          {/* Section 2 — Document-specific */}
          <Card>
            <CardContent className="p-5 space-y-4">
              <h3 className="text-sm font-semibold text-gray-800">
                Document-Specific Details
              </h3>

              <FieldRow label="Lockout devices and locks stored" hint="Jan · LOTO" value={details.loto_device_location} onChange={(v) => setDetails((d) => ({ ...d, loto_device_location: v }))} placeholder="Red cabinet near batch plant control panel" />

              <MultiFieldRow label="SDS binder/station locations" hint="Mar · HazCom" values={details.sds_locations} onChange={(i, v) => updateMultiValue("sds_locations", i, v)} onAdd={() => addMultiValue("sds_locations")} onRemove={(i) => removeMultiValue("sds_locations", i)} placeholder="Break room, left of the sink" />

              <FieldRow label="PPE replacement location" hint="Apr · PPE" value={details.ppe_replacement_location} onChange={(v) => setDetails((d) => ({ ...d, ppe_replacement_location: v }))} placeholder="Supply cabinet in the shop" />

              {/* Electrical panels — N/A capable */}
              <NaFieldGroup
                label="Electrical panel locations"
                hint="May · Electrical"
                applicable={!details.electrical_panels_not_applicable}
                onToggle={(applicable) => setDetails((d) => ({ ...d, electrical_panels_not_applicable: !applicable }))}
                applicableLabel="Our employees work near electrical panels"
                naLabel="All electrical work handled by outside contractors"
                naDescription="The May training will focus on hazard awareness and reporting rather than panel locations."
              >
                <MultiFieldRow label="" values={details.electrical_panel_locations} onChange={(i, v) => updateMultiValue("electrical_panel_locations", i, v)} onAdd={() => addMultiValue("electrical_panel_locations")} onRemove={(i) => removeMultiValue("electrical_panel_locations", i)} placeholder="East wall of production building" />
              </NaFieldGroup>

              <FieldRow label="Earplug dispenser location" hint="Jun · Hearing" value={details.earplug_dispenser_location} onChange={(v) => setDetails((d) => ({ ...d, earplug_dispenser_location: v }))} placeholder="Near production floor entrance" />

              <MultiFieldRow label="First aid kit locations" hint="Sep · First Aid" values={details.first_aid_kit_locations} onChange={(i, v) => updateMultiValue("first_aid_kit_locations", i, v)} onAdd={() => addMultiValue("first_aid_kit_locations")} onRemove={(i) => removeMultiValue("first_aid_kit_locations", i)} placeholder="Break room" />

              <MultiFieldRow label="CPR/first aid trained employees" hint="Sep · First Aid" values={details.first_aid_trained_employees} onChange={(i, v) => updateMultiValue("first_aid_trained_employees", i, v)} onAdd={() => addMultiValue("first_aid_trained_employees")} onRemove={(i) => removeMultiValue("first_aid_trained_employees", i)} placeholder="Dave Martinez (certified March 2026)" />

              {/* Overhead crane — N/A capable */}
              <NaFieldGroup
                label="Overhead crane rated capacity"
                hint="Aug · Crane"
                applicable={!details.overhead_crane_not_applicable}
                onToggle={(applicable) => setDetails((d) => ({ ...d, overhead_crane_not_applicable: !applicable }))}
                applicableLabel="We operate an overhead crane"
                naLabel="We do not operate an overhead crane"
                naDescription="The August training will note that crane operations are not performed at this facility."
              >
                <FieldRow label="" value={details.crane_rated_capacity} onChange={(v) => setDetails((d) => ({ ...d, crane_rated_capacity: v }))} placeholder="10" suffix="tons" />
              </NaFieldGroup>

              {/* Forklift / pedestrian walkways — N/A capable (paired) */}
              <NaFieldGroup
                label="Forklift operations"
                hint="Feb · Forklift"
                applicable={!details.forklift_not_applicable}
                onToggle={(applicable) => setDetails((d) => ({ ...d, forklift_not_applicable: !applicable }))}
                applicableLabel="We operate forklifts or powered industrial trucks"
                naLabel="We do not operate forklifts or powered industrial trucks"
                naDescription="The February training will be scoped to general material handling safety instead."
              >
                <FieldRow label="Pedestrian walkways" value={details.pedestrian_walkway_description} onChange={(v) => setDetails((d) => ({ ...d, pedestrian_walkway_description: v }))} placeholder="Yellow striped walkways along east and west walls" />
              </NaFieldGroup>

              <FieldRow label="Ladder storage location" hint="Oct · Fall Protection" value={details.ladder_storage_location} onChange={(v) => setDetails((d) => ({ ...d, ladder_storage_location: v }))} placeholder="Storage room adjacent to loading dock" />

              {/* Confined spaces — N/A capable (paired with permit issuer) */}
              <NaFieldGroup
                label="Confined spaces"
                hint="Nov · Confined Space"
                applicable={!details.confined_spaces_not_applicable}
                onToggle={(applicable) => setDetails((d) => ({ ...d, confined_spaces_not_applicable: !applicable }))}
                applicableLabel="We have confined spaces"
                naLabel="We do not have permit-required confined spaces"
                naDescription="The November training will cover awareness for work performed at other sites."
              >
                <MultiFieldRow label="Confined spaces in facility" values={details.confined_spaces} onChange={(i, v) => updateMultiValue("confined_spaces", i, v)} onAdd={() => addMultiValue("confined_spaces")} onRemove={(i) => removeMultiValue("confined_spaces", i)} placeholder="Septic tanks, product forms during curing" />
                <FieldRow label="Who issues entry permits?" value={details.confined_space_permit_issuer} onChange={(v) => setDetails((d) => ({ ...d, confined_space_permit_issuer: v }))} placeholder="Dave Martinez (safety manager)" />
              </NaFieldGroup>
            </CardContent>
          </Card>

          {/* Footer */}
          <div className="flex items-center justify-between pt-2">
            <Button variant="ghost" onClick={() => setStage(1)} className="gap-1">
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            <Button
              onClick={async () => {
                await saveDetails();
                setStage("2.5");
              }}
              className="gap-1"
            >
              Preview a document first <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* ═══ STAGE 2b — UPLOAD OWN DOCUMENTS ═══ */}
      {stage === "2b" && (
        <div className="space-y-6">
          <div>
            <h2 className="text-base font-semibold text-gray-900">
              Upload your safety training documents
            </h2>
            <p className="text-sm text-gray-500">
              Upload a PDF for each monthly training topic. Topics without an upload
              will use the platform template.
            </p>
          </div>

          <Card>
            <CardContent className="p-4 text-center text-sm text-gray-500">
              <p>
                Use the{" "}
                <Link to="/settings/safety/training-documents" className="text-blue-600 hover:underline">
                  Training Documents
                </Link>{" "}
                page to upload your documents for each topic. Then return here to complete setup.
              </p>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between pt-2">
            <Button variant="ghost" onClick={() => setStage(1)} className="gap-1">
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            <Button onClick={() => setStage(3)} className="gap-1">
              Continue <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* ═══ STAGE 2.5 — PREVIEW SINGLE PDF ═══ */}
      {stage === "2.5" && (
        <div className="space-y-6">
          <div>
            <h2 className="text-base font-semibold text-gray-900">
              Preview Your Training Document
            </h2>
            <p className="text-sm text-gray-500">
              We'll generate a preview of your January training (Lockout/Tagout)
              so you can verify your facility details are filling in correctly.
            </p>
            <p className="text-xs text-gray-400 mt-1">
              LOTO uses the most facility-specific details — if it looks right,
              the others will too.
            </p>
          </div>

          {!previewUrl && !previewLoading && (
            <Card>
              <CardContent className="p-8 text-center">
                <FileText className="mx-auto h-10 w-10 text-gray-300 mb-3" />
                <Button
                  onClick={async () => {
                    setPreviewLoading(true);
                    try {
                      const res = await apiClient.post("/safety/training/preview");
                      setPreviewUrl(res.data.pdf_url);
                      setFieldsFilled(res.data.fields_filled || []);
                      setFieldsPlaceholder(res.data.fields_placeholder || []);
                    } catch {
                      toast.error("Failed to generate preview");
                    } finally {
                      setPreviewLoading(false);
                    }
                  }}
                  className="gap-1"
                >
                  Generate preview <ArrowRight className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          )}

          {previewLoading && (
            <Card>
              <CardContent className="p-8 text-center">
                <Loader2 className="mx-auto h-8 w-8 animate-spin text-gray-400 mb-2" />
                <p className="text-sm text-gray-500">Generating preview...</p>
              </CardContent>
            </Card>
          )}

          {previewUrl && (
            <>
              <Card>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Preview — January: Lockout/Tagout
                    </h3>
                    <a
                      href={previewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                    >
                      Open full PDF in new tab
                    </a>
                  </div>

                  {/* Field completion status */}
                  <div className="space-y-1.5 mt-4">
                    <p className="text-xs font-medium text-gray-500 mb-2">
                      Fields in this document:
                    </p>
                    {fieldsFilled.map((f) => (
                      <div key={f} className="flex items-center gap-2 text-xs">
                        <Check className="h-3.5 w-3.5 text-green-600" />
                        <span className="text-gray-700">{f}</span>
                      </div>
                    ))}
                    {fieldsPlaceholder.map((f) => (
                      <div key={f} className="flex items-center gap-2 text-xs">
                        <span className="h-3.5 w-3.5 text-amber-500 font-bold text-center">⚠</span>
                        <span className="text-amber-700">
                          {f} — still blank (placeholder shown in PDF)
                        </span>
                        <button
                          onClick={() => {
                            setPreviewUrl(null);
                            setStage("2a");
                          }}
                          className="text-blue-600 hover:underline ml-1"
                        >
                          Edit →
                        </button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <div className="flex items-center justify-between pt-2">
                <Button
                  variant="ghost"
                  onClick={() => {
                    setPreviewUrl(null);
                    setStage("2a");
                  }}
                  className="gap-1"
                >
                  <ArrowLeft className="h-4 w-4" /> Edit facility details
                </Button>
                <Button onClick={handleGenerate} disabled={generating} className="gap-1">
                  {generating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Generating all 12...
                    </>
                  ) : (
                    <>
                      <Check className="h-4 w-4" /> Looks good — generate all 12
                    </>
                  )}
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══ STAGE 3 — REVIEW & COMPLETE ═══ */}
      {stage === 3 && (
        <div className="space-y-6">
          <h2 className="text-base font-semibold text-gray-900">
            Your training documents are ready
          </h2>

          {generated.length > 0 && (
            <Card>
              <CardContent className="p-5">
                <div className="space-y-2">
                  {generated.map((title) => (
                    <div key={title} className="flex items-center gap-2 text-sm">
                      <Check className="h-4 w-4 text-green-600 shrink-0" />
                      <span className="text-gray-700">{title}</span>
                      <span className="text-xs text-gray-400">Personalized</span>
                    </div>
                  ))}
                  {skipped.map((title) => (
                    <div key={title} className="flex items-center gap-2 text-sm">
                      <FileText className="h-4 w-4 text-blue-500 shrink-0" />
                      <span className="text-gray-700">{title}</span>
                      <span className="text-xs text-gray-400">Your document</span>
                    </div>
                  ))}
                </div>
                <p className="text-sm text-gray-500 mt-4">
                  {generated.length + skipped.length} of 12 documents ready
                </p>
              </CardContent>
            </Card>
          )}

          {generated.length === 0 && skipped.length === 0 && (
            <Card>
              <CardContent className="p-5 text-center">
                <Check className="mx-auto h-8 w-8 text-green-600 mb-2" />
                <p className="text-sm text-gray-700">
                  Your safety training program is configured. Training documents
                  are ready for your monthly schedule.
                </p>
              </CardContent>
            </Card>
          )}

          {filled < TOTAL_FIELDS && generated.length > 0 && (
            <p className="text-sm text-amber-600">
              {TOTAL_FIELDS - filled} facility details still have placeholders.{" "}
              <button
                onClick={() => setStage("2a")}
                className="text-blue-600 hover:underline"
              >
                Complete facility details →
              </button>
            </p>
          )}

          <div className="flex items-center justify-between pt-2">
            <Button
              variant="ghost"
              onClick={() => setStage("2a")}
              className="gap-1"
            >
              <ArrowLeft className="h-4 w-4" /> Edit details
            </Button>
            <Button onClick={handleComplete} disabled={saving} className="gap-1">
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Saving...
                </>
              ) : isOnboarding ? (
                <>
                  Finish setup <ArrowRight className="h-4 w-4" />
                </>
              ) : (
                "Save changes"
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Reusable field components ──

function NaFieldGroup({
  label,
  hint,
  applicable,
  onToggle,
  applicableLabel,
  naLabel,
  naDescription,
  children,
}: {
  label: string;
  hint?: string;
  applicable: boolean;
  onToggle: (applicable: boolean) => void;
  applicableLabel: string;
  naLabel: string;
  naDescription: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-md border p-3 ${!applicable ? "border-amber-200 bg-amber-50/30" : "border-gray-200"}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        {hint && <span className="text-xs text-gray-400">{hint}</span>}
      </div>
      <div className="space-y-1.5 mb-2">
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input type="radio" name={`na-${label}`} checked={applicable} onChange={() => onToggle(true)} className="h-4 w-4" />
          {applicableLabel}
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input type="radio" name={`na-${label}`} checked={!applicable} onChange={() => onToggle(false)} className="h-4 w-4" />
          {naLabel}
        </label>
      </div>
      {applicable ? (
        <div className="ml-6">{children}</div>
      ) : (
        <p className="ml-6 text-xs text-amber-700 italic">{naDescription}</p>
      )}
    </div>
  );
}

function FieldRow({
  label,
  hint,
  value,
  onChange,
  placeholder,
  suffix,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  suffix?: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        {hint && <span className="text-xs text-gray-400">{hint}</span>}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        {suffix && <span className="text-sm text-gray-500 shrink-0">{suffix}</span>}
      </div>
    </div>
  );
}

function MultiFieldRow({
  label,
  hint,
  values,
  onChange,
  onAdd,
  onRemove,
  placeholder,
}: {
  label: string;
  hint?: string;
  values: string[];
  onChange: (index: number, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        {hint && <span className="text-xs text-gray-400">{hint}</span>}
      </div>
      <div className="space-y-1.5">
        {values.map((v, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type="text"
              value={v}
              onChange={(e) => onChange(i, e.target.value)}
              placeholder={placeholder}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {values.length > 1 && (
              <button
                type="button"
                onClick={() => onRemove(i)}
                className="text-gray-400 hover:text-red-500 text-sm shrink-0"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="text-xs text-blue-600 hover:underline mt-1"
      >
        + Add another
      </button>
    </div>
  );
}
