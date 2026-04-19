import { useState } from "react";
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
import { AlertTriangle } from "lucide-react";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  PromptDetailResponse,
  PromptVersionResponse,
} from "@/types/intelligence";
import { DiffView } from "@/components/intelligence/DiffView";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prompt: PromptDetailResponse;
  target: PromptVersionResponse; // the retired version we're rolling back to
  activeVersion: PromptVersionResponse | null;
  requiresConfirmationText: boolean;
  onRolledBack: () => void;
}

/**
 * Roll back to a retired version by cloning its content into a NEW active
 * version (spec: "rollback always creates a new version"). Version numbers
 * stay monotonic; audit trail stays clean.
 */
export function RollbackDialog({
  open,
  onOpenChange,
  prompt,
  target,
  activeVersion,
  requiresConfirmationText,
  onRolledBack,
}: Props) {
  const [changelog, setChangelog] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const confirmationOk =
    !requiresConfirmationText || confirmation.trim() === prompt.prompt_key;
  const changelogOk = changelog.trim().length > 0;
  const canSubmit = confirmationOk && changelogOk && !submitting;

  async function handleRollback() {
    setSubmitting(true);
    setErr(null);
    try {
      await intelligenceService.rollback(prompt.id, target.id, {
        changelog: changelog.trim(),
        confirmation_text: requiresConfirmationText ? confirmation : undefined,
      });
      onRolledBack();
      onOpenChange(false);
    } catch (e) {
      const anyErr = e as { response?: { data?: { detail?: unknown } } };
      const detail = anyErr.response?.data?.detail;
      setErr(
        typeof detail === "string"
          ? detail
          : detail
          ? JSON.stringify(detail, null, 2)
          : e instanceof Error
          ? e.message
          : String(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            Roll back to v{target.version_number} of{" "}
            <code className="font-mono">{prompt.prompt_key}</code>?
          </DialogTitle>
          <DialogDescription>
            Rolling back <em>creates a new version</em> that is a copy of v
            {target.version_number}. Version numbers are never reused.{" "}
            {activeVersion && (
              <>
                The current active version (v{activeVersion.version_number}
                ) will be retired.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        {prompt.company_id === null && (
          <div className="rounded-md border border-amber-500/60 bg-amber-500/5 p-3 text-xs">
            <div className="flex items-center gap-2 font-medium">
              <AlertTriangle className="h-4 w-4" />
              Platform-global prompt — change affects every tenant.
            </div>
          </div>
        )}

        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            What changes vs current active
          </h3>
          {activeVersion ? (
            <DiffView
              before={activeVersion}
              after={target}
              beforeLabel={`v${activeVersion.version_number} (current active)`}
              afterLabel={`v${target.version_number} (rollback target)`}
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              No current active version.
            </p>
          )}
        </div>

        <label className="block space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Reason for rollback <span className="text-destructive">*</span>
          </span>
          <textarea
            className="h-20 w-full rounded-md border border-input bg-transparent p-2 text-sm"
            value={changelog}
            onChange={(e) => setChangelog(e.target.value)}
            placeholder="Why roll back?"
          />
        </label>

        {requiresConfirmationText && (
          <label className="block space-y-1">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Confirm — type <code>{prompt.prompt_key}</code>
            </span>
            <Input
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              placeholder={prompt.prompt_key}
              autoComplete="off"
            />
          </label>
        )}

        {err && (
          <pre className="max-h-40 overflow-auto rounded-md border border-destructive bg-destructive/10 p-3 font-mono text-xs text-destructive">
            {err}
          </pre>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!canSubmit} onClick={handleRollback}>
            {submitting ? "Rolling back…" : "Roll back"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
