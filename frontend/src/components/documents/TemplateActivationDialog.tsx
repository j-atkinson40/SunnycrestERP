import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  documentsV2Service,
  type DocumentTemplateDetail,
  type DocumentTemplateVersion,
} from "@/services/documents-v2-service";

export default function TemplateActivationDialog({
  open,
  onOpenChange,
  template,
  draft,
  requiresConfirmation,
  onActivated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  template: DocumentTemplateDetail;
  draft: DocumentTemplateVersion;
  requiresConfirmation: boolean;
  onActivated: () => void;
}) {
  const [changelog, setChangelog] = useState(draft.changelog ?? "");
  const [confirmationText, setConfirmationText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [issues, setIssues] = useState<
    { severity: string; issue_type: string; message: string }[]
  >([]);

  const current = template.current_version;
  const diff = useMemo(
    () => buildDiff(current, draft),
    [current, draft]
  );

  async function submit() {
    setErr(null);
    setIssues([]);
    setSubmitting(true);
    try {
      await documentsV2Service.activateVersion(template.id, draft.id, {
        changelog,
        confirmation_text: requiresConfirmation ? confirmationText : undefined,
      });
      onActivated();
      onOpenChange(false);
    } catch (e: unknown) {
      // Try to extract structured validation issues
      const maybe = e as { response?: { data?: { detail?: unknown } } } | undefined;
      const detail = maybe?.response?.data?.detail;
      if (detail && typeof detail === "object" && "issues" in detail) {
        setIssues(
          (detail as { issues: { severity: string; issue_type: string; message: string }[] })
            .issues
        );
      } else {
        setErr(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    changelog.trim().length > 0 &&
    (!requiresConfirmation || confirmationText === template.template_key) &&
    !submitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            Activate v{draft.version_number} of {template.template_key}?
          </DialogTitle>
          <DialogDescription>
            This version will be used for all future renders. Current
            active v{current?.version_number ?? "?"} will be retired.
          </DialogDescription>
        </DialogHeader>

        {template.scope === "platform" && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <strong>Platform template —</strong> this affects every tenant
            not overriding this template.
          </div>
        )}

        {/* Diff view */}
        <div className="space-y-3 rounded-md border p-3">
          <div className="text-xs font-semibold uppercase text-muted-foreground">
            Changes
          </div>
          {diff.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No changes detected vs the current active version.
            </div>
          ) : (
            diff.map((d) => (
              <div key={d.field} className="space-y-1">
                <div className="text-xs font-semibold">
                  {d.field}{" "}
                  <Badge variant="outline" className="ml-1 text-[10px]">
                    changed
                  </Badge>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground">
                      Current (v{current?.version_number ?? "—"})
                    </div>
                    <pre className="max-h-32 overflow-auto rounded-md border bg-muted/20 p-2 font-mono text-[11px]">
                      {d.before}
                    </pre>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase text-muted-foreground">
                      Draft (v{draft.version_number})
                    </div>
                    <pre className="max-h-32 overflow-auto rounded-md border border-blue-500/40 bg-blue-500/5 p-2 font-mono text-[11px]">
                      {d.after}
                    </pre>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase text-muted-foreground">
            Changelog (required)
          </label>
          <textarea
            className="h-24 w-full rounded-md border bg-muted/10 p-2 text-sm"
            value={changelog}
            onChange={(e) => setChangelog(e.target.value)}
          />
        </div>

        {requiresConfirmation && (
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase text-muted-foreground">
              Type the template key to confirm
            </label>
            <Input
              value={confirmationText}
              onChange={(e) => setConfirmationText(e.target.value)}
              placeholder={template.template_key}
            />
            {confirmationText && confirmationText !== template.template_key && (
              <div className="text-xs text-destructive">
                Does not match.
              </div>
            )}
          </div>
        )}

        {issues.length > 0 && (
          <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
            <div className="font-semibold">Variable schema validation:</div>
            <ul className="ml-4 list-disc space-y-1">
              {issues.map((i, idx) => (
                <li key={idx}>
                  <Badge variant="outline" className="text-[10px]">
                    {i.severity}
                  </Badge>{" "}
                  <span className="font-mono text-xs">{i.issue_type}</span> —{" "}
                  {i.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {err && (
          <div className="rounded-md border border-destructive bg-destructive/10 p-2 text-sm text-destructive">
            {err}
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSubmit}>
            {submitting ? "Activating…" : "Activate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


type DiffField = { field: string; before: string; after: string };

function buildDiff(
  current: DocumentTemplateVersion | null,
  draft: DocumentTemplateVersion
): DiffField[] {
  const out: DiffField[] = [];
  const fields: Array<keyof DocumentTemplateVersion> = [
    "body_template",
    "subject_template",
    "variable_schema",
    "css_variables",
  ];
  for (const f of fields) {
    const before = stringify(current?.[f] ?? "");
    const after = stringify(draft[f] ?? "");
    if (before !== after) out.push({ field: f as string, before, after });
  }
  return out;
}

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}
