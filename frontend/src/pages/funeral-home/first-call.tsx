import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { funeralHomeService } from "@/services/funeral-home-service";
import * as firstCallService from "@/services/first-call-service";
import type { FirstCallFormValues } from "@/types/first-call";
import type { FHDirector } from "@/types/funeral-home";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const REQUIRED_FIELDS = [
  "deceased_first_name",
  "contact_first_name",
  "contact_phone_primary",
] as const;

const REQUIRED_LABELS: Record<string, string> = {
  deceased_first_name: "Deceased first name",
  contact_first_name: "Contact first name",
  contact_phone_primary: "Contact phone",
};

const PLACE_OF_DEATH_OPTIONS = [
  { value: "", label: "Select..." },
  { value: "hospital", label: "Hospital" },
  { value: "home", label: "Home" },
  { value: "nursing_facility", label: "Nursing Facility" },
  { value: "hospice", label: "Hospice" },
  { value: "other", label: "Other" },
];

const DISPOSITION_OPTIONS = [
  { value: "", label: "Select..." },
  { value: "burial", label: "Burial" },
  { value: "cremation", label: "Cremation" },
  { value: "green_burial", label: "Green Burial" },
  { value: "donation", label: "Donation" },
  { value: "entombment", label: "Entombment" },
];

const SERVICE_TYPE_OPTIONS = [
  { value: "", label: "Select..." },
  { value: "traditional_funeral", label: "Traditional Funeral" },
  { value: "graveside_only", label: "Graveside Only" },
  { value: "memorial_service", label: "Memorial Service" },
  { value: "direct_burial", label: "Direct Burial" },
  { value: "direct_cremation", label: "Direct Cremation" },
  { value: "celebration_of_life", label: "Celebration of Life" },
  { value: "no_service", label: "No Service" },
];

const RELATIONSHIP_OPTIONS = [
  { value: "", label: "Select..." },
  { value: "spouse", label: "Spouse" },
  { value: "child", label: "Child" },
  { value: "parent", label: "Parent" },
  { value: "sibling", label: "Sibling" },
  { value: "other", label: "Other" },
];

const GENDER_OPTIONS = [
  { value: "", label: "Select..." },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "non_binary", label: "Non-Binary" },
];

const INITIAL_VALUES: FirstCallFormValues = {
  deceased_first_name: "",
  deceased_last_name: "",
  deceased_date_of_death: "",
  deceased_time_of_death: "",
  deceased_place_of_death: "",
  deceased_place_of_death_name: "",
  deceased_place_of_death_city: "",
  deceased_place_of_death_state: "",
  deceased_age_at_death: "",
  deceased_date_of_birth: "",
  deceased_gender: "",
  deceased_veteran: false,
  contact_first_name: "",
  contact_last_name: "",
  contact_relationship: "",
  contact_phone_primary: "",
  contact_phone_secondary: "",
  contact_email: "",
  send_portal: true,
  disposition_type: "",
  service_type: "",
  disposition_location: "",
  estimated_service_date: "",
  assigned_director_id: "",
  referral_source: "",
  notes: "",
};

const DRAFT_KEY = "first-call-draft";

const PLACEHOLDER_EXAMPLES = [
  "Got a call from Mary Johnson — her husband Robert passed at St. Mary's Hospital around 3 PM today. She'd like a traditional funeral with burial at Greenwood Cemetery. Her number is 555-0142.",
  "Daughter Susan Miller called about her father Thomas Miller, age 82, died at home this morning. They want cremation. Susan's phone 555-0198, she's the daughter.",
  "This is for James Wilson, passed away at Sunrise Nursing Facility. Wife Carol is the contact, 555-0167. They're thinking memorial service, maybe next Thursday. He was a veteran.",
];

type ExtractionStatus = "idle" | "processing" | "complete" | "error";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function sectionCompletionStatus(
  fields: (keyof FirstCallFormValues)[],
  values: FirstCallFormValues,
): "empty" | "partial" | "complete" {
  let filled = 0;
  for (const f of fields) {
    const v = values[f];
    if (typeof v === "boolean" || (typeof v === "string" && v.trim())) filled++;
  }
  if (filled === 0) return "empty";
  if (filled === fields.length) return "complete";
  return "partial";
}

