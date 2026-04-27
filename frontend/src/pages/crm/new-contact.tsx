/**
 * /vault/crm/contacts/new — modest contact creation form.
 *
 * Phase 4 Tab-fallback target. Users who hit Tab from the NL
 * overlay land here with `?nl=<original input>` query param — the
 * form pre-extracts deterministic fields (name, phone, email) at
 * mount so the director doesn't re-type.
 *
 * Also accessible via Phase 1's `create.contact` command-bar action.
 * Previously declared but unrouted (audit gap); Phase 4 fixes.
 *
 * Company picker uses the existing `/api/v1/company_entities` fuzzy
 * search — not the NL pipeline. This page is the fallback, so it
 * stays conservative and doesn't depend on Phase 4 services.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Loader2, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import apiClient from "@/lib/api-client";

interface CompanyEntityMatch {
  id: string;
  name: string;
}

export default function NewContactPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const nlPrefill = searchParams.get("nl") ?? "";

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [companyQuery, setCompanyQuery] = useState("");
  const [companyOptions, setCompanyOptions] = useState<CompanyEntityMatch[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<CompanyEntityMatch | null>(
    null,
  );
  const [isSearching, setIsSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Parse the NL prefill once on mount ──────────────────────────
  useEffect(() => {
    if (!nlPrefill) return;
    // Email pattern (greedy)
    const emailMatch = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.exec(
      nlPrefill,
    );
    if (emailMatch) setEmail(emailMatch[0].toLowerCase());
    // Phone pattern (US)
    const phoneMatch = /(\+?1?[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})/.exec(
      nlPrefill,
    );
    if (phoneMatch) {
      setPhone(`(${phoneMatch[2]}) ${phoneMatch[3]}-${phoneMatch[4]}`);
    }
    // Name heuristic: first two capitalized tokens that aren't
    // an email / phone / "at Acme"-style segment.
    const nameTokens = nlPrefill
      .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/, "")
      .replace(/\d+/g, "")
      .replace(/\b(at|from|with)\s+[\w\s]+/i, " ")
      .trim()
      .split(/\s+/)
      .filter((t) => /^[A-Z][a-z]+$/.test(t));
    if (nameTokens[0]) setFirstName(nameTokens[0]);
    if (nameTokens[1]) setLastName(nameTokens[1]);
    // Seed the company picker with any "at X" segment
    const atMatch = /\bat\s+([A-Z][\w&.'\- ]+?)(?:\s*(?:,|\.|$|\s+(?:phone|email|office)))/i.exec(
      nlPrefill,
    );
    if (atMatch) setCompanyQuery(atMatch[1].trim());
  }, [nlPrefill]);

  // ── Debounced company search ─────────────────────────────────────
  useEffect(() => {
    if (!companyQuery || companyQuery.length < 2) {
      setCompanyOptions([]);
      return;
    }
    const t = setTimeout(async () => {
      setIsSearching(true);
      try {
        const r = await apiClient.get<{ entities: CompanyEntityMatch[] }>(
          "/company_entities",
          { params: { search: companyQuery, limit: 8 } },
        );
        const results = (r.data as unknown as { entities?: CompanyEntityMatch[] }).entities
          ?? (r.data as unknown as CompanyEntityMatch[]);
        setCompanyOptions(
          Array.isArray(results) ? results : [],
        );
      } catch {
        setCompanyOptions([]);
      } finally {
        setIsSearching(false);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [companyQuery]);

  const canSubmit = useMemo(
    () =>
      !submitting &&
      (firstName.trim().length > 0 || lastName.trim().length > 0) &&
      selectedCompany !== null,
    [submitting, firstName, lastName, selectedCompany],
  );

  async function handleSubmit() {
    if (!selectedCompany) {
      setError("Please pick a company.");
      return;
    }
    const fullName = `${firstName.trim()} ${lastName.trim()}`.trim();
    if (!fullName) {
      setError("Please enter a name.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const r = await apiClient.post<{ id: string }>(
        `/company_entities/${selectedCompany.id}/contacts`,
        {
          name: fullName,
          phone: phone || null,
          email: email || null,
          role: role || null,
          title: role || null,
          is_active: true,
        },
      );
      void r;
      navigate(`/vault/crm/companies/${selectedCompany.id}`);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to create contact");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4 p-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate(-1)}
          className="gap-1 text-muted-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
      </div>
      <h1 className="text-2xl font-semibold">New contact</h1>
      {nlPrefill && (
        <p className="text-xs text-muted-foreground">
          Pre-filled from: <span className="italic">"{nlPrefill}"</span> — edit
          as needed.
        </p>
      )}

      <div className="space-y-3 rounded-md border bg-card p-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label htmlFor="first-name">First name</Label>
            <Input
              id="first-name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              autoFocus
              data-testid="contact-first-name"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="last-name">Last name</Label>
            <Input
              id="last-name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              data-testid="contact-last-name"
            />
          </div>
        </div>

        <div className="space-y-1">
          <Label>Company</Label>
          {selectedCompany ? (
            <div className="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2 text-sm">
              <span data-testid="selected-company">{selectedCompany.name}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedCompany(null)}
              >
                Change
              </Button>
            </div>
          ) : (
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                value={companyQuery}
                onChange={(e) => setCompanyQuery(e.target.value)}
                placeholder="Start typing a company name…"
                className="pl-8"
                data-testid="company-search"
              />
              {companyOptions.length > 0 && (
                <div className="absolute z-10 mt-1 w-full rounded-md border bg-popover shadow-sm">
                  {companyOptions.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className="block w-full px-3 py-2 text-left text-sm hover:bg-accent-subtle"
                      onClick={() => {
                        setSelectedCompany(c);
                        setCompanyOptions([]);
                      }}
                      data-testid={`company-option-${c.id}`}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              )}
              {isSearching && (
                <Loader2 className="absolute right-2.5 top-2.5 size-4 animate-spin text-muted-foreground" />
              )}
            </div>
          )}
        </div>

        <div className="space-y-1">
          <Label htmlFor="role">Role / title</Label>
          <Input
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Office manager"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label htmlFor="phone">Phone</Label>
            <Input
              id="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="(555) 123-4567"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
            />
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => navigate(-1)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {submitting ? "Creating…" : "Create contact"}
          </Button>
        </div>
      </div>
    </div>
  );
}
