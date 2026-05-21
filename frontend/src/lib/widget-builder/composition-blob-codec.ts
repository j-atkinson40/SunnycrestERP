/**
 * Composition blob codec — defensive parsing + deterministic
 * serialization for the WB-1 composition blob shape.
 *
 * `parseCompositionBlob` is the frontend's structural gate for
 * incoming JSON (from API responses, localStorage drafts, paste-in
 * imports). Throws `CompositionBlobParseError` on malformed input
 * with a list of error messages (matches the backend validator's
 * error-collection shape).
 *
 * `serializeCompositionBlob` produces a stable JSON shape (sorted
 * object keys at every level) so two-blobs-equal-by-structure
 * compare bytewise. Matches the backend's Pydantic v2
 * `model_dump_json(sort_keys=True)` shape semantics — the round-trip
 * test asserts `parseCompositionBlob(JSON.parse(
 *   serializeCompositionBlob(blob)))` returns structurally-equal
 * results.
 *
 * NOTE: this is a STRUCTURAL parser. Semantic validation (root_atom_id
 * existence, dangling children, binding integrity, etc.) lives on
 * the BACKEND validator at
 * `backend/app/services/widget_definitions/validators.py`. WB-2/WB-3
 * may ship a frontend mirror of the semantic checks when the
 * authoring UI needs real-time feedback; WB-1 ships structural-only.
 */

import type {
  AtomNode,
  AtomType,
  BindingRef,
  BindingType,
  CompositionBlob,
  IterationMode,
  TargetSurface,
  VariantDefinition,
  VariantId,
} from "./types/composition-blob";

const ATOM_TYPES: ReadonlySet<AtomType> = new Set([
  "text_label",
  "value_display",
  "icon",
  "status_badge",
  "divider",
  "button",
  "image",
  "conditional_container",
]);

const BINDING_TYPES: ReadonlySet<BindingType> = new Set([
  "literal",
  "field_path",
]);

const ITERATION_MODES: ReadonlySet<IterationMode> = new Set([
  "per_row",
  "single_summary",
  "single_record",
]);

const VARIANT_IDS: ReadonlySet<VariantId> = new Set([
  "glance",
  "brief",
  "detail",
  "deep",
]);

const TARGET_SURFACES: ReadonlySet<TargetSurface> = new Set([
  "focus_canvas",
  "page_canvas",
  "palette_preview",
]);

export class CompositionBlobParseError extends Error {
  errors: string[];

  constructor(errors: string[]) {
    super(errors.length ? errors.join("; ") : "validation failed");
    this.name = "CompositionBlobParseError";
    this.errors = errors;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === "object" && value !== null && !Array.isArray(value)
  );
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((v) => typeof v === "string")
  );
}

function pushFieldError(
  errors: string[],
  path: string,
  message: string,
): void {
  errors.push(`${path}: ${message}`);
}

function parseBindingRef(
  raw: unknown,
  path: string,
  errors: string[],
): BindingRef | null {
  if (!isObject(raw)) {
    pushFieldError(errors, path, "must be an object");
    return null;
  }
  const bindingId = raw.binding_id;
  const bindingType = raw.binding_type;
  if (typeof bindingId !== "string") {
    pushFieldError(errors, `${path}.binding_id`, "must be a string");
  }
  if (typeof bindingType !== "string" || !BINDING_TYPES.has(bindingType as BindingType)) {
    pushFieldError(
      errors,
      `${path}.binding_type`,
      `must be one of ${[...BINDING_TYPES].join(", ")}`,
    );
  }
  if (
    typeof bindingId !== "string" ||
    typeof bindingType !== "string" ||
    !BINDING_TYPES.has(bindingType as BindingType)
  ) {
    return null;
  }
  const ref: BindingRef = {
    binding_id: bindingId,
    binding_type: bindingType as BindingType,
  };
  if (raw.literal_value !== undefined) {
    ref.literal_value = raw.literal_value;
  }
  if (raw.saved_view_id !== undefined) {
    if (typeof raw.saved_view_id !== "string") {
      pushFieldError(errors, `${path}.saved_view_id`, "must be a string");
    } else {
      ref.saved_view_id = raw.saved_view_id;
    }
  }
  if (raw.field_path !== undefined) {
    if (typeof raw.field_path !== "string") {
      pushFieldError(errors, `${path}.field_path`, "must be a string");
    } else {
      ref.field_path = raw.field_path;
    }
  }
  if (raw.iteration_mode !== undefined) {
    if (
      typeof raw.iteration_mode !== "string" ||
      !ITERATION_MODES.has(raw.iteration_mode as IterationMode)
    ) {
      pushFieldError(
        errors,
        `${path}.iteration_mode`,
        `must be one of ${[...ITERATION_MODES].join(", ")}`,
      );
    } else {
      ref.iteration_mode = raw.iteration_mode as IterationMode;
    }
  }
  return ref;
}

