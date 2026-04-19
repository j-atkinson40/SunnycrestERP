"""Template validator — Phase D-3.

Validates draft template content before activation. Parses the Jinja2
AST via `jinja2.meta.find_undeclared_variables` so control-flow
references (e.g. `{% for x in items %}`) resolve to their upstream
variable names, not to the loop-local name.

Activation is blocked on severity="error" issues. Warnings are surfaced
but don't block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    issue_type: str
    message: str
    variable_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "issue_type": self.issue_type,
            "message": self.message,
            "variable_name": self.variable_name,
        }


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {"issues": [i.to_dict() for i in self.issues]}


def extract_template_variables(template_source: str) -> set[str]:
    """Parse a Jinja2 template and return the set of top-level variable
    names it references.

    Uses `jinja2.meta.find_undeclared_variables` which returns variables
    referenced but not defined inside the template itself (loop-locals,
    `{% set %}`-bound names, etc. are automatically excluded).

    Raises `ValueError` on Jinja syntax errors — callers should catch it
    and surface as an `invalid_jinja_syntax` ValidationIssue.
    """
    if not template_source:
        return set()
    # Local import so the module doesn't force Jinja2 at import time
    from jinja2 import Environment, meta
    from jinja2.exceptions import TemplateSyntaxError

    env = Environment()
    try:
        ast = env.parse(template_source)
    except TemplateSyntaxError as exc:
        raise ValueError(f"Template syntax error: {exc.message} (line {exc.lineno})") from exc
    return set(meta.find_undeclared_variables(ast))


def validate_template_content(
    body_template: str,
    subject_template: str | None = None,
    variable_schema: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate template body + optional subject against a declared
    variable schema.

    Checks:
    - Jinja syntax is valid in both body + subject (errors block)
    - Every `{{ var }}` or `{% for x in var %}` reference has a schema
      entry (errors — "undeclared_variable")
    - Every declared non-optional schema entry is actually referenced in
      at least one of body or subject (warnings — "unused_variable")

    A schema entry is "optional" if its value is a dict with
    `{"optional": true}`. This mirrors Phase 3b Intelligence prompt
    validation.
    """
    issues: list[ValidationIssue] = []
    schema = variable_schema or {}
    declared = set(schema.keys())

    # ── Parse body ────────────────────────────────────────────────
    try:
        body_refs = extract_template_variables(body_template)
    except ValueError as exc:
        issues.append(
            ValidationIssue(
                severity="error",
                issue_type="invalid_jinja_syntax",
                message=f"body_template: {exc}",
            )
        )
        body_refs = set()

    # ── Parse subject (optional) ──────────────────────────────────
    subject_refs: set[str] = set()
    if subject_template:
        try:
            subject_refs = extract_template_variables(subject_template)
        except ValueError as exc:
            issues.append(
                ValidationIssue(
                    severity="error",
                    issue_type="invalid_jinja_syntax",
                    message=f"subject_template: {exc}",
                )
            )

    all_refs = body_refs | subject_refs

    # ── Check 1: undeclared variables (ERROR) ─────────────────────
    for var in sorted(all_refs - declared):
        issues.append(
            ValidationIssue(
                severity="error",
                issue_type="undeclared_variable",
                message=(
                    f"Variable {var!r} is referenced in the template but "
                    f"not declared in variable_schema. Add it to the "
                    f"schema or remove the reference."
                ),
                variable_name=var,
            )
        )

    # ── Check 2: unused non-optional variables (WARNING) ──────────
    for var in sorted(declared - all_refs):
        spec = schema.get(var)
        is_optional = isinstance(spec, dict) and bool(spec.get("optional"))
        if is_optional:
            continue
        issues.append(
            ValidationIssue(
                severity="warning",
                issue_type="unused_variable",
                message=(
                    f"Variable {var!r} is declared in variable_schema "
                    f"but never referenced in body or subject. Either "
                    f"use it or mark optional."
                ),
                variable_name=var,
            )
        )

    return ValidationResult(issues=issues)
