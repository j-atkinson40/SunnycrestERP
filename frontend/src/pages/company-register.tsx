import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { companyService } from "@/services/company-service";
import { setCompanySlug } from "@/lib/tenant";
import { getApiErrorMessage } from "@/lib/api-error";

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 63);
}

export default function CompanyRegisterPage() {
  const [companyName, setCompanyName] = useState("");
  const [companySlug, setCompanySlugValue] = useState("");
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleCompanyNameChange(value: string) {
    setCompanyName(value);
    if (!slugManuallyEdited) {
      setCompanySlugValue(slugify(value));
    }
  }

  function handleSlugChange(value: string) {
    setSlugManuallyEdited(true);
    setCompanySlugValue(slugify(value));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await companyService.registerCompany({
        company_name: companyName,
        company_slug: companySlug,
        email,
        password,
        first_name: firstName,
        last_name: lastName,
      });

      // Store the slug for tenant context and redirect to login
      setCompanySlug(companySlug);
      // Force a full page reload so the app picks up the new tenant context
      window.location.href = "/login";
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Registration failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Register Your Company</CardTitle>
          <CardDescription>
            Create a company workspace and admin account
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            {/* Company Details */}
            <div className="space-y-2">
              <Label htmlFor="companyName">Company Name</Label>
              <Input
                id="companyName"
                placeholder="Acme Corporation"
                value={companyName}
                onChange={(e) => handleCompanyNameChange(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="companySlug">Company URL Slug</Label>
              <Input
                id="companySlug"
                placeholder="acme"
                value={companySlug}
                onChange={(e) => handleSlugChange(e.target.value)}
                required
                minLength={3}
                maxLength={63}
              />
              <p className="text-xs text-muted-foreground">
                Your workspace will be accessible at{" "}
                <span className="font-mono">
                  {companySlug || "your-company"}.{import.meta.env.VITE_APP_DOMAIN || "platform.app"}
                </span>
              </p>
            </div>

            <div className="my-2 border-t" />

            {/* Admin User Details */}
            <p className="text-sm font-medium text-muted-foreground">
              Admin Account
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="firstName">First Name</Label>
                <Input
                  id="firstName"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="lastName">Last Name</Label>
                <Input
                  id="lastName"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-2">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating company..." : "Create Company"}
            </Button>
            <p className="text-sm text-muted-foreground">
              <Link to="/" className="text-primary underline">
                Back to home
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
