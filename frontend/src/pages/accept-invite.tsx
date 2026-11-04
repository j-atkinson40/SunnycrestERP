import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { inviteService, type InvitePreview } from "@/services/two-step-service";
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

const MIN_LENGTH = 8;

/**
 * Accept an invitation and set your own password.
 *
 * Payroll 2, ruling 4. Unauthenticated by necessity — she has no credential
 * yet, and the single-use token in the URL is what stands in for one.
 *
 * The page deliberately does NOT sign her in on success. The backend returns
 * no token pair (handing out a session on the strength of a link from an inbox
 * is a weaker thing than a password), so she lands on the sign-in page and
 * types the password she just chose, which is also the fastest way to find out
 * she remembers it.
 */
export default function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();

  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [invalid, setInvalid] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState<{ twoStep: boolean } | null>(null);

  useEffect(() => {
    if (!token) {
      setInvalid(true);
      setLoading(false);
      return;
    }
    inviteService
      .preview(token)
      .then(setPreview)
      .catch(() => setInvalid(true))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < MIN_LENGTH) {
      setError(`Password must be at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Those two passwords don't match.");
      return;
    }
    setSaving(true);
    try {
      const res = await inviteService.accept(token, password);
      setDone({ twoStep: res.two_step_required });
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "That didn't work. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Shell>
        <CardContent className="py-10 text-center text-content-muted">
          Checking your invitation&hellip;
        </CardContent>
      </Shell>
    );
  }

  if (invalid) {
    return (
      <Shell title="This link isn't valid">
        <CardContent className="space-y-4">
          <p className="text-sm text-content-muted">
            It may have expired or already been used. Invitations last 3 days
            and work once. Ask whoever set up your account to send a new one.
          </p>
          <Button onClick={() => navigate("/login")} className="w-full">
            Go to sign in
          </Button>
        </CardContent>
      </Shell>
    );
  }

  if (done) {
    return (
      <Shell title="Your password is set">
        <CardContent className="space-y-4">
          {done.twoStep ? (
            <p className="text-sm text-content-muted">
              Because your account can reach payroll, you&rsquo;ll be asked to
              set up two-step sign-in the first time you sign in. Have your
              phone with you &mdash; it takes about a minute.
            </p>
          ) : (
            <p className="text-sm text-content-muted">
              You can sign in now.
            </p>
          )}
          <Button onClick={() => navigate("/login")} className="w-full">
            Sign in
          </Button>
        </CardContent>
      </Shell>
    );
  }

  return (
    <Shell
      title={`Welcome, ${preview?.first_name ?? ""}`}
      description={
        preview
          ? `Choose a password for your ${preview.company_name} account.`
          : undefined
      }
    >
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>Email</Label>
            {/* Read-only: she cannot change which account this link is for. */}
            <Input value={preview?.email ?? ""} disabled className="mt-1" />
          </div>
          <div>
            <Label htmlFor="pw">
              New password{" "}
              <span className="font-normal text-content-subtle">
                (at least {MIN_LENGTH} characters)
              </span>
            </Label>
            <Input
              id="pw"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="pw2">Confirm password</Label>
            <Input
              id="pw2"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="mt-1"
            />
          </div>
          {error && <p className="text-sm text-status-error">{error}</p>}
          <Button type="submit" disabled={saving} className="w-full">
            {saving ? "Setting your password…" : "Set password"}
          </Button>
          <p className="text-xs text-content-subtle">
            Nobody else can see or set this password &mdash; including whoever
            set up your account.
          </p>
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
