/**
 * Custom ESLint rule — flags widget operational handlers without an
 * `_editMode` gate.
 *
 * Phase R-1.5 (defense-in-depth over SelectionOverlay's capture-phase
 * click suppression): every widget under `frontend/src/components/widgets/`
 * must read `_editMode` somewhere in its source so its operational
 * handlers can no-op when the runtime editor is in edit mode.
 *
 * The rule is HEURISTIC — it doesn't AST-trace per-handler gates.
 * It catches the common shape: a file under `widgets/` that declares
 * any `handle*` or `on*` function taking an event-like argument but
 * never mentions `_editMode` in its source. False positives flag
 * inline with `eslint-disable-next-line` + reason.
 *
 * The capture-phase suppression in SelectionOverlay remains the
 * architectural gate; this rule enforces the defense-in-depth layer.
 */

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Widget operational handlers must read `_editMode` for runtime editor safety.",
      recommended: false,
    },
    schema: [],
    messages: {
      missingGate:
        "Widget file declares operational handler `{{name}}` but does not reference `_editMode`. " +
        "Read `_editMode` (and optionally combine with `useEditMode().isEditing`) and gate the " +
        "handler body with `if (editModeActive) return`. Disable inline with " +
        "`eslint-disable-next-line bridgeable/widget-handlers-edit-mode-gated -- <reason>` " +
        "if the handler legitimately doesn't need a gate.",
    },
  },
  create(context) {
    // Phase R-1.5 — narrow scope to the 6 R-1 registered widgets only.
    // These are the widgets the runtime editor recognizes via
    // `data-component-name`; their operational handlers gate behind
    // `_editMode` as defense-in-depth over SelectionOverlay's capture-
    // phase suppression. Future phases that promote additional widgets
    // to the registry must extend this allowlist + gate the new
    // widget's handlers in lockstep.
    //
    // Per spec discipline: "Better an opinionated narrow rule than a
    // noisy broad one that gets disabled."
    const filename = context.filename ?? context.getFilename()
    const R_1_REGISTERED_WIDGETS = [
      "foundation/TodayWidget.tsx",
      "foundation/OperatorProfileWidget.tsx",
      "foundation/RecentActivityWidget.tsx",
      "foundation/AnomaliesWidget.tsx",
      "manufacturing/VaultScheduleWidget.tsx",
      "manufacturing/LineStatusWidget.tsx",
    ]
    const inScope = R_1_REGISTERED_WIDGETS.some((suffix) =>
      filename.includes(`/components/widgets/${suffix}`),
    )
    if (!inScope) {
      return {}
    }

    // Skip test files — they assert handler behavior with mocked
    // edit-mode props; the handlers under test live in the widget
    // source files, not the test files themselves.
    if (/\.test\.(ts|tsx)$/.test(filename)) {
      return {}
    }

    // Pre-flight: check whether the file source contains the
    // `_editMode` identifier anywhere. If yes, skip — the file has
    // adopted the gate convention and per-handler verification is
    // out of scope for this heuristic.
    const sourceText = context.sourceCode.getText()
    if (sourceText.includes("_editMode")) {
      return {}
    }

    // Otherwise, walk function declarations + arrow functions named
    // `handle*` or `on*` taking ≥1 param. Any match is the canonical
    // "operational handler shape" that should be gated.
    const HANDLER_NAME_RE = /^(handle|on)[A-Z]/

    function reportIfHandler(node, name) {
      if (!name || !HANDLER_NAME_RE.test(name)) return
      // Functions that take 0 params are unlikely to be event handlers
      // — they tend to be navigation memo'd callbacks. R-1.5 still
      // wants those gated, so we don't filter on arity.
      context.report({
        node,
        messageId: "missingGate",
        data: { name },
      })
    }

    return {
      FunctionDeclaration(node) {
        reportIfHandler(node, node.id?.name ?? null)
      },
      VariableDeclarator(node) {
        // Catch `const handleX = () => { … }` + `const onX = function …`.
        if (
          node.id?.type === "Identifier" &&
          (node.init?.type === "ArrowFunctionExpression" ||
            node.init?.type === "FunctionExpression")
        ) {
          reportIfHandler(node, node.id.name)
        }
      },
    }
  },
}
