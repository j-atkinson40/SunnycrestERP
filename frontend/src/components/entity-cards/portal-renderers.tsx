/**
 * Per-entity Brief bodies for EntityPortalCard — S-1 (§4.2).
 *
 * Six shipped types: company_entity (FLAGSHIP), contact, fh_case,
 * sales_order, invoice, product. document + task deliberately
 * omitted in S-1 (thin card / peek-covered) — additive later.
 *
 * Pure presentational: data arrives via the card's self-fetch;
 * pivots emit through onPivot; zero spatial/host logic. Functional
 * color is meaning-only (status pills, overdue terracotta);
 * numerics are tabular per §8.
 */

import { StatusPill } from "@/components/ui/status-pill";
import type { PortalPivot, PortalResponse } from "@/types/entity-portal";

import { PivotLink } from "./EntityPortalCard";

type PivotFn = ((entityType: string, entityId: string) => void) | undefined;

export function PortalBody({
  data,
  onPivot,
}: {
  data: PortalResponse;
  onPivot?: (entityType: string, entityId: string) => void;
}) {
  const p = data.portal;
  switch (data.entity_type) {
    case "company_entity":
      return <CompanyBody p={p} onPivot={onPivot} />;
    case "contact":
      return <ContactBody p={p} pivots={data.pivots} onPivot={onPivot} />;
    case "fh_case":
      return <CaseBody p={p} />;
    case "sales_order":
      return <OrderBody p={p} pivots={data.pivots} onPivot={onPivot} />;
    case "invoice":
      return <InvoiceBody p={p} pivots={data.pivots} onPivot={onPivot} />;
    case "product":
      return <ProductBody p={p} />;
    default:
      return null;
  }
}

// ── Shared primitives ───────────────────────────────────────────────

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-micro uppercase tracking-wide text-content-subtle">
        {label}
      </span>
      <span className="truncate text-caption text-content-base tabular-nums">
        {value}
      </span>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-4 py-2.5 border-b border-border-subtle last:border-b-0 space-y-1.5">
      {title && (
        <p className="font-mono text-micro uppercase tracking-widest text-content-subtle">
          {title}
        </p>
      )}
      {children}
    </div>
  );
}

const money = (v: unknown): string | null =>
  typeof v === "number"
    ? v.toLocaleString(undefined, {
        style: "currency",
        currency: "USD",
      })
    : null;

// ── company_entity — the FLAGSHIP card ──────────────────────────────

