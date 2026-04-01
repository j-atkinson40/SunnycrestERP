"""Legacy Series print template registry — R2 paths and availability.

Templates are Wilbert blank TIF files uploaded manually to R2.
This file is the source of truth for which templates exist and their paths.
"""


def _t(name: str, key: str, available: bool = False, text_color: str = "white") -> dict:
    base = key.rsplit("/", 1)[-1].replace(".tif", "")
    return {
        "print_name": name,
        "r2_key": key,
        "cache_key": key.replace("templates/", "cache/").replace(".tif", "_bg.jpg"),
        "default_text_color": text_color,
        "available": available,
    }


STANDARD_TEMPLATES: list[dict] = [
    _t("American Flag", "templates/standard/WLP-AmFlag.tif", True),
    _t("Autumn Lake", "templates/standard/WLP-AutumnLake.tif", True),
    _t("Bridge 1", "templates/standard/WLP-Bridge-1.tif"),
    _t("Bridge 2", "templates/standard/WLP-Bridge-2.tif"),
    _t("Clouds", "templates/standard/WLP-Clouds.tif", True),
    _t("Combine", "templates/standard/WLP-Combine.tif"),
    _t("Corn", "templates/standard/WLP-Corn.tif"),
    _t("Country Road", "templates/standard/WLP-CountryRoad.tif", True),
    _t("Crucifix — Bible", "templates/standard/WLP-Crucifix-Bible.tif"),
    _t("Dock", "templates/standard/WLP-Dock.tif", True),
    _t("EMT", "templates/standard/WLP-EMT.tif", True),
    _t("Farm Field with Tractor", "templates/standard/WLP-SunsetFarmFieldTractor.tif"),
    _t("Father 1", "templates/standard/WLP-Father-1.tif"),
    _t("Father 2", "templates/standard/WLP-Father-2.tif"),
    _t("Field and Barn", "templates/standard/WLP-FieldRBarn.tif"),
    _t("Firefighter", "templates/standard/WLP-Firefighter.tif", True),
    _t("Fisherman", "templates/standard/WLP-Fisherman.tif", True),
    _t("Fisherman with Dog", "templates/standard/WLP-Fisherman-Dog.tif"),
    _t("Footprints", "templates/standard/WLP-Footprints.tif", True),
    _t("Footprints with Poem", "templates/standard/WLP-FootprintsPoem.tif", True),
    _t("Forever in God's Care — Cross", "templates/standard/WLP-ForeverGodsCareCross.tif"),
    _t("Forever in God's Care — Sunset", "templates/standard/WLP-ForeverGodsCareSunset.tif"),
    _t("Forever in Our Hearts — Cloud", "templates/standard/WLP-ForeverOurHeartsCloud.tif"),
    _t("Forever in Our Hearts — Sunset", "templates/standard/WLP-ForeverOurHeartsSunset.tif"),
    _t("Going Home", "templates/standard/WLP-GoingHome.tif", True),
    _t("Golf Course", "templates/standard/WLP-GolfCourse.tif", True),
    _t("Golfer", "templates/standard/WLP-Golfer.tif"),
    _t("Gone Fishing", "templates/standard/WLP-GoneFishin.tif", True),
    _t("Horses", "templates/standard/WLP-Horse.tif"),
    _t("Irish Blessing", "templates/standard/WLP-IrishBlessing.tif", True),
    _t("Jesus", "templates/standard/WLP-Jesus.tif"),
    _t("Jesus at Dawn", "templates/standard/WLP-Jesus-dwn.tif", True),
    _t("Jewish", "templates/standard/WLP-Jewish.tif"),
    _t("Lighthouse", "templates/standard/WLP-Lighthouse.tif", True),
    _t("Mother 1", "templates/standard/WLP-Mother-1.tif"),
    _t("Mother 2", "templates/standard/WLP-Mother-2.tif"),
    _t("Motorcycle 1", "templates/standard/WLP-Motorcycle_1.tif"),
    _t("Motorcycle 2", "templates/standard/WLP-Motorcycle_2.tif"),
    _t("Music", "templates/standard/WLP-Music.tif", True),
    _t("Police", "templates/standard/WLP-Police.tif"),
    _t("Red Barn", "templates/standard/WLP-RedBarn.tif", True),
    _t("Red Roses", "templates/standard/WLP-R-Roses.tif"),
    _t("Roses on Silk", "templates/standard/WLP-Roses_On_Silk.tif"),
    _t("School", "templates/standard/WLP-School.tif"),
    _t("Sunrise", "templates/standard/WLP-Sunrise.tif"),
    _t("Sunset", "templates/standard/WLP-Sunset.tif"),
    _t("Three Crosses", "templates/standard/WLP-3Crosses.tif"),
    _t("Tobacco Barn", "templates/standard/WLP-TobBarn.tif", True),
    _t("Tobacco Field", "templates/standard/WLP-TobaccoField.tif"),
    _t("Tropical", "templates/standard/WLP-Tropical-Island.tif"),
    _t("Yellow Roses", "templates/standard/WLP-Y-Roses.tif"),
]

