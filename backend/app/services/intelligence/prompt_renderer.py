"""Jinja2 rendering + variable validation + canonical input hashing."""

import hashlib
import json
from typing import Any

from jinja2 import Environment, StrictUndefined, UndefinedError, meta

from app.models.intelligence import IntelligencePromptVersion


class MissingVariableError(Exception):
    """Raised when required variables are missing for a prompt version render."""


class ResponseSchemaValidationError(Exception):
    """Raised when a response fails response_schema validation."""


_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,  # prompts are not HTML
    trim_blocks=False,
    lstrip_blocks=False,
)


def _required_variables(schema: dict[str, Any]) -> set[str]:
    """Extract the set of required variable names from a variable_schema dict.

    The schema shape is: {var_name: {type, required, description}}.
    A variable is required if `required` is truthy (defaults to True if absent).
    """
    required: set[str] = set()
    for name, spec in (schema or {}).items():
        if isinstance(spec, dict):
            if spec.get("required", True):
                required.add(name)
        else:
            # schema entry isn't a dict — assume required for safety
            required.add(name)
    return required


def validate_variables(
    version: IntelligencePromptVersion,
    variables: dict[str, Any],
) -> None:
    """Raise MissingVariableError listing required vars not present in `variables`.

    Also catches variables that Jinja templates reference but aren't declared
    in the schema — those are treated as required-by-usage.
    """
    variables = variables or {}
    schema_required = _required_variables(version.variable_schema or {})

    # Also extract undeclared template references
    try:
        sys_ast = _env.parse(version.system_prompt or "")
        user_ast = _env.parse(version.user_template or "")
        template_refs = meta.find_undeclared_variables(sys_ast) | meta.find_undeclared_variables(user_ast)
    except Exception:
        template_refs = set()

    required = schema_required | template_refs
    missing = sorted(v for v in required if v not in variables)
    if missing:
        raise MissingVariableError(
            f"Missing required variables: {', '.join(missing)}"
        )


def render(
    version: IntelligencePromptVersion,
    variables: dict[str, Any],
) -> tuple[str, str | list[dict[str, Any]]]:
    """Render (system_prompt, user_content) with the given variables.

    For text-only prompts (supports_vision=False, the default), user_content
    is a plain string (original Phase 1 contract).

    For vision prompts (supports_vision=True), user_content is a list whose
    first element is a {"type": "text", "text": rendered_user_template} block.
    `intelligence_service.execute` appends the caller-supplied content_blocks
    (images/documents) after this text block before sending to Anthropic.
    """
    validate_variables(version, variables)
    try:
        system = _env.from_string(version.system_prompt or "").render(**(variables or {}))
        user_text = _env.from_string(version.user_template or "").render(**(variables or {}))
    except UndefinedError as e:
        raise MissingVariableError(str(e)) from e

    if getattr(version, "supports_vision", False):
        # Vision prompts always return a list. If user_template was empty, we
        # still return a (possibly empty) text block so downstream code has a
        # stable shape. Anthropic tolerates empty text blocks.
        blocks: list[dict[str, Any]] = []
        if user_text.strip():
            blocks.append({"type": "text", "text": user_text})
        return system, blocks
    return system, user_text


def _hash_content_blocks(blocks: list[dict[str, Any]]) -> str:
    """Canonicalize a list of content blocks for hashing.

    Block bodies can be large (base64 PDF/image). We hash each block's
    base64 data separately and include only the digest in the overall canon
    so large payloads don't balloon the input_hash computation or the JSON
    payload we're hashing.
    """
    parts: list[dict[str, Any]] = []
    for block in blocks or []:
        btype = block.get("type") if isinstance(block, dict) else None
        if btype == "text":
            text = (block.get("text") or "") if isinstance(block, dict) else ""
            parts.append({"type": "text", "text": text})
        elif btype in ("image", "document"):
            source = (block.get("source") or {}) if isinstance(block, dict) else {}
            data = source.get("data") or ""
            media_type = source.get("media_type") or ""
            data_digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
            parts.append(
                {
                    "type": btype,
                    "media_type": media_type,
                    "data_sha256": data_digest,
                    "bytes_len": len(data),
                }
            )
        else:
            # Unknown block type — fall back to repr so the hash still differs
            parts.append({"type": "unknown", "repr": repr(block)[:200]})
    return json.dumps(parts, sort_keys=True, ensure_ascii=False)


def compute_input_hash(
    rendered_system: str,
    rendered_user: str | list[dict[str, Any]],
    model_preference: str,
) -> str:
    """Canonical SHA-256 of a render, used for A/B bucketing and dedup.

    Includes model_preference so switching routes invalidates prior buckets.
    Vision prompts' content blocks are canonicalized via `_hash_content_blocks`
    — same image + same text always produces the same hash, even though the
    raw base64 data is not stored in the hash input.
    """
    if isinstance(rendered_user, list):
        user_canon = _hash_content_blocks(rendered_user)
    else:
        user_canon = rendered_user

    payload = json.dumps(
        {
            "system": rendered_system,
            "user": user_canon,
            "model_preference": model_preference,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_response_against_schema(
    response: dict[str, Any] | list | None,
    response_schema: dict[str, Any] | None,
) -> None:
    """Lightweight JSON-schema-style check of required top-level keys.

    We keep this permissive on purpose — full JSON Schema validation would pull
    in jsonschema and we only need required-key checks today. Extend later
    when callers need type enforcement.
    """
    if not response_schema or not isinstance(response, dict):
        return
    required_keys = response_schema.get("required") or []
    missing = [k for k in required_keys if k not in response]
    if missing:
        raise ResponseSchemaValidationError(
            f"Response missing required keys: {', '.join(missing)}"
        )
