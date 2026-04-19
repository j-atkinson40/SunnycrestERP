"""The primary entry point for every AI call in Bridgeable.

Phase 1 behavior:
  1. Look up active version via prompt_registry (tenant override beats platform)
  2. If an active experiment exists, assign variant and use that version instead
  3. Validate and render variables
  4. Compute input_hash
  5. Resolve the model route
  6. Call Anthropic with fallback-on-retryable
  7. Parse response (force_json → JSON parse; else freeform)
  8. Persist an intelligence_executions row with full caller linkage
  9. Return IntelligenceResult

No caller has been migrated yet — this is exercised by Phase 1 tests and by
the /api/v1/intelligence/prompts/{id}/test playground endpoint.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.intelligence import (
    IntelligenceExecution,
    IntelligenceExperiment,
    IntelligencePrompt,
    IntelligencePromptVersion,
)
from app.services.intelligence import cost_service, experiment_service, model_router
from app.services.intelligence import prompt_registry, prompt_renderer

logger = logging.getLogger(__name__)


class PromptNotFoundError(prompt_registry.PromptNotFoundError):
    """Re-exported here for ergonomic imports."""


class MissingVariableError(prompt_renderer.MissingVariableError):
    """Re-exported here for ergonomic imports."""


class IntelligenceError(Exception):
    """Runtime validation error raised by execute() — e.g. vision prompt called
    without content_blocks, or malformed content blocks."""


# Content block validation (Phase 2c-0b)
_ALLOWED_IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
_ALLOWED_DOCUMENT_MEDIA_TYPES = frozenset({"application/pdf"})


def _validate_content_blocks(blocks: list[dict[str, Any]]) -> None:
    """Sanity-check every content block before we hand it to Anthropic.

    Shape expected (Anthropic's API):
      {"type": "image",    "source": {"type": "base64", "media_type": "image/jpeg", "data": "..."}}
      {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "..."}}

    Raises IntelligenceError on any malformed entry. This runs BEFORE the
    call so we don't waste tokens on a bad request.
    """
    if not isinstance(blocks, list):
        raise IntelligenceError(
            f"content_blocks must be a list, got {type(blocks).__name__}"
        )
    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise IntelligenceError(f"content_blocks[{i}] is not a dict")
        btype = block.get("type")
        if btype not in ("image", "document"):
            raise IntelligenceError(
                f"content_blocks[{i}].type must be 'image' or 'document' (got {btype!r})"
            )
        source = block.get("source")
        if not isinstance(source, dict):
            raise IntelligenceError(
                f"content_blocks[{i}].source must be a dict"
            )
        if source.get("type") != "base64":
            raise IntelligenceError(
                f"content_blocks[{i}].source.type must be 'base64' (got {source.get('type')!r})"
            )
        media_type = source.get("media_type")
        if btype == "image" and media_type not in _ALLOWED_IMAGE_MEDIA_TYPES:
            raise IntelligenceError(
                f"content_blocks[{i}].source.media_type {media_type!r} is not an allowed image type"
            )
        if btype == "document" and media_type not in _ALLOWED_DOCUMENT_MEDIA_TYPES:
            raise IntelligenceError(
                f"content_blocks[{i}].source.media_type {media_type!r} is not an allowed document type"
            )
        data = source.get("data")
        if not isinstance(data, str) or not data:
            raise IntelligenceError(
                f"content_blocks[{i}].source.data must be a non-empty base64 string"
            )


@dataclass
class IntelligenceResult:
    """Return value from intelligence_service.execute.

    Callers read .response_parsed when force_json was set (or response_text for
    freeform prompts). execution_id is the audit trail id — always logged.
    """
    execution_id: str
    prompt_id: str | None
    prompt_version_id: str | None
    model_used: str | None
    status: str
    response_text: str | None
    response_parsed: dict | list | None
    rendered_system_prompt: str
    rendered_user_prompt: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    cost_usd: Decimal | None
    experiment_variant: str | None = None
    fallback_used: bool = False
    error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _serialize_user_for_storage(user_content: str | list[dict[str, Any]]) -> str:
    """Redact a rendered user payload for safe storage in the audit row.

    Text prompts return the string as-is. Vision payloads become a JSON dump
    where each image/document block is replaced with {type, media_type,
    bytes_len, data_sha256} — no raw base64 — so the audit row is compact
    and does not leak sensitive document contents into logs.
    """
    import hashlib as _hashlib

    if isinstance(user_content, str):
        return user_content
    if not isinstance(user_content, list):
        return json.dumps({"__unknown_content__": repr(user_content)[:500]})

    redacted: list[dict[str, Any]] = []
    for block in user_content:
        if not isinstance(block, dict):
            redacted.append({"type": "unknown", "repr": repr(block)[:200]})
            continue
        btype = block.get("type")
        if btype == "text":
            redacted.append({"type": "text", "text": block.get("text", "")})
        elif btype in ("image", "document"):
            source = block.get("source") or {}
            data = source.get("data") or ""
            redacted.append(
                {
                    "type": btype,
                    "media_type": source.get("media_type"),
                    "bytes_len": len(data),
                    "data_sha256": _hashlib.sha256(data.encode("utf-8")).hexdigest(),
                }
            )
        else:
            redacted.append({"type": str(btype or "unknown")})
    return json.dumps(redacted, ensure_ascii=False)


def _strip_code_fences(text: str) -> str:
    stripped = (text or "").strip()
    m = _FENCE_RE.match(stripped)
    return m.group(1).strip() if m else stripped


def _parse_json(response_text: str) -> dict | list | None:
    """Attempt JSON parse; return None on failure rather than raising.

    Callers that declared force_json get parse errors surfaced via status=parse_error.
    """
    if not response_text:
        return None
    try:
        return json.loads(_strip_code_fences(response_text))
    except json.JSONDecodeError:
        return None


def _build_system_with_json_wrap(system: str) -> str:
    """Append a JSON-only directive — mirrors legacy call_anthropic behavior."""
    return (
        f"{system}\n\n"
        "IMPORTANT: You must respond with valid JSON only. "
        "No markdown, no code fences, no extra text. Just a JSON object."
    )


def _call_anthropic(
    *,
    client: anthropic.Anthropic,
    model: str,
    system: str,
    user: str | list[dict[str, Any]],
    max_tokens: int,
    temperature: float,
    tools: list | None,
):
    """Non-streaming messages.create wrapper.

    `user` is either a plain string (text-only prompt) or a list of content
    blocks (vision prompt with text + image/document). Both shapes are valid
    Anthropic payloads — the SDK accepts `content` as string OR list.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)


