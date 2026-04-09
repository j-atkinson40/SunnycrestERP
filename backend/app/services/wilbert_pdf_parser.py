"""Wilbert PDF catalog parser — extracts structured product data from PDF.

Uses PyMuPDF (fitz) to extract text, then line-by-line parsing to identify
products with SKU, type, dimensions, engravability flag, and material category.

Designed for Wilbert Cremation Choices Catalog (Volume 11, 88 pages).

PDF text format (per page):
    material                    <- section header or page number
    3                           <- page number
    Product Name E              <- product name (E = engravable)
    Description text line       <- material description
    P2037 Urn                   <- SKU + type
    Height\t                    <- dimension label (value on NEXT line)
    10 1/2"                     <- dimension value
    Diameter\t
    6"
    Cubic Inch\t
    200
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParsedProduct:
    """A single product extracted from the Wilbert PDF catalog."""

    name: str
    sku: str
    product_type: str  # Urn, Memento, Heart, Pendant
    material_category: str  # Metal, Wood, Stone, etc.
    description: str = ""
    height: str | None = None
    width_or_diameter: str | None = None
    depth: str | None = None
    cubic_inches: int | None = None
    engravable: bool = False
    companion_of_sku: str | None = None
    color_name: str | None = None
    catalog_page: int | None = None


@dataclass
class PDFParseResult:
    """Result of parsing the full PDF catalog."""

    products: list[ParsedProduct] = field(default_factory=list)
    total_pages: int = 0
    pages_processed: int = 0
    skipped_pages: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Page ranges for each material category section
SECTION_MAP = {
    "Metal": (4, 17),
    "Wood": (18, 31),
    "Stone": (32, 36),
    "Cultured Marble": (37, 40),
    "Cloisonne": (41, 44),
    "Glass": (45, 49),
    "Ceramic": (50, 51),
    "Synthetic": (52, 55),
    "Eco": (56, 59),
    "Jewelry": (60, 66),
    "Urn Vaults": (67, 70),
    "Personalization": (71, 79),
    "Limited Stock": (80, 82),
}

# Pages to skip entirely (non-product content)
SKIP_PAGES = {1, 2, 3, 83, 84, 85, 86, 87, 88}

# Regex patterns
SKU_LINE = re.compile(r"^(P\d{4}|D\d{4})\s+(.*)")  # e.g., "P2037 Urn" or "P9090 Blue Gray Memento"
SKU_ONLY = re.compile(r"^(P\d{4}|D\d{4})$")
DIM_LABEL = re.compile(r"^(Height|Diameter|Width|Depth|Cubic Inch)\s*\t?\s*$", re.IGNORECASE)
DIM_VALUE = re.compile(r'^(\d+(?:\s+\d+[⁄/]\d+)?"?\s*)$')
CUBIC_VALUE = re.compile(r"^(\d+)\s*$")
SECTION_HEADERS = {"metal", "wood", "stone", "cultured marble", "cloisonne", "glass",
                    "ceramic", "synthetic", "eco", "jewelry", "urn vaults",
                    "personalization", "limited stock"}


def _get_material_category(page_num: int) -> str | None:
    """Determine material category from page number."""
    for category, (start, end) in SECTION_MAP.items():
        if start <= page_num <= end:
            return category
    return None


def _clean_dimension(raw: str) -> str:
    """Normalize dimension string."""
    val = raw.strip().rstrip('"').strip()
    # Replace unicode fraction slash with regular
    val = val.replace("⁄", "/")
    # Fix doubled digits from PDF extraction (e.g., "11 1⁄22" -> "11 1/2")
    val = re.sub(r"(\d)/(\d)\2", r"\1/\2", val)
    if val and not val.endswith('"'):
        val += '"'
    return val


def _is_noise_line(line: str) -> bool:
    """Check if a line is page number, section header, or other noise."""
    stripped = line.strip().lower()
    if not stripped:
        return True
    if stripped.isdigit() and len(stripped) <= 3:  # page numbers
        return True
    if stripped in SECTION_HEADERS:
        return True
    if stripped in ("e", ""):  # stray engravable markers
        return True
    return False


def _parse_page(lines: list[str], material_category: str, page_num: int) -> list[ParsedProduct]:
    """Parse all products from a single page's text lines.

    Strategy: Walk lines sequentially. Maintain state for current product name,
    description, and per-SKU dimensions.
    """
    products = []
    current_name = ""
    current_desc = ""
    current_engravable = False
    current_sku = None
    current_type = "Urn"
    current_color_suffix = ""
    main_sku_for_page = None

    # Per-SKU dimension accumulators
    height = None
    diameter = None
    width = None
    depth = None
    cubic_inches = None
    pending_dim_label = None  # waiting for value on next line

    def _flush_product():
        """Save the current SKU entry as a ParsedProduct."""
        nonlocal current_sku, height, diameter, width, depth, cubic_inches, pending_dim_label

        if not current_sku:
            return

        w_or_d = diameter or width
        name = current_name
        if current_color_suffix:
            name = f"{current_name} ({current_color_suffix})" if current_name else current_color_suffix

        companion_of = None
        if current_type in ("Memento", "Heart") and main_sku_for_page:
            companion_of = main_sku_for_page

        products.append(ParsedProduct(
            name=name or f"Unknown {current_sku}",
            sku=current_sku,
            product_type=current_type,
            material_category=material_category,
            description=current_desc,
            height=height,
            width_or_diameter=w_or_d,
            depth=depth,
            cubic_inches=cubic_inches,
            engravable=current_engravable,
            companion_of_sku=companion_of,
            catalog_page=page_num,
        ))

        # Reset per-SKU state
        current_sku = None
        height = None
        diameter = None
        width = None
        depth = None
        cubic_inches = None
        pending_dim_label = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        # Check if this is a dimension label (value comes on next line)
        dim_match = DIM_LABEL.match(line)
        if dim_match:
            pending_dim_label = dim_match.group(1).lower()
            continue

        # If we're expecting a dimension value
        if pending_dim_label:
            val = line.strip()
            if pending_dim_label == "height":
                height = _clean_dimension(val)
            elif pending_dim_label == "diameter":
                diameter = _clean_dimension(val)
            elif pending_dim_label == "width":
                width = _clean_dimension(val)
            elif pending_dim_label == "depth":
                depth = _clean_dimension(val)
            elif pending_dim_label == "cubic inch":
                m = CUBIC_VALUE.match(val)
                if m:
                    cubic_inches = int(m.group(1))
            pending_dim_label = None
            continue

        # Check for SKU line (e.g., "P2037 Urn" or "P9090 Blue Gray Memento")
        sku_match = SKU_LINE.match(line)
        if sku_match:
            _flush_product()  # save previous SKU if any

            current_sku = sku_match.group(1)
            suffix = sku_match.group(2).strip()

            # Parse type and optional color from suffix
            # Examples: "Urn", "Memento", "Blue Gray Memento", "Heart"
            type_found = False
            for t in ("Urn", "Memento", "Heart", "Pendant"):
                if suffix.lower().endswith(t.lower()):
                    current_type = t
                    current_color_suffix = suffix[:len(suffix) - len(t)].strip()
                    type_found = True
                    break
            if not type_found:
                current_type = "Urn"
                current_color_suffix = suffix

            if current_type == "Urn" and not main_sku_for_page:
                main_sku_for_page = current_sku
            elif current_type == "Urn":
                # Reset main SKU for new urn under same name
                main_sku_for_page = current_sku

            continue

        # Check for standalone SKU (no type)
        sku_only = SKU_ONLY.match(line)
        if sku_only:
            _flush_product()
            current_sku = sku_only.group(1)
            current_type = "Urn"
            current_color_suffix = ""
            continue

        # If we don't have a SKU yet, this line is part of name/description
        if not current_sku and not _is_noise_line(line):
            # Could be a new product name or description continuation
            # Name line: typically title case, may end with " E" (engravable)
            is_engravable = False
            name_candidate = line
            if line.endswith(" E") or line.endswith("\tE"):
                is_engravable = True
                name_candidate = line.rstrip().rstrip("E").rstrip().rstrip("\t").strip()

            # Heuristic: if no current name, this is the name
            # If we have a name but no description, this is the description
            if not current_name or (current_name and products and products[-1].name != current_name):
                # Check if this looks like a fresh product name:
                # - After we just flushed products with dimensions
                # - Contains uppercase letters typical of product names
                if not current_name:
                    current_name = name_candidate
                    current_engravable = is_engravable
                    current_desc = ""
                    main_sku_for_page = None  # reset for new product family
                else:
                    # New product family
                    current_name = name_candidate
                    current_engravable = is_engravable
                    current_desc = ""
                    main_sku_for_page = None
            elif not current_desc:
                current_desc = line
            else:
                current_desc += " " + line
            continue

        # If we already have a SKU and this isn't a dim/sku/noise,
        # it's probably a new product name
        if current_sku and not _is_noise_line(line):
            _flush_product()
            # This line is a new product name
            is_engravable = False
            name_candidate = line
            if line.endswith(" E") or line.endswith("\tE"):
                is_engravable = True
                name_candidate = line.rstrip().rstrip("E").rstrip().rstrip("\t").strip()

            current_name = name_candidate
            current_engravable = is_engravable
            current_desc = ""
            main_sku_for_page = None

    # Flush last product
    _flush_product()

    return products


def parse_pdf(pdf_path: str | Path) -> PDFParseResult:
    """Parse the Wilbert PDF catalog and extract all products."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return PDFParseResult(errors=["PyMuPDF (fitz) not installed. Run: pip install PyMuPDF"])

    result = PDFParseResult()

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        return PDFParseResult(errors=[f"Failed to open PDF: {e}"])

    result.total_pages = len(doc)
    logger.info("Parsing Wilbert catalog: %d pages", result.total_pages)

    for page_num in range(1, result.total_pages + 1):
        if page_num in SKIP_PAGES:
            result.skipped_pages.append(page_num)
            continue

        material_category = _get_material_category(page_num)
        if not material_category:
            result.skipped_pages.append(page_num)
            continue

        # Skip non-product sections
        if material_category in ("Personalization", "Urn Vaults"):
            result.skipped_pages.append(page_num)
            continue

        try:
            page = doc[page_num - 1]  # 0-indexed
            text = page.get_text("text")

            if not text or not text.strip():
                result.skipped_pages.append(page_num)
                continue

            lines = text.split("\n")
            parsed = _parse_page(lines, material_category, page_num)
            result.products.extend(parsed)
            result.pages_processed += 1

        except Exception as e:
            result.errors.append(f"Page {page_num}: {e}")

    doc.close()

    # Deduplicate by SKU (keep last occurrence which has best data)
    seen_skus: dict[str, int] = {}
    unique_products = []
    for p in result.products:
        if p.sku in seen_skus:
            unique_products[seen_skus[p.sku]] = p
        else:
            seen_skus[p.sku] = len(unique_products)
            unique_products.append(p)
    result.products = unique_products

    logger.info(
        "PDF parse complete: %d products from %d pages (%d skipped, %d errors)",
        len(result.products),
        result.pages_processed,
        len(result.skipped_pages),
        len(result.errors),
    )

    return result


def parse_pdf_to_dicts(pdf_path: str | Path) -> list[dict]:
    """Convenience wrapper: parse PDF and return list of flat dicts for DB import."""
    result = parse_pdf(pdf_path)

    products = []
    for p in result.products:
        products.append({
            "name": p.name,
            "sku": p.sku,
            "product_type": p.product_type,
            "material": p.material_category.lower() if p.material_category else None,
            "material_category": p.material_category,
            "wilbert_description": p.description,
            "height": p.height,
            "width_or_diameter": p.width_or_diameter,
            "depth": p.depth,
            "cubic_inches": p.cubic_inches,
            "engravable": p.engravable,
            "companion_of_sku": p.companion_of_sku,
            "catalog_page": p.catalog_page,
        })

    return products
