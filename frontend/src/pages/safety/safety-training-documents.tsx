import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, Upload, RotateCcw, ExternalLink, Check } from "lucide-react";
import apiClient from "@/lib/api-client";

const MONTH_NAMES = [
  "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const TOPIC_LABELS: Record<string, string> = {
  lockout_tagout: "Lockout/Tagout",
  forklift_safety: "Forklift Safety",
  hazard_communication: "Hazard Comm.",
  ppe: "PPE",
  electrical_safety: "Electrical Safety",
  hearing_conservation: "Hearing Conservation",
  heat_illness_prevention: "Heat Illness",
  crane_rigging: "Crane & Rigging",
  bloodborne_pathogens: "Bloodborne Pathogens",
  fall_protection: "Fall Protection",
  confined_space: "Confined Space",
  emergency_action_fire: "Emergency / Fire",
};

interface TrainingDoc {
  topic_key: string;
  source: "platform" | "tenant";
  filename: string;
  url: string;
  uploaded_at: string | null;
  uploaded_by_name: string | null;
  notes: string | null;
}

export default function SafetyTrainingDocumentsPage() {
  const [docs, setDocs] = useState<TrainingDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadingKey, setUploadingKey] = useState<string | null>(null);
  const [uploadUrl, setUploadUrl] = useState("");
  const [uploadFilename, setUploadFilename] = useState("");
  const [uploadNotes, setUploadNotes] = useState("");

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/safety/training/documents");
      setDocs(res.data);
    } catch {
      toast.error("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  const handleUpload = async (topicKey: string) => {
    if (!uploadUrl.trim() || !uploadFilename.trim()) {
      toast.error("URL and filename are required");
      return;
    }
    try {
      await apiClient.post("/safety/training/documents", {
        topic_key: topicKey,
        filename: uploadFilename.trim(),
        file_url: uploadUrl.trim(),
        notes: uploadNotes.trim() || null,
      });
      toast.success("Document uploaded");
      setUploadingKey(null);
      setUploadUrl("");
      setUploadFilename("");
      setUploadNotes("");
      fetchDocs();
    } catch {
      toast.error("Failed to upload document");
    }
  };

  const handleRevert = async (topicKey: string) => {
    try {
      await apiClient.delete(`/safety/training/documents/${topicKey}`);
      toast.success("Reverted to platform default");
      fetchDocs();
    } catch {
      toast.error("Failed to revert");
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          Training Documents
        </h2>
        <p className="text-sm text-gray-500">
          Replace any platform-provided training template with your company's
          own safety programs.
        </p>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="divide-y divide-gray-100">
            {docs.map((doc, idx) => {
              const monthNum = idx + 1;
              const topicLabel =
                TOPIC_LABELS[doc.topic_key] ?? doc.topic_key;
              const isUploading = uploadingKey === doc.topic_key;

              return (
                <div key={doc.topic_key} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <span className="text-xs font-medium text-gray-400 w-8 shrink-0">
                        {MONTH_NAMES[monthNum]}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-gray-900">
                          {topicLabel}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          {doc.source === "tenant" ? (
                            <>
                              <span className="inline-flex items-center gap-1 text-xs text-green-700">
                                <Check className="h-3 w-3" /> Your document
                              </span>
                              <span className="text-xs text-gray-400">
                                {doc.filename}
                              </span>
                              {doc.uploaded_by_name && (
                                <span className="text-xs text-gray-400">
                                  by {doc.uploaded_by_name}
                                </span>
                              )}
                            </>
                          ) : (
                            <span className="text-xs text-gray-400">
                              <FileText className="inline h-3 w-3 mr-0.5" />
                              Platform default
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-0.5"
                      >
                        <ExternalLink className="h-3 w-3" /> Preview
                      </a>
                      {doc.source === "tenant" ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-xs"
                            onClick={() => {
                              setUploadingKey(doc.topic_key);
                              setUploadUrl("");
                              setUploadFilename("");
                              setUploadNotes("");
                            }}
                          >
                            <Upload className="h-3 w-3 mr-1" /> Replace
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-xs text-gray-500"
                            onClick={() => handleRevert(doc.topic_key)}
                          >
                            <RotateCcw className="h-3 w-3 mr-1" /> Revert
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs"
                          onClick={() => {
                            setUploadingKey(doc.topic_key);
                            setUploadUrl("");
                            setUploadFilename("");
                            setUploadNotes("");
                          }}
                        >
                          <Upload className="h-3 w-3 mr-1" /> Upload yours
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Inline upload form */}
                  {isUploading && (
                    <div className="mt-3 ml-11 p-3 border border-gray-200 rounded-md bg-gray-50 space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Document URL
                        </label>
                        <input
                          type="url"
                          value={uploadUrl}
                          onChange={(e) => setUploadUrl(e.target.value)}
                          className="w-full rounded-md border border-gray-300 px-2.5 py-1.5 text-sm"
                          placeholder="https://..."
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Filename
                        </label>
                        <input
                          type="text"
                          value={uploadFilename}
                          onChange={(e) => setUploadFilename(e.target.value)}
                          className="w-full rounded-md border border-gray-300 px-2.5 py-1.5 text-sm"
                          placeholder="Company_LOTO_Program_v3.pdf"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">
                          Notes (optional)
                        </label>
                        <input
                          type="text"
                          value={uploadNotes}
                          onChange={(e) => setUploadNotes(e.target.value)}
                          className="w-full rounded-md border border-gray-300 px-2.5 py-1.5 text-sm"
                          placeholder="e.g. Our LOTO program v3.2"
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleUpload(doc.topic_key)}
                        >
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setUploadingKey(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