def _extract_text(message) -> str:
    """Pull the plain-text response from an Anthropic Message.

    For tool-use responses we return the concatenated text blocks; tool_use
    blocks are returned as their input JSON so callers can inspect them.
    """
    parts: list[str] = []
    for block in (getattr(message, "content", None) or []):
        block_type = getattr(block, "type", None)
        if block_type == "text":
            parts.append(getattr(block, "text", "") or "")
        elif block_type == "tool_use":
            try:
                parts.append(json.dumps(getattr(block, "input", {}) or {}))
            except (TypeError, ValueError):
                pass
    return "".join(parts)


def _get_client() -> anthropic.Anthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured; cannot execute prompts."
        )
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _select_version(
    db: Session,
    prompt_key: str,
    company_id: str | None,
    experiment_id: str | None,
    input_hash: str | None,
) -> tuple[
    IntelligencePrompt,
    IntelligencePromptVersion,
    tuple[str, str] | None,  # (experiment_id, variant) or None
]:
    """Resolve the prompt + version to use for this call.

    Flow:
      1. Load the platform/tenant prompt for prompt_key.
      2. Check for an active experiment on that prompt (caller-supplied id wins).
      3. If an experiment is running, assign a variant and use that version.
      4. Otherwise use the prompt's active version.

    input_hash is only used if an experiment is active. If caller doesn't have
    it yet (we haven't rendered), we defer — assignment is performed after
    render in execute().
    """
    prompt = prompt_registry.get_prompt(db, prompt_key, company_id)
    default_version = prompt_registry.get_active_version(db, prompt_key, company_id)
    return prompt, default_version, None


