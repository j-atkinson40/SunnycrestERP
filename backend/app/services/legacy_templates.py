"""Legacy Series print template registry — R2 paths and availability.

Templates are Wilbert blank TIF files uploaded manually to R2.
This file is the source of truth for which templates exist and their paths.
"""


def _t(name: str, key: str, available: bool = False, text_color: str = "white") -> dict:
    return {
        "print_name": name,
        "r2_key": key,
        "cache_key": key.replace("templates/", "cache/").replace(".tif", "_bg.jpg"),
        "default_text_color": text_color,
        "available": available,
    }


# ── Standard vault templates ─────────────────────────────────────────────────
# R2 keys must match the actual uploaded filenames in templates/standard/

STANDARD_TEMPLATES: list[dict] = [
    # Religious & Spiritual
    _t("American Flag", "templates/standard/WLP-AmFlag.tif", True),
    _t("Canadian Flag", "templates/standard/WLP-CanFlag.tif", True),
    _t("Cross — Gold", "templates/standard/WLP-Cross-G.tif", True),
    _t("Cross — Silver", "templates/standard/WLP-Cross-S.tif", True),
    _t("Cross — White Horizontal", "templates/standard/WLP-Cross-W-horiz.tif", True),
    _t("Crucifix — Bible", "templates/standard/WLP-Crucifix-Bible.tif", True),
    _t("Forever in God's Care", "templates/standard/WLP-ForeverInGodsCare.tif", True),
    _t("Going Home", "templates/standard/WLP-GoingHome.tif", True),
    _t("Irish Blessing", "templates/standard/WLP-IrishBlessing.tif", True),
    _t("Irish Blessing — No Poem", "templates/standard/WLP-IrishBlessing-noPoem.tif", True),
    _t("Jesus", "templates/standard/WLP-Jesus.tif", True),
    _t("Jesus at Dawn", "templates/standard/WLP-Jesus-Dwn.tif", True),
    _t("Jewish 1", "templates/standard/WLP-Jewish-1.tif", True),
    _t("Jewish 2", "templates/standard/WLP-Jewish-2.tif", True),
    _t("Our Lady of Guadalupe", "templates/standard/WLP-OurLadyOfGuadalupe-Clouds.tif", True),
    _t("Pieta", "templates/standard/WLP-Pieta.tif", True),
    _t("Stained Glass — Gold Marble", "templates/standard/WLP-Stained-Glass-Marble-G.tif", True),
    _t("Stained Glass — White Marble", "templates/standard/WLP-Stained-Glass-Marble-W.tif", True),
    _t("Star of David — Gold", "templates/standard/WLP-StarOfDavid-G.tif", True),
    _t("Star of David — White", "templates/standard/WLP-StarOfDavid-W.tif", True),
    _t("Three Crosses", "templates/standard/WLP-3-Crosses.tif", True),

    # Nature & Landscapes
    _t("Autumn Lake", "templates/standard/WLP-AutumnLake.tif", True),
    _t("Bridge 1", "templates/standard/WLP-Bridge-1.tif", True),
    _t("Bridge 2", "templates/standard/WLP-Bridge-2.tif", True),
    _t("Cardinal", "templates/standard/WLP-Cardinal.tif", True),
    _t("Clouds", "templates/standard/WLP-Clouds.tif", True),
    _t("Country Road", "templates/standard/WLP-CountryRoad.tif", True),
    _t("Dock", "templates/standard/WLP-Dock.tif", True),
    _t("Footprints", "templates/standard/WLP-Footprints.tif", True),
    _t("Footprints with Poem", "templates/standard/WLP-Footprints-Poem.tif", True),
    _t("Green Field & Barn", "templates/standard/WLP-GFieldRBarn.tif", True),
    _t("Lighthouse", "templates/standard/WLP-Lighthouse.tif", True),
    _t("Marble — Gold", "templates/standard/WLP-Marble-G.tif", True),
    _t("Marble — White", "templates/standard/WLP-Marble-W.tif", True),
    _t("Red Barn", "templates/standard/WLP-RedBarn.tif", True),
    _t("Sunrise-Sunset", "templates/standard/WLP-Sunrise-Sunset.tif", True),
    _t("Sunrise-Sunset 2", "templates/standard/WLP-Sunrise-Sunset-3.tif", True),
    _t("Tropical", "templates/standard/WLP-Tropical-Island.tif", True),
    _t("Whitetail Buck", "templates/standard/WLP-WhitetailBuck.tif", True),

    # Floral
    _t("Roses on Silk", "templates/standard/WLP-Roses On Silk.tif", True),
    _t("Red Roses", "templates/standard/WLP-R-Roses.tif", True),
    _t("Yellow Roses", "templates/standard/WLP-Y-Roses.tif", True),

    # Occupations & Hobbies
    _t("Combine", "templates/standard/WLP-Combine.tif", True),
    _t("Corn", "templates/standard/WLP-Corn.tif", True),
    _t("EMT", "templates/standard/WLP-EMT.tif", True),
    _t("Farm Field with Tractor", "templates/standard/WLP-SunsetFarmFieldTractor.tif", True),
    _t("Father 1", "templates/standard/WLP-Father-1.tif", True),
    _t("Father 2", "templates/standard/WLP-Father-2.tif", True),
    _t("Firefighter", "templates/standard/WLP-Firefighter.tif", True),
    _t("Fisherman", "templates/standard/WLP-Fisherman.tif", True),
    _t("Fisherman with Dog", "templates/standard/WLP-Fisherman-Dog.tif", True),
    _t("Golf Course", "templates/standard/WLP-GolfCourse.tif", True),
    _t("Golfer", "templates/standard/WLP-Golfer.tif", True),
    _t("Gone Fishing", "templates/standard/WLP-GoneFishin.tif", True),
    _t("Horses", "templates/standard/WLP-Horse.tif", True),
    _t("Mother 1", "templates/standard/WLP-Mother-1.tif", True),
    _t("Mother 2", "templates/standard/WLP-Mother-2.tif", True),
    _t("Motorcycle 1", "templates/standard/WLP-Motorcycle_1.tif", True),
    _t("Motorcycle 2", "templates/standard/WLP-Motorcycle_2.tif", True),
    _t("Music", "templates/standard/WLP-Music.tif", True),
    _t("Police", "templates/standard/WLP-Police.tif", True),
    _t("School", "templates/standard/WLP-School.tif", True),
    _t("Tobacco Barn", "templates/standard/WLP-TobBarn.tif", True),
    _t("Tobacco Field", "templates/standard/WLP-TobaccoField.tif", True),
]


