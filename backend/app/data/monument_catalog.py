"""Monument catalog — seed data until Memorial Monuments portal scraping is wired.

Matches Wilbert monument product categories at a representative level. All
display-only fields (price_addition omitted here; pricing lives in tenant
configuration). AI suggestion logic in MonumentComposerService uses this.
"""

SHAPES = {
    "upright_standard": {
        "display_name": "Upright — Standard",
        "image_placeholder": "/static/monument/shapes/upright_standard.jpg",
        "available_stones": ["absolute_black", "blue_pearl", "georgia_gray", "paradiso", "balmoral_red", "imperial_red", "jet_black", "american_black"],
        "standard_dimensions": {"height_in": 42, "width_in": 36, "depth_in": 8},
    },
    "slant": {
        "display_name": "Slant",
        "image_placeholder": "/static/monument/shapes/slant.jpg",
        "available_stones": ["absolute_black", "georgia_gray", "blue_pearl", "american_black"],
        "standard_dimensions": {"height_in": 18, "width_in": 36, "depth_in": 10},
    },
    "flat_marker": {
        "display_name": "Flat Marker",
        "image_placeholder": "/static/monument/shapes/flat_marker.jpg",
        "available_stones": ["absolute_black", "georgia_gray", "american_black", "paradiso"],
        "standard_dimensions": {"height_in": 4, "width_in": 24, "depth_in": 12},
    },
    "bevel": {
        "display_name": "Bevel",
        "image_placeholder": "/static/monument/shapes/bevel.jpg",
        "available_stones": ["georgia_gray", "absolute_black", "american_black"],
        "standard_dimensions": {"height_in": 10, "width_in": 24, "depth_in": 14},
    },
    "obelisk": {
        "display_name": "Obelisk",
        "image_placeholder": "/static/monument/shapes/obelisk.jpg",
        "available_stones": ["absolute_black", "american_black", "georgia_gray"],
        "standard_dimensions": {"height_in": 60, "width_in": 14, "depth_in": 14},
    },
    "heart": {
        "display_name": "Heart",
        "image_placeholder": "/static/monument/shapes/heart.jpg",
        "available_stones": ["absolute_black", "imperial_red", "blue_pearl", "georgia_gray"],
        "standard_dimensions": {"height_in": 24, "width_in": 30, "depth_in": 6},
    },
    "cross": {
        "display_name": "Cross",
        "image_placeholder": "/static/monument/shapes/cross.jpg",
        "available_stones": ["absolute_black", "georgia_gray", "american_black"],
        "standard_dimensions": {"height_in": 30, "width_in": 24, "depth_in": 6},
    },
}


STONES = {
    "absolute_black": {
        "display_name": "Absolute Black",
        "origin": "India",
        "texture_color": "#0a0a0a",
        "description": "Deep, solid black granite — the most popular premium stone.",
    },
    "blue_pearl": {
        "display_name": "Blue Pearl",
        "origin": "Norway",
        "texture_color": "#1a3a5c",
        "description": "Blue-gray granite with iridescent crystal flecks.",
    },
    "georgia_gray": {
        "display_name": "Georgia Gray",
        "origin": "Georgia, USA",
        "texture_color": "#6b6d6e",
        "description": "Medium gray granite, traditional New England and Southern preference.",
    },
    "paradiso": {
        "display_name": "Paradiso",
        "origin": "India",
        "texture_color": "#705543",
        "description": "Warm brown granite with crystalline movement.",
    },
    "balmoral_red": {
        "display_name": "Balmoral Red",
        "origin": "Finland",
        "texture_color": "#6a2024",
        "description": "Rich burgundy red granite.",
    },
    "imperial_red": {
        "display_name": "Imperial Red",
        "origin": "India",
        "texture_color": "#7a1818",
        "description": "Deep red granite with fine grain.",
    },
    "jet_black": {
        "display_name": "Jet Black",
        "origin": "Zimbabwe",
        "texture_color": "#000000",
        "description": "Pure jet-black granite.",
    },
    "american_black": {
        "display_name": "American Black",
        "origin": "Pennsylvania, USA",
        "texture_color": "#1a1a1a",
        "description": "Domestic black granite. Lower cost than Absolute Black.",
    },
}


ENGRAVINGS = {
    # Religious
    "cross_simple": {"category": "religious", "display_name": "Cross — Simple"},
    "cross_ornate": {"category": "religious", "display_name": "Cross — Ornate"},
    "star_of_david": {"category": "religious", "display_name": "Star of David"},
    "praying_hands": {"category": "religious", "display_name": "Praying Hands"},
    "rosary": {"category": "religious", "display_name": "Rosary"},
    "ichthys": {"category": "religious", "display_name": "Ichthys (Fish)"},
    # Military
    "army": {"category": "military", "display_name": "U.S. Army Emblem"},
    "navy": {"category": "military", "display_name": "U.S. Navy Emblem"},
    "marines": {"category": "military", "display_name": "U.S. Marines Emblem"},
    "air_force": {"category": "military", "display_name": "U.S. Air Force Emblem"},
    "coast_guard": {"category": "military", "display_name": "U.S. Coast Guard Emblem"},
    "veteran_emblem": {"category": "military", "display_name": "Veteran Emblem"},
    "pow_mia": {"category": "military", "display_name": "POW/MIA"},
    # Nature
    "roses": {"category": "nature", "display_name": "Roses"},
    "oak_tree": {"category": "nature", "display_name": "Oak Tree"},
    "mountains": {"category": "nature", "display_name": "Mountain Scene"},
    "butterfly": {"category": "nature", "display_name": "Butterfly"},
    "dove": {"category": "nature", "display_name": "Dove"},
    # Custom
    "custom_upload": {"category": "custom", "display_name": "Custom Upload"},
}


ACCESSORIES = {
    "bronze_vase": {
        "display_name": "Bronze Vase",
        "compatible_shapes": ["upright_standard", "slant", "bevel"],
        "price_addition": 185.00,
    },
    "granite_planter": {
        "display_name": "Granite Planter",
        "compatible_shapes": ["upright_standard", "slant", "bevel", "flat_marker"],
        "price_addition": 240.00,
    },
    "porcelain_photo_oval": {
        "display_name": "Porcelain Photo Oval",
        "compatible_shapes": ["upright_standard", "slant", "heart"],
        "price_addition": 320.00,
    },
    "companion_flat_marker": {
        "display_name": "Companion Flat Marker",
        "compatible_shapes": ["upright_standard"],
        "price_addition": 450.00,
    },
}


def get_shapes() -> dict:
    return SHAPES


def get_stones() -> dict:
    return STONES


def get_engravings(category: str | None = None) -> dict:
    if not category:
        return ENGRAVINGS
    return {k: v for k, v in ENGRAVINGS.items() if v["category"] == category}


def get_accessories_for_shape(shape: str) -> dict:
    return {k: v for k, v in ACCESSORIES.items() if shape in v["compatible_shapes"]}


def suggest_engraving(
    is_veteran: bool = False,
    branch: str | None = None,
    religion: str | None = None,
) -> str:
    """AI suggestion logic. Returns an engraving key."""
    if is_veteran and branch:
        b = branch.lower()
        if "army" in b:
            return "army"
        if "navy" in b:
            return "navy"
        if "marine" in b:
            return "marines"
        if "air" in b:
            return "air_force"
        if "coast" in b:
            return "coast_guard"
        return "veteran_emblem"

    if religion:
        r = religion.lower()
        if "catholic" in r or "christian" in r:
            return "cross_ornate"
        if "jewish" in r:
            return "star_of_david"

    # Most common default
    return "roses"
