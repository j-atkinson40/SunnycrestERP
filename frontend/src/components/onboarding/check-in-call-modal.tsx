import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

interface CheckInCallModalProps {
  open: boolean;
  onClose: (scheduled: boolean) => void;
}

export function CheckInCallModal({ open, onClose }: CheckInCallModalProps) {
  return (
    <Dialog open={open} onOpenChange={(open) => { if (!open) onClose(false); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Schedule Your Free Check-In Call</DialogTitle>
          <DialogDescription>
            Every new customer gets a complimentary 30-minute call with our
            onboarding team. We'll review your setup, answer questions, and share
            tips to help your team get the most out of the platform.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <div className="rounded-lg bg-muted/50 p-4 space-y-2">
            <h4 className="text-sm font-medium">What we'll cover:</h4>
            <ul className="space-y-1.5 text-xs text-muted-foreground">
              <li className="flex items-start gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-primary" />
                Review your company configuration and module setup
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-primary" />
                Walk through any features you'd like help with
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-primary" />
                Answer questions about integrations and data import
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-primary" />
                Share best practices from similar businesses
              </li>
            </ul>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onClose(false)}>
            I'm all set, no thanks
          </Button>
          <Button
            onClick={() => {
              // In production, this would open Calendly or a scheduling tool
              window.open("https://calendly.com", "_blank");
              onClose(true);
            }}
          >
            Schedule a Call
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
