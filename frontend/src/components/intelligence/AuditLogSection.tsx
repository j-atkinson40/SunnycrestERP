import { useEffect, useState } from "react";
import { intelligenceService } from "@/services/intelligence-service";
import type { AuditLogEntry } from "@/types/intelligence";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { formatAbsoluteTime } from "@/components/intelligence/formatting";

const PAGE = 10;

const ACTION_LABEL: Record<string, string> = {
  activate: "Activated",
  rollback: "Rolled back",
  create_draft: "Draft created",
  update_draft: "Draft updated",
  delete_draft: "Draft discarded",
};

function actionVariant(
  action: string,
): "default" | "destructive" | "outline" | "secondary" {
  if (action === "activate") return "default";
  if (action === "rollback") return "secondary";
  if (action === "delete_draft") return "destructive";
  return "outline";
}

interface Props {
  promptId: string;
  /** Bump to force re-fetch after an edit action completes. */
  refreshToken?: number;
}

export function AuditLogSection({ promptId, refreshToken }: Props) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    intelligenceService
      .listAuditLog(promptId, PAGE + 1, offset)
      .then((rows) => {
        setHasMore(rows.length > PAGE);
        setEntries(rows.slice(0, PAGE));
      })
      .catch((e) =>
        setErr(e instanceof Error ? e.message : String(e)),
      )
      .finally(() => setLoading(false));
  }, [promptId, offset, refreshToken]);

  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">History</h2>
      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-xs text-destructive">
          {err}
        </div>
      )}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Changelog</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : entries.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="py-4 text-center text-muted-foreground"
                >
                  No history yet for this prompt.
                </TableCell>
              </TableRow>
            ) : (
              entries.map((e) => (
                <TableRow key={e.id}>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={e.created_at}
                  >
                    {formatAbsoluteTime(e.created_at)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={actionVariant(e.action)}>
                      {ACTION_LABEL[e.action] ?? e.action}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {e.actor_email ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {e.version_id
                      ? (e.meta_json["version_number"] as number) !== undefined
                        ? `v${e.meta_json["version_number"]}`
                        : e.version_id.slice(0, 8)
                      : "—"}
                  </TableCell>
                  <TableCell
                    className="max-w-[360px] truncate text-xs"
                    title={e.changelog_summary ?? ""}
                  >
                    {e.changelog_summary ?? "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {(offset > 0 || hasMore) && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Offset {offset}</span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset <= 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!hasMore}
              onClick={() => setOffset(offset + PAGE)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