function CompanyBody({
  p,
  onPivot,
}: {
  p: Record<string, unknown>;
  onPivot: PivotFn;
}) {
  const roles = (p.roles as string[]) ?? [];
  const contacts =
    (p.contacts as Array<{
      id: string;
      name: string;
      title?: string | null;
    }>) ?? [];
  const orders =
    (p.recent_orders as Array<{
      id: string;
      number: string;
      status: string;
      total?: number | null;
    }>) ?? [];
  const fin = p.financial as
    | {
        outstanding?: number | null;
        overdue_count?: number;
        overdue_total?: number | null;
        payment_terms?: string | null;
      }
    | undefined;

  return (
    <>
      <Section>
        {roles.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {roles.map((r) => (
              <span
                key={r}
                className="rounded-full border border-border-base px-2 py-0.5 text-micro text-content-muted"
              >
                {r}
              </span>
            ))}
          </div>
        )}
        <Row
          label="Location"
          value={[p.city, p.state].filter(Boolean).join(", ") || null}
        />
        <Row label="Phone" value={p.phone as string | null} />
      </Section>

      {contacts.length > 0 && (
        <Section title="Contacts">
          <div className="space-y-1">
            {contacts.map((c) => (
              <div key={c.id}>
                <PivotLink
                  label={c.name}
                  context={c.title}
                  onClick={() => onPivot?.("contact", c.id)}
                />
              </div>
            ))}
          </div>
        </Section>
      )}

      {orders.length > 0 && (
        <Section
          title={`Recent orders${
            typeof p.open_order_count === "number" && p.open_order_count > 0
              ? ` · ${p.open_order_count} open`
              : ""
          }`}
        >
          <div className="space-y-1">
            {orders.slice(0, 3).map((o) => (
              <div
                key={o.id}
                className="flex items-center justify-between gap-2"
              >
                <PivotLink
                  label={o.number}
                  onClick={() => onPivot?.("sales_order", o.id)}
                />
                <span className="flex items-center gap-2">
                  <span className="text-caption text-content-muted tabular-nums">
                    {money(o.total)}
                  </span>
                  <StatusPill status={o.status} className="text-micro" />
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {fin && (
        <Section title="Financial standing">
          <Row label="Outstanding" value={money(fin.outstanding)} />
          {typeof fin.overdue_count === "number" &&
            fin.overdue_count > 0 && (
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-micro uppercase tracking-wide text-content-subtle">
                  Overdue
                </span>
                {/* fn-negative — meaning-only terracotta */}
                <span className="text-caption font-medium text-status-error tabular-nums">
                  {fin.overdue_count} · {money(fin.overdue_total)}
                </span>
              </div>
            )}
          <Row label="Terms" value={fin.payment_terms} />
        </Section>
      )}
      {/* Permission-omitted sections render NOTHING (quiet omit). */}
      {/* v1 coverage note: contacts here are CRM Contact rows only —
          the CustomerContact/VendorContact/FHCaseContact parallel
          tables are not surfaced until the CRM unification. */}
    </>
  );
}

// ── contact ─────────────────────────────────────────────────────────

function ContactBody({
  p,
  pivots,
  onPivot,
}: {
  p: Record<string, unknown>;
  pivots: PortalPivot[];
  onPivot: PivotFn;
}) {
  const companyPivot = pivots.find(
    (pv) => pv.entity_type === "company_entity",
  );
  return (
    <Section>
      <Row label="Title" value={p.title as string | null} />
      <Row label="Phone" value={p.phone as string | null} />
      <Row label="Email" value={p.email as string | null} />
      {companyPivot && (
        <div className="pt-1">
          <PivotLink
            label={companyPivot.label}
            context="Company"
            onClick={() =>
              onPivot?.(companyPivot.entity_type, companyPivot.entity_id)
            }
          />
        </div>
      )}
    </Section>
  );
}

// ── fh_case ─────────────────────────────────────────────────────────

function CaseBody({ p }: { p: Record<string, unknown> }) {
  return (
    <Section>
      <Row label="Case" value={p.case_number as string | null} />
      <Row label="Deceased" value={p.deceased_name as string | null} />
      <Row label="Date of death" value={p.date_of_death as string | null} />
      <Row label="Service" value={p.next_service_date as string | null} />
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-micro uppercase tracking-wide text-content-subtle">
          Status
        </span>
        <StatusPill status={(p.status as string) ?? ""} className="text-micro" />
      </div>
    </Section>
  );
}

// ── sales_order ─────────────────────────────────────────────────────

function OrderBody({
  p,
  pivots,
  onPivot,
}: {
  p: Record<string, unknown>;
  pivots: PortalPivot[];
  onPivot: PivotFn;
}) {
  return (
    <>
      <Section>
        <Row label="Customer" value={p.customer_name as string | null} />
        <Row label="Ordered" value={p.order_date as string | null} />
        <Row label="Required" value={p.required_date as string | null} />
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-micro uppercase tracking-wide text-content-subtle">
            Status
          </span>
          <StatusPill
            status={(p.status as string) ?? ""}
            className="text-micro"
          />
        </div>
      </Section>
      <PivotSection pivots={pivots} onPivot={onPivot} />
    </>
  );
}

// ── invoice ─────────────────────────────────────────────────────────

function InvoiceBody({
  p,
  pivots,
  onPivot,
}: {
  p: Record<string, unknown>;
  pivots: PortalPivot[];
  onPivot: PivotFn;
}) {
  return (
    <>
      <Section>
        <Row label="Customer" value={p.customer_name as string | null} />
        <Row label="Total" value={money(p.total)} />
        <Row label="Balance" value={money(p.balance)} />
        <Row label="Due" value={p.due_date as string | null} />
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-micro uppercase tracking-wide text-content-subtle">
            Status
          </span>
          <StatusPill
            status={(p.status as string) ?? ""}
            className="text-micro"
          />
        </div>
      </Section>
      <PivotSection pivots={pivots} onPivot={onPivot} />
    </>
  );
}

// ── product ─────────────────────────────────────────────────────────

function ProductBody({ p }: { p: Record<string, unknown> }) {
  return (
    <Section>
      <Row label="SKU" value={p.sku as string | null} />
      <Row label="Price" value={money(p.price)} />
      <Row
        label="On hand"
        value={typeof p.on_hand === "number" ? p.on_hand : null}
      />
      {typeof p.description === "string" && p.description && (
        <p className="pt-1 text-caption leading-snug text-content-muted">
          {p.description}
        </p>
      )}
    </Section>
  );
}

// ── shared pivot section ────────────────────────────────────────────

function PivotSection({
  pivots,
  onPivot,
}: {
  pivots: PortalPivot[];
  onPivot: PivotFn;
}) {
  if (pivots.length === 0) return null;
  return (
    <Section title="Related">
      <div className="space-y-1">
        {pivots.slice(0, 4).map((pv) => (
          <div key={`${pv.entity_type}:${pv.entity_id}`}>
            <PivotLink
              label={pv.label}
              context={pv.context}
              onClick={() => onPivot?.(pv.entity_type, pv.entity_id)}
            />
          </div>
        ))}
      </div>
    </Section>
  );
}
