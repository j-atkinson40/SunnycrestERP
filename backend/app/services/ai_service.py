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
