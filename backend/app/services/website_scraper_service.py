"""Website scraper — fetches and extracts text content from tenant websites."""

import json
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MAX_CONTENT_LENGTH = 50_000
TIMEOUT = 30.0

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


def scrape_website(url: str, max_pages: int = 5) -> dict:
    """Scrape a website and extract text content.

    Returns: {"raw_content": str, "pages_scraped": list[str]}
    """
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    pages_scraped: list[str] = []
    all_text_parts: list[str] = []

    try:
        with httpx.Client(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        ) as client:
            # 1. Fetch homepage
            resp = client.get(url)
            resp.raise_for_status()
            homepage_html = resp.text
            pages_scraped.append(url)
            all_text_parts.append(f"=== PAGE: {url} ===\n{_extract_text(homepage_html)}")

            # 2. Find nav links to scrape
            nav_links = _find_nav_links(homepage_html, url)

            # 3. Scrape additional pages
            for link in nav_links[:max_pages]:
                try:
                    resp = client.get(link)
                    resp.raise_for_status()
                    pages_scraped.append(link)
                    all_text_parts.append(
                        f"=== PAGE: {link} ===\n{_extract_text(resp.text)}"
                    )
                except Exception as e:
                    logger.debug(f"Failed to scrape {link}: {e}")
                    continue

    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.warning(f"First scrape attempt failed for {url}: {e}. Retrying with relaxed SSL...")
        # Retry with SSL verification disabled (some sites have cert issues from datacenter IPs)
        try:
            with httpx.Client(
                timeout=TIMEOUT,
                follow_redirects=True,
                verify=False,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            ) as client:
                resp = client.get(url)
                resp.raise_for_status()
                homepage_html = resp.text
                pages_scraped.append(url)
                all_text_parts.append(f"=== PAGE: {url} ===\n{_extract_text(homepage_html)}")
                nav_links = _find_nav_links(homepage_html, url)
                for link in nav_links[:max_pages]:
                    try:
                        resp = client.get(link)
                        resp.raise_for_status()
                        pages_scraped.append(link)
                        all_text_parts.append(f"=== PAGE: {link} ===\n{_extract_text(resp.text)}")
                    except Exception:
                        continue
        except Exception as retry_err:
            logger.error(f"Retry also failed for {url}: {retry_err}")
            raise

    # Combine all text, truncate to limit
    combined = "\n\n".join(all_text_parts)
    if len(combined) > MAX_CONTENT_LENGTH:
        combined = combined[:MAX_CONTENT_LENGTH]

    return {
        "raw_content": combined,
        "pages_scraped": pages_scraped,
    }
