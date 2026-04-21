"""Portal branding — Workflow Arc Phase 8e.2.

Per-tenant branding config read by the public `/portal/<slug>/branding`
endpoint. Storage: `Company.settings_json.portal.*` — no new table.

Fields:
  - display_name: `Company.name` (reused)
  - logo_url: `Company.logo_url` (reused — already existed)
  - brand_color: new; hex string like "#1E40AF"; stored at
    `Company.settings_json.portal.brand_color`
  - footer_text: new; optional; stored at
    `Company.settings_json.portal.footer_text`

"Wash, not reskin" — see SPACES_ARCHITECTURE.md §10.6. Brand color
applies to header bg + primary CTA + bottom nav active indicator.
NOT applied to status colors, typography, surface tokens, border
radius, or motion. Portal stays DESIGN_LANGUAGE-coherent with a
tenant tint on the highest-attention surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.company import Company


# Default brand color — falls through to the platform brass accent.
_DEFAULT_BRAND_COLOR = "#8D6F3A"


@dataclass(frozen=True)
class PortalBranding:
    slug: str
    display_name: str
    logo_url: str | None
    brand_color: str
    footer_text: str | None


def get_portal_branding(db: Session, *, slug: str) -> PortalBranding | None:
    """Return the tenant's portal branding, or None if the slug
    doesn't match an active company. Called from the public
    `/api/v1/portal/<slug>/branding` endpoint (pre-auth)."""
    company = (
        db.query(Company)
        .filter(Company.slug == slug.lower().strip(), Company.is_active.is_(True))
        .first()
    )
    if company is None:
        return None

    portal_settings = (company.settings or {}).get("portal", {}) or {}
    return PortalBranding(
        slug=company.slug,
        display_name=company.name,
        logo_url=company.logo_url,
        brand_color=portal_settings.get("brand_color") or _DEFAULT_BRAND_COLOR,
        footer_text=portal_settings.get("footer_text"),
    )


def set_portal_branding(
    db: Session,
    *,
    company: Company,
    brand_color: str | None = None,
    footer_text: str | None = None,
    logo_url: str | None = None,
) -> PortalBranding:
    """Admin-only setter — updates Company.settings_json.portal.*.
    Phase 8e.2 ships the backend setter; Phase 8e.2.1 ships the UI.
    """
    current = company.settings or {}
    portal_settings = dict(current.get("portal", {}) or {})
    if brand_color is not None:
        portal_settings["brand_color"] = brand_color
    if footer_text is not None:
        portal_settings["footer_text"] = footer_text

    # Store back. set_setting re-serializes.
    company.set_setting("portal", portal_settings)

    if logo_url is not None:
        company.logo_url = logo_url

    db.commit()
    db.refresh(company)
    return get_portal_branding(db, slug=company.slug)  # type: ignore[return-value]
