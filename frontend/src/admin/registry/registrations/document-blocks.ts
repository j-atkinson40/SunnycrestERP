/**
 * Registry registrations — document blocks.
 *
 * Two example blocks for Phase 1: a header block and a signature
 * block. Document templates (D-2 registry, document_renderer)
 * compose blocks during PDF + email rendering.
 *
 * Phase 3 backfill: configurableProps describe the actual visual
 * configuration each block exposes — alignment, accent token,
 * date format, label position. Per-tenant template overrides
 * vary these to match brand identity.
 */

import { registerComponent } from "../register"
import { makePlaceholder } from "./_placeholders"


registerComponent({
  type: "document-block",
  name: "header-block",
  displayName: "Document Header",
  description:
    "Tenant-branded document header. Composes logo + tenant name + document title + optional subtitle. Token-driven palette so tenants override accent without editing block markup.",
  category: "document-blocks",
  verticals: ["all"],
  userParadigms: ["all"],
  consumedTokens: [
    "surface-elevated",
    "border-subtle",
    "content-strong",
    "content-base",
    "accent",
    "text-display",
    "text-h2",
    "text-body",
  ],
  configurableProps: {
    showLogo: {
      type: "boolean",
      default: true,
      displayLabel: "Show tenant logo",
    },
    logoPosition: {
      type: "enum",
      default: "top-left",
      bounds: ["top-left", "top-right", "centered"],
      displayLabel: "Logo position",
    },
    logoMaxWidthPx: {
      type: "number",
      default: 200,
      bounds: [40, 600],
      displayLabel: "Logo max width (px)",
    },
    title: {
      type: "string",
      default: "{{ document_title }}",
      displayLabel: "Title (Jinja-templated)",
      description:
        "Header title. Jinja variables (e.g., {{ document_title }}) resolve at render time.",
      bounds: { maxLength: 120 },
    },
    subtitle: {
      type: "string",
      default: "",
      displayLabel: "Subtitle",
      bounds: { maxLength: 160 },
    },
    accentToken: {
      type: "tokenReference",
      default: "accent",
      tokenCategory: "accent",
      displayLabel: "Accent token",
      description: "Token driving the accent rule + brand bar in the header.",
    },
    accentBarHeight: {
      type: "number",
      default: 4,
      bounds: [0, 16],
      displayLabel: "Accent bar height (px)",
      description:
        "Height of the colored brand bar above the title. Set 0 to hide.",
    },
    alignment: {
      type: "enum",
      default: "left",
      bounds: ["left", "center", "right"],
      displayLabel: "Alignment",
    },
    showSeparatorRule: {
      type: "boolean",
      default: false,
      displayLabel: "Show separator rule below header",
    },
  },
  schemaVersion: 1,
  componentVersion: 2,
  extensions: {
    blockKind: "structural",
    appliesTo: ["pdf", "email"],
  },
})(makePlaceholder("Document Header Block"))


registerComponent({
  type: "document-block",
  name: "signature-block",
  displayName: "Signature Block",
  description:
    "Renders a signature anchor (visible signature line OR invisible anchor for D-5 PyMuPDF overlay). Pairs with platform_action_tokens for native e-signing flows.",
  category: "document-blocks",
  verticals: ["all"],
  userParadigms: ["all"],
  consumedTokens: [
    "border-strong",
    "border-base",
    "content-strong",
    "content-muted",
    "text-body-sm",
    "text-caption",
  ],
  configurableProps: {
    partyRole: {
      type: "enum",
      default: "funeral_home_director",
      bounds: [
        "funeral_home_director",
        "cemetery_rep",
        "next_of_kin",
        "manufacturer",
        "custom",
      ],
      displayLabel: "Party role",
      description:
        "Maps to SignatureField.party_role. Drives sequential routing order on the envelope.",
    },
    showAnchor: {
      type: "boolean",
      default: true,
      displayLabel: "Render visible signature line",
      description:
        "When true, prints a visible line + label. When false, emits an invisible anchor (1pt white text) for PyMuPDF overlay-based placement.",
    },
    showDate: {
      type: "boolean",
      default: true,
      displayLabel: "Show date line",
    },
    dateFormat: {
      type: "enum",
      default: "month-day-year",
      bounds: ["month-day-year", "iso", "long-month-day-year"],
      displayLabel: "Date format",
      description:
        "month-day-year: 5/12/2026 · iso: 2026-05-12 · long: May 12, 2026.",
    },
    label: {
      type: "string",
      default: "Signature",
      displayLabel: "Line label",
      bounds: { maxLength: 32 },
    },
    labelPosition: {
      type: "enum",
      default: "below",
      bounds: ["below", "above", "right"],
      displayLabel: "Label position",
    },
    signatureLineStyle: {
      type: "enum",
      default: "solid",
      bounds: ["solid", "dotted", "dashed"],
      displayLabel: "Signature line style",
    },
    requireDigitalCertificate: {
      type: "boolean",
      default: false,
      displayLabel: "Require digital certificate of completion",
      description:
        "When true, the signing flow generates a Certificate of Completion artifact alongside the signed PDF.",
    },
  },
  schemaVersion: 1,
  componentVersion: 2,
  extensions: {
    blockKind: "interactive",
    appliesTo: ["pdf"],
    pairsWith: "platform_action_tokens",
  },
})(makePlaceholder("Signature Block"))