# ── Urn vault templates ──────────────────────────────────────────────────────
# R2 keys must match the actual uploaded filenames in templates/urn/

URN_TEMPLATES: list[dict] = [
    # Religious & Spiritual
    _t("U.S. Flag", "templates/urn/WLP-UV-Am-Flag.tif", True),
    _t("Crucifix on Bible", "templates/urn/WLP-UV-Crucifix-Bible-L2.tif", True),
    _t("Forever in God's Care", "templates/urn/WLP-UV-ForeverInGodsCare.tif", True),
    _t("Going Home", "templates/urn/WLP-UV-GoingHome.tif", True),
    _t("Irish Blessing", "templates/urn/WLP-UV-IrishBlessing-L2.tif", True),
    _t("Jesus", "templates/urn/WLP-UV-Jesus.tif", True),
    _t("Three Crosses", "templates/urn/WLP-UV-3-Crosses-L2.tif", True),

    # Nature & Landscapes
    _t("Autumn Lake", "templates/urn/WLP-UV-AutumnLake-L2.tif", True),
    _t("Barn", "templates/urn/WLP-UV-Barn.tif", True),
    _t("Bridge 1", "templates/urn/WLP-UV-Bridge-1.tif", True),
    _t("Bridge 2", "templates/urn/WLP-UV-Bridge-2.tif", True),
    _t("Cardinal", "templates/urn/WLP-UV-Cardinal-L2.tif", True),
    _t("Clouds", "templates/urn/WLP-UV-Clouds.tif", True),
    _t("Country Road", "templates/urn/WLP-UV-CountryRoad.tif", True),
    _t("Dock", "templates/urn/WLP-UV-Dock-L2.tif", True),
    _t("Footprints", "templates/urn/WLP-UV-Footprints.tif", True),
    _t("Green Field & Barn", "templates/urn/WLP-UV-GFieldRBarn-L2.tif", True),
    _t("Horses", "templates/urn/WLP-UV-Horse.tif", True),

    # Occupations & Hobbies
    _t("Combine", "templates/urn/WLP-UV-Combine-L2.tif", True),
    _t("Corn", "templates/urn/WLP-UV-Corn-L2.tif", True),
    _t("EMT", "templates/urn/WLP-UV-EMT.tif", True),
    _t("Father 1", "templates/urn/WLP-UV-Father-1.tif", True),
    _t("Father 2", "templates/urn/WLP-UV-Father-2.tif", True),
    _t("Firefighter", "templates/urn/WLP-UV-Firefighter.tif", True),
    _t("Fisherman", "templates/urn/WLP-UV-Fisherman.tif", True),
    _t("Fisherman with Dog", "templates/urn/WLP-UV-Fisherman-Dog-L2.tif", True),
    _t("Golf Course", "templates/urn/WLP-UV-GolfCourse.tif", True),
    _t("Golfer", "templates/urn/WLP-UV-Golfer.tif", True),
    _t("Gone Fishing", "templates/urn/WLP-UV-GoneFishin.tif", True),
]


