import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, ArrowLeft, AlertTriangle, Loader2 } from "lucide-react";
import apiClient from "@/lib/api-client";

interface YearEndStatus {
  year: number;
  review_status: string;
  review_completed_at: string | null;
  entry_count: number;
  unreviewed_count: number;
  form_300a_generated_at: string | null;
  form_300a_certified_at: string | null;
  form_300a_certified_name: string | null;
  posting_confirmed_at: string | null;
  posting_location: string | null;
  retention_acknowledged_at: string | null;
}

export default function SafetyOSHA300YearEndPage() {
  const { year: yearParam } = useParams<{ year: string }>();
  const year = yearParam ? parseInt(yearParam) : new Date().getFullYear() - 1;

  const [status, setStatus] = useState<YearEndStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  // Step-specific state
  const [reviewNotes, setReviewNotes] = useState("");
  const [totalHours, setTotalHours] = useState("");
  const [certName, setCertName] = useState("");
  const [certTitle, setCertTitle] = useState("");
  const [postingLocation, setPostingLocation] = useState("");
  const [saveLocation, setSaveLocation] = useState(true);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get(`/safety/osha-300/year-end/${year}`);
      setStatus(res.data);
      // Determine current step from status
      if (res.data.posting_confirmed_at) setStep(4);
      else if (res.data.form_300a_certified_at) setStep(4);
      else if (res.data.form_300a_generated_at) setStep(3);
      else if (res.data.review_status === "complete") setStep(2);
      else setStep(1);

      if (res.data.posting_location) setPostingLocation(res.data.posting_location);
    } catch {
      toast.error("Failed to load year-end status");
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const completeReview = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/safety/osha-300/year-end/${year}/complete-review`, { notes: reviewNotes || null });
      toast.success("Review completed");
      setStep(2);
      fetchStatus();
    } catch { toast.error("Failed"); } finally { setSaving(false); }
  };

  const certify = async () => {
    if (!certName.trim() || !certTitle.trim()) { toast.error("Name and title required"); return; }
    setSaving(true);
    try {
      await apiClient.post(`/safety/osha-300/year-end/${year}/certify`, { certified_name: certName, certified_title: certTitle });
      toast.success("300A certified");
      setStep(4);
      fetchStatus();
    } catch { toast.error("Failed"); } finally { setSaving(false); }
  };

  const confirmPosting = async () => {
    if (!postingLocation.trim()) { toast.error("Enter posting location"); return; }
    setSaving(true);
    try {
      await apiClient.post(`/safety/osha-300/year-end/${year}/confirm-posting`, { location: postingLocation, save_location: saveLocation });
      toast.success("Posting confirmed");
      fetchStatus();
    } catch { toast.error("Failed"); } finally { setSaving(false); }
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>;

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <Link to="/safety/osha-300" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft className="h-4 w-4" /> Back to OSHA 300 Log
      </Link>

      <div>
        <h1 className="text-xl font-bold text-gray-900">{year} Year-End Review</h1>
        <p className="text-sm text-gray-500">Complete the year-end compliance workflow</p>
      </div>

      {/* Progress */}
      <div className="flex items-center gap-2">
        {[1, 2, 3, 4].map((s) => (
          <div key={s} className="flex items-center gap-2 flex-1">
            <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold ${s < step ? "bg-green-100 text-green-700" : s === step ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-400"}`}>
              {s < step ? <Check className="h-4 w-4" /> : s}
            </div>
            <span className="text-xs text-gray-500 hidden sm:inline">
              {s === 1 ? "Review" : s === 2 ? "Generate" : s === 3 ? "Certify" : "Post"}
            </span>
            {s < 4 && <div className={`flex-1 h-0.5 ${s < step ? "bg-green-300" : "bg-gray-200"}`} />}
          </div>
        ))}
      </div>

      {/* Step 1 — Review */}
      {step === 1 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Step 1 — Review Your Entries</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-gray-700">
              {year} OSHA 300 Log — {status?.entry_count ?? 0} entries
            </p>
            {(status?.unreviewed_count ?? 0) > 0 && (
              <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 rounded-md p-3">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {status?.unreviewed_count} entries are auto-populated and not yet reviewed
              </div>
            )}
            <Link to="/safety/osha-300" className="text-sm text-blue-600 hover:underline">
              Review entries in the OSHA 300 Log →
            </Link>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
              <textarea value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} rows={2} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="All entries verified with HR records" />
            </div>
            <Button onClick={completeReview} disabled={saving}>{saving ? "Saving..." : "Complete review and continue →"}</Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2 — Generate 300A */}
      {step === 2 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Step 2 — Generate Your 300A Summary</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-gray-700">The OSHA 300A is an annual summary that must be signed by a company executive and posted by February 1st.</p>
            <div className="bg-gray-50 rounded-md p-4 text-sm space-y-1">
              <p><strong>Total cases:</strong> {status?.entry_count ?? 0}</p>
              <p className="text-xs text-gray-500">Full summary will be generated with the 300A PDF.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Total hours worked in {year}</label>
              <input type="number" value={totalHours} onChange={(e) => setTotalHours(e.target.value)} className="w-48 rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="e.g. 104000" />
              <p className="text-xs text-gray-400 mt-1">Check your payroll records for this figure.</p>
            </div>
            <Button onClick={() => setStep(3)}>Continue to certification →</Button>
          </CardContent>
        </Card>
      )}

      {/* Step 3 — Certify */}
      {step === 3 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Step 3 — Executive Certification</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-gray-700">OSHA requires the 300A to be signed by a company owner, officer, or highest-ranking official.</p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input type="text" value={certName} onChange={(e) => setCertName(e.target.value)} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="James Smith" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
              <input type="text" value={certTitle} onChange={(e) => setCertTitle(e.target.value)} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="Owner" />
            </div>
            <p className="text-xs text-gray-500">By certifying, you attest that the {year} OSHA 300A Summary is true, accurate, and complete.</p>
            <Button onClick={certify} disabled={saving}>{saving ? "Certifying..." : "✓ Certify 300A"}</Button>
          </CardContent>
        </Card>
      )}

      {/* Step 4 — Post */}
      {step === 4 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Step 4 — Post and Confirm</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {status?.posting_confirmed_at ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-green-700">
                  <Check className="h-5 w-5" />
                  <span className="text-sm font-semibold">Year-End Workflow Complete</span>
                </div>
                <div className="text-sm text-gray-600 space-y-1">
                  <p>Review completed: {status.review_completed_at ? new Date(status.review_completed_at).toLocaleDateString() : "—"}</p>
                  <p>Certified by: {status.form_300a_certified_name}</p>
                  <p>Posted at: {status.posting_location}</p>
                  <p>Posting period ends: April 30, {year + 1}</p>
                  <p>Retention required through: December 31, {year + 5}</p>
                </div>
              </div>
            ) : (
              <>
                <p className="text-sm text-gray-700">Print your certified 300A and post it where employees can see it.</p>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Where will you post it?</label>
                  <input type="text" value={postingLocation} onChange={(e) => setPostingLocation(e.target.value)} className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="Break room bulletin board" />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={saveLocation} onChange={(e) => setSaveLocation(e.target.checked)} className="h-4 w-4 rounded border-gray-300" />
                  Save this location for future years
                </label>
                <Button onClick={confirmPosting} disabled={saving}>{saving ? "Confirming..." : "✓ I have posted the 300A"}</Button>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
