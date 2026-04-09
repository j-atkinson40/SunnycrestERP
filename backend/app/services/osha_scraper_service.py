"""OSHA Standard Scraper Service.

Fetches OSHA standard text from osha.gov for use in safety program generation.
Uses httpx + BeautifulSoup (no browser automation needed — OSHA pages are static HTML).
"""

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Known OSHA standard URL patterns
OSHA_BASE_URL = "https://www.osha.gov/laws-regs/regulations/standardnumber"

# Map common standard codes to their URL paths
STANDARD_URL_MAP = {
    # General Industry (29 CFR 1910)
    "1910.132": "1910.132",   # PPE
    "1910.134": "1910.134",   # Respiratory Protection
    "1910.146": "1910.146",   # Permit-Required Confined Spaces
    "1910.147": "1910.147",   # Lockout/Tagout
    "1910.151": "1910.151",   # First Aid
    "1910.157": "1910.157",   # Portable Fire Extinguishers
    "1910.178": "1910.178",   # Powered Industrial Trucks (Forklifts)
    "1910.212": "1910.212",   # Machine Guarding
    "1910.1200": "1910.1200", # Hazard Communication (HazCom)
    "1910.38": "1910.38",     # Emergency Action Plans
    "1910.22": "1910.22",     # Walking-Working Surfaces
    "1910.95": "1910.95",     # Occupational Noise Exposure
    # Construction (29 CFR 1926)
    "1926.501": "1926.501",   # Fall Protection
    "1926.1153": "1926.1153", # Respirable Crystalline Silica
}

# User agent for polite scraping
HEADERS = {
    "User-Agent": "Bridgeable-SafetyPlatform/1.0 (safety program generation; +https://getbridgeable.com)",
    "Accept": "text/html",
}

REQUEST_TIMEOUT = 15.0


def scrape_osha_standard(standard_code: str) -> dict:
    """Scrape an OSHA standard page and extract the regulation text.

    Args:
        standard_code: e.g. "1910.147" for Lockout/Tagout

    Returns:
        {
            "success": bool,
            "standard_code": str,
            "url": str,
            "title": str | None,
            "text": str | None,   # cleaned regulation text (truncated to ~15000 chars)
            "error": str | None,
        }
    """
    # Normalize code
    code = standard_code.strip()
    if code.startswith("29 CFR "):
        code = code.replace("29 CFR ", "")

    url_path = STANDARD_URL_MAP.get(code, code)
    url = f"{OSHA_BASE_URL}/{url_path}"

    result = {
        "success": False,
        "standard_code": code,
        "url": url,
        "title": None,
        "text": None,
        "error": None,
    }

    try:
        logger.info(f"Scraping OSHA standard {code} from {url}")
        resp = httpx.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title
        title_el = soup.find("h1")
        if title_el:
            result["title"] = title_el.get_text(strip=True)

        # Extract main content — OSHA standard pages use <div class="field--name-body">
        content_div = (
            soup.find("div", class_="field--name-body")
            or soup.find("div", class_="node__content")
            or soup.find("article")
            or soup.find("main")
        )

        if content_div:
            # Remove script/style tags
            for tag in content_div.find_all(["script", "style", "nav", "header", "footer"]):
                tag.decompose()

            text = content_div.get_text(separator="\n", strip=True)
            # Clean up excessive whitespace
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)

            # Truncate to reasonable size for Claude prompt
            max_chars = 15000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[... truncated for length ...]"

            result["text"] = text
            result["success"] = True
        else:
            result["error"] = "Could not find main content on OSHA page"
            logger.warning(f"No content div found for {code} at {url}")

    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP {e.response.status_code}: {str(e)[:200]}"
        logger.warning(f"OSHA scrape HTTP error for {code}: {result['error']}")
    except httpx.TimeoutException:
        result["error"] = "Request timed out"
        logger.warning(f"OSHA scrape timeout for {code}")
    except Exception as e:
        result["error"] = str(e)[:500]
        logger.error(f"OSHA scrape error for {code}: {e}", exc_info=True)

    return result


def scrape_osha_topic_page(topic_url: str) -> dict:
    """Scrape an OSHA topic overview page (e.g., osha.gov/lockout-tagout).

    Returns summary text for supplemental context.
    """
    result = {
        "success": False,
        "url": topic_url,
        "title": None,
        "text": None,
        "error": None,
    }

    try:
        resp = httpx.get(topic_url, headers=HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        title_el = soup.find("h1")
        if title_el:
            result["title"] = title_el.get_text(strip=True)

        content = (
            soup.find("div", class_="field--name-body")
            or soup.find("div", class_="node__content")
            or soup.find("main")
        )

        if content:
            for tag in content.find_all(["script", "style", "nav"]):
                tag.decompose()

            text = content.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)

            # Topic pages are typically shorter; cap at 8000 chars
            if len(text) > 8000:
                text = text[:8000] + "\n\n[... truncated ...]"

            result["text"] = text
            result["success"] = True
        else:
            result["error"] = "Could not find content on OSHA topic page"

    except Exception as e:
        result["error"] = str(e)[:500]
        logger.warning(f"OSHA topic page scrape error: {e}")

    return result
