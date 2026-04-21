/**
 * Per-entity peek renderers — vitest smoke tests.
 *
 * Each of the 6 renderers takes the typed peek shape and emits
 * label/value pairs. These tests check that:
 *   - Required fields render
 *   - Empty / null fields gracefully omit (PeekField returns null
 *     for nullish values)
 *   - Status badge renders for entities with a status
 *   - Date + currency formatters apply
 *
 * One test per renderer; the shared helpers (PeekField, fmtDate,
 * fmtCurrency, StatusBadge) are exercised transitively.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CasePeekRenderer } from "./CasePeekRenderer";
import { ContactPeekRenderer } from "./ContactPeekRenderer";
import { InvoicePeekRenderer } from "./InvoicePeekRenderer";
import { SalesOrderPeekRenderer } from "./SalesOrderPeekRenderer";
import { SavedViewPeekRenderer } from "./SavedViewPeekRenderer";
import { TaskPeekRenderer } from "./TaskPeekRenderer";


describe("CasePeekRenderer", () => {
  it("renders deceased name + DOD + step", () => {
    render(
      <CasePeekRenderer
        data={{
          case_number: "C-001",
          deceased_name: "John Smith",
          date_of_death: "2026-03-15",
          current_step: "arrangement_conference",
          next_service_date: "2026-03-20",
          status: "active",
        }}
      />,
    );
    expect(screen.getByText("C-001")).toBeInTheDocument();
    expect(screen.getByText("John Smith")).toBeInTheDocument();
    expect(screen.getByText("arrangement conference")).toBeInTheDocument();
    expect(screen.getByText(/active/i)).toBeInTheDocument();
  });

  it("omits null fields gracefully", () => {
    render(
      <CasePeekRenderer
        data={{
          case_number: "C-002",
          deceased_name: null,
          date_of_death: null,
          current_step: "complete",
          next_service_date: null,
          status: "complete",
        }}
      />,
    );
    expect(screen.getByText("C-002")).toBeInTheDocument();
    // Deceased label should not render.
    expect(screen.queryByText("Deceased")).not.toBeInTheDocument();
    expect(screen.queryByText("DOD")).not.toBeInTheDocument();
  });
});


describe("InvoicePeekRenderer", () => {
  it("formats currency + status badge", () => {
    render(
      <InvoicePeekRenderer
        data={{
          invoice_number: "INV-2026-0001",
          status: "sent",
          amount_total: 540,
          amount_paid: 100,
          amount_due: 440,
          customer_name: "Hopkins FH",
          invoice_date: "2026-04-01",
          due_date: "2026-05-01",
        }}
      />,
    );
    expect(screen.getByText("INV-2026-0001")).toBeInTheDocument();
    expect(screen.getByText("Hopkins FH")).toBeInTheDocument();
    // Currency formatter outputs $ — exact format depends on locale but
    // contains "$540" or "$540.00" somewhere.
    expect(
      screen.getByText((c) => c.includes("$540")),
    ).toBeInTheDocument();
    expect(screen.getByText(/sent/i)).toBeInTheDocument();
  });
});


describe("SalesOrderPeekRenderer", () => {
  it("renders order number + line count pluralization", () => {
    render(
      <SalesOrderPeekRenderer
        data={{
          order_number: "SO-001",
          status: "confirmed",
          customer_name: "Riverside FH",
          deceased_name: "Jane Doe",
          order_date: "2026-04-01",
          required_date: "2026-04-08",
          total: 1080,
          line_count: 3,
        }}
      />,
    );
    expect(screen.getByText("SO-001")).toBeInTheDocument();
    expect(screen.getByText("3 items")).toBeInTheDocument();
  });

  it("singular line count uses 'item'", () => {
    render(
      <SalesOrderPeekRenderer
        data={{
          order_number: "SO-002",
          status: "draft",
          customer_name: null,
          deceased_name: null,
          order_date: null,
          required_date: null,
          total: 100,
          line_count: 1,
        }}
      />,
    );
    expect(screen.getByText("1 item")).toBeInTheDocument();
  });
});


describe("TaskPeekRenderer", () => {
  it("renders title-via-header + description + assignee + linked entity", () => {
    render(
      <TaskPeekRenderer
        data={{
          title: "Verify quote",
          description: "Check pricing tiers",
          status: "open",
          priority: "high",
          assignee_name: "Alice",
          due_date: "2026-04-20",
          related_entity_type: "sales_order",
          related_entity_id: "so-1",
        }}
      />,
    );
    expect(screen.getByText("Check pricing tiers")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("sales order")).toBeInTheDocument();
  });
});


describe("ContactPeekRenderer", () => {
  it("renders phone + email as clickable tel:/mailto: links", () => {
    render(
      <ContactPeekRenderer
        data={{
          name: "Taylor Reyes",
          title: "Sales Director",
          role: null,
          phone: "+15551234567",
          email: "taylor@example.com",
          is_primary: null,
          company_name: "Acme",
          master_company_id: "ce-1",
        }}
      />,
    );
    const phoneLink = screen.getByText("+15551234567").closest("a");
    expect(phoneLink).toHaveAttribute("href", "tel:+15551234567");
    const emailLink = screen.getByText("taylor@example.com").closest("a");
    expect(emailLink).toHaveAttribute("href", "mailto:taylor@example.com");
  });
});


describe("SavedViewPeekRenderer", () => {
  it("renders entity type, mode, filter count phrasing", () => {
    render(
      <SavedViewPeekRenderer
        data={{
          title: "My orders",
          description: null,
          entity_type: "sales_order",
          presentation_mode: "table",
          filter_count: 2,
          sort_count: 0,
          visibility: "private",
          owner_user_id: "u-1",
        }}
      />,
    );
    expect(screen.getByText("sales order")).toBeInTheDocument();
    expect(screen.getByText("table")).toBeInTheDocument();
    expect(screen.getByText("2 active")).toBeInTheDocument();
    expect(screen.getByText("default")).toBeInTheDocument();
  });
});
