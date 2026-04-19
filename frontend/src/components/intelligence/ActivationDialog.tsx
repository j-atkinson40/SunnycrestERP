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
  draft: PromptVersionResponse;
  activeVersion: PromptVersionResponse | null;
  requiresConfirmationText: boolean;
  onActivated: () => void;
}

/**
 * Final gate before a draft goes live. Shows a field-level diff,
 * forces a non-empty changelog, and for platform-global prompts
 * requires the prompt_key typed verbatim.
 */
export function ActivationDialog({
  open,
  onOpenChange,
  prompt,
  draft,
  activeVersion,
  requiresConfirmationText,
  onActivated,
}: Props) {
  const [changelog, setChangelog] = useState(draft.changelog ?? "");
  const [confirmation, setConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const confirmationOk =
    !requiresConfirmationText || confirmation.trim() === prompt.prompt_key;
  const changelogOk = changelog.trim().length > 0;
  const canSubmit = confirmationOk && changelogOk && !submitting;

  async function handleActivate() {
    setSubmitting(true);
    setErr(null);
    try {
      await intelligenceService.activateDraft(prompt.id, draft.id, {
        changelog: changelog.trim(),
        confirmation_text: requiresConfirmationText
          ? confirmation
          : undefined,
      });
      onActivated();
      onOpenChange(false);
    } catch (e) {
      // Surface backend validation errors verbatim
      const anyErr = e as { response?: { data?: { detail?: unknown } } };
      const detail = anyErr.response?.data?.detail;
      if (detail && typeof detail === "object") {
        setErr(JSON.stringify(detail, null, 2));
      } else {
        setErr(
          typeof detail === "string"
            ? detail
            : e instanceof Error
            ? e.message
            : String(e),
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            Activate v{draft.version_number} of{" "}
            <code className="font-mono">{prompt.prompt_key}</code>?
          </DialogTitle>
          <DialogDescription>
            This version will be used for every future execution of this
            prompt.{" "}
            {activeVersion && (
              <>
                The current active version (v{activeVersion.version_number})
                will be retired.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        {prompt.company_id === null && (
          <div className="rounded-md border border-amber-500/60 bg-amber-500/5 p-3 text-xs">
            <div className="flex items-center gap-2 font-medium">
              <AlertTriangle className="h-4 w-4" />
              This is a platform-global prompt — change affects every tenant.
            </div>
          </div>
        )}

        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Diff
          </h3>
          {activeVersion ? (
            <DiffView
              before={activeVersion}
              after={draft}
              beforeLabel={`v${activeVersion.version_number} (active)`}
              afterLabel={`v${draft.version_number} (draft)`}
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              No current active version — diff unavailable.
            </p>
          )}
        </div>

        <label className="block space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Changelog <span className="text-destructive">*</span>
          </span>
          <textarea
            className="h-20 w-full rounded-md border border-input bg-transparent p-2 text-sm"
            value={changelog}
            onChange={(e) => setChangelog(e.target.value)}
            placeholder="Why are you making this change?"
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
          <Button disabled={!canSubmit} onClick={handleActivate}>
            {submitting ? "Activating…" : "Activate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
