import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { twoStepService, type TwoStepStatus } from "@/services/two-step-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Phase = "loading" | "enrol" | "codes" | "verify";

/**
 * Two-step sign-in: set it up, or pass it.
 *
 * ⚠️ **ONE PAGE FOR BOTH, BECAUSE THE USER CANNOT TELL THEM APART AND SHOULD
 * NOT HAVE TO.** After signing in she holds a token with no `mfa` claim, which
 * reaches only this area and the shell. Whether she needs to ENROL or just to
 * VERIFY is a fact about the server's records, not about what she did — so the
 * page asks, rather than relying on being routed to the right URL.
 *
 * Both paths end the same way: a token pair carrying the claim, swapped into
 * localStorage, and a reload so every client picks it up.
 */
export default function TwoStepSetupPage() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>("loading");
  const [status, setStatus] = useState<TwoStepStatus | null>(null);
  const [secret, setSecret] = useState("");
  const [uri, setUri] = useState("");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [useRecovery, setUseRecovery] = useState(false);

  useEffect(() => {
    twoStepService
      .getStatus()
      .then((s) => {
        setStatus(s);
        if (!s.required) {
          navigate("/", { replace: true });
          return;
        }
        setPhase(s.enrolled ? "verify" : "enrol");
      })
      .catch(() => setError("Couldn't load your sign-in settings."));
  }, [navigate]);

  async function startEnrolment() {
    setError("");
    setBusy(true);
    try {
      const r = await twoStepService.begin();
      setSecret(r.secret);
      setUri(r.provisioning_uri);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Couldn't start setup."));
    } finally {
      setBusy(false);
    }
  }

  function adopt(tokens: { access_token: string; refresh_token: string }) {
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
  }

  async function handleConfirm(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const r = await twoStepService.confirm(code.trim());
      adopt(r);
      setCodes(r.recovery_codes);
      setPhase("codes");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "That code didn't match."));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const r = useRecovery
        ? await twoStepService.useRecoveryCode(code.trim())
        : await twoStepService.verify(code.trim());
      adopt(r);
      // Full reload: the whole app's data was fetched under a token that
      // could not reach most of it.
      window.location.assign("/");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "That code didn't match."));
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  if (phase === "loading") {
    return <Shell><CardContent className="py-10 text-center text-content-muted">
      One moment&hellip;
    </CardContent></Shell>;
  }

  if (phase === "codes") {
    return (
      <Shell
        title="Save these recovery codes"
        description="This is the only time they're shown."
      >
        <CardContent className="space-y-4">
          <p className="text-sm text-content-muted">
            Each code works once, and they&rsquo;re the way back in if you lose
            your phone. Put them in your password manager now &mdash; the
            Passwords app on an iPhone will hold them.
          </p>
          <ul className="grid grid-cols-2 gap-2 rounded-md border border-border-subtle bg-surface-sunken p-3 font-plex-mono text-sm">
            {codes.map((c) => <li key={c}>{c}</li>)}
          </ul>
          <Button
            className="w-full"
            onClick={() => {
              void navigator.clipboard?.writeText(codes.join("\n"));
            }}
            variant="outline"
          >
            Copy all
          </Button>
          <Button className="w-full" onClick={() => window.location.assign("/")}>
            I&rsquo;ve saved them &mdash; continue
          </Button>
        </CardContent>
      </Shell>
    );
  }

  if (phase === "enrol") {
    return (
      <Shell
        title="Set up two-step sign-in"
        description="Your account can reach payroll, so it needs a second step."
      >
        <CardContent className="space-y-4">
          {!secret ? (
            <>
              <p className="text-sm text-content-muted">
                You&rsquo;ll need the authenticator on your phone &mdash; the
                Passwords app on an iPhone, or Google Authenticator. This takes
                about a minute.
              </p>
              <Button className="w-full" onClick={startEnrolment} disabled={busy}>
                {busy ? "Starting…" : "Start"}
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm text-content-muted">
                Add this key to your authenticator, then type the 6-digit code
                it shows.
              </p>
              <div className="rounded-md border border-border-subtle bg-surface-sunken p-3">
                <p className="font-plex-mono text-sm break-all">{secret}</p>
              </div>
              {uri && (
                <a
                  href={uri}
                  className="block text-sm text-accent underline"
                >
                  Open in your authenticator app
                </a>
              )}
              <form onSubmit={handleConfirm} className="space-y-3">
                <div>
                  <Label htmlFor="code">6-digit code</Label>
                  <Input
                    id="code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                    className="mt-1 font-plex-mono tracking-widest"
                  />
                </div>
                {error && <p className="text-sm text-status-error">{error}</p>}
                <Button type="submit" className="w-full" disabled={busy || code.length < 6}>
                  {busy ? "Checking…" : "Finish setup"}
                </Button>
              </form>
            </>
          )}
          {error && !secret && <p className="text-sm text-status-error">{error}</p>}
        </CardContent>
      </Shell>
    );
  }

  // phase === "verify"
  return (
    <Shell
      title="Two-step sign-in"
      description={
        useRecovery
          ? "Enter one of your recovery codes."
          : "Enter the code from your authenticator."
      }
    >
      <CardContent>
        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <Label htmlFor="vcode">{useRecovery ? "Recovery code" : "6-digit code"}</Label>
            <Input
              id="vcode"
              autoFocus
              inputMode={useRecovery ? "text" : "numeric"}
              autoComplete="one-time-code"
              maxLength={useRecovery ? 12 : 6}
              value={code}
              onChange={(e) =>
                setCode(useRecovery ? e.target.value.toUpperCase() : e.target.value.replace(/\D/g, ""))
              }
              className="mt-1 font-plex-mono tracking-widest"
            />
          </div>
          {error && <p className="text-sm text-status-error">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy || !code}>
            {busy ? "Checking…" : "Continue"}
          </Button>
          <button
            type="button"
            className="w-full text-sm text-content-muted underline"
            onClick={() => {
              setUseRecovery(!useRecovery);
              setCode("");
              setError("");
            }}
          >
            {useRecovery
              ? "Use my authenticator instead"
              : "I don't have my phone — use a recovery code"}
          </button>
          {useRecovery && status && (
            <p className="text-xs text-content-subtle">
              {status.unused_recovery_codes} unused{" "}
              {status.unused_recovery_codes === 1 ? "code" : "codes"} left. If
              you&rsquo;re out, ask another administrator to reset your two-step
              setup.
            </p>
          )}
        </form>
      </CardContent>
    </Shell>
  );
}

function Shell({
  title,
  description,
  children,
}: {
  title?: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-base p-4">
      <Card className="w-full max-w-md">
        {title && (
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </CardHeader>
        )}
        {children}
      </Card>
    </div>
  );
}