def execute(
    db: Session,
    prompt_key: str,
    variables: dict[str, Any] | None = None,
    company_id: str | None = None,
    caller_module: str = "unknown",
    caller_entity_type: str | None = None,
    caller_entity_id: str | None = None,
    caller_workflow_run_id: str | None = None,
    caller_workflow_step_id: str | None = None,
    caller_workflow_run_step_id: str | None = None,
    caller_agent_job_id: str | None = None,
    caller_conversation_id: str | None = None,
    caller_command_bar_session_id: str | None = None,
    # Phase 2c-0a — extended linkage kwargs
    caller_accounting_analysis_run_id: str | None = None,
    caller_price_list_import_id: str | None = None,
    caller_fh_case_id: str | None = None,
    caller_ringcentral_call_log_id: str | None = None,
    caller_kb_document_id: str | None = None,
    caller_import_session_id: str | None = None,
    experiment_id: str | None = None,
    override_model: str | None = None,
    stream: bool = False,
    tools: list | None = None,
    # Phase 2c-0b — multimodal content blocks (images, PDFs).
    # Caller supplies a list of Anthropic-shape content blocks. Each block:
    #   {"type": "image"|"document", "source": {"type": "base64", "media_type": ..., "data": ...}}
    content_blocks: list[dict[str, Any]] | None = None,
    override_version_id: str | None = None,
    persist: bool = True,
    # Phase 3b — admin test runs set this True so the execution doesn't
    # pollute production stats. Stats endpoints filter WHERE = False.
    is_test_execution: bool = False,
    client_factory: Callable[[], anthropic.Anthropic] | None = None,
) -> IntelligenceResult:
    """Execute a prompt by key, record an audit row, return the result.

    `override_version_id` lets the playground endpoint test a specific version
    without respecting the active-version flag. `persist=False` lets the
    playground render/execute without saving an execution row.
    `client_factory` is a test seam.
    """
    variables = variables or {}

    # ── 1. Resolve prompt + default (active) version ────────────────────
    prompt_row: IntelligencePrompt | None = None
    version: IntelligencePromptVersion | None = None
    if override_version_id:
        version = (
            db.query(IntelligencePromptVersion)
            .filter_by(id=override_version_id)
            .first()
        )
        if version is None:
            raise PromptNotFoundError(f"Version not found: {override_version_id}")
        prompt_row = db.query(IntelligencePrompt).filter_by(id=version.prompt_id).first()
    else:
        prompt_row, version, _ = _select_version(
            db, prompt_key, company_id, experiment_id, None
        )

    # ── 2. Validate + render ────────────────────────────────────────────
    # (Render uses the default version first; if an experiment routes us to a
    # different version we re-render below.)
    rendered_system, rendered_user = prompt_renderer.render(version, variables)

    # ── 3. Experiment resolution (after render, so input_hash is stable) ─
    variant_label: str | None = None
    active_experiment = None
    if not override_version_id and prompt_row is not None:
        if experiment_id:
            active_experiment = (
                db.query(IntelligenceExperiment)
                .filter_by(id=experiment_id)
                .first()
            )
            if active_experiment and active_experiment.status != "active":
                active_experiment = None
        else:
            active_experiment = experiment_service.get_active_experiment(
                db, prompt_row.id, company_id
            )

    # We need input_hash for deterministic assignment; compute after render
    input_hash = prompt_renderer.compute_input_hash(
        rendered_system, rendered_user, version.model_preference
    )
    if active_experiment is not None:
        variant_label = experiment_service.assign_variant(active_experiment, input_hash)
        variant_version_id = experiment_service.version_for_variant(
            active_experiment, variant_label
        )
        if variant_version_id != version.id:
            version = (
                db.query(IntelligencePromptVersion).filter_by(id=variant_version_id).first()
            )
            if version is None:
                raise PromptNotFoundError(
                    f"Experiment points to missing version: {variant_version_id}"
                )
            # Re-render with the variant's templates
            rendered_system, rendered_user = prompt_renderer.render(version, variables)
            input_hash = prompt_renderer.compute_input_hash(
                rendered_system, rendered_user, version.model_preference
            )

    # ── 3b. Multimodal validation + content_blocks merge (Phase 2c-0b) ──
    supports_vision = bool(getattr(version, "supports_vision", False))
    if supports_vision and content_blocks is None:
        raise IntelligenceError(
            f"Prompt {prompt_key!r} (version {version.id}) has supports_vision=True "
            "but was invoked without content_blocks. Pass an 'image' or 'document' "
            "block via the content_blocks kwarg."
        )
    if not supports_vision and content_blocks:
        raise IntelligenceError(
            f"Prompt {prompt_key!r} (version {version.id}) has supports_vision=False "
            "but content_blocks were supplied. Either remove content_blocks or migrate "
            "this caller to a vision-capable prompt_key."
        )
    if supports_vision and content_blocks:
        _validate_content_blocks(content_blocks)
        # Renderer returns a list[dict] for vision prompts; append the caller's
        # content blocks after the text block. Defensive: if somehow rendered_user
        # came back as a string, wrap it first so the final payload is valid.
        if not isinstance(rendered_user, list):
            rendered_user = (
                [{"type": "text", "text": rendered_user}] if rendered_user else []
            )
        rendered_user = list(rendered_user) + list(content_blocks)
        # Re-hash with the full payload so A/B bucketing + dedup see the same
        # hash for identical image+text across calls.
        input_hash = prompt_renderer.compute_input_hash(
            rendered_system, rendered_user, version.model_preference
        )

    # ── 4. Resolve model ─────────────────────────────────────────────────
    route = model_router.resolve_model(db, version.model_preference)

    # If force_json is set, append the JSON-only directive
    system_for_call = (
        _build_system_with_json_wrap(rendered_system) if version.force_json else rendered_system
    )

    max_tokens = version.max_tokens or route.max_tokens_default
    temperature = (
        version.temperature if version.temperature is not None else route.temperature_default
    )

    # ── 5. Call Anthropic with fallback ──────────────────────────────────
    factory = client_factory or _get_client
    client = factory()

    started = time.monotonic()
    status = "success"
    error_message: str | None = None
    response_text: str = ""
    response_parsed: dict | list | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    model_used: str | None = override_model
    fallback_used = False

    try:
        if override_model:
            message = _call_anthropic(
                client=client,
                model=override_model,
                system=system_for_call,
                user=rendered_user,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
            )
        else:
            fr = model_router.route_with_fallback(
                route,
                lambda model_id: _call_anthropic(
                    client=client,
                    model=model_id,
                    system=system_for_call,
                    user=rendered_user,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                ),
            )
            message = fr.response
            model_used = fr.model_used
            fallback_used = fr.fallback_used
            if fallback_used:
                status = "fallback_used"

        # Extract text + usage
        response_text = _extract_text(message)
        usage = getattr(message, "usage", None)
        if usage is not None:
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)

        # Parse JSON if force_json
        if version.force_json:
            response_parsed = _parse_json(response_text)
            if response_parsed is None:
                status = "parse_error"
                error_message = "force_json=True but response was not valid JSON"
            else:
                try:
                    prompt_renderer.validate_response_against_schema(
                        response_parsed, version.response_schema
                    )
                except prompt_renderer.ResponseSchemaValidationError as e:
                    status = "parse_error"
                    error_message = str(e)

    except anthropic.RateLimitError as e:
        status = "rate_limited"
        error_message = str(e)
        logger.warning("Intelligence rate_limited: %s", e)
    except model_router.AllModelsFailedError as e:
        status = "api_error"
        error_message = str(e)
        logger.error("Intelligence all-models-failed: %s", e)
    except anthropic.APIError as e:
        status = "api_error"
        error_message = str(e)
        logger.error("Intelligence api_error: %s", e)
    except Exception as e:  # noqa: BLE001 — record, then re-raise at end if needed
        exc_name = type(e).__name__
        if "Timeout" in exc_name:
            status = "timeout"
        else:
            status = "api_error"
        error_message = f"{exc_name}: {e}"
        logger.exception("Intelligence unexpected error")

    latency_ms = int((time.monotonic() - started) * 1000)

    cost_usd: Decimal | None = None
    if model_used is not None:
        cost_usd = cost_service.compute_cost(db, model_used, input_tokens, output_tokens)

    # Serialize rendered_user for storage. Vision payloads are lists of
    # content blocks; we persist a redacted JSON representation that keeps
    # text + a hash/size fingerprint for each image/document, so the audit
    # row stays small and reproducible (without storing multi-MB base64 blobs).
    rendered_user_for_storage = _serialize_user_for_storage(rendered_user)

    # ── 6. Persist execution row ─────────────────────────────────────────
    execution_id = ""
    if persist:
        row = IntelligenceExecution(
            company_id=company_id,
            prompt_id=prompt_row.id if prompt_row is not None else None,
            prompt_version_id=version.id,
            model_preference=version.model_preference,
            model_used=model_used,
            input_hash=input_hash,
            input_variables=variables,
            rendered_system_prompt=rendered_system,
            rendered_user_prompt=rendered_user_for_storage,
            response_text=response_text or None,
            response_parsed=response_parsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            status=status,
            error_message=error_message,
            caller_module=caller_module,
            caller_entity_type=caller_entity_type,
            caller_entity_id=caller_entity_id,
            caller_workflow_run_id=caller_workflow_run_id,
            caller_workflow_step_id=caller_workflow_step_id,
            caller_workflow_run_step_id=caller_workflow_run_step_id,
            caller_agent_job_id=caller_agent_job_id,
            caller_conversation_id=caller_conversation_id,
            caller_command_bar_session_id=caller_command_bar_session_id,
            caller_accounting_analysis_run_id=caller_accounting_analysis_run_id,
            caller_price_list_import_id=caller_price_list_import_id,
            caller_fh_case_id=caller_fh_case_id,
            caller_ringcentral_call_log_id=caller_ringcentral_call_log_id,
            caller_kb_document_id=caller_kb_document_id,
            caller_import_session_id=caller_import_session_id,
            experiment_id=active_experiment.id if active_experiment is not None else None,
            experiment_variant=variant_label,
            is_test_execution=is_test_execution,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        execution_id = row.id

    return IntelligenceResult(
        execution_id=execution_id,
        prompt_id=prompt_row.id if prompt_row is not None else None,
        prompt_version_id=version.id,
        model_used=model_used,
        status=status,
        response_text=response_text or None,
        response_parsed=response_parsed,
        rendered_system_prompt=rendered_system,
        rendered_user_prompt=rendered_user_for_storage,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        experiment_variant=variant_label,
        fallback_used=fallback_used,
        error_message=error_message,
    )
