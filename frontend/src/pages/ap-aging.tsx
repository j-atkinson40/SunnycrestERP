import { useCallback, useEffect, useState } from "react";
import {
  apAgingService,
  type AgingReport,
} from "@/services/ap-aging-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";

function fmtCurrency(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(n);
}

export default function APAgingPage() {
  const [report, setReport] = useState<AgingReport | null>(null);
  const [asOfDate, setAsOfDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apAgingService.getAging(asOfDate || undefined);
      setReport(data);
    } catch {
      toast.error("Failed to load AP aging report");
    } finally {
      setLoading(false);
    }
  }, [asOfDate]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  async function handleExportCsv() {
    setExporting(true);
    try {
      await apAgingService.downloadAgingCsv(asOfDate || undefined);
      toast.success("CSV downloaded");
    } catch {
      toast.error("Failed to export CSV");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">AP Aging Report</h1>
          <p className="text-muted-foreground">
            Outstanding payables by vendor
          </p>
        </div>
        <Button
          variant="outline"
          onClick={handleExportCsv}
          disabled={exporting}
        >
          {exporting ? "Exporting..." : "Export CSV"}
        </Button>
      </div>

      {/* Filter */}
      <div className="flex items-end gap-4">
        <div className="space-y-2">
          <Label>As of Date</Label>
          <Input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="w-48"
          />
        </div>
        <Button variant="outline" onClick={loadReport}>
          Refresh
        </Button>
      </div>

      {/* Summary cards */}
      {report && (
        <div className="grid grid-cols-3 gap-4 md:grid-cols-6">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Current</p>
            <p className="text-lg font-bold">
              {fmtCurrency(report.totals.current)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">1-30 Days</p>
            <p className="text-lg font-bold text-yellow-600">
              {fmtCurrency(report.totals.d1_30)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">31-60 Days</p>
            <p className="text-lg font-bold text-orange-600">
              {fmtCurrency(report.totals.d31_60)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">61-90 Days</p>
            <p className="text-lg font-bold text-red-500">
              {fmtCurrency(report.totals.d61_90)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">90+ Days</p>
            <p className="text-lg font-bold text-red-700">
              {fmtCurrency(report.totals.d90_plus)}
            </p>
          </Card>
          <Card className="p-4 border-2">
            <p className="text-sm text-muted-foreground">Total</p>
            <p className="text-xl font-bold">
              {fmtCurrency(report.totals.total)}
            </p>
          </Card>
        </div>
      )}

      {/* Aging table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Vendor</TableHead>
              <TableHead className="text-right">Current</TableHead>
              <TableHead className="text-right">1-30</TableHead>
              <TableHead className="text-right">31-60</TableHead>
              <TableHead className="text-right">61-90</TableHead>
              <TableHead className="text-right">90+</TableHead>
              <TableHead className="text-right font-bold">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : !report || report.vendors.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No outstanding payables
                </TableCell>
              </TableRow>
            ) : (
              <>
                {report.vendors.map((v) => (
                  <TableRow key={v.vendor_id}>
                    <TableCell className="font-medium">
                      {v.vendor_name}
                    </TableCell>
                    <TableCell className="text-right">
                      {v.current > 0 ? fmtCurrency(v.current) : "\u2014"}
                    </TableCell>
                    <TableCell className="text-right">
                      {v.d1_30 > 0 ? (
                        <span className="text-yellow-600">
                          {fmtCurrency(v.d1_30)}
                        </span>
                      ) : (
                        "\u2014"
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {v.d31_60 > 0 ? (
                        <span className="text-orange-600">
                          {fmtCurrency(v.d31_60)}
                        </span>
                      ) : (
                        "\u2014"
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {v.d61_90 > 0 ? (
                        <span className="text-red-500">
                          {fmtCurrency(v.d61_90)}
                        </span>
                      ) : (
                        "\u2014"
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {v.d90_plus > 0 ? (
                        <span className="text-red-700 font-medium">
                          {fmtCurrency(v.d90_plus)}
                        </span>
                      ) : (
                        "\u2014"
                      )}
                    </TableCell>
                    <TableCell className="text-right font-bold">
                      {fmtCurrency(v.total)}
                    </TableCell>
                  </TableRow>
                ))}
                {/* Totals row */}
                <TableRow className="bg-muted/50 font-bold">
                  <TableCell>TOTAL</TableCell>
                  <TableCell className="text-right">
                    {fmtCurrency(report.totals.current)}
                  </TableCell>
                  <TableCell className="text-right text-yellow-600">
                    {fmtCurrency(report.totals.d1_30)}
                  </TableCell>
                  <TableCell className="text-right text-orange-600">
                    {fmtCurrency(report.totals.d31_60)}
                  </TableCell>
                  <TableCell className="text-right text-red-500">
                    {fmtCurrency(report.totals.d61_90)}
                  </TableCell>
                  <TableCell className="text-right text-red-700">
                    {fmtCurrency(report.totals.d90_plus)}
                  </TableCell>
                  <TableCell className="text-right text-lg">
                    {fmtCurrency(report.totals.total)}
                  </TableCell>
                </TableRow>
              </>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
