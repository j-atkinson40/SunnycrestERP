"""Static configuration for vault personalization options.

These are Wilbert standard options that change infrequently.
No database storage needed — the option lists are defined here.
"""

PERSONALIZATION_TIERS: dict = {
    "wilbert_standard": {
        "description": "Full Wilbert personalization",
        "available_types": ["legacy_print", "lifes_reflections", "nameplate", "cover_emblem"],
        "mutual_exclusive_groups": [
            ["legacy_print", "lifes_reflections"],
            ["legacy_print", "nameplate"],
            ["legacy_print", "cover_emblem"],
            ["lifes_reflections", "nameplate"],
            ["lifes_reflections", "cover_emblem"],
        ],
    },
    "continental": {
        "description": "Nameplate only",
        "available_types": ["nameplate"],
        "mutual_exclusive_groups": [],
    },
    "salute": {
        "description": "Nameplate and cover emblem",
        "available_types": ["nameplate", "cover_emblem"],
        "mutual_exclusive_groups": [],
    },
    "urn_vault": {
        "description": "Full personalization with urn prints",
        "available_types": ["legacy_print", "lifes_reflections", "nameplate", "cover_emblem"],
        "mutual_exclusive_groups": [
            ["legacy_print", "lifes_reflections"],
            ["legacy_print", "nameplate"],
            ["legacy_print", "cover_emblem"],
            ["lifes_reflections", "nameplate"],
            ["lifes_reflections", "cover_emblem"],
        ],
        "uses_urn_prints": True,
    },
}

LIFES_REFLECTIONS_SYMBOLS: list[str] = [
    "Cross",
    "Star of David",
    "Praying Hands",
    "Floral",
    "Patriotic / American Flag",
    "Masonic",
    "Dove",
    "Other (specify in notes)",
]

LEGACY_SERIES_PRINTS: list[dict] = [
    {
        "category": "Religious & Spiritual",
        "prints": [
            "American Flag", "Crucifix — Bible",
            "Forever in God's Care — Cross", "Forever in God's Care — Sunset",
            "Forever in Our Hearts — Cloud", "Forever in Our Hearts — Sunset",
            "Going Home", "Irish Blessing", "Jesus", "Jesus at Dawn",
            "Jewish", "Three Crosses",
        ],
    },
    {
        "category": "Nature & Landscapes",
        "prints": [
            "Autumn Lake", "Bridge 1", "Bridge 2", "Clouds",
            "Country Road", "Dock", "Field and Barn", "Footprints",
            "Footprints with Poem", "Lighthouse", "Red Barn",
            "Sunrise", "Sunset", "Tropical",
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
    """Return the complete personalization config for the frontend."""
    return {
        "tiers": PERSONALIZATION_TIERS,
        "lifes_reflections_symbols": LIFES_REFLECTIONS_SYMBOLS,
        "legacy_prints": LEGACY_SERIES_PRINTS,
        "legacy_print_images": LEGACY_PRINT_IMAGE_URLS,
    }


def validate_personalization(
    personalization_data: list[dict], personalization_tier: str
) -> dict:
    """Validate personalization selections against tier rules."""
    tier = PERSONALIZATION_TIERS.get(personalization_tier)
    if not tier:
        return {"valid": False, "errors": [f"Unknown tier: {personalization_tier}"]}

    available = set(tier["available_types"])
    selected_types = [p.get("type") for p in personalization_data if p.get("type")]
    errors = []

    for t in selected_types:
        if t not in available:
            errors.append(f"'{t}' is not available for {personalization_tier} tier")

    for group in tier.get("mutual_exclusive_groups", []):
        matches = [t for t in selected_types if t in group]
        if len(matches) > 1:
            errors.append(f"Cannot combine {' and '.join(matches)}")

    return {"valid": len(errors) == 0, "errors": errors}
