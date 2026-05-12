/**
 * Arc 4b.1a — Documents block-kind configurableProps schemas.
 *
 * Maps each of the 6 canonical block kinds (header, body_section,
 * line_items, totals, signature, conditional_wrapper) to a
 * `Record<string, ConfigPropSchema>` consumed by `BlockConfigEditor`
 * for canonical PropControlDispatcher dispatch.
 *
 * Three simple kinds (`header`, `body_section`, `signature.show_dates`)
 * dispatch entirely through the existing PropControlDispatcher
 * chain (boolean / string / enum / array primitives).
 *
 * Four complex shapes route through Arc 4b.1a's vocabulary extension:
 *   - `line_items.columns` → `tableOfColumns` control
 *   - `totals.rows` → `tableOfRows` control
 *   - `signature.parties` → `listOfParties` control
 *   - `conditional_wrapper.condition` → `conditionalRule` control
 *     (bounded grammar — field/operator/value triple; NOT unbounded
 *     Jinja expression language)
 *
 * The `body_section.body` field is intentionally kept as a `string`
 * with `multiline` hint — rich-text + Jinja-aware editing is the
 * Arc 4b.1b shared-component concern (TextAreaEditor + slash + mention
 * dropdown), not Arc 4b.1a substrate.
 *
 * Backend `block_registry.py` carries an inline JSON-schema-flavored
 * shape with `type` discriminator (boolean / string / enum / array /
 * text). Arc 4b.1a does NOT change the backend shape — frontend
 * declares its own canonical schemas here, and `BlockConfigEditor`
 * uses these instead of the backend's raw shape. Future arcs may
 * collapse the two (backend emits ConfigPropSchema directly); not
 * Arc 4b.1a scope.
 */
import type { ConfigPropSchema } from "../types"


// ─── Header ─────────────────────────────────────────────────────


export const HEADER_BLOCK_SCHEMA: Record<string, ConfigPropSchema> = {
  show_logo: {
    type: "boolean",
    default: true,
    displayLabel: "Show logo",
    description: "Render the tenant logo in the header.",
  },
  logo_position: {
    type: "enum",
    default: "top-left",
    bounds: ["top-left", "top-right", "centered"],
    displayLabel: "Logo position",
  },
  title: {
    type: "string",
    default: "{{ document_title }}",
    displayLabel: "Title",
    description:
      "Document title. May contain Jinja variables (e.g. {{ document_title }}).",
  },
  subtitle: {
    type: "string",
    default: "",
    displayLabel: "Subtitle",
  },
  accent_color: {
    type: "string",
    default: "#9C5640",
    displayLabel: "Accent color",
    description: "Top-border accent color (CSS color string).",
  },
  show_date: {
    type: "boolean",
    default: true,
    displayLabel: "Show date",
  },
}


// ─── Body Section ───────────────────────────────────────────────


export const BODY_SECTION_BLOCK_SCHEMA: Record<string, ConfigPropSchema> = {
  heading: {
    type: "string",
    default: "",
    displayLabel: "Heading",
    description: "Optional section heading.",
  },
  body: {
    type: "string",
    default: "",
    displayLabel: "Body",
    description:
      "Body content. May contain Jinja variables. Rich-text + slash + mention UX ships in Arc 4b.1b.",
  },
  accent_color: {
    type: "string",
    default: "",
    displayLabel: "Heading accent color",
    description: "Optional heading color (CSS color string).",
  },
}


// ─── Line Items ─────────────────────────────────────────────────


export const LINE_ITEMS_BLOCK_SCHEMA: Record<string, ConfigPropSchema> = {
  items_variable: {
    type: "string",
    default: "items",
    displayLabel: "Items variable",
    description: "Name of the Jinja variable that holds the items list.",
  },
  columns: {
    type: "tableOfColumns",
    default: [
      { header: "Description", field: "description" },
      { header: "Qty", field: "quantity" },
      { header: "Unit Price", field: "unit_price" },
      { header: "Total", field: "line_total" },
    ],
    displayLabel: "Columns",
    description:
      "Column definitions. Header text + field path within each item + optional Jinja format filter.",
  },
}


