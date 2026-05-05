"""Static configuration for vault personalization options.

Canonical 4-options vocabulary per BRIDGEABLE_MASTER.md §3.26.11.12.19.2 (Path C canon update):

- ``legacy_print`` — photo-based legacy print design (91 named Wilbert prints + per-tenant custom)
- ``physical_nameplate`` — physical nameplate engraving on vault
- ``physical_emblem`` — physical emblem affixed to vault
- ``vinyl`` — vinyl-applied personalization (canonical name; per-tenant display label customization
  per Q1 — e.g., Wilbert tenant displays "Life's Reflections", Sunnycrest tenant displays "Vinyl")

Substrate canonicalization migrated to canonical vocabulary at r74_personalization_vocabulary_canonicalization
(Step-0 migration of Personalization Studio implementation arc).

Per-tenant display label customization stored at ``Company.settings_json.personalization_display_labels``
JSONB (canonical Workshop Tune mode customization within canonical 4 options vocabulary per
§3.26.11.12.19 — Tune mode operations are parameter overrides; cannot add/remove canonical option types).

Wilbert option lists below are canonical Wilbert standard options that change infrequently.
No database storage needed — the option lists are defined here.
"""

from __future__ import annotations

# Canonical option type values per §3.26.11.12.19.2.
# Values stored verbatim in case_merchandise.vault_personalization JSONB +
# order_personalization_tasks.task_type string column.
OPTION_TYPE_LEGACY_PRINT = "legacy_print"
OPTION_TYPE_PHYSICAL_NAMEPLATE = "physical_nameplate"
OPTION_TYPE_PHYSICAL_EMBLEM = "physical_emblem"
OPTION_TYPE_VINYL = "vinyl"

# Canonical 4-options vocabulary canonical at canon level.
CANONICAL_OPTION_TYPES: tuple[str, ...] = (
    OPTION_TYPE_LEGACY_PRINT,
    OPTION_TYPE_PHYSICAL_NAMEPLATE,
    OPTION_TYPE_PHYSICAL_EMBLEM,
    OPTION_TYPE_VINYL,
)


PERSONALIZATION_TIERS: dict = {
    "wilbert_standard": {
        "description": "Full Wilbert personalization",
        "available_types": [
            OPTION_TYPE_LEGACY_PRINT,
            OPTION_TYPE_VINYL,
            OPTION_TYPE_PHYSICAL_NAMEPLATE,
            OPTION_TYPE_PHYSICAL_EMBLEM,
        ],
        "mutual_exclusive_groups": [
            [OPTION_TYPE_LEGACY_PRINT, OPTION_TYPE_VINYL],
            [OPTION_TYPE_LEGACY_PRINT, OPTION_TYPE_PHYSICAL_NAMEPLATE],
            [OPTION_TYPE_LEGACY_PRINT, OPTION_TYPE_PHYSICAL_EMBLEM],
            [OPTION_TYPE_VINYL, OPTION_TYPE_PHYSICAL_NAMEPLATE],
            [OPTION_TYPE_VINYL, OPTION_TYPE_PHYSICAL_EMBLEM],
        ],
    },
    "continental": {
        "description": "Nameplate only",
        "available_types": [OPTION_TYPE_PHYSICAL_NAMEPLATE],
        "mutual_exclusive_groups": [],
    },
    "salute": {
        "description": "Nameplate and cover emblem",
        "available_types": [OPTION_TYPE_PHYSICAL_NAMEPLATE, OPTION_TYPE_PHYSICAL_EMBLEM],
        "mutual_exclusive_groups": [],
    },
    "urn_vault": {
        "description": "Full personalization with urn prints",
        "available_types": [
            OPTION_TYPE_LEGACY_PRINT,
            OPTION_TYPE_VINYL,
            OPTION_TYPE_PHYSICAL_NAMEPLATE,
            OPTION_TYPE_PHYSICAL_EMBLEM,
        ],
        "mutual_exclusive_groups": [
            [OPTION_TYPE_LEGACY_PRINT, OPTION_TYPE_VINYL],
            [OPTION_TYPE_LEGACY_PRINT, OPTION_TYPE_PHYSICAL_NAMEPLATE],
            [OPTION_TYPE_LEGACY_PRINT, OPTION_TYPE_PHYSICAL_EMBLEM],
            [OPTION_TYPE_VINYL, OPTION_TYPE_PHYSICAL_NAMEPLATE],
            [OPTION_TYPE_VINYL, OPTION_TYPE_PHYSICAL_EMBLEM],
        ],
        "uses_urn_prints": True,
    },
}