const DECEASED_FIELDS: (keyof FirstCallFormValues)[] = [
  "deceased_first_name",
  "deceased_last_name",
  "deceased_date_of_death",
  "deceased_date_of_birth",
  "deceased_gender",
  "deceased_place_of_death",
];
const CONTACT_FIELDS: (keyof FirstCallFormValues)[] = [
  "contact_first_name",
  "contact_last_name",
  "contact_phone_primary",
  "contact_relationship",
];
const SERVICE_FIELDS: (keyof FirstCallFormValues)[] = [
  "disposition_type",
  "service_type",
  "disposition_location",
  "estimated_service_date",
];
const ASSIGNMENT_FIELDS: (keyof FirstCallFormValues)[] = [
  "assigned_director_id",
  "referral_source",
  "notes",
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FirstCallPage() {
  const navigate = useNavigate();

  // Form state
  const [values, setValues] = useState<FirstCallFormValues>(INITIAL_VALUES);
  const [directors, setDirectors] = useState<FHDirector[]>([]);
  const [saving, setSaving] = useState(false);
  const [successCaseNumber, setSuccessCaseNumber] = useState<string | null>(
    null,
  );

  // AI extraction state
  const [promptText, setPromptText] = useState("");
  const [extractionStatus, setExtractionStatus] =
    useState<ExtractionStatus>("idle");
  const [fieldsUpdatedCount, setFieldsUpdatedCount] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manuallyEditedFields = useRef(new Set<string>());
  const highlightTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  // Collapsible sections
  const [deceasedOpen, setDeceasedOpen] = useState(true);
  const [contactOpen, setContactOpen] = useState(true);
  const [serviceOpen, setServiceOpen] = useState(false);
  const [assignmentOpen, setAssignmentOpen] = useState(false);

  // Draft restore
  const [savedDraft, setSavedDraft] = useState<{
    values: FirstCallFormValues;
    prompt: string;
    timeAgo: string;
  } | null>(null);

  // Placeholder rotation
  const [placeholderIdx, setPlaceholderIdx] = useState(0);

  // Highlighted fields (for animation)
  const [highlightedFields, setHighlightedFields] = useState(
    new Set<string>(),
  );

  // What-to-include helper collapsed
  const [helperOpen, setHelperOpen] = useState(false);

  // ── Load directors ──────────────────────────────────────────
  useEffect(() => {
    funeralHomeService.getDirectors().then(setDirectors).catch(() => {});
  }, []);

  // ── Placeholder rotation ────────────────────────────────────
  useEffect(() => {
    if (promptText) return;
    const id = setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % PLACEHOLDER_EXAMPLES.length);
    }, 8000);
    return () => clearInterval(id);
  }, [promptText]);

  // ── Check for saved draft on mount ──────────────────────────
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        values: FirstCallFormValues;
        prompt: string;
        savedAt: number;
      };
      // Only show if less than 24h old
      if (Date.now() - parsed.savedAt > 86400000) {
        localStorage.removeItem(DRAFT_KEY);
        return;
      }
      // Only show if there's meaningful data
      const hasData =
        parsed.values.deceased_first_name ||
        parsed.values.contact_first_name ||
        parsed.prompt;
      if (hasData) {
        setSavedDraft({
          values: parsed.values,
          prompt: parsed.prompt,
          timeAgo: timeAgo(parsed.savedAt),
        });
      }
    } catch {
      localStorage.removeItem(DRAFT_KEY);
    }
  }, []);

  // ── Auto-save draft on change ───────────────────────────────
  useEffect(() => {
    const hasData =
      values.deceased_first_name ||
      values.contact_first_name ||
      promptText;
    if (!hasData) return;
    const id = setTimeout(() => {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({ values, prompt: promptText, savedAt: Date.now() }),
      );
    }, 2000);
    return () => clearTimeout(id);
  }, [values, promptText]);

  // ── Cleanup highlight timers on unmount ─────────────────────
  useEffect(() => {
    return () => {
      highlightTimers.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  // ── Draft restore / clear ───────────────────────────────────
  const restoreDraft = useCallback(() => {
    if (!savedDraft) return;
    setValues(savedDraft.values);
    setPromptText(savedDraft.prompt);
    setSavedDraft(null);
  }, [savedDraft]);

  const clearDraft = useCallback(() => {
    localStorage.removeItem(DRAFT_KEY);
    setSavedDraft(null);
  }, []);

  // ── Field update helpers ────────────────────────────────────
  const updateField = useCallback(
    (field: keyof FirstCallFormValues, value: string | boolean) => {
      setValues((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const handleManualChange = useCallback(
    (field: keyof FirstCallFormValues, value: string | boolean) => {
      manuallyEditedFields.current.add(field);
      updateField(field, value);
    },
    [updateField],
  );

  // ── Highlight animation ─────────────────────────────────────
  const highlightField = useCallback((field: string) => {
    setHighlightedFields((prev) => new Set(prev).add(field));
    // Clear existing timer for this field
    const existing = highlightTimers.current.get(field);
    if (existing) clearTimeout(existing);
    const timer = setTimeout(() => {
      setHighlightedFields((prev) => {
        const next = new Set(prev);
        next.delete(field);
        return next;
      });
      highlightTimers.current.delete(field);
    }, 1200);
    highlightTimers.current.set(field, timer);
  }, []);

  // ── AI Extraction ───────────────────────────────────────────
  const runExtraction = useCallback(
    async (text: string) => {
      if (!text.trim() || text.trim().length < 15) return;
      setExtractionStatus("processing");
      try {
        const result = await firstCallService.extractFirstCall(
          text,
          values as unknown as Record<string, unknown>,
        );
        setExtractionStatus("complete");
        setFieldsUpdatedCount(result.fields_updated);

        // Apply extracted values, skipping manually edited fields
        setValues((prev) => {
          const next = { ...prev };
          for (const [field, extracted] of Object.entries(result.extracted)) {
            if (manuallyEditedFields.current.has(field)) continue;
            if (extracted.value == null) continue;
            const key = field as keyof FirstCallFormValues;
            if (key in next) {
              (next as Record<string, unknown>)[key] = extracted.value;
              highlightField(field);
            }
          }
          return next;
        });

        // Auto-open sections that received data
        if (
          result.extracted.deceased_first_name ||
          result.extracted.deceased_last_name
        ) {
          setDeceasedOpen(true);
        }
        if (
          result.extracted.contact_first_name ||
          result.extracted.contact_phone_primary
        ) {
          setContactOpen(true);
        }
        if (
          result.extracted.disposition_type ||
          result.extracted.service_type
        ) {
          setServiceOpen(true);
        }
      } catch {
        setExtractionStatus("error");
      }
    },
    [values, highlightField],
  );

  const handlePromptChange = useCallback(
    (text: string) => {
      setPromptText(text);
      if (extractionStatus === "complete" || extractionStatus === "error") {
        setExtractionStatus("idle");
      }
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        runExtraction(text);
      }, 1000);
    },
    [runExtraction, extractionStatus],
  );

  const handlePromptKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (debounceRef.current) clearTimeout(debounceRef.current);
        runExtraction(promptText);
      }
    },
    [runExtraction, promptText],
  );

  // ── Validation ──────────────────────────────────────────────
  const missingRequired = REQUIRED_FIELDS.filter((f) => {
    const v = values[f];
    return typeof v === "string" ? !v.trim() : !v;
  });
  const isReadyToOpen = missingRequired.length === 0;

  // ── Open Case ───────────────────────────────────────────────
  const handleOpenCase = useCallback(async () => {
    if (!isReadyToOpen) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        deceased_first_name: values.deceased_first_name.trim(),
        deceased_last_name: values.deceased_last_name.trim() || undefined,
        deceased_date_of_death:
          values.deceased_date_of_death || undefined,
        deceased_date_of_birth:
          values.deceased_date_of_birth || undefined,
        deceased_place_of_death:
          values.deceased_place_of_death || undefined,
        deceased_place_of_death_name:
          values.deceased_place_of_death_name.trim() || undefined,
        deceased_place_of_death_city:
          values.deceased_place_of_death_city.trim() || undefined,
        deceased_place_of_death_state:
          values.deceased_place_of_death_state.trim() || undefined,
        deceased_gender: values.deceased_gender || undefined,
        deceased_age_at_death: values.deceased_age_at_death
          ? Number(values.deceased_age_at_death)
          : undefined,
        deceased_veteran: values.deceased_veteran,
        disposition_type: values.disposition_type || undefined,
        service_type: values.service_type || undefined,
        disposition_location:
          values.disposition_location.trim() || undefined,
        referred_by: values.referral_source.trim() || undefined,
        notes: values.notes.trim() || undefined,
        assigned_director_id:
          values.assigned_director_id || undefined,
        primary_contact: {
          first_name: values.contact_first_name.trim(),
          last_name: values.contact_last_name.trim() || undefined,
          phone_primary: values.contact_phone_primary.trim(),
          phone_secondary:
            values.contact_phone_secondary.trim() || undefined,
          relationship_to_deceased:
            values.contact_relationship || undefined,
          email: values.contact_email.trim() || undefined,
        },
      };

      const created = await funeralHomeService.createCase(payload);
      localStorage.removeItem(DRAFT_KEY);
      setSuccessCaseNumber(created.case_number);
      toast.success("Case opened successfully");

      setTimeout(() => {
        navigate(`/cases/${created.id}`);
      }, 2000);
    } catch {
      toast.error("Failed to open case");
    } finally {
      setSaving(false);
    }
  }, [isReadyToOpen, values, navigate]);

  // ── Section completion dots ─────────────────────────────────
  const dotColor = (status: "empty" | "partial" | "complete") => {
    if (status === "complete") return "bg-emerald-500";
    if (status === "partial") return "bg-amber-400";
    return "bg-gray-300";
  };

  // ── Render helpers ──────────────────────────────────────────
  const fieldClass = (field: string) =>
    cn(
      "w-full rounded-md border border-input bg-background px-3 py-2 text-sm transition-colors duration-200",
      "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
      highlightedFields.has(field) && "bg-teal-500/15",
    );

  const selectClass = (field: string) =>
    cn(
      "w-full rounded-md border border-input bg-background px-3 py-2 text-sm transition-colors duration-200",
      "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
      highlightedFields.has(field) && "bg-teal-500/15",
    );

  const checkboxBgClass = (field: string) =>
    cn(
      "rounded-lg border p-3 transition-colors duration-200",
      highlightedFields.has(field) && "bg-teal-500/15",
    );

  // ── Success banner ──────────────────────────────────────────
  if (successCaseNumber) {
    return (
      <div className="mx-auto max-w-7xl p-6">
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100">
            <svg
              className="h-6 w-6 text-emerald-600"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4.5 12.75l6 6 9-13.5"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-emerald-900">
            Case {successCaseNumber} Opened
          </h2>
          <p className="mt-1 text-sm text-emerald-700">
            Redirecting to case detail...
          </p>
        </div>
      </div>
    );
  }

  // ── Main render ─────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-7xl p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">New First Call</h1>
          <p className="text-sm text-muted-foreground">
            Type what you know in the prompt — we'll fill in the form as you go
          </p>
        </div>
        <button
          onClick={handleOpenCase}
          disabled={!isReadyToOpen || saving}
          className={cn(
            "hidden rounded-lg px-6 py-2.5 text-sm font-medium transition-colors lg:inline-flex",
            isReadyToOpen && !saving
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "cursor-not-allowed bg-muted text-muted-foreground",
          )}
        >
          {saving ? "Opening..." : "Open Case"}
        </button>
      </div>

      {/* Draft restore banner */}
      {savedDraft && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 p-3">
          <span className="text-sm text-amber-800">
            You have an unsaved first call from {savedDraft.timeAgo}. Restore
            it?
          </span>
          <div className="flex gap-2">
            <button
              onClick={restoreDraft}
              className="text-sm font-medium text-amber-700 hover:text-amber-900"
            >
              Yes
            </button>
            <button
              onClick={clearDraft}
              className="text-sm text-amber-600 hover:text-amber-800"
            >
              No
            </button>
          </div>
        </div>
      )}

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-[55%_45%]">
        {/* ─── Left: Form ─────────────────────────────────────── */}
        <div className="order-2 space-y-4 lg:order-1">
          {/* Section: Deceased */}
          <SectionCard
            title="Deceased Information"
            status={sectionCompletionStatus(DECEASED_FIELDS, values)}
            dotColor={dotColor}
            open={deceasedOpen}
            onToggle={() => setDeceasedOpen((o) => !o)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  First Name <span className="text-red-500">*</span>
                </label>
                <input
                  className={fieldClass("deceased_first_name")}
                  value={values.deceased_first_name}
                  onChange={(e) =>
                    handleManualChange("deceased_first_name", e.target.value)
                  }
                  placeholder="First name"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Last Name</label>
                <input
                  className={fieldClass("deceased_last_name")}
                  value={values.deceased_last_name}
                  onChange={(e) =>
                    handleManualChange("deceased_last_name", e.target.value)
                  }
                  placeholder="Last name"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Date of Death</label>
                <input
                  type="date"
                  className={fieldClass("deceased_date_of_death")}
                  value={values.deceased_date_of_death}
                  onChange={(e) =>
                    handleManualChange("deceased_date_of_death", e.target.value)
                  }
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Time of Death</label>
                <input
                  type="time"
                  className={fieldClass("deceased_time_of_death")}
                  value={values.deceased_time_of_death}
                  onChange={(e) =>
                    handleManualChange("deceased_time_of_death", e.target.value)
                  }
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Date of Birth</label>
                <input
                  type="date"
                  className={fieldClass("deceased_date_of_birth")}
                  value={values.deceased_date_of_birth}
                  onChange={(e) =>
                    handleManualChange("deceased_date_of_birth", e.target.value)
                  }
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Age at Death</label>
                <input
                  type="number"
                  className={fieldClass("deceased_age_at_death")}
                  value={values.deceased_age_at_death}
                  onChange={(e) =>
                    handleManualChange("deceased_age_at_death", e.target.value)
                  }
                  placeholder="Age"
                  min={0}
                  max={150}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Gender</label>
                <select
                  className={selectClass("deceased_gender")}
                  value={values.deceased_gender}
                  onChange={(e) =>
                    handleManualChange("deceased_gender", e.target.value)
                  }
                >
                  {GENDER_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className={checkboxBgClass("deceased_veteran")}>
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={values.deceased_veteran}
                    onChange={(e) =>
                      handleManualChange("deceased_veteran", e.target.checked)
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span className="text-sm font-medium">Veteran</span>
                </label>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Place of Death</label>
                <select
                  className={selectClass("deceased_place_of_death")}
                  value={values.deceased_place_of_death}
                  onChange={(e) =>
                    handleManualChange(
                      "deceased_place_of_death",
                      e.target.value,
                    )
                  }
                >
                  {PLACE_OF_DEATH_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Facility Name</label>
                <input
                  className={fieldClass("deceased_place_of_death_name")}
                  value={values.deceased_place_of_death_name}
                  onChange={(e) =>
                    handleManualChange(
                      "deceased_place_of_death_name",
                      e.target.value,
                    )
                  }
                  placeholder="Hospital or facility name"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">City</label>
                <input
                  className={fieldClass("deceased_place_of_death_city")}
                  value={values.deceased_place_of_death_city}
                  onChange={(e) =>
                    handleManualChange(
                      "deceased_place_of_death_city",
                      e.target.value,
                    )
                  }
                  placeholder="City"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">State</label>
                <input
                  className={fieldClass("deceased_place_of_death_state")}
                  value={values.deceased_place_of_death_state}
                  onChange={(e) =>
                    handleManualChange(
                      "deceased_place_of_death_state",
                      e.target.value,
                    )
                  }
                  placeholder="State"
                />
              </div>
            </div>
          </SectionCard>

          {/* Section: Primary Contact */}
          <SectionCard
            title="Primary Contact"
            status={sectionCompletionStatus(CONTACT_FIELDS, values)}
            dotColor={dotColor}
            open={contactOpen}
            onToggle={() => setContactOpen((o) => !o)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  First Name <span className="text-red-500">*</span>
                </label>
                <input
                  className={fieldClass("contact_first_name")}
                  value={values.contact_first_name}
                  onChange={(e) =>
                    handleManualChange("contact_first_name", e.target.value)
                  }
                  placeholder="First name"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Last Name</label>
                <input
                  className={fieldClass("contact_last_name")}
                  value={values.contact_last_name}
                  onChange={(e) =>
                    handleManualChange("contact_last_name", e.target.value)
                  }
                  placeholder="Last name"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  Phone <span className="text-red-500">*</span>
                </label>
                <input
                  type="tel"
                  className={fieldClass("contact_phone_primary")}
                  value={values.contact_phone_primary}
                  onChange={(e) =>
                    handleManualChange("contact_phone_primary", e.target.value)
                  }
                  placeholder="(555) 555-5555"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Secondary Phone</label>
                <input
                  type="tel"
                  className={fieldClass("contact_phone_secondary")}
                  value={values.contact_phone_secondary}
                  onChange={(e) =>
                    handleManualChange(
                      "contact_phone_secondary",
                      e.target.value,
                    )
                  }
                  placeholder="(555) 555-5555"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Relationship</label>
                <select
                  className={selectClass("contact_relationship")}
                  value={values.contact_relationship}
                  onChange={(e) =>
                    handleManualChange("contact_relationship", e.target.value)
                  }
                >
                  {RELATIONSHIP_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Email</label>
                <input
                  type="email"
                  className={fieldClass("contact_email")}
                  value={values.contact_email}
                  onChange={(e) =>
                    handleManualChange("contact_email", e.target.value)
                  }
                  placeholder="email@example.com"
                />
              </div>
            </div>

            <div className={checkboxBgClass("send_portal")}>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={values.send_portal}
                  onChange={(e) =>
                    handleManualChange("send_portal", e.target.checked)
                  }
                  className="h-4 w-4 rounded border-gray-300"
                />
                <span className="text-sm font-medium">
                  Send family portal invite
                </span>
              </label>
            </div>
          </SectionCard>

          {/* Section: Service Preferences */}
          <SectionCard
            title="Service Preferences"
            status={sectionCompletionStatus(SERVICE_FIELDS, values)}
            dotColor={dotColor}
            open={serviceOpen}
            onToggle={() => setServiceOpen((o) => !o)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Disposition</label>
                <select
                  className={selectClass("disposition_type")}
                  value={values.disposition_type}
                  onChange={(e) =>
                    handleManualChange("disposition_type", e.target.value)
                  }
                >
                  {DISPOSITION_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Service Type</label>
                <select
                  className={selectClass("service_type")}
                  value={values.service_type}
                  onChange={(e) =>
                    handleManualChange("service_type", e.target.value)
                  }
                >
                  {SERVICE_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  Disposition Location
                </label>
                <input
                  className={fieldClass("disposition_location")}
                  value={values.disposition_location}
                  onChange={(e) =>
                    handleManualChange("disposition_location", e.target.value)
                  }
                  placeholder="Cemetery, crematorium, etc."
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  Estimated Service Date
                </label>
                <input
                  type="date"
                  className={fieldClass("estimated_service_date")}
                  value={values.estimated_service_date}
                  onChange={(e) =>
                    handleManualChange("estimated_service_date", e.target.value)
                  }
                />
              </div>
            </div>
          </SectionCard>

          {/* Section: Assignment */}
          <SectionCard
            title="Assignment"
            status={sectionCompletionStatus(ASSIGNMENT_FIELDS, values)}
            dotColor={dotColor}
            open={assignmentOpen}
            onToggle={() => setAssignmentOpen((o) => !o)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  Assigned Director
                </label>
                <select
                  className={selectClass("assigned_director_id")}
                  value={values.assigned_director_id}
                  onChange={(e) =>
                    handleManualChange("assigned_director_id", e.target.value)
                  }
                >
                  <option value="">Select a director...</option>
                  {directors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.first_name} {d.last_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Referral Source</label>
                <input
                  className={fieldClass("referral_source")}
                  value={values.referral_source}
                  onChange={(e) =>
                    handleManualChange("referral_source", e.target.value)
                  }
                  placeholder="How they heard about us"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">Notes</label>
              <textarea
                className={cn(fieldClass("notes"), "resize-none")}
                value={values.notes}
                onChange={(e) =>
                  handleManualChange("notes", e.target.value)
                }
                rows={3}
                placeholder="Any additional notes from the call..."
              />
            </div>
          </SectionCard>
        </div>

        {/* ─── Right: Prompt ──────────────────────────────────── */}
        <div className="order-1 space-y-4 lg:sticky lg:top-6 lg:order-2 lg:self-start">
          {/* Prompt textarea */}
          <div className="rounded-lg border bg-card p-4 shadow-sm">
            <label className="mb-2 block text-sm font-medium">
              Describe the first call
            </label>
            <textarea
              autoFocus
              value={promptText}
              onChange={(e) => handlePromptChange(e.target.value)}
              onKeyDown={handlePromptKeyDown}
              rows={8}
              className="w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm leading-relaxed placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              placeholder={PLACEHOLDER_EXAMPLES[placeholderIdx]}
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              {navigator.platform.includes("Mac") ? "Cmd" : "Ctrl"}+Enter to
              extract immediately
            </p>

            {/* Extraction status */}
            <div className="mt-3">
              {extractionStatus === "processing" && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <svg
                    className="h-4 w-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Reading your notes...
                </div>
              )}
              {extractionStatus === "complete" && (
                <div className="flex items-center gap-2 text-sm text-emerald-600">
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M4.5 12.75l6 6 9-13.5"
                    />
                  </svg>
                  Filled {fieldsUpdatedCount} field
                  {fieldsUpdatedCount !== 1 ? "s" : ""}
                </div>
              )}
              {extractionStatus === "error" && (
                <div className="flex items-center gap-2 text-sm text-red-500">
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                  </svg>
                  Extraction failed — try again or fill manually
                </div>
              )}
            </div>
          </div>

          {/* Still needed pills */}
          {missingRequired.length > 0 && (
            <div className="rounded-lg border bg-card p-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Still needed
              </p>
              <div className="flex flex-wrap gap-2">
                {missingRequired.map((f) => (
                  <span
                    key={f}
                    className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700"
                  >
                    {REQUIRED_LABELS[f]}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* What to include helper */}
          <div className="rounded-lg border bg-card">
            <button
              onClick={() => setHelperOpen((o) => !o)}
              className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              What to include
              <svg
                className={cn(
                  "h-4 w-4 transition-transform",
                  helperOpen && "rotate-180",
                )}
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                />
              </svg>
            </button>
            {helperOpen && (
              <div className="border-t px-4 pb-4 pt-3 text-sm text-muted-foreground">
                <ul className="space-y-1.5">
                  <li>Name of the deceased</li>
                  <li>Date, time, and place of death</li>
                  <li>Who is calling and their relationship</li>
                  <li>Contact phone number</li>
                  <li>Desired disposition (burial, cremation, etc.)</li>
                  <li>Service type and approximate date</li>
                  <li>Whether deceased was a veteran</li>
                  <li>How they heard about us</li>
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile sticky footer */}
      <div className="fixed inset-x-0 bottom-0 border-t bg-background p-4 lg:hidden">
        <button
          onClick={handleOpenCase}
          disabled={!isReadyToOpen || saving}
          className={cn(
            "w-full rounded-lg px-6 py-3 text-sm font-medium transition-colors",
            isReadyToOpen && !saving
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "cursor-not-allowed bg-muted text-muted-foreground",
          )}
        >
          {saving ? "Opening..." : "Open Case"}
        </button>
      </div>

      {/* Bottom spacer for mobile footer */}
      <div className="h-20 lg:hidden" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// SectionCard sub-component
// ---------------------------------------------------------------------------

function SectionCard({
  title,
  status,
  dotColor,
  open,
  onToggle,
  children,
}: {
  title: string;
  status: "empty" | "partial" | "complete";
  dotColor: (s: "empty" | "partial" | "complete") => string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border bg-card shadow-sm">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <span className={cn("h-2.5 w-2.5 rounded-full", dotColor(status))} />
        <span className="flex-1 text-sm font-semibold">{title}</span>
        <svg
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 8.25l-7.5 7.5-7.5-7.5"
          />
        </svg>
      </button>
      {open && <div className="space-y-4 border-t px-4 pb-4 pt-4">{children}</div>}
    </div>
  );
}