// ─── Totals ─────────────────────────────────────────────────────


export const TOTALS_BLOCK_SCHEMA: Record<string, ConfigPropSchema> = {
  rows: {
    type: "tableOfRows",
    default: [
      { label: "Subtotal", variable: "subtotal" },
      { label: "Tax", variable: "tax" },
      { label: "Total", variable: "total", emphasis: true },
    ],
    displayLabel: "Rows",
    description:
      "Row definitions. Label + Jinja variable + optional emphasis flag (typically the final total).",
  },
}


// ─── Signature ──────────────────────────────────────────────────


export const SIGNATURE_BLOCK_SCHEMA: Record<string, ConfigPropSchema> = {
  parties: {
    type: "listOfParties",
    default: [{ role: "Customer" }],
    displayLabel: "Parties",
    description:
      "One block per party. Each generates a `.sig-anchor` marker for PyMuPDF overlay (Phase D-5 native signing).",
  },
  show_dates: {
    type: "boolean",
    default: true,
    displayLabel: "Show date lines",
    description: "Render a date line under each signature.",
  },
}


// ─── Conditional Wrapper ────────────────────────────────────────


export const CONDITIONAL_WRAPPER_BLOCK_SCHEMA: Record<string, ConfigPropSchema> = {
  label: {
    type: "string",
    default: "",
    displayLabel: "Editor label",
    description:
      "Display label for the editor. The actual condition lives on the block row, NOT in config.",
  },
  // The condition is stored on `document_template_blocks.condition`
  // (not in config). BlockConfigEditor wires a synthetic
  // `__condition__` prop that reads/writes the row's column. The
  // schema entry below declares the editor UX for the row-level
  // condition; the underlying storage is row-column, not config-JSON.
  __condition__: {
    type: "conditionalRule",
    default: { field: "", operator: "equals", value: "" },
    displayLabel: "Condition",
    description:
      "When this expression is true at render time, the wrapped child blocks are rendered. Bounded grammar (field/operator/value).",
  },
}


// ─── Registry ───────────────────────────────────────────────────


/** Map of block kind → frontend configurableProps schema. The
 *  `BlockConfigEditor` resolves the kind's schema here and dispatches
 *  per field through `PropControlDispatcher`. New block kinds
 *  register a schema entry alongside their backend `register_block_kind`
 *  registration.
 *
 *  Block kinds present in the backend but absent here render via a
 *  generic JSON-textarea fallback in `BlockConfigEditor` (forward-
 *  compatible escape hatch). */
export const BLOCK_KIND_CONFIG_SCHEMAS: Record<
  string,
  Record<string, ConfigPropSchema>
> = {
  header: HEADER_BLOCK_SCHEMA,
  body_section: BODY_SECTION_BLOCK_SCHEMA,
  line_items: LINE_ITEMS_BLOCK_SCHEMA,
  totals: TOTALS_BLOCK_SCHEMA,
  signature: SIGNATURE_BLOCK_SCHEMA,
  conditional_wrapper: CONDITIONAL_WRAPPER_BLOCK_SCHEMA,
}


/** Lookup helper — returns the schema entry for a block kind, or
 *  `null` if the kind isn't registered (canonical fallback signal). */
export function getBlockKindConfigSchema(
  kind: string,
): Record<string, ConfigPropSchema> | null {
  return BLOCK_KIND_CONFIG_SCHEMAS[kind] ?? null
}


/** Field-name allow-list per kind for canonical-vs-fallback decisions.
 *  Backend config may carry stray keys (legacy data, mid-migration);
 *  editor only renders the canonical fields declared here. Future
 *  arcs may add field-deprecation warnings via this list. */
export function getCanonicalFieldsForKind(kind: string): string[] {
  const schema = BLOCK_KIND_CONFIG_SCHEMAS[kind]
  return schema ? Object.keys(schema) : []
}
