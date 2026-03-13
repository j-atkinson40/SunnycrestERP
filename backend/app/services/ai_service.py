import json
import logging
import re

import anthropic
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

# Model and token settings for all AI calls
AI_MODEL = "claude-sonnet-4-20250514"
AI_MAX_TOKENS = 1024


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences if present (```json ... ``` or ``` ... ```)."""
    stripped = text.strip()
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
    match = re.match(pattern, stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def call_anthropic(
    system_prompt: str,
    user_message: str,
    context_data: dict | None = None,
) -> dict:
    """
    Send a prompt to the Anthropic API and return parsed JSON.

    The system prompt is wrapped to enforce JSON-only responses.
    If context_data is provided, it is serialized and appended to the user message.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please set ANTHROPIC_API_KEY.",
        )

    # Wrap system prompt to enforce JSON response
    wrapped_system = (
        f"{system_prompt}\n\n"
        "IMPORTANT: You must respond with valid JSON only. "
        "No markdown, no code fences, no extra text. Just a JSON object."
    )

    # Build user message with optional context
    full_user_message = user_message
    if context_data:
        context_str = json.dumps(context_data, default=str)
        full_user_message = f"{user_message}\n\nContext data:\n{context_str}"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=AI_MODEL,
            max_tokens=AI_MAX_TOKENS,
            system=wrapped_system,
            messages=[{"role": "user", "content": full_user_message}],
        )

        # Extract text from response
        response_text = message.content[0].text

        # Strip code fences if present, then parse JSON
        cleaned = _strip_code_fences(response_text)
        parsed = json.loads(cleaned)
        return parsed

    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI service is temporarily busy. Please try again in a moment.",
        )
    except anthropic.AuthenticationError:
        logger.error("Anthropic authentication failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service authentication failed. Please check configuration.",
        )
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service encountered an error. Please try again.",
        )
    except json.JSONDecodeError:
        logger.warning(
            f"Failed to parse AI response as JSON: {response_text[:200]}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned an invalid response. Please try again.",
        )
    except Exception as e:
        logger.error(f"Unexpected AI service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred with the AI service.",
        )


# ---------------------------------------------------------------------------
# Inventory-specific AI parsing
# ---------------------------------------------------------------------------

_INVENTORY_SYSTEM_PROMPT = """\
You are an inventory management assistant for a food production company.
Your job is to parse natural-language inventory commands into structured JSON.

You will receive:
1. A user command (e.g. "Add 500 units of SKU-1042 to bin 4B")
2. A product catalog with id, name, and sku for each product

Return a JSON object with these fields:
{
  "action": one of "receive", "production", "write_off", "adjust",
  "product_id": the matched product's id (string) or null if unmatched,
  "product_name": the matched product's name or the name from user input,
  "product_sku": the matched product's SKU or the SKU from user input,
  "quantity": integer quantity parsed from the command (null if unclear),
  "location": storage location if mentioned (string or null),
  "reference": reference number if mentioned (string or null),
  "reason": reason for write-off if applicable (string or null),
  "notes": any additional notes (string or null),
  "confidence": "high", "medium", or "low",
  "ambiguous": true if the command is unclear or could be interpreted multiple ways,
  "clarification_message": a short message asking for clarification if ambiguous (null otherwise)
}

Rules:
- Match products by SKU first (exact or partial match), then by name (fuzzy).
- Keywords: "produce", "produced", "made", "manufacture" → action "production"
- Keywords: "receive", "received", "incoming", "delivery" → action "receive"
- Keywords: "write off", "writeoff", "damaged", "expired", "lost", "spoiled", "discard" → action "write_off"
- Keywords: "adjust", "set", "correct", "count" → action "adjust"
- If the user mentions adding/increasing stock without a specific keyword, default to "receive".
- For write_off, extract the reason from context (e.g. "damaged", "expired").
- If you cannot match a product from the catalog, set product_id to null and confidence to "low".
- If quantity is not specified, set it to null and set ambiguous to true.
- If the command mentions multiple products, return a JSON object with a "commands" array instead,
  where each element follows the same structure above.
"""


def parse_inventory_command(
    user_input: str,
    product_catalog: list[dict],
) -> dict:
    """
    Parse a natural-language inventory command into structured action data.

    Args:
        user_input: The user's free-text inventory command.
        product_catalog: List of dicts with keys: id, name, sku.

    Returns:
        Parsed command dict with action, product_id, quantity, etc.
    """
    return call_anthropic(
        system_prompt=_INVENTORY_SYSTEM_PROMPT,
        user_message=user_input,
        context_data={"product_catalog": product_catalog},
    )
