import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, CheckCircle, Loader2, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ScannedCheck {
  extracted: {
    payer_name?: string | null;
    amount?: number | null;
    check_number?: string | null;
    check_date?: string | null;
    memo?: string | null;
    bank_name?: string | null;
    confidence?: Record<string, number>;
  };
  matched_customer: {
    customer_id: string;
    name: string;
    match_confidence: number;
    match_method: string;
  } | null;
  suggested_applications: Array<{
    invoice_id: string;
    invoice_number: string;
    invoice_date: string;
    balance_remaining: number;
    amount_to_apply: number;
    covers_fully: boolean;
  }>;
  error?: string;
}

interface CheckScannerProps {
  onComplete: (result: ScannedCheck) => void;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Confidence badge
// ---------------------------------------------------------------------------

function ConfidenceBadge({ value }: { value?: number }) {
  if (value == null) return null;
  if (value >= 0.85)
    return (
      <Badge className="bg-green-100 text-green-700 text-xs">
        {Math.round(value * 100)}%
      </Badge>
    );
  if (value >= 0.6)
    return (
      <Badge className="bg-yellow-100 text-yellow-700 text-xs">
        {Math.round(value * 100)}%
      </Badge>
    );
  return (
    <Badge className="bg-red-100 text-red-700 text-xs">
      {Math.round(value * 100)}%
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CheckScanner({ onComplete, onClose }: CheckScannerProps) {
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScannedCheck | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);

    setScanning(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiClient.post("/sales/payments/scan-check", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Check scan failed"));
    } finally {
      setScanning(false);
    }
  }, []);

  const conf = result?.extracted.confidence;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center p-4">
      <div className="bg-background rounded-lg shadow-2xl w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div className="flex items-center gap-2">
            <Camera className="w-4 h-4 text-muted-foreground" />
            <h2 className="font-semibold">Scan Check</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="p-5 space-y-4">
          {!result && (
            <>
              {imagePreview && (
                <div className="relative rounded-md overflow-hidden border">
                  <img
                    src={imagePreview}
                    alt="Check preview"
                    className="w-full object-contain max-h-48"
                  />
                  {scanning && (
                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                      <div className="text-white text-center">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto mb-1" />
                        <span className="text-sm">Reading check...</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
              {!imagePreview && (
                <div
                  className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                  <p className="text-sm font-medium">Upload a photo of the check</p>
                  <p className="text-xs text-muted-foreground mt-1">JPG, PNG, or HEIC</p>
                </div>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              {!imagePreview && (
                <Button
                  className="w-full"
                  onClick={() => fileRef.current?.click()}
                  disabled={scanning}
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Choose Image
                </Button>
              )}
            </>
          )}

          {result && (
            <div className="space-y-4">
              {/* Extracted fields */}
              <div className="rounded-md border bg-muted/30 p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-sm font-medium text-green-700 mb-3">
                  <CheckCircle className="w-4 h-4" />
                  Check scanned
                </div>
                {(
                  [
                    { label: "Payer", value: result.extracted.payer_name, key: "payer_name" },
                    {
                      label: "Amount",
                      value:
                        result.extracted.amount != null
                          ? `$${result.extracted.amount.toFixed(2)}`
                          : null,
                      key: "amount",
                    },
                    { label: "Check #", value: result.extracted.check_number, key: "check_number" },
                    { label: "Date", value: result.extracted.check_date, key: "check_date" },
                  ] as { label: string; value: string | null | undefined; key: string }[]
                ).map(({ label, value, key }) => (
                  <div key={key} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{label}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">
                        {value ?? (
                          <span className="text-muted-foreground italic">Not detected</span>
                        )}
                      </span>
                      <ConfidenceBadge value={conf?.[key]} />
                    </div>
                  </div>
                ))}
              </div>

              {/* Matched customer */}
              {result.matched_customer && (
                <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm">
                  <p className="font-medium text-blue-800">{result.matched_customer.name}</p>
                  <p className="text-blue-600 text-xs mt-0.5">
                    Matched with{" "}
                    {Math.round(result.matched_customer.match_confidence * 100)}% confidence
                  </p>
                </div>
              )}

              {/* Suggested applications */}
              {result.suggested_applications.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Suggested application
                  </p>
                  {result.suggested_applications.map((app) => (
                    <div
                      key={app.invoice_id}
                      className="flex justify-between text-sm rounded border px-3 py-2"
                    >
                      <span>Invoice #{app.invoice_number}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">${app.amount_to_apply.toFixed(2)}</span>
                        {app.covers_fully && (
                          <Badge className="bg-green-100 text-green-700 text-xs">Full</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <Button className="flex-1" onClick={() => onComplete(result)}>
                  Confirm &amp; Record Payment
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setResult(null);
                    setImagePreview(null);
                  }}
                >
                  Rescan
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
