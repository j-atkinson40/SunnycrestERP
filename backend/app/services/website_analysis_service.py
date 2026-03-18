"""Website analysis — calls Claude Haiku to extract structured business info."""

import json
import logging
import re

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048
# ~15000 tokens ≈ 60000 chars
MAX_CONTENT_CHARS = 60_000

SYSTEM_PROMPT = """\
You are a business intelligence analyst examining a company's website content.
Extract structured information about this business, focusing on precast concrete /
burial vault / funeral product manufacturing. If the business is in a different
industry, adapt your analysis accordingly.

Return a JSON object with these fields:

{
  "business_name": "string — company name",
  "industry": "string — primary industry (e.g. 'precast_concrete', 'burial_vaults', 'funeral_products', 'general_manufacturing', 'other')",
  "description": "string — 1-2 sentence business summary",
  "product_lines": [
    {"name": "string", "confidence": 0.0-1.0, "evidence": "string — quote or reference from content"}
  ],
  "vault_lines": [
    {"name": "string", "confidence": 0.0-1.0, "evidence": "string"}
  ],
  "certifications": [
    {"name": "string", "type": "string — e.g. 'npca', 'iso', 'other'", "confidence": 0.0-1.0, "evidence": "string"}
  ],
  "npca_certified": {"detected": true/false, "confidence": 0.0-1.0, "evidence": "string or null"},
  "spring_burials": {"detected": true/false, "confidence": 0.0-1.0, "evidence": "string or null"},
  "urn_categories": [
    {"name": "string", "confidence": 0.0-1.0, "evidence": "string"}
  ],
  "services": ["string — list of services offered"],
  "locations": ["string — any mentioned locations or service areas"],
  "key_differentiators": ["string — notable capabilities or selling points"],
  "recommended_extensions": [
    {"key": "string — extension identifier", "reason": "string", "confidence": 0.0-1.0}
  ],
  "summary": "string — 2-3 sentence onboarding summary with recommendations"
}

Rules:
- Set confidence between 0.0 and 1.0 based on how clearly the info is stated.
- Only include items you actually find evidence for; do not fabricate.
- For vault_lines, look for brand names like Wilbert, Trigard, etc.
- For spring_burials, look for references to winter/spring burial, temporary storage, seasonal burial.
- For NPCA, look for "National Precast Concrete Association" or "NPCA certified/member".
- For urn_categories, look for cremation urns, keepsakes, companion urns, etc.
- recommended_extensions should map to: vault_program, spring_burial, cremation_tracking, npca_compliance, urn_catalog.
"""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    stripped = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
    match = re.match(pattern, stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def analyze_website_content(raw_content: str) -> dict:
    """Call Claude Haiku to extract structured business info.

    Returns: {"analysis": dict, "input_tokens": int, "output_tokens": int}
    """
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    # Truncate content to fit token limits
    truncated = raw_content[:MAX_CONTENT_CHARS]

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze the following website content and extract structured "
                    "business information. Respond with valid JSON only.\n\n"
                    f"{truncated}"
                ),
            }
        ],
    )

    response_text = message.content[0].text
    cleaned = _strip_code_fences(response_text)

    try:
        analysis = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse analysis JSON: {response_text[:200]}")
        analysis = {"error": "Failed to parse AI response", "raw": response_text[:500]}

    return {
        "analysis": analysis,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
