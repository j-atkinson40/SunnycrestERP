import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  signingService,
  type SignerStatus,
} from "@/services/signing-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Public signer experience — no auth. Token from URL is the sole access
 * check. Renders one of 7 flow states based on party/envelope status:
 *
 *   1. Loading
 *   2. Terminal — expired / voided / declined (envelope)
 *   3. Already signed by this party
 *   4. Not-my-turn — sequential routing, previous party still pending
 *   5. Welcome — envelope sent, party hasn't viewed
 *   6. Review / Consent / Sign — main flow (steps within one screen)
 *   7. Complete — this party just signed
 */
export default function SignerLandingPage() {
  const { token = "" } = useParams<{ token: string }>();
  const [status, setStatus] = useState<SignerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // Inline step state (review → consent → sign)
  const [step, setStep] = useState<"welcome" | "review" | "consent" | "sign">(
    "welcome"
  );
  const [consentChecked, setConsentChecked] = useState(false);
  const [signMode, setSignMode] = useState<"draw" | "typed">("draw");
  const [typedName, setTypedName] = useState("");
  const [drawnData, setDrawnData] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [declineOpen, setDeclineOpen] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [finished, setFinished] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const s = await signingService.getSignerStatus(token);
      setStatus(s);
      // If previously-signed, jump straight to finished view
      if (s.party_status === "signed") setFinished(true);
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } };
      if (err.response?.status === 404) {
        setErr("This signing link is invalid or has expired.");
      } else {
        setErr(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <FullScreen>
        <div className="text-muted-foreground">Loading…</div>
      </FullScreen>
    );
  }
  if (err) {
    return (
      <FullScreen>
        <div className="max-w-md space-y-3 rounded-md border border-destructive/40 bg-destructive/5 p-6">
          <h1 className="text-xl font-semibold text-destructive">
            Link unavailable
          </h1>
          <p className="text-sm text-muted-foreground">{err}</p>
        </div>
      </FullScreen>
    );
  }
  if (!status) return null;

  // Terminal states
  if (status.envelope_status === "expired") {
    return (
      <TerminalScreen
        title="This signing request has expired"
        body="The deadline for this envelope has passed. Please contact the sender if you need to re-open it."
      />
    );
  }
  if (status.envelope_status === "voided") {
    return (
      <TerminalScreen
        title="This signing request was cancelled"
        body="The sender cancelled this envelope. You don't need to take any action."
      />
    );
  }
  if (status.envelope_status === "declined") {
    return (
      <TerminalScreen
        title="This signing request was declined"
        body="Another party declined to sign. The envelope is closed."
      />
    );
  }
  if (finished) {
    return (
      <TerminalScreen
        title="Thank you"
        body={
          status.envelope_status === "completed"
            ? "All parties have signed. A copy of the signed document and your Certificate of Completion has been emailed to you."
            : "Your signature has been recorded. You'll receive a copy of the signed document when the remaining parties have signed."
        }
        success
      />
    );
  }
  if (!status.is_my_turn) {
    return (
      <FullScreen>
        <div className="max-w-md space-y-3 rounded-md border p-6 bg-background">
          <h1 className="text-xl font-semibold">
            Waiting for earlier signer
          </h1>
          <p className="text-sm text-muted-foreground">
            This envelope uses sequential routing. Another party needs to
            sign before it's your turn. We'll email you when you're up.
          </p>
          <div className="mt-3 text-xs text-muted-foreground">
            <strong>Document:</strong> {status.envelope_subject}<br />
            <strong>Your role:</strong> {status.party_role.replace(/_/g, " ")}
          </div>
        </div>
      </FullScreen>
    );
  }

  // Main flow — welcome / review / consent / sign
  return (
    <FullScreen>
      <div className="w-full max-w-4xl space-y-6">
        <Header
          companyName={status.company_name}
          signerName={status.party_display_name}
          subject={status.envelope_subject}
          description={status.envelope_description}
          role={status.party_role}
        />
        {step === "welcome" && (
          <WelcomeStep
            status={status}
            onContinue={() => setStep("review")}
            onDecline={() => setDeclineOpen(true)}
          />
        )}
        {step === "review" && (
          <ReviewStep
            token={token}
            onContinue={() => setStep("consent")}
            onDecline={() => setDeclineOpen(true)}
          />
        )}
        {step === "consent" && (
          <ConsentStep
            checked={consentChecked}
            onChange={setConsentChecked}
            onContinue={async () => {
              setSubmitting(true);
              try {
                await signingService.recordConsent(
                  token,
                  DEFAULT_CONSENT_TEXT
                );
                setStep("sign");
              } catch (e) {
                setErr(e instanceof Error ? e.message : String(e));
              } finally {
                setSubmitting(false);
              }
            }}
            onDecline={() => setDeclineOpen(true)}
            submitting={submitting}
          />
        )}
        {step === "sign" && (
          <SignStep
            signMode={signMode}
            setSignMode={setSignMode}
            typedName={typedName}
            setTypedName={setTypedName}
            drawnData={drawnData}
            setDrawnData={setDrawnData}
            signerDefaultName={status.party_display_name}
            onSign={async () => {
              setSubmitting(true);
              try {
                if (signMode === "typed") {
                  await signingService.sign(token, {
                    signature_type: "typed",
                    signature_data: typedName,
                    typed_signature_name: typedName,
                    field_values: {},
                  });
                } else {
                  if (!drawnData) {
                    setErr("Please draw your signature first");
                    setSubmitting(false);
                    return;
                  }
                  await signingService.sign(token, {
                    signature_type: "drawn",
                    // Strip "data:image/png;base64," prefix for the server
                    signature_data: drawnData.replace(
                      /^data:image\/png;base64,/,
                      ""
                    ),
                    field_values: {},
                  });
                }
                setFinished(true);
                await load();
              } catch (e: unknown) {
                const err = e as {
                  response?: { data?: { detail?: string } };
                };
                setErr(
                  err.response?.data?.detail ??
                    (e instanceof Error ? e.message : String(e))
                );
              } finally {
                setSubmitting(false);
              }
            }}
            onDecline={() => setDeclineOpen(true)}
            submitting={submitting}
          />
        )}
      </div>
      {declineOpen && (
        <DeclineModal
          reason={declineReason}
          setReason={setDeclineReason}
          onCancel={() => setDeclineOpen(false)}
          onConfirm={async () => {
            setSubmitting(true);
            try {
              await signingService.decline(token, declineReason);
              await load();
              setDeclineOpen(false);
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
            } finally {
              setSubmitting(false);
            }
          }}
          submitting={submitting}
        />
      )}
    </FullScreen>
  );
}