# Per-tenant default display labels.
# Tenants override via Company.settings_json.personalization_display_labels.
# Canonical example per Q1: Wilbert tenant overrides VINYL display label to "Life's Reflections".
DEFAULT_DISPLAY_LABELS: dict[str, str] = {
    OPTION_TYPE_LEGACY_PRINT: "Legacy Print",
    OPTION_TYPE_PHYSICAL_NAMEPLATE: "Nameplate",
    OPTION_TYPE_PHYSICAL_EMBLEM: "Cover Emblem",
    OPTION_TYPE_VINYL: "Vinyl",
}


# Canonical Wilbert vinyl/Life's Reflections symbol catalog — applies to canonical ``vinyl`` option
# type. Wilbert-tenant operators see "Life's Reflections" display label per per-tenant
# customization; canonical substrate value is ``vinyl``.
VINYL_SYMBOLS: list[str] = [
    "Cross",
    "Star of David",
    "Praying Hands",
    "Floral",
    "Patriotic / American Flag",
    "Masonic",
    "Dove",
    "Other (specify in notes)",
]

# Backward-compat alias preserved for callers referencing legacy attribute name during
# transition window. Removed at next refactor pass when no callers remain.
LIFES_REFLECTIONS_SYMBOLS = VINYL_SYMBOLS

LEGACY_SERIES_PRINTS: list[dict] = [
    {
        "category": "Religious & Spiritual",
        "prints": [
            "American Flag", "Canadian Flag",
            "Cross — Gold", "Cross — Silver", "Cross — White Horizontal",
            "Crucifix — Bible", "Forever in God's Care",
            "Going Home", "Irish Blessing", "Irish Blessing — No Poem",
            "Jesus", "Jesus at Dawn", "Jewish 1", "Jewish 2",
            "Our Lady of Guadalupe", "Pieta",
            "Stained Glass — Gold Marble", "Stained Glass — White Marble",
            "Star of David — Gold", "Star of David — White", "Three Crosses",
        ],
    },
    {
        "category": "Nature & Landscapes",
        "prints": [
            "Autumn Lake", "Bridge 1", "Bridge 2", "Cardinal", "Clouds",
            "Country Road", "Dock", "Footprints", "Footprints with Poem",
            "Green Field & Barn", "Lighthouse", "Marble — Gold", "Marble — White",
            "Red Barn", "Sunrise-Sunset", "Sunrise-Sunset 2",
            "Tropical", "Whitetail Buck",
        ],
    },
    {
        "category": "Floral",
        "prints": ["Roses on Silk", "Red Roses", "Yellow Roses"],
    },
    {
        "category": "Occupations & Hobbies",
        "prints": [
            "Combine", "Corn", "EMT", "Farm Field with Tractor",
            "Father 1", "Father 2", "Firefighter", "Fisherman",
            "Fisherman with Dog", "Golf Course", "Golfer",
            "Gone Fishing", "Horses", "Mother 1", "Mother 2",
            "Motorcycle 1", "Motorcycle 2", "Music", "Police",
            "School", "Tobacco Barn", "Tobacco Field",
        ],
    },
]

_CDN = "https://www.wilbert.com/assets/1/14"

