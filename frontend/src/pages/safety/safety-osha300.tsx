import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import { safetyService } from "@/services/safety-service";
import type { OSHA300Entry, OSHA300ASummary } from "@/types/safety";

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function buildYearOptions(): number[] {
  const currentYear = new Date().getFullYear();
  const years: number[] = [];
  for (let y = currentYear; y >= currentYear - 5; y--) {
    years.push(y);
  }
  return years;
}

export default function SafetyOSHA300Page() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [entries, setEntries] = useState<OSHA300Entry[]>([]);
  const [summary, setSummary] = useState<OSHA300ASummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const yearOptions = buildYearOptions();

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [logData, summaryData] = await Promise.all([
        safetyService.getOSHA300Log(year),
        safetyService.getOSHA300ASummary(year),
      ]);
      setEntries(logData);
      setSummary(summaryData);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load OSHA 300 data";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [year]);

  if (error && entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => loadData()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">OSHA 300 Log</h1>
          <p className="text-muted-foreground">
            Log of Work-Related Injuries and Illnesses
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium">Year:</label>
          <select
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value))}
          >
            {yearOptions.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <p className="text-muted-foreground">Loading OSHA 300 data...</p>
        </div>
      ) : entries.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">
            No OSHA recordable incidents for {year}
          </p>
        </Card>
      ) : (
        <>
          {/* OSHA 300 Log Table */}
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="whitespace-nowrap">Case #</TableHead>
                  <TableHead className="whitespace-nowrap">Employee Name</TableHead>
                  <TableHead className="whitespace-nowrap">Date</TableHead>
                  <TableHead className="whitespace-nowrap">Location</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="whitespace-nowrap">Injury Type</TableHead>
                  <TableHead className="whitespace-nowrap text-right">Days Away</TableHead>
                  <TableHead className="whitespace-nowrap text-right">Days Restricted</TableHead>
                  <TableHead className="whitespace-nowrap">Treatment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry) => (
                  <TableRow key={entry.case_number}>
                    <TableCell className="font-medium">{entry.case_number}</TableCell>
                    <TableCell>{entry.employee_name}</TableCell>
                    <TableCell className="text-muted-foreground whitespace-nowrap">
                      {formatDate(entry.incident_date)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{entry.location}</TableCell>
                    <TableCell className="max-w-[300px] truncate text-muted-foreground">
                      {entry.description}
                    </TableCell>
                    <TableCell className="text-muted-foreground capitalize">
                      {entry.injury_type?.replace(/_/g, " ") || "\u2014"}
                    </TableCell>
                    <TableCell className="text-right">{entry.days_away_from_work}</TableCell>
                    <TableCell className="text-right">
                      {entry.days_on_restricted_duty}
                    </TableCell>
                    <TableCell className="text-muted-foreground capitalize whitespace-nowrap">
                      {entry.medical_treatment.replace(/_/g, " ")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* OSHA 300A Summary */}
          {summary && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  OSHA 300A Summary &mdash; {summary.year}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.total_cases}</p>
                    <p className="text-xs text-muted-foreground">Total Cases</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold text-red-600">{summary.total_deaths}</p>
                    <p className="text-xs text-muted-foreground">Deaths</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.total_days_away}</p>
                    <p className="text-xs text-muted-foreground">Total Days Away</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.total_days_restricted}</p>
                    <p className="text-xs text-muted-foreground">Total Days Restricted</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.total_other_recordable}</p>
                    <p className="text-xs text-muted-foreground">Other Recordable</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.injury_count}</p>
                    <p className="text-xs text-muted-foreground">Injuries</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.skin_disorder_count}</p>
                    <p className="text-xs text-muted-foreground">Skin Disorders</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.respiratory_count}</p>
                    <p className="text-xs text-muted-foreground">Respiratory</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.poisoning_count}</p>
                    <p className="text-xs text-muted-foreground">Poisonings</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.hearing_loss_count}</p>
                    <p className="text-xs text-muted-foreground">Hearing Loss</p>
                  </div>
                  <div className="rounded-md border p-3 text-center">
                    <p className="text-2xl font-bold">{summary.other_illness_count}</p>
                    <p className="text-xs text-muted-foreground">Other Illnesses</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
