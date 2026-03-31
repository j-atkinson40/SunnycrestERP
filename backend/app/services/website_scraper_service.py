"""Website scraper — fetches and extracts text content from tenant websites."""

import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
MAX_CONTENT_LENGTH = 50_000
TIMEOUT = 30

# Navigation link patterns that indicate useful pages
NAV_PATTERNS = re.compile(
    r"(product|service|vault|catalog|about|certif|capabilit|manufactur|offering)",
    re.IGNORECASE,
)


def _extract_text(html: str) -> str:
    """Parse HTML and extract meaningful text, stripping nav/footer/script."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _find_nav_links(html: str, base_url: str) -> list[str]:
    """Find internal navigation links matching product/service/about patterns."""
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    seen: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Only follow internal links
        if parsed.netloc and parsed.netloc != base_domain:
            continue

        # Normalize: drop fragment, drop trailing slash
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if normalized in seen or normalized == base_url.rstrip("/"):
            continue

        # Check if link text or href matches useful patterns
        link_text = a_tag.get_text(strip=True)
        if NAV_PATTERNS.search(href) or NAV_PATTERNS.search(link_text):
            seen.add(normalized)
            links.append(full_url)

    return links


def extract_branding(html_content: str, page_url: str) -> dict:
    """Extract logo URL and brand colors from a homepage's HTML.

    Returns:
        {
            logo_url: str | None,
            logo_confidence: float,
            primary_color: str | None,
            secondary_color: str | None,
            colors_found: list[str],
        }
    """
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_base = urlparse(page_url)

    def _abs(src: str) -> str:
        if not src:
            return src
        if src.startswith("//"):
            return f"{parsed_base.scheme}:{src}"
        if src.startswith("http"):
            return src
        return urljoin(page_url, src)

    # ── Logo detection ────────────────────────────────────────────────────────
    logo_url: str | None = None
    logo_confidence: float = 0.0

    # 1. Open Graph image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        logo_url = _abs(og["content"])
        logo_confidence = 0.7

    # 2. Header/nav img with meaningful size
    if logo_confidence < 0.9:
        for container_selector in [
            "header", "nav",
            "[class*='header']", "[class*='navbar']",
            "[class*='logo']", "[class*='brand']",
        ]:
            try:
                containers = soup.select(container_selector)
            except Exception:
                continue
            for container in containers:
                for img in container.find_all("img"):
                    src = img.get("src", "")
                    if not src:
                        continue
                    try:
                        w = int(img.get("width", 0))
                        h = int(img.get("height", 0))
                        if w and h and (w < 100 or h < 50):
                            continue
                    except (ValueError, TypeError):
                        pass
                    logo_url = _abs(src)
                    logo_confidence = 0.9
                    break
                if logo_confidence >= 0.9:
                    break
            if logo_confidence >= 0.9:
                break

    # 3. Apple touch icon
    if logo_confidence < 0.8:
        ati = soup.find("link", rel=lambda r: r and "apple-touch-icon" in r)
        if ati and ati.get("href"):
            logo_url = _abs(ati["href"])
            logo_confidence = 0.8

    # 4. Favicon as last resort (skip generic /favicon.ico)
    if logo_confidence < 0.4:
        fav = soup.find("link", rel=lambda r: r and "icon" in r)
        if fav and fav.get("href"):
            href = fav["href"]
            if href not in ("/favicon.ico", "favicon.ico"):
                logo_url = _abs(href)
                logo_confidence = 0.4

    # ── Color extraction ──────────────────────────────────────────────────────
    HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
    CSS_VAR_RE = re.compile(
        r"--(primary|brand|main|accent|header|nav)[-\w]*\s*:\s*(#[0-9a-fA-F]{3,6})",
        re.IGNORECASE,
    )
    all_colors: list[str] = []

    def _norm(h: str) -> str:
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return f"#{h.upper()}"

    SKIP = {"#FFFFFF", "#000000", "#FEFEFE", "#F0F0F0", "#EEEEEE", "#DDDDDD", "#CCCCCC"}

    for style_tag in soup.find_all("style"):
        css_text = style_tag.get_text() or ""
        for m in CSS_VAR_RE.finditer(css_text):
            color = _norm(m.group(2))
            if color not in SKIP and color not in all_colors:
                all_colors.insert(0, color)
        for m in HEX_RE.finditer(css_text):
            color = _norm(m.group(0))
            if color not in SKIP and color not in all_colors:
                all_colors.append(color)

    for tag in soup.select("header, nav, button, a[class*='btn'], [class*='cta']"):
        style = tag.get("style", "")
        for m in HEX_RE.finditer(style):
            color = _norm(m.group(0))
            if color not in SKIP and color not in all_colors:
                all_colors.append(color)

    primary_color = all_colors[0] if all_colors else None
    secondary_color = all_colors[1] if len(all_colors) > 1 else None

    return {
        "logo_url": logo_url,
        "logo_confidence": logo_confidence,
        "primary_color": primary_color,
        "secondary_color": secondary_color,
        "colors_found": all_colors[:10],
    }


def scrape_website(url: str, max_pages: int = 5) -> dict:
    """Scrape a website and extract text content.

    Returns: {"raw_content": str, "pages_scraped": list[str]}
    """
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    pages_scraped: list[str] = []
    all_text_parts: list[str] = []

    session = requests.Session()
    session.headers.update(HEADERS)

    # Try with SSL verification first, then without
    for verify_ssl in [True, False]:
        if not verify_ssl:
            logger.info(f"Retrying {url} with SSL verification disabled")
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        try:
            # 1. Fetch homepage
            logger.info(f"Fetching homepage: {url} (verify={verify_ssl})")
            resp = session.get(url, timeout=TIMEOUT, verify=verify_ssl)
            resp.raise_for_status()
            homepage_html = resp.text
            pages_scraped.append(url)
            all_text_parts.append(f"=== PAGE: {url} ===\n{_extract_text(homepage_html)}")
            logger.info(f"Homepage fetched: {len(resp.text)} bytes, status {resp.status_code}")

            # 2. Find nav links to scrape
            nav_links = _find_nav_links(homepage_html, url)
            logger.info(f"Found {len(nav_links)} nav links to scrape")

            # 3. Scrape additional pages
            for link in nav_links[:max_pages]:
                try:
                    resp = session.get(link, timeout=TIMEOUT, verify=verify_ssl)
                    resp.raise_for_status()
                    pages_scraped.append(link)
                    all_text_parts.append(
                        f"=== PAGE: {link} ===\n{_extract_text(resp.text)}"
                    )
                except Exception as e:
                    logger.debug(f"Failed to scrape {link}: {e}")
                    continue

            # Success — break out of retry loop
            break

        except requests.exceptions.SSLError as e:
            if verify_ssl:
                logger.warning(f"SSL error for {url}: {e}. Will retry without verification.")
                pages_scraped.clear()
                all_text_parts.clear()
                continue
            else:
                logger.error(f"SSL error even without verification for {url}: {e}")
                raise
        except requests.exceptions.ConnectionError as e:
            # Extract the root cause from the exception chain
            root = e
            while root.__cause__ or root.__context__:
                root = root.__cause__ or root.__context__
            detail = f"ConnectionError: {e} | Root: {type(root).__name__}: {root}"
            if verify_ssl:
                logger.warning(f"Connection error for {url}: {detail}. Will retry without SSL.")
                pages_scraped.clear()
                all_text_parts.clear()
                continue
            else:
                logger.error(f"Connection error on retry for {url}: {detail}")
                raise RuntimeError(detail) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error scraping {url}: {e}")
            raise

    # Combine all text, truncate to limit
    combined = "\n\n".join(all_text_parts)
    if len(combined) > MAX_CONTENT_LENGTH:
        combined = combined[:MAX_CONTENT_LENGTH]

    logger.info(f"Scrape complete: {len(pages_scraped)} pages, {len(combined)} chars of content")

    return {
        "raw_content": combined,
        "pages_scraped": pages_scraped,
    }
