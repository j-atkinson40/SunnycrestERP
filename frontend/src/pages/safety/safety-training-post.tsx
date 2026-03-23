import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, FileText, Send, AlertTriangle, Check } from "lucide-react";
import apiClient from "@/lib/api-client";

const MONTH_NAMES = [
  "", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

interface TopicDetail {
  id: string;
  topic_key: string;
  title: string;
  description: string | null;
  osha_standard: string | null;
  osha_standard_label: string | null;
  suggested_duration_minutes: number;
  target_roles: string[];
  key_points: string[];
  discussion_questions: string[];
  pdf_filename_template: string | null;
  is_high_risk: boolean;
}

interface ScheduleDetail {
  id: string;
  year: number;
  month_number: number;
  status: string;
  topic: TopicDetail;
  announcement_id: string | null;
  posted_at: string | null;
  completion_rate: number | null;
  notes: string | null;
}

export default function SafetyTrainingPostPage() {
  const { scheduleId } = useParams<{ scheduleId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<ScheduleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);

  // Form state
  const [documentUrl, setDocumentUrl] = useState("");
  const [customMessage, setCustomMessage] = useState("");
  const [targetType, setTargetType] = useState("everyone");
  const [deadline, setDeadline] = useState("");
  const [complianceRelevant, setComplianceRelevant] = useState(false);

  const fetchDetail = useCallback(async () => {
    if (!scheduleId) return;
    setLoading(true);
    try {
      const res = await apiClient.get(
        `/safety/training/schedule/${scheduleId}`
      );
      setDetail(res.data);
      // Set defaults based on topic
      if (res.data.topic.is_high_risk) {
        setComplianceRelevant(true);
      }
      // Default deadline: end of month
      const month = res.data.month_number;
      const year = res.data.year;
      const lastDay = new Date(year, month, 0).getDate();
      setDeadline(`${year}-${String(month).padStart(2, "0")}-${lastDay}`);
      // Default target
      const roles = res.data.topic.target_roles || [];
      if (roles.length === 1 && roles[0] === "all") {
        setTargetType("everyone");
      } else {
        setTargetType("everyone"); // default to all, user can change
      }
    } catch {
      toast.error("Failed to load training details");
    } finally {
      setLoading(false);
    }
  }, [scheduleId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handlePost = async () => {
    if (!detail) return;
    setPosting(true);
    try {
      const monthName = MONTH_NAMES[detail.month_number];
      const title = `${monthName} Safety Training: ${detail.topic.title}`;
      const defaultBody = `${monthName} safety training: ${detail.topic.title}. Please read the attached document and acknowledge by ${deadline}. Contact your safety manager with questions.`;
      const body = customMessage.trim() || defaultBody;

      // 1. Create the safety notice announcement
      const annRes = await apiClient.post("/announcements/", {
        title,
        body,
        priority: detail.topic.is_high_risk ? "critical" : "warning",
        content_type: "safety_notice",
        safety_category: "procedure",
        target_type: targetType,
        requires_acknowledgment: true,
        is_compliance_relevant: complianceRelevant,
        document_url: documentUrl.trim() || null,
        document_filename: detail.topic.pdf_filename_template
          ?.replace("[Year]", String(detail.year))
          ?.replace("[Month]", monthName) || null,
        acknowledgment_deadline: deadline || null,
      });

      // 2. Link to training schedule
      await apiClient.post(
        `/safety/training/schedule/${detail.id}/post`,
        { announcement_id: annRes.data.id }
      );

      toast.success("Training notice posted successfully");
      navigate("/safety/training/calendar");
    } catch {
      toast.error("Failed to post training notice");
    } finally {
      setPosting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="text-center py-12 text-gray-500">
        Training schedule entry not found.
      </div>
    );
  }

  const monthName = MONTH_NAMES[detail.month_number];
  const alreadyPosted = detail.status === "posted" || detail.status === "complete";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        to="/safety/training/calendar"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to calendar
      </Link>

      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          {monthName} Safety Training
        </h2>
        <h3 className="text-xl font-bold text-gray-900 mt-1">
          {detail.topic.title}
          {detail.topic.is_high_risk && (
            <span className="ml-2 text-sm text-red-600 font-medium">
              <AlertTriangle className="inline h-4 w-4" /> High Risk
            </span>
          )}
        </h3>
        <p className="text-sm text-gray-500 mt-1">
          OSHA Standard: {detail.topic.osha_standard} —{" "}
          {detail.topic.osha_standard_label}
        </p>
      </div>

      {/* Already posted banner */}
      {alreadyPosted && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="p-4 flex items-center gap-2">
            <Check className="h-5 w-5 text-green-600" />
            <span className="text-sm text-green-800">
              This training was posted on{" "}
              {detail.posted_at
                ? new Date(detail.posted_at).toLocaleDateString()
                : "—"}
              {detail.completion_rate != null &&
                ` · ${Math.round(detail.completion_rate)}% completion`}
            </span>
          </CardContent>
        </Card>
      )}

      {/* Topic info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">This Training Covers</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-700 mb-4">{detail.topic.description}</p>
          {detail.topic.key_points.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-800 mb-2">
                Key Points
              </h4>
              <ul className="list-disc pl-5 space-y-1 text-sm text-gray-600">
                {detail.topic.key_points.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {detail.topic.discussion_questions.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-800 mb-2">
                Discussion Questions
              </h4>
              <ul className="list-disc pl-5 space-y-1 text-sm text-gray-600">
                {detail.topic.discussion_questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Post form — only if not already posted */}
      {!alreadyPosted && (
        <>
          {/* Step 1: Document */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Step 1 — Attach Training Document
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Document URL
                </label>
                <input
                  type="url"
                  value={documentUrl}
                  onChange={(e) => setDocumentUrl(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  placeholder="https://..."
                />
                <p className="text-xs text-gray-400 mt-1">
                  <FileText className="inline h-3 w-3" /> Suggested filename:{" "}
                  {detail.topic.pdf_filename_template
                    ?.replace("[Year]", String(detail.year))
                    ?.replace("[Month]", monthName)}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Step 2: Message */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Step 2 — Customize Message (Optional)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <textarea
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                rows={3}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                placeholder="Leave blank to use the default message..."
              />
              <p className="text-xs text-gray-400 mt-1">
                Default: "{monthName} safety training: {detail.topic.title}.
                Please read the attached document and acknowledge by {deadline}."
              </p>
            </CardContent>
          </Card>

          {/* Step 3: Targeting + options */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Step 3 — Review Settings
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Who receives this training
                </label>
                <div className="flex flex-col gap-2">
                  {["everyone", "functional_area", "specific_employees"].map(
                    (t) => (
                      <label
                        key={t}
                        className="flex items-center gap-2 text-sm cursor-pointer"
                      >
                        <input
                          type="radio"
                          name="target"
                          checked={targetType === t}
                          onChange={() => setTargetType(t)}
                          className="h-4 w-4"
                        />
                        {t === "everyone"
                          ? "All employees"
                          : t === "functional_area"
                            ? "Production staff only"
                            : "Specific employees"}
                      </label>
                    )
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Acknowledgment deadline
                </label>
                <input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="compliance"
                  checked={complianceRelevant}
                  onChange={(e) => setComplianceRelevant(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <label htmlFor="compliance" className="text-sm text-gray-700">
                  Mark as compliance-relevant (OSHA)
                </label>
              </div>
            </CardContent>
          </Card>

          {/* Post button */}
          <div className="flex justify-end">
            <Button
              onClick={handlePost}
              disabled={posting}
              className="gap-2"
            >
              <Send className="h-4 w-4" />
              {posting ? "Posting..." : "Post Training Notice"}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
