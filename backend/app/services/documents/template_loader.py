"""Template loader for the Documents layer — Phase D-2.

D-2 replaced the file-based loader with a DB-backed managed template
registry. Templates now live in `document_templates` +
`document_template_versions` and are resolved with tenant-specific-first
fallback semantics.

Template keys follow the same dotted convention as before:
  <document_type>.<variant>

Examples:
  invoice.modern, invoice.professional, invoice.clean_minimal
  price_list.grouped
  disinterment.release_form
  statement.modern, statement.professional, statement.clean_minimal
  pdf.social_service_certificate
  pdf.legacy_vault_print
  pdf.safety_program_base
  email.statement, email.collections, email.invitation, ...

Callers should use `load(template_key, company_id, db)` — the D-1
signature `load(template_key)` still works as a compatibility shim that
resolves platform-only (company_id=NULL) by opening a short-lived
session, but the preferred path is to pass the session explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document_template import DocumentTemplate, DocumentTemplateVersion


class TemplateNotFoundError(Exception):
    """Raised when a template_key doesn't resolve to a known template
    (or resolves but has no active version)."""


@dataclass
class LoadedTemplate:
    """A template ready to be rendered."""

    template_key: str
    body_template: str
    subject_template: str | None
    output_format: str  # "pdf" | "html" | "text"
    version: int  # version_number
    version_id: str
    template_id: str
    company_id: str | None  # None = platform-global resolution
    variable_schema: dict | None
    css_variables: dict | None
    template_dir: str  # For WeasyPrint base_url — falls back to templates root

    @property
    def is_tenant_override(self) -> bool:
        return self.company_id is not None


# Kept as the base_url for WeasyPrint. Templates are stored in DB now, but
# images/CSS they reference (relative paths) should still resolve against
# the on-disk templates root — which is how it worked in D-1.
_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent.parent / "templates"


def _resolve_version(
    db: Session,
    template_key: str,
    company_id: str | None,
    vertical: str | None = None,
) -> Optional[tuple[DocumentTemplate, DocumentTemplateVersion]]:
    """Return the (template, active_version) pair for the effective
    template.

    Phase D-11 (June 2026): three-tier resolution:
      1. tenant_override (company_id=X, vertical NULL)
      2. vertical_default (company_id NULL, vertical=X) — only if
         `vertical` is provided
      3. platform_default (company_id NULL, vertical NULL)

    First match wins. The vertical tier slots between tenant and
    platform — a tenant in vertical X without their own override
    inherits vertical_default; falls through to platform if no
    vertical_default exists.

    The `vertical` parameter is optional. Callers that don't know the
    tenant's vertical (admin tooling, etc.) get the two-tier
    behavior — same semantics as before D-11.
    """

    def _load_active_version(t: DocumentTemplate) -> DocumentTemplateVersion | None:
        if not t.current_version_id:
            return None
        return (
            db.query(DocumentTemplateVersion)
            .filter(DocumentTemplateVersion.id == t.current_version_id)
            .first()
        )

    # 1. Tenant-specific override
    if company_id is not None:
        tenant_template = (
            db.query(DocumentTemplate)
            .filter(
                DocumentTemplate.template_key == template_key,
                DocumentTemplate.company_id == company_id,
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if tenant_template is not None:
            version = _load_active_version(tenant_template)
            if version is not None:
                return tenant_template, version

    # 2. Vertical default — slots between tenant and platform.
    if vertical is not None:
        vertical_template = (
            db.query(DocumentTemplate)
            .filter(
                DocumentTemplate.template_key == template_key,
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.vertical == vertical,
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if vertical_template is not None:
            version = _load_active_version(vertical_template)
            if version is not None:
                return vertical_template, version

    # 3. Platform default
    platform_template = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.template_key == template_key,
            DocumentTemplate.company_id.is_(None),
            DocumentTemplate.vertical.is_(None),
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if platform_template is None:
        return None
    version = _load_active_version(platform_template)
    if version is None:
        return None
    return platform_template, version


def load(
    template_key: str,
    company_id: str | None = None,
    db: Session | None = None,
    *,
    vertical: str | None = None,
) -> LoadedTemplate:
    """Resolve a template by key with three-tier inheritance.

    Phase D-11: resolution chain is tenant → vertical → platform.
    Pass `vertical` (the tenant's vertical) to enable the vertical
    tier; omit for two-tier (back-compat with pre-D-11 callers).

    Raises TemplateNotFoundError if no tier resolves a template with
    an active version.

    If `db` is None, opens a short-lived session. Callers inside a request
    context should always pass their own session for efficiency.
    """
    close_db = False
    if db is None:
        from app.database import SessionLocal

        db = SessionLocal()
        close_db = True

    try:
        pair = _resolve_version(db, template_key, company_id, vertical)
        if pair is None:
            raise TemplateNotFoundError(
                f"No template registered for key {template_key!r} "
                f"(company_id={company_id!r}). "
                "Either the key is misspelled or the platform seed is missing."
            )
        template, version = pair
        # Choose template_dir: for file-based templates keep the old dir so
        # WeasyPrint can resolve relative includes. For DB-native templates
        # use the templates root as a reasonable base.
        template_dir = _guess_template_dir(template.template_key)
        return LoadedTemplate(
            template_key=template.template_key,
            body_template=version.body_template,
            subject_template=version.subject_template,
            output_format=template.output_format,
            version=version.version_number,
            version_id=version.id,
            template_id=template.id,
            company_id=template.company_id,
            variable_schema=version.variable_schema,
            css_variables=version.css_variables,
            template_dir=str(template_dir),
        )
    finally:
        if close_db:
            db.close()


def load_by_version_id(
    version_id: str,
    *,
    db: Session | None = None,
) -> LoadedTemplate:
    """Resolve a specific `DocumentTemplateVersion` by id.

    D-9 addition — powers the unified render path. The test-render
    endpoint needs to render a specific draft/retired/active version
    rather than "the current active for this key". Loading by id
    skips the current-active lookup and returns exactly the version
    requested.

    Raises TemplateNotFoundError if the version doesn't exist or its
    parent template is soft-deleted.
    """
    close_db = False
    if db is None:
        from app.database import SessionLocal

        db = SessionLocal()
        close_db = True

    try:
        version = (
            db.query(DocumentTemplateVersion)
            .filter(DocumentTemplateVersion.id == version_id)
            .first()
        )
        if version is None:
            raise TemplateNotFoundError(
                f"No template version with id {version_id!r}"
            )
        template = (
            db.query(DocumentTemplate)
            .filter(
                DocumentTemplate.id == version.template_id,
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if template is None:
            raise TemplateNotFoundError(
                f"Template for version {version_id!r} is deleted or missing"
            )
        return LoadedTemplate(
            template_key=template.template_key,
            body_template=version.body_template,
            subject_template=version.subject_template,
            output_format=template.output_format,
            version=version.version_number,
            version_id=version.id,
            template_id=template.id,
            company_id=template.company_id,
            variable_schema=version.variable_schema,
            css_variables=version.css_variables,
            template_dir=str(_guess_template_dir(template.template_key)),
        )
    finally:
        if close_db:
            db.close()


def _guess_template_dir(template_key: str) -> Path:
    """Best-effort base_url for WeasyPrint. File-based templates still map
    to their original directories; DB-native templates use the root."""
    head = template_key.split(".", 1)[0]
    candidate = _TEMPLATES_ROOT / head
    if candidate.is_dir():
        return candidate
    # Plural fallbacks (invoice → invoices, statement → statements, etc.)
    for plural in (f"{head}s", f"{head}es"):
        c = _TEMPLATES_ROOT / plural
        if c.is_dir():
            return c
    return _TEMPLATES_ROOT


def list_template_keys(db: Session | None = None) -> list[str]:
    """Return all registered platform template keys, sorted. Used by admin
    UI dropdowns (e.g. WorkflowBuilder's generate_document step)."""
    close_db = False
    if db is None:
        from app.database import SessionLocal

        db = SessionLocal()
        close_db = True
    try:
        rows = (
            db.query(DocumentTemplate.template_key)
            .filter(
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.deleted_at.is_(None),
                DocumentTemplate.is_active.is_(True),
            )
            .order_by(DocumentTemplate.template_key)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        if close_db:
            db.close()


# Backwards-compatibility shim: D-1 callers that use the old
# `_TEMPLATE_REGISTRY` dict directly (e.g. `statement_pdf_service`) get a
# proxy that always says "yes" for any key. The real check happens inside
# `load()` against the DB. Keep this around as a dict-like so code that
# did `if key in _TEMPLATE_REGISTRY` still works.


class _AllKeysTrueRegistry:
    """`key in registry` is always True — DB lookup does the real gating."""

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str)

    def __iter__(self):
        return iter([])

    def get(self, key, default=None):
        return default


_TEMPLATE_REGISTRY = _AllKeysTrueRegistry()


# ---------------------------------------------------------------------------
# Arc 4d — Scope-cascade resolver returns (Q-ARC4D-3 settled).
#
# Documents transitions Class C (no source metadata) → Class B (per-instance
# source metadata) by exposing the full resolution chain alongside the
# winning template. Inspector tab's SourceBadge + ScopeDiffPopover consume
# this to render hover-reveal cascade visualization.
#
# Parallel canon: themes (`platform_themes.theme_service.resolve_theme` returns
# `{tokens, sources, ...}`), component_configurations (sources field on
# ResolvedConfiguration), workflow_templates (resolver returns `{source,
# source_id, source_version, ...}`), focus_compositions (resolver returns
# `{source, source_id, sources, ...}`). Documents was the holdout returning
# only the winning version.
# ---------------------------------------------------------------------------

from dataclasses import field as _dc_field
from typing import Literal as _Literal


# Canonical scope vocabulary — mirrors frontend
# `lib/visual-editor/source-badge/ScopeDiffPopover.ts::ResolutionScope`.
DocumentResolutionScope = _Literal[
    "platform_default",
    "vertical_default",
    "tenant_override",
]


@dataclass
class DocumentResolutionSourceEntry:
    """One entry in the Documents resolution chain.

    Resolver-order: winning entry FIRST. Parallels themes / component_configs
    / focus_compositions resolver convention (first-match-wins; deepest scope
    that matched wins per §4 Documents canon three-tier inheritance).
    """

    scope: str  # DocumentResolutionScope (Literal not enforceable at field)
    template_id: str
    version_id: str
    version_number: int
    company_id: str | None = None
    vertical: str | None = None


@dataclass
class ResolvedTemplateWithSources:
    """Full resolution result for Arc 4d Class B → C transition.

    - `version`: winning DocumentTemplateVersion (same as legacy return).
    - `template`: winning DocumentTemplate (carries scope discriminator).
    - `source`: winning scope (`tenant_override`/`vertical_default`/
      `platform_default`).
    - `sources`: full resolution chain in resolver order (winning entry
      FIRST). May contain 1-3 entries depending on which tiers have
      templates registered for the key.
    """

    template: DocumentTemplate
    version: DocumentTemplateVersion
    source: str  # DocumentResolutionScope
    sources: list[DocumentResolutionSourceEntry] = _dc_field(
        default_factory=list,
    )


def resolve_with_sources(
    db: Session,
    template_key: str,
    *,
    company_id: str | None = None,
    vertical: str | None = None,
) -> ResolvedTemplateWithSources | None:
    """Arc 4d — return (version, source, sources) triple instead of single
    version. Powers inspector tab's hover-reveal scope diff.

    First-match-wins semantics preserved from `_resolve_version`: walks
    tenant → vertical → platform; deepest scope with an active version
    wins. The non-winning tiers (if registered) also populate `sources` so
    the operator can see what the winning value overrides.

    Returns None if no tier resolves an active version (same contract as
    `_resolve_version`).
    """

    def _load_active_version(
        t: DocumentTemplate,
    ) -> DocumentTemplateVersion | None:
        if not t.current_version_id:
            return None
        return (
            db.query(DocumentTemplateVersion)
            .filter(DocumentTemplateVersion.id == t.current_version_id)
            .first()
        )

    # Collect ALL tier candidates first (regardless of which wins), then
    # decide winner. This lets us populate `sources` with the up-the-chain
    # entries even when the operator's tenant has an override.
    candidates: list[
        tuple[str, DocumentTemplate, DocumentTemplateVersion]
    ] = []

    # 1. Tenant override.
    if company_id is not None:
        tenant_template = (
            db.query(DocumentTemplate)
            .filter(
                DocumentTemplate.template_key == template_key,
                DocumentTemplate.company_id == company_id,
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if tenant_template is not None:
            version = _load_active_version(tenant_template)
            if version is not None:
                candidates.append(("tenant_override", tenant_template, version))

    # 2. Vertical default.
    if vertical is not None:
        vertical_template = (
            db.query(DocumentTemplate)
            .filter(
                DocumentTemplate.template_key == template_key,
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.vertical == vertical,
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if vertical_template is not None:
            version = _load_active_version(vertical_template)
            if version is not None:
                candidates.append(
                    ("vertical_default", vertical_template, version)
                )

    # 3. Platform default.
    platform_template = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.template_key == template_key,
            DocumentTemplate.company_id.is_(None),
            DocumentTemplate.vertical.is_(None),
            DocumentTemplate.deleted_at.is_(None),
        )
        .first()
    )
    if platform_template is not None:
        version = _load_active_version(platform_template)
        if version is not None:
            candidates.append(
                ("platform_default", platform_template, version)
            )

    if not candidates:
        return None

    # Winning entry = first candidate (resolver order: tenant > vertical >
    # platform). Sources list mirrors resolver order; UI consumers (Arc 4d
    # ScopeDiffPopover) render winning entry FIRST with accent.
    winner_scope, winner_template, winner_version = candidates[0]
    sources = [
        DocumentResolutionSourceEntry(
            scope=scope,
            template_id=t.id,
            version_id=v.id,
            version_number=v.version_number,
            company_id=t.company_id,
            vertical=t.vertical,
        )
        for scope, t, v in candidates
    ]
    return ResolvedTemplateWithSources(
        template=winner_template,
        version=winner_version,
        source=winner_scope,
        sources=sources,
    )
