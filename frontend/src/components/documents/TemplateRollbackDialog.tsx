import { useEffect, useState } from "react";
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
import {
  documentsV2Service,
  type DocumentTemplateDetail,
  type DocumentTemplateVersion,
} from "@/services/documents-v2-service";

/**
 * Rollback creates a NEW version that copies a retired version's
 * content. Version numbers stay monotonic — no row is reactivated.
 */
export default function TemplateRollbackDialog({
  open,
  onOpenChange,
  template,
  targetVersionId,
  requiresConfirmation,
  onRolledBack,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  template: DocumentTemplateDetail;
  targetVersionId: string;
  requiresConfirmation: boolean;
  onRolledBack: () => void;
}) {
  const [target, setTarget] = useState<DocumentTemplateVersion | null>(null);
  const [changelog, setChangelog] = useState("");
  const [confirmationText, setConfirmationText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const v = await documentsV2Service.getTemplateVersion(
          template.id,
          targetVersionId
        );
        if (!cancelled) {
          setTarget(v);
          setChangelog(`Rolled back to v${v.version_number}`);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    }
    if (open) load();
    return () => {
      cancelled = true;
    };
  }, [open, template.id, targetVersionId]);

  async function submit() {
    setErr(null);
    setSubmitting(true);
    try {
      await documentsV2Service.rollbackVersion(
        template.id,
        targetVersionId,
        {
          changelog,
          confirmation_text: requiresConfirmation
            ? confirmationText
            : undefined,
        }
      );
      onRolledBack();
      onOpenChange(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
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
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            Roll back to v{target?.version_number ?? "…"} of{" "}
            {template.template_key}?
          </DialogTitle>
          <DialogDescription>
            Rollback creates a new version that is a copy of
            v{target?.version_number ?? "…"}. Version numbers stay
            monotonic — no version is ever reactivated directly.
          </DialogDescription>
        </DialogHeader>

        {template.scope === "platform" && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <strong>Platform template —</strong> this affects every tenant
            not overriding this template.
          </div>
        )}

        {target && (
          <div className="space-y-1">
            <div className="text-xs font-semibold uppercase text-muted-foreground">
              Target version content
            </div>
            <pre className="max-h-60 overflow-auto rounded-md border bg-muted/20 p-2 font-mono text-xs">
              {target.body_template}
            </pre>
          </div>
        )}

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
            {submitting ? "Rolling back…" : "Rollback"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