function parseAtomNode(
  raw: unknown,
  path: string,
  errors: string[],
): AtomNode | null {
  if (!isObject(raw)) {
    pushFieldError(errors, path, "must be an object");
    return null;
  }
  const atomId = raw.atom_id;
  const atomType = raw.atom_type;
  if (typeof atomId !== "string") {
    pushFieldError(errors, `${path}.atom_id`, "must be a string");
  }
  if (typeof atomType !== "string" || !ATOM_TYPES.has(atomType as AtomType)) {
    pushFieldError(
      errors,
      `${path}.atom_type`,
      `must be one of ${[...ATOM_TYPES].join(", ")}`,
    );
  }
  if (
    typeof atomId !== "string" ||
    typeof atomType !== "string" ||
    !ATOM_TYPES.has(atomType as AtomType)
  ) {
    return null;
  }
  const config = raw.config ?? {};
  if (!isObject(config)) {
    pushFieldError(errors, `${path}.config`, "must be an object");
    return null;
  }
  const node: AtomNode = {
    atom_id: atomId,
    atom_type: atomType as AtomType,
    config,
  };
  if (raw.children !== undefined && raw.children !== null) {
    if (!isStringArray(raw.children)) {
      pushFieldError(errors, `${path}.children`, "must be an array of strings");
    } else {
      node.children = raw.children;
    }
  }
  if (raw.visible_in_variants !== undefined && raw.visible_in_variants !== null) {
    if (!isStringArray(raw.visible_in_variants)) {
      pushFieldError(
        errors,
        `${path}.visible_in_variants`,
        "must be an array of strings",
      );
    } else {
      for (const v of raw.visible_in_variants) {
        if (!VARIANT_IDS.has(v as VariantId)) {
          pushFieldError(
            errors,
            `${path}.visible_in_variants`,
            `unknown variant_id ${JSON.stringify(v)}`,
          );
        }
      }
      node.visible_in_variants = raw.visible_in_variants as VariantId[];
    }
  }
  if (raw.binding_refs !== undefined && raw.binding_refs !== null) {
    if (!isObject(raw.binding_refs)) {
      pushFieldError(errors, `${path}.binding_refs`, "must be an object");
    } else {
      const refs: Record<string, string> = {};
      for (const [k, v] of Object.entries(raw.binding_refs)) {
        if (typeof v !== "string") {
          pushFieldError(
            errors,
            `${path}.binding_refs.${k}`,
            "must be a string",
          );
        } else {
          refs[k] = v;
        }
      }
      node.binding_refs = refs;
    }
  }
  return node;
}

function parseVariantDefinition(
  raw: unknown,
  path: string,
  errors: string[],
): VariantDefinition | null {
  if (!isObject(raw)) {
    pushFieldError(errors, path, "must be an object");
    return null;
  }
  const vid = raw.variant_id;
  const vname = raw.variant_name;
  const ts = raw.target_surface;
  if (typeof vid !== "string") {
    pushFieldError(errors, `${path}.variant_id`, "must be a string");
  }
  if (typeof vname !== "string") {
    pushFieldError(errors, `${path}.variant_name`, "must be a string");
  }
  if (
    typeof ts !== "string" ||
    !TARGET_SURFACES.has(ts as TargetSurface)
  ) {
    pushFieldError(
      errors,
      `${path}.target_surface`,
      `must be one of ${[...TARGET_SURFACES].join(", ")}`,
    );
  }
  if (
    typeof vid !== "string" ||
    typeof vname !== "string" ||
    typeof ts !== "string" ||
    !TARGET_SURFACES.has(ts as TargetSurface)
  ) {
    return null;
  }
  const def: VariantDefinition = {
    variant_id: vid,
    variant_name: vname,
    target_surface: ts as TargetSurface,
  };
  if (raw.canonical_dimensions !== undefined && raw.canonical_dimensions !== null) {
    if (!isObject(raw.canonical_dimensions)) {
      pushFieldError(
        errors,
        `${path}.canonical_dimensions`,
        "must be an object",
      );
    } else {
      const w = raw.canonical_dimensions.width;
      const h = raw.canonical_dimensions.height;
      if (typeof w !== "number" || typeof h !== "number") {
        pushFieldError(
          errors,
          `${path}.canonical_dimensions`,
          "width + height must be numbers",
        );
      } else {
        def.canonical_dimensions = { width: w, height: h };
      }
    }
  }
  return def;
}