LEGACY_PRINT_IMAGE_URLS: dict[str, str] = {
    "American Flag": f"{_CDN}/WLP-AmFlag-L2-750.jpg",
    "Crucifix — Bible": f"{_CDN}/WLP-Crucifix-Bible-L2-750.jpg",
    "Forever in God's Care — Cross": f"{_CDN}/WLP-ForeverGodsCareCross-L2-750.jpg",
    "Forever in God's Care — Sunset": f"{_CDN}/WLP-ForeverGodsCareSunset-L2-750.jpg",
    "Forever in Our Hearts — Cloud": f"{_CDN}/WLP-ForeverOurHeartsCloud-L2-750.jpg",
    "Forever in Our Hearts — Sunset": f"{_CDN}/WLP-ForeverOurHeartsSunset-L2-750.jpg",
    "Going Home": f"{_CDN}/WLP-GoingHome-L2-750.jpg",
    "Irish Blessing": f"{_CDN}/WLP-IrishBlessing-L2-750.jpg",
    "Jesus": f"{_CDN}/WLP-Jesus-L2-750.jpg",
    "Jesus at Dawn": f"{_CDN}/WLP-Jesus-dwn-L2-750.jpg",
    "Jewish": f"{_CDN}/WLP-Jewish-L2-750.jpg",
    "Three Crosses": f"{_CDN}/WLP-3Crosses-L2-750.jpg",
    "Autumn Lake": f"{_CDN}/WLP-AutumnLake-L2-750.jpg",
    "Bridge 1": f"{_CDN}/WLP-Bridge-1-L2-750.jpg",
    "Bridge 2": f"{_CDN}/WLP-Bridge-2-L2-750.jpg",
    "Clouds": f"{_CDN}/WLP-Clouds-L2-750.jpg",
    "Country Road": f"{_CDN}/WLP-CountryRoad-L2-750.jpg",
    "Dock": f"{_CDN}/WLP-Dock-L2-750.jpg",
    "Field and Barn": f"{_CDN}/WLP-FieldRBarn-L2-750.jpg",
    "Footprints": f"{_CDN}/WLP-Footprints-L2-750.jpg",
    "Footprints with Poem": f"{_CDN}/WLP-FootprintsPoem-L2-750.jpg",
    "Lighthouse": f"{_CDN}/WLP-Lighthouse-L2-750.jpg",
    "Red Barn": f"{_CDN}/WLP-RedBarn-L2-750.jpg",
    "Sunrise": f"{_CDN}/WLP-Sunrise-L2-750.jpg",
    "Sunset": f"{_CDN}/WLP-Sunset-L2-750.jpg",
    "Tropical": f"{_CDN}/WLP-Tropical-Island-L2-750.jpg",
    "Roses on Silk": f"{_CDN}/WLP-Roses_On_Silk-L2-750.jpg",
    "Red Roses": f"{_CDN}/WLP-R-Roses-L2-750.jpg",
    "Yellow Roses": f"{_CDN}/WLP-Y-Roses-L2-750.jpg",
    "Combine": f"{_CDN}/WLP-Combine-L2-750.jpg",
    "Corn": f"{_CDN}/WLP-Corn-L2-750.jpg",
    "EMT": f"{_CDN}/WLP-EMT-L2-750.jpg",
    "Farm Field with Tractor": f"{_CDN}/WLP-SunsetFarmFieldTractor-L2-750.jpg",
    "Father 1": f"{_CDN}/WLP-Father-1-L2-750.jpg",
    "Father 2": f"{_CDN}/WLP-Father-2-L2-750.jpg",
    "Firefighter": f"{_CDN}/WLP-Firefighter-L2-750.jpg",
    "Fisherman": f"{_CDN}/WLP-Fisherman-L2-750.jpg",
    "Fisherman with Dog": f"{_CDN}/WLP-Fisherman-Dog-L2-750.jpg",
    "Golf Course": f"{_CDN}/WLP-GolfCourse-L2-750.jpg",
    "Golfer": f"{_CDN}/WLP-Golfer-L2-750.jpg",
    "Gone Fishing": f"{_CDN}/WLP-GoneFishin-L2-750.jpg",
    "Horses": f"{_CDN}/WLP-Horse-L2-750.jpg",
    "Mother 1": f"{_CDN}/WLP-Mother-1-L2-750.jpg",
    "Mother 2": f"{_CDN}/WLP-Mother-2-L2-750.jpg",
    "Motorcycle 1": f"{_CDN}/WLP-Motorcycle_1-L2-750.jpg",
    "Motorcycle 2": f"{_CDN}/WLP-Motorcycle_2-L2-750.jpg",
    "Music": f"{_CDN}/WLP-Music-L2-750.jpg",
    "Police": f"{_CDN}/WLP-Police-L2-750.jpg",
    "School": f"{_CDN}/WLP-School-L2-750.jpg",
    "Tobacco Barn": f"{_CDN}/WLP-TobBarn-L2-750.jpg",
    "Tobacco Field": f"{_CDN}/WLP-TobaccoField-750.jpg",
}


def get_full_config() -> dict:
    """Return the complete personalization config for the frontend.

    Canonical 4-options vocabulary per §3.26.11.12.19.2. Per-tenant display label customization
    NOT applied at this function — callers consume canonical substrate values + apply per-tenant
    display labels at rendering layer via ``get_display_label_for_tenant()``.
    """
    return {
        "tiers": PERSONALIZATION_TIERS,
        "canonical_option_types": list(CANONICAL_OPTION_TYPES),
        "default_display_labels": DEFAULT_DISPLAY_LABELS,
        "vinyl_symbols": VINYL_SYMBOLS,
        # Backward-compat alias preserved during transition window.
        "lifes_reflections_symbols": VINYL_SYMBOLS,
        "legacy_prints": LEGACY_SERIES_PRINTS,
        "legacy_print_images": LEGACY_PRINT_IMAGE_URLS,
    }