const DEFAULT_CONSENT_TEXT =
  "I understand that this document will be electronically signed. " +
  "My electronic signature has the same legal effect as a handwritten " +
  "signature. I consent to conducting this transaction electronically " +
  "and receiving electronic records.";


function FullScreen({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 p-4 flex items-start justify-center sm:p-8">
      {children}
    </div>
  );
}

function Header({
  companyName,
  signerName,
  subject,
  description,
  role,
}: {
  companyName: string;
  signerName: string;
  subject: string;
  description: string | null;
  role: string;
}) {
  return (
    <div className="rounded-md border bg-background p-6">
      <div className="text-xs text-muted-foreground uppercase tracking-wider">
        From {companyName}
      </div>
      <h1 className="mt-1 text-2xl font-semibold">{subject}</h1>
      {description && (
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      )}
      <div className="mt-4 flex items-center gap-3 border-t pt-4">
        <div className="text-sm">
          <div>
            <strong>Signing as:</strong> {signerName}
          </div>
          <div className="text-xs text-muted-foreground">
            Role: {role.replace(/_/g, " ")}
          </div>
        </div>
      </div>
    </div>
  );
}

function StepFrame({
  step,
  total,
  title,
  children,
  actions,
}: {
  step: number;
  total: number;
  title: string;
  children: React.ReactNode;
  actions: React.ReactNode;
}) {
  return (
    <div className="rounded-md border bg-background p-6 space-y-4">
      <div className="text-xs text-muted-foreground">
        Step {step} of {total}
      </div>
      <h2 className="text-lg font-semibold">{title}</h2>
      <div>{children}</div>
      <div className="flex gap-2 pt-2">{actions}</div>
    </div>
  );
}

