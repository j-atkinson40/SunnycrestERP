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
import { documentsV2Service } from "@/services/documents-v2-service";
import { useAuth } from "@/contexts/auth-context";

export default function TemplateForkDialog({
  open,
  onOpenChange,
  templateId,
  templateKey,
  onForked,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  templateId: string;
  templateKey: string;
  onForked: (newTemplateId: string) => void;
}) {
  const { user } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    if (!user?.company_id) return;
    setErr(null);
    setSubmitting(true);
    try {
      const newTemplate = await documentsV2Service.forkToTenant(
        templateId,
        user.company_id
      );
      onForked(newTemplate.id);
      onOpenChange(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Fork {templateKey} to your tenant?</DialogTitle>
          <DialogDescription>
            Creates a tenant-scoped copy of this platform template with
            independent version history. Your tenant's copy will take
            precedence over the platform template for all future renders.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-md border border-blue-500/40 bg-blue-500/5 p-3 text-sm">
          <ul className="ml-4 list-disc space-y-1">
            <li>Tenant version starts at v1 (independent history).</li>
            <li>Content copied from current platform active version.</li>
            <li>You can edit your tenant's copy without super_admin.</li>
            <li>
              Removing your tenant's copy (by retiring it) reverts to the
              platform template.
            </li>
          </ul>
        </div>

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
          <Button onClick={submit} disabled={submitting}>
            {submitting ? "Forking…" : "Fork to tenant"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