def get_display_label_for_tenant(option_type: str, company_settings_json: dict | None) -> str:
    """Return per-tenant display label for canonical option type.

    Canonical substrate value (``option_type``) maps to per-tenant display label via
    ``Company.settings_json.personalization_display_labels`` JSONB override; falls back to
    ``DEFAULT_DISPLAY_LABELS`` per canonical default.

    Per Q1 canonical resolution: Wilbert tenant overrides ``vinyl`` display label to
    "Life's Reflections"; Sunnycrest tenant displays default "Vinyl"; cross-tenant
    DocumentShare grant payload carries canonical ``vinyl`` substrate value (per-tenant
    display labels apply at rendering layer only, NOT at substrate persistence layer).

    Args:
        option_type: Canonical option type per ``CANONICAL_OPTION_TYPES``.
        company_settings_json: Company.settings_json dict (may be None).

    Returns:
        Display label string (per-tenant override OR canonical default).
    """
    if option_type not in CANONICAL_OPTION_TYPES:
        # Defense against caller passing legacy vocabulary post-r74 migration.
        # Return option_type verbatim so callers see the unexpected value.
        return option_type

    if company_settings_json:
        overrides = company_settings_json.get("personalization_display_labels") or {}
        if isinstance(overrides, dict):
            override = overrides.get(option_type)
            if override and isinstance(override, str):
                return override

    return DEFAULT_DISPLAY_LABELS.get(option_type, option_type)


def set_display_labels_for_tenant(
    company_settings_json: dict, display_labels: dict[str, str]
) -> dict:
    """Set per-tenant display labels canonically at ``Company.settings_json``.

    Mutates the provided ``company_settings_json`` dict in-place + returns it. Caller commits
    via SQLAlchemy ``flag_modified(company, "settings_json")`` after invocation.

    Per Workshop Tune mode customization canonical at §3.26.11.12.19 — display label customization
    is parameter override on canonical 4 options vocabulary; cannot add/remove canonical option types.

    Args:
        company_settings_json: Company.settings_json dict (mutated in-place).
        display_labels: Map from canonical option_type → tenant display label string.

    Returns:
        Mutated company_settings_json dict.

    Raises:
        ValueError: If display_labels contains key NOT in CANONICAL_OPTION_TYPES.
    """
    for option_type in display_labels:
        if option_type not in CANONICAL_OPTION_TYPES:
            raise ValueError(
                f"Display label for {option_type!r} rejected — only canonical option types "
                f"in {CANONICAL_OPTION_TYPES} permitted per Workshop Tune mode discipline. "
                f"Adding/removing canonical option types canonically deferred per §3.26.11.12.19.2 "
                f"canonical options vocabulary scope freeze."
            )

    existing = company_settings_json.get("personalization_display_labels") or {}
    if not isinstance(existing, dict):
        existing = {}
    existing.update(display_labels)
    company_settings_json["personalization_display_labels"] = existing
    return company_settings_json


def validate_personalization(
    personalization_data: list[dict], personalization_tier: str
) -> dict:
    """Validate personalization selections against tier rules.

    Canonical 4-options vocabulary per §3.26.11.12.19.2 enforced — ``type`` field values must
    match canonical vocabulary post-r74 substrate canonicalization migration.
    """
    tier = PERSONALIZATION_TIERS.get(personalization_tier)
    if not tier:
        return {"valid": False, "errors": [f"Unknown tier: {personalization_tier}"]}

    available = set(tier["available_types"])
    selected_types = [p.get("type") for p in personalization_data if p.get("type")]
    errors = []

    for t in selected_types:
        if t not in available:
            # Defense against legacy vocabulary leaking through (e.g., pre-r74 cached state).
            # Surface canonical vocabulary expectation in error message.
            if t in {"nameplate", "cover_emblem", "lifes_reflections"}:
                errors.append(
                    f"'{t}' is legacy vocabulary; canonical post-r74 vocabulary required "
                    f"(canonical {CANONICAL_OPTION_TYPES})"
                )
            else:
                errors.append(f"'{t}' is not available for {personalization_tier} tier")

    for group in tier.get("mutual_exclusive_groups", []):
        matches = [t for t in selected_types if t in group]
        if len(matches) > 1:
            errors.append(f"Cannot combine {' and '.join(matches)}")

    return {"valid": len(errors) == 0, "errors": errors}