/**
 * Defensive parser — accepts any JSON value, returns a typed
 * `CompositionBlob`, throws `CompositionBlobParseError` on malformed
 * shape.
 *
 * STRUCTURAL only — does not enforce semantic cross-references
 * (root_atom_id existence, dangling children refs, etc.). The
 * backend validator at
 * `backend/app/services/widget_definitions/validators.py` is the
 * canonical semantic gate.
 */
export function parseCompositionBlob(raw: unknown): CompositionBlob {
  const errors: string[] = [];
  if (!isObject(raw)) {
    throw new CompositionBlobParseError(["must be an object"]);
  }
  const schemaVersion = raw.schema_version;
  if (schemaVersion !== 1) {
    pushFieldError(
      errors,
      "schema_version",
      `expected 1 for WB Phase 1, got ${JSON.stringify(schemaVersion)}`,
    );
  }
  const rootAtomId = raw.root_atom_id;
  if (typeof rootAtomId !== "string") {
    pushFieldError(errors, "root_atom_id", "must be a string");
  }
  const atomTreeRaw = raw.atom_tree;
  if (!isObject(atomTreeRaw)) {
    pushFieldError(errors, "atom_tree", "must be an object");
    throw new CompositionBlobParseError(errors);
  }
  const atomTree: Record<string, AtomNode> = {};
  for (const [key, val] of Object.entries(atomTreeRaw)) {
    const node = parseAtomNode(val, `atom_tree[${key}]`, errors);
    if (node !== null) {
      atomTree[key] = node;
    }
  }
  const variantsRaw = raw.variants ?? [];
  if (!Array.isArray(variantsRaw)) {
    pushFieldError(errors, "variants", "must be an array");
    throw new CompositionBlobParseError(errors);
  }
  const variants: VariantDefinition[] = [];
  variantsRaw.forEach((vRaw, idx) => {
    const v = parseVariantDefinition(vRaw, `variants[${idx}]`, errors);
    if (v !== null) {
      variants.push(v);
    }
  });
  const bindingsCatalogRaw = raw.bindings_catalog ?? {};
  if (!isObject(bindingsCatalogRaw)) {
    pushFieldError(errors, "bindings_catalog", "must be an object");
    throw new CompositionBlobParseError(errors);
  }
  const bindingsCatalog: Record<string, BindingRef> = {};
  for (const [key, val] of Object.entries(bindingsCatalogRaw)) {
    const ref = parseBindingRef(val, `bindings_catalog[${key}]`, errors);
    if (ref !== null) {
      bindingsCatalog[key] = ref;
    }
  }

  if (errors.length > 0 || schemaVersion !== 1 || typeof rootAtomId !== "string") {
    throw new CompositionBlobParseError(errors);
  }

  return {
    schema_version: 1,
    root_atom_id: rootAtomId,
    atom_tree: atomTree,
    variants,
    bindings_catalog: bindingsCatalog,
  };
}

/**
 * Deterministic key ordering at every level. Recursively sorts
 * object keys (arrays preserve order; primitive values pass
 * through). Matches the backend's `sort_keys=True` shape so
 * cross-side byte-equality holds.
 */
function sortKeysDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortKeysDeep);
  }
  if (isObject(value)) {
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(value).sort()) {
      sorted[key] = sortKeysDeep(value[key]);
    }
    return sorted;
  }
  return value;
}

/**
 * Serialize a CompositionBlob into a deterministic JSON string.
 * Keys at every level sorted lexicographically; same blob
 * structurally yields the same byte sequence.
 */
export function serializeCompositionBlob(blob: CompositionBlob): string {
  return JSON.stringify(sortKeysDeep(blob));
}