function WelcomeStep({
  status,
  onContinue,
  onDecline,
}: {
  status: SignerStatus;
  onContinue: () => void;
  onDecline: () => void;
}) {
  return (
    <StepFrame
      step={1}
      total={4}
      title="Welcome"
      actions={
        <>
          <Button onClick={onContinue}>Continue</Button>
          <Button variant="ghost" onClick={onDecline}>
            Decline to sign
          </Button>
        </>
      }
    >
      <p className="text-sm">
        Hi {status.party_display_name}, {status.company_name} has requested
        your signature on <strong>{status.envelope_subject}</strong>.
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        You'll review the document, give consent to sign electronically,
        then capture your signature. It should take less than a minute.
      </p>
    </StepFrame>
  );
}

function ReviewStep({
  token,
  onContinue,
  onDecline,
}: {
  token: string;
  onContinue: () => void;
  onDecline: () => void;
}) {
  return (
    <StepFrame
      step={2}
      total={4}
      title="Review the document"
      actions={
        <>
          <Button onClick={onContinue}>I've reviewed it</Button>
          <Button variant="ghost" onClick={onDecline}>
            Decline
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted-foreground">
        Please read the document below before signing. Use the iframe's
        controls to zoom or open in a new tab.
      </p>
      <div className="mt-3 overflow-hidden rounded-md border bg-muted/20">
        <iframe
          src={signingService.getDocumentUrl(token)}
          className="h-[70vh] w-full"
          title="Document"
        />
      </div>
    </StepFrame>
  );
}

function ConsentStep({
  checked,
  onChange,
  onContinue,
  onDecline,
  submitting,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  onContinue: () => void;
  onDecline: () => void;
  submitting: boolean;
}) {
  return (
    <StepFrame
      step={3}
      total={4}
      title="Consent to electronic signing"
      actions={
        <>
          <Button
            onClick={onContinue}
            disabled={!checked || submitting}
          >
            {submitting ? "Recording…" : "Continue to signing"}
          </Button>
          <Button variant="ghost" onClick={onDecline}>
            Decline
          </Button>
        </>
      }
    >
      <div className="rounded-md border bg-muted/20 p-4 text-sm">
        {DEFAULT_CONSENT_TEXT}
      </div>
      <label className="mt-3 flex cursor-pointer items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="mt-1"
        />
        <span>
          I have read and agree to sign this document electronically
          under the United States ESIGN Act.
        </span>
      </label>
    </StepFrame>
  );
}

function SignStep({
  signMode,
  setSignMode,
  typedName,
  setTypedName,
  drawnData,
  setDrawnData,
  signerDefaultName,
  onSign,
  onDecline,
  submitting,
}: {
  signMode: "draw" | "typed";
  setSignMode: (m: "draw" | "typed") => void;
  typedName: string;
  setTypedName: (v: string) => void;
  drawnData: string | null;
  setDrawnData: (v: string | null) => void;
  signerDefaultName: string;
  onSign: () => void;
  onDecline: () => void;
  submitting: boolean;
}) {
  return (
    <StepFrame
      step={4}
      total={4}
      title="Sign"
      actions={
        <>
          <Button onClick={onSign} disabled={submitting}>
            {submitting ? "Signing…" : "Apply signature"}
          </Button>
          <Button variant="ghost" onClick={onDecline}>
            Decline
          </Button>
        </>
      }
    >
      <div className="flex gap-2 border-b">
        <button
          type="button"
          className={`px-4 py-2 text-sm ${
            signMode === "draw"
              ? "border-b-2 border-primary font-semibold"
              : "text-muted-foreground"
          }`}
          onClick={() => setSignMode("draw")}
        >
          Draw
        </button>
        <button
          type="button"
          className={`px-4 py-2 text-sm ${
            signMode === "typed"
              ? "border-b-2 border-primary font-semibold"
              : "text-muted-foreground"
          }`}
          onClick={() => setSignMode("typed")}
        >
          Type
        </button>
      </div>

      {signMode === "draw" ? (
        <DrawCanvas onChange={setDrawnData} drawnData={drawnData} />
      ) : (
        <div className="space-y-2">
          <label className="text-sm font-medium">Type your full name</label>
          <Input
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            placeholder={signerDefaultName}
            className="text-lg"
          />
          {typedName && (
            <div className="rounded-md border bg-muted/20 p-4 text-center">
              <div
                className="text-3xl"
                style={{
                  fontFamily:
                    "'Caveat', 'Brush Script MT', 'Lucida Handwriting', cursive",
                }}
              >
                {typedName}
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                Preview of your typed signature
              </div>
            </div>
          )}
        </div>
      )}
    </StepFrame>
  );
}

function DrawCanvas({
  drawnData,
  onChange,
}: {
  drawnData: string | null;
  onChange: (data: string | null) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef<boolean>(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#111";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, []);

  function getPos(e: React.MouseEvent | React.TouchEvent): {
    x: number;
    y: number;
  } {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const point =
      "touches" in e
        ? e.touches[0] ?? e.changedTouches[0]
        : (e as React.MouseEvent);
    return {
      x: (point.clientX - rect.left) * scaleX,
      y: (point.clientY - rect.top) * scaleY,
    };
  }

  function start(e: React.MouseEvent | React.TouchEvent) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    e.preventDefault();
    drawingRef.current = true;
    const ctx = canvas.getContext("2d")!;
    const { x, y } = getPos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function move(e: React.MouseEvent | React.TouchEvent) {
    if (!drawingRef.current) return;
    e.preventDefault();
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    const { x, y } = getPos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
  }

  function end() {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    const canvas = canvasRef.current;
    if (!canvas) return;
    onChange(canvas.toDataURL("image/png"));
  }

  function clear() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    onChange(null);
  }

  return (
    <div className="space-y-2">
      <div className="rounded-md border bg-white">
        <canvas
          ref={canvasRef}
          width={800}
          height={240}
          className="w-full touch-none"
          style={{ cursor: "crosshair" }}
          onMouseDown={start}
          onMouseMove={move}
          onMouseUp={end}
          onMouseLeave={end}
          onTouchStart={start}
          onTouchMove={move}
          onTouchEnd={end}
        />
      </div>
      <div className="flex items-center justify-between">
        <div className="text-xs text-muted-foreground">
          {drawnData ? "Signature captured" : "Draw your signature above"}
        </div>
        <Button variant="ghost" size="sm" onClick={clear}>
          Clear
        </Button>
      </div>
    </div>
  );
}

function DeclineModal({
  reason,
  setReason,
  onCancel,
  onConfirm,
  submitting,
}: {
  reason: string;
  setReason: (v: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  submitting: boolean;
}) {
  const valid = reason.trim().length >= 10 && reason.trim().length <= 500;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md space-y-3 rounded-md bg-background p-6">
        <h2 className="text-lg font-semibold">Decline to sign?</h2>
        <p className="text-sm text-muted-foreground">
          Declining cancels this signing request. All other signers will
          be notified that you declined.
        </p>
        <textarea
          className="w-full h-24 rounded-md border bg-muted/10 p-2 text-sm"
          placeholder="Reason (10–500 characters)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={!valid || submitting}
            variant="destructive"
          >
            {submitting ? "Declining…" : "Confirm decline"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function TerminalScreen({
  title,
  body,
  success,
}: {
  title: string;
  body: string;
  success?: boolean;
}) {
  return (
    <FullScreen>
      <div
        className={`max-w-md space-y-3 rounded-md border p-6 ${
          success ? "border-green-500/40 bg-green-500/5" : "bg-background"
        }`}
      >
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-muted-foreground">{body}</p>
      </div>
    </FullScreen>
  );
}