URN_TEMPLATES: list[dict] = [
    _t("U.S. Flag", "templates/urn/WLP-UV-AmFlag.tif"),
    _t("Autumn Lake", "templates/urn/WLP-UV-AutumnLake.tif"),
    _t("Bridge 1", "templates/urn/WLP-UV-Bridge-1.tif"),
    _t("Bridge 2", "templates/urn/WLP-UV-Bridge-2.tif"),
    _t("Cardinal", "templates/urn/WLP-UV-Cardinal.tif"),
    _t("Clouds", "templates/urn/WLP-UV-Clouds.tif"),
    _t("Combine", "templates/urn/WLP-UV-Combine.tif"),
    _t("Corn", "templates/urn/WLP-UV-Corn.tif"),
    _t("Country Road", "templates/urn/WLP-UV-CountryRoad.tif"),
    _t("Crucifix on Bible", "templates/urn/WLP-UV-Crucifix-Bible.tif"),
    _t("Dock", "templates/urn/WLP-UV-Dock.tif"),
    _t("EMT", "templates/urn/WLP-UV-EMT.tif"),
    _t("Farm Field & Tractor", "templates/urn/WLP-UV-SunsetFarmFieldTractor.tif"),
    _t("Father 1", "templates/urn/WLP-UV-Father-1.tif"),
    _t("Father 2", "templates/urn/WLP-UV-Father-2.tif"),
    _t("Firefighter", "templates/urn/WLP-UV-Firefighter.tif"),
    _t("Fisherman", "templates/urn/WLP-UV-Fisherman.tif"),
    _t("Fisherman with Dog", "templates/urn/WLP-UV-Fisherman-Dog.tif"),
    _t("Going Home", "templates/urn/WLP-UV-GoingHome.tif"),
    _t("Golf Course", "templates/urn/WLP-UV-GolfCourse.tif"),
    _t("Golfer", "templates/urn/WLP-UV-Golfer.tif"),
    _t("Gone Fishing", "templates/urn/WLP-UV-GoneFishin.tif"),
    _t("Green Field & Barn", "templates/urn/WLP-UV-GFieldRBarn.tif"),
    _t("Horses", "templates/urn/WLP-UV-Horse.tif"),
    _t("Irish Blessing", "templates/urn/WLP-UV-IrishBlessing.tif"),
    _t("Jesus", "templates/urn/WLP-UV-Jesus.tif"),
    _t("Jesus at Dawn", "templates/urn/WLP-UV-Jesus-dwn.tif"),
    _t("Jewish 1", "templates/urn/WLP-UV-Jewish-1.tif"),
    _t("Jewish 2", "templates/urn/WLP-UV-Jewish-2.tif"),
    _t("Lighthouse", "templates/urn/WLP-UV-Lighthouse.tif"),
    _t("Mother 1", "templates/urn/WLP-UV-Mother-1.tif"),
    _t("Mother 2", "templates/urn/WLP-UV-Mother-2.tif"),
    _t("Motorcycle", "templates/urn/WLP-UV-Motorcycle_1.tif"),
    _t("Motorcycle 2", "templates/urn/WLP-UV-Motorcycle_2.tif"),
    _t("Music", "templates/urn/WLP-UV-Music.tif"),
    _t("Pieta", "templates/urn/WLP-UV-Pieta.tif"),
    _t("Police", "templates/urn/WLP-UV-Police.tif"),
    _t("Red Barn", "templates/urn/WLP-UV-RedBarn.tif"),
    _t("Red Roses", "templates/urn/WLP-UV-R-Roses.tif"),
    _t("Roses on Silk", "templates/urn/WLP-UV-Roses_On_Silk.tif"),
    _t("School", "templates/urn/WLP-UV-School.tif"),
    _t("Sunrise-Sunset 1", "templates/urn/WLP-UV-Sunrise-Sunset.tif"),
    _t("Sunrise-Sunset 2", "templates/urn/WLP-UV-Sunrise-Sunset-3.tif"),
    _t("Three Crosses", "templates/urn/WLP-UV-3-Crosses.tif"),
    _t("Tobacco Barn", "templates/urn/WLP-UV-TobBarn.tif"),
    _t("Tropical Island", "templates/urn/WLP-UV-Tropical-Island.tif"),
    _t("Whitetail Buck", "templates/urn/WLP-UV-WhitetailBuck.tif"),
]


def get_template(print_name: str, is_urn: bool = False) -> dict | None:
    """Find template by print name (case-insensitive)."""
    templates = URN_TEMPLATES if is_urn else STANDARD_TEMPLATES
    name_lower = print_name.lower()
    for t in templates:
        if t["print_name"].lower() == name_lower:
            return t
    return None


def get_available_templates(is_urn: bool = False) -> list[dict]:
    """Return templates where available=True."""
    templates = URN_TEMPLATES if is_urn else STANDARD_TEMPLATES
    return [t for t in templates if t["available"]]


def get_all_templates(is_urn: bool = False) -> list[dict]:
    """Return all templates with availability status."""
    return URN_TEMPLATES if is_urn else STANDARD_TEMPLATES
