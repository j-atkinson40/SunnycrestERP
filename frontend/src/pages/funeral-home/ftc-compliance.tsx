import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { funeralHomeService } from "@/services/funeral-home-service";
import type { FTCComplianceReport } from "@/types/funeral-home";

const fmtDate = (d?: string) => (d ? new Date(d).toLocaleDateString() : "—");

function ComplianceCircle({ score }: { score: number }) {
  const radius = 56;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 90 ? "text-green-500" : score >= 70 ? "text-amber-500" : "text-red-500";

  return (
    <div className="relative h-36 w-36">
      <svg className="h-36 w-36 -rotate-90" viewBox="0 0 128 128">
        <circle cx="64" cy="64" r={radius} fill="none" stroke="currentColor" strokeWidth="10" className="text-muted" />
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={color}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-3xl font-bold", color)}>{score}%</span>
        <span className="text-xs text-muted-foreground">Compliant</span>
      </div>
    </div>
  );
}

export default function FTCCompliancePage() {
  const [report, setReport] = useState<FTCComplianceReport | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const data = await funeralHomeService.getCompliance();
      setReport(data);
    } catch {
      toast.error("Failed to load compliance data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreateVersion = async () => {
    try {
      await funeralHomeService.createGPLVersion({
        effective_date: new Date().toISOString().slice(0, 10),
        notes: "New GPL version",
      });
      toast.success("GPL version created");
      fetchData();
    } catch {
      toast.error("Failed to create GPL version");
    }
  };

  if (loading || !report) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading compliance data...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">FTC Compliance</h1>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* Left: Score */}
        <div className="space-y-6">
          <Card>
            <CardContent className="flex flex-col items-center gap-4 pt-6">
              <ComplianceCircle score={report.compliance_score} />
              {report.last_review_date && (
                <p className="text-xs text-muted-foreground">
                  Last review: {fmtDate(report.last_review_date)}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Total Cases</span>
                <span className="font-medium">{report.total_cases}</span>
              </div>
              <div className="flex justify-between">
                <span>Missing GPL Record</span>
                <span className={cn("font-medium", report.cases_missing_gpl_record > 0 && "text-red-600")}>
                  {report.cases_missing_gpl_record}
                </span>
              </div>
              <div className="flex justify-between">
                <span>All Required Items Present</span>
                <span className={cn("font-medium", report.all_required_items_present ? "text-green-600" : "text-red-600")}>
                  {report.all_required_items_present ? "Yes" : "No"}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Details */}
        <div className="space-y-6">
          {/* GPL Status */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                General Price List (GPL) Status
                {report.gpl_overdue && (
                  <Badge variant="destructive">Overdue</Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span>GPL Age</span>
                <span className={cn("font-medium", report.gpl_overdue ? "text-red-600" : "text-green-600")}>
                  {report.gpl_age_days} days
                </span>
              </div>
              {report.gpl_age_days > 365 && (
                <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
                  FTC Funeral Rule requires the GPL to be reviewed annually. Your GPL is overdue for review.
                </div>
              )}
              <Button variant="outline" size="sm" onClick={handleCreateVersion}>
                Create New GPL Version
              </Button>
            </CardContent>
          </Card>

          {/* Missing Items */}
          {report.missing_items.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm text-red-700">Missing Required Items</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1">
                  {report.missing_items.map((item) => (
                    <li key={item} className="text-sm text-red-600 flex items-center gap-2">
                      <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                      {item}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Items Missing Prices */}
          {report.items_missing_prices.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm text-amber-700">Items Missing Prices</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1">
                  {report.items_missing_prices.map((item) => (
                    <li key={item} className="text-sm text-amber-600">{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Disclosure Check */}
          {report.items_missing_disclosure.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm text-amber-700">Items Missing FTC Disclosure Text</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1">
                  {report.items_missing_disclosure.map((item) => (
                    <li key={item} className="text-sm text-amber-600">{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* All Issues */}
          {report.issues.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">All Compliance Issues</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {report.issues.map((issue, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <svg className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      {issue}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {report.issues.length === 0 && report.missing_items.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center">
                <svg className="mx-auto h-12 w-12 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <p className="mt-2 text-lg font-medium text-green-700">Fully Compliant</p>
                <p className="text-sm text-muted-foreground mt-1">No compliance issues found.</p>
              </CardContent>
            </Card>
          )}

          {/* GPL Version History */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">GPL Version History</CardTitle>
            </CardHeader>
            <CardContent>
              {report.gpl_versions.length === 0 ? (
                <p className="text-sm text-muted-foreground">No GPL versions recorded.</p>
              ) : (
                <div className="space-y-2">
                  {report.gpl_versions.map((v) => (
                    <div key={v.id} className="flex items-center justify-between text-sm border-b pb-2 last:border-0">
                      <div>
                        <span className="font-medium">Version {v.version_number}</span>
                        {v.notes && <span className="ml-2 text-muted-foreground">{v.notes}</span>}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Effective {fmtDate(v.effective_date)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
