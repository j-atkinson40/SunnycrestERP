"""Model routing — decouples prompt `model_preference` from concrete model IDs.

Given a route_key (e.g. "extraction"), resolve_model returns the primary model,
optional fallback, and config. route_with_fallback wraps a call_fn so that
transient failures on the primary (rate limit, overload, timeout) fail over to
the fallback and record which model actually answered.
"""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.models.intelligence import IntelligenceModelRoute


class ModelRouteNotFoundError(Exception):
    """Raised when no route exists for a given preference key."""


class AllModelsFailedError(Exception):
    """Raised when primary and fallback both fail."""


@dataclass
class ResolvedRoute:
    route_key: str
    primary_model: str
    fallback_model: str | None
    max_tokens_default: int
    temperature_default: float
    provider: str


def is_vision_route(route_key: str) -> bool:
    """True iff the given route_key is the vision route.

    Used by intelligence_service.execute to warn when content_blocks are
    passed alongside a non-vision route (which would still work in some models
    but indicates caller confusion).
    """
    return route_key == "vision"


def resolve_model(db: Session, model_preference: str) -> ResolvedRoute:
    """Resolve a route_key to concrete model IDs + defaults."""
    route = (
        db.query(IntelligenceModelRoute)
        .filter(IntelligenceModelRoute.route_key == model_preference)
        .filter(IntelligenceModelRoute.is_active.is_(True))
        .first()
    )
    if route is None:
        raise ModelRouteNotFoundError(
            f"No active model route for preference: {model_preference!r}"
        )
    return ResolvedRoute(
        route_key=route.route_key,
        primary_model=route.primary_model,
        fallback_model=route.fallback_model,
        max_tokens_default=route.max_tokens_default,
        temperature_default=route.temperature_default,
        provider=route.provider,
    )


# Exception classes the caller's call_fn may raise that we treat as retryable
# with fallback. Imported lazily to avoid hard-binding on anthropic SDK types
# when the SDK is absent.
_RETRYABLE_EXC_NAMES = frozenset({
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "InternalServerError",
    "ServiceUnavailableError",
    # Anthropic sometimes raises OverloadedError or similar
    "OverloadedError",
})


def _is_retryable(exc: BaseException) -> bool:
    """True if this exception should trigger fallback to the secondary model.

    We match on exception class name to stay loosely coupled from the SDK.
    Concrete match for HTTPX / Anthropic timeout types is handled by name.
    """
    name = type(exc).__name__
    if name in _RETRYABLE_EXC_NAMES:
        return True
    # httpx timeouts
    if "Timeout" in name:
        return True
    return False


@dataclass
class FallbackResult:
    model_used: str
    fallback_used: bool
    response: object  # whatever call_fn returned


def route_with_fallback(
    route: ResolvedRoute,
    call_fn: Callable[[str], object],
) -> FallbackResult:
    """Invoke call_fn(model_id) on primary; on retryable error, retry on fallback.

    call_fn is expected to return whatever the caller needs (an Anthropic
    Message object, for example). This helper's only job is picking which
    model to pass and tracking which model actually answered.
    """
    try:
        response = call_fn(route.primary_model)
        return FallbackResult(
            model_used=route.primary_model,
            fallback_used=False,
            response=response,
        )
    except Exception as exc:  # noqa: BLE001 — we re-raise if non-retryable
        if not _is_retryable(exc):
            raise
        if route.fallback_model is None or route.fallback_model == route.primary_model:
            raise

    # Primary hit a retryable error and we have a distinct fallback
    try:
        response = call_fn(route.fallback_model)
        return FallbackResult(
            model_used=route.fallback_model,
            fallback_used=True,
            response=response,
        )
    except Exception as exc:
        raise AllModelsFailedError(
            f"Both primary ({route.primary_model}) and fallback "
            f"({route.fallback_model}) failed: {exc}"
        ) from exc