# ── Bronze vault (BV) standard templates ────────────────────────────────────
# Custom photo layout templates — different from WLP (full background) templates.
# These have a photo cutout area (heart, cross, etc.) on a decorative background.

BV_STANDARD_TEMPLATES: list[dict] = [
    _t("Cross Set", "templates/bv_standard/BV-CrossSet-Custom.tif"),
    _t("Cross Set — No Token", "templates/bv_standard/BV-CrossSet-Custom_NoToken.tif"),
    _t("Cross Sky", "templates/bv_standard/BV-CrossSky-Custom.tif"),
    _t("Cross Sky — No Token", "templates/bv_standard/BV-CrossSky-Custom_NoToken.tif"),
    _t("Heart Cloud", "templates/bv_standard/BV-HeartCld-Custom.tif"),
    _t("Heart Cloud — No Token", "templates/bv_standard/BV-HeartCld-Custom_NoToken.tif"),
    _t("Heart Ribbon", "templates/bv_standard/BV-HeartRbn-Custom.tif"),
    _t("Heart Ribbon — No Token", "templates/bv_standard/BV-HeartRbn-Custom_NoToken.tif"),
    _t("Heart Ribbon — No Token/Type", "templates/bv_standard/BV-HeartRbn-Custom_NoTokenNoType.tif"),
]

# ── Bronze vault (BV) urn templates ─────────────────────────────────────────

BV_URN_TEMPLATES: list[dict] = [
    _t("Cross Set", "templates/bv_urn/UV-CrossSet.tif"),
    _t("Cross Set — No Token", "templates/bv_urn/UV-CrossSet_NoToken.tif"),
    _t("Cross Sky", "templates/bv_urn/UV-CrossSky.tif"),
    _t("Cross Sky — No Token", "templates/bv_urn/UV-CrossSky_NoToken.tif"),
    _t("Heart Cloud", "templates/bv_urn/UV-HeartCld.tif"),
    _t("Heart Cloud — No Token", "templates/bv_urn/UV-HeartCld_NoToken.tif"),
    _t("Heart Ribbon", "templates/bv_urn/UV-HeartRbn.tif"),
    _t("Heart Ribbon — No Token", "templates/bv_urn/UV-HeartRbn_NoToken.tif"),
]


def get_template(print_name: str, is_urn: bool = False, template_type: str = "standard") -> dict | None:
    """Find template by print name (case-insensitive)."""
    templates = _get_template_list(is_urn, template_type)
    name_lower = print_name.lower()
    for t in templates:
        if t["print_name"].lower() == name_lower:
            return t
    return None


def get_available_templates(is_urn: bool = False, template_type: str = "standard") -> list[dict]:
    """Return templates where available=True."""
    templates = _get_template_list(is_urn, template_type)
    return [t for t in templates if t["available"]]


def get_all_templates(is_urn: bool = False, template_type: str = "standard") -> list[dict]:
    """Return all templates with availability status."""
    return _get_template_list(is_urn, template_type)


def _get_template_list(is_urn: bool, template_type: str = "standard") -> list[dict]:
    """Resolve which template list to use."""
    if template_type == "bv":
        return BV_URN_TEMPLATES if is_urn else BV_STANDARD_TEMPLATES
    return URN_TEMPLATES if is_urn else STANDARD_TEMPLATES
