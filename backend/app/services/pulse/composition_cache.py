"""Pulse composition cache — work_areas-aware invalidation.

Per D1: 5-minute composition cache keyed on
  ``pulse:{user_id}:{work_areas_hash}:{minute_window}``

Where:
  • `work_areas_hash` = stable SHA-256 prefix of the user's
    work_areas list (sorted, joined). When the user updates
    work_areas, the hash changes → cache key changes → next request
    misses → composition recomputes against the new work areas.
    This is the active-invalidation mechanism per D1.
  • `minute_window` = `current_unix_minute // 5` (5-minute buckets).
    Once a key is written it lives in this bucket; the next bucket
    re-keys naturally so stale data ages out within 5 minutes
    regardless of TTL semantics in the underlying store.

**Two-tier storage:**
  1. Redis when `REDIS_URL` is configured (production path).
  2. In-memory dict fallback when Redis unavailable (dev / tests).

Both implementations use the same key shape; switching between them
is a deployment configuration concern, not an API one.

**TTL = 5 minutes** — both Redis and in-memory honor it. Combined
with the minute-window key, stale data is bounded to 5 minutes max.
A user explicitly editing work_areas + immediately reloading Pulse
hits a cache miss (different hash) and sees the new composition
within one round trip.

**Manual refresh bypass** is implemented at the API layer
(`?refresh=true` query param) — this module exposes invalidation
via `invalidate_for_user()` which the API can call directly.

**Tests / dev caveat:** the in-memory store is per-process. Pytest's
test client runs in the same process so state persists across
requests within a test; explicit `_test_clear()` resets it between
test cases. Redis is process-shared by definition.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.pulse.types import (
    IntelligenceStream,
    LayerContent,
    LayerItem,
    PulseComposition,
    PulseCompositionMetadata,
    ReferencedItem,
)

logger = logging.getLogger(__name__)


CACHE_TTL_SECONDS = 5 * 60  # 5 minutes per D1


# ── In-memory fallback store ────────────────────────────────────────


# (key → (expires_at_unix, payload_json)). Per-process; matches the
# typical "no Redis configured" dev path.
_MEMORY_STORE: dict[str, tuple[float, str]] = {}


def _test_clear() -> None:
    """Clear the in-memory store. Tests call this in their setup
    teardown to isolate cache state across test cases."""
    _MEMORY_STORE.clear()


# ── Key construction ────────────────────────────────────────────────


def _hash_work_areas(work_areas: list[str] | None) -> str:
    """Stable hash of the user's work_areas. Returns "none" when
    work_areas is missing/empty so cache keys are still stable for
    the vertical-default fallback path."""
    if not work_areas:
        return "none"
    # Sort for stability across order changes; user's selection
    # order doesn't affect composition.
    sorted_areas = sorted(work_areas)
    payload = "|".join(sorted_areas).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _minute_window(now: datetime | None = None) -> int:
    """Current 5-minute window — `unix_minute // 5`."""
    n = now or datetime.now(timezone.utc)
    unix_minutes = int(n.timestamp() // 60)
    return unix_minutes // 5


def cache_key(
    *,
    user_id: str,
    work_areas: list[str] | None,
    now: datetime | None = None,
) -> str:
    """Construct the canonical cache key for a user + work_areas at a
    given minute window. Public so the API layer can also key
    cache-aware refreshes (e.g., conditional warm-up jobs)."""
    return (
        f"pulse:{user_id}:{_hash_work_areas(work_areas)}:"
        f"{_minute_window(now)}"
    )


# ── Serialization ──────────────────────────────────────────────────


def _dataclass_to_dict(obj: Any) -> Any:
    """Serialize PulseComposition to a JSON-compatible dict.

    `asdict` from dataclasses recurses but doesn't handle datetime
    (we ISO-format manually). Frozen dataclasses round-trip cleanly
    through JSON when datetimes are stringified.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _dataclass_to_dict(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, list):
        return [_dataclass_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    return obj


def _serialize(comp: PulseComposition) -> str:
    return json.dumps(_dataclass_to_dict(comp))


def _deserialize(s: str) -> PulseComposition:
    """Reconstruct a `PulseComposition` from its serialized form.

    Layer items + intelligence streams + referenced items + metadata
    all need explicit reconstruction since `json.loads` only gives
    plain dicts. Frozen dataclasses are constructed positionally
    here for tightness.
    """
    raw = json.loads(s)
    return PulseComposition(
        user_id=raw["user_id"],
        composed_at=datetime.fromisoformat(raw["composed_at"]),
        layers=[
            LayerContent(
                layer=lc["layer"],
                items=[
                    LayerItem(
                        item_id=it["item_id"],
                        kind=it["kind"],
                        component_key=it["component_key"],
                        variant_id=it["variant_id"],
                        cols=it["cols"],
                        rows=it["rows"],
                        priority=it["priority"],
                        payload=it.get("payload") or {},
                        dismissed=it.get("dismissed", False),
                    )
                    for it in lc["items"]
                ],
                advisory=lc.get("advisory"),
            )
            for lc in raw["layers"]
        ],
        intelligence_streams=[
            IntelligenceStream(
                stream_id=s["stream_id"],
                layer=s["layer"],
                title=s["title"],
                synthesized_text=s["synthesized_text"],
                referenced_items=[
                    ReferencedItem(
                        kind=r["kind"],
                        entity_id=r["entity_id"],
                        label=r["label"],
                        href=r.get("href"),
                    )
                    for r in s["referenced_items"]
                ],
                priority=s["priority"],
            )
            for s in raw["intelligence_streams"]
        ],
        metadata=PulseCompositionMetadata(
            work_areas_used=raw["metadata"]["work_areas_used"],
            vertical_default_applied=raw["metadata"][
                "vertical_default_applied"
            ],
            time_of_day_signal=raw["metadata"]["time_of_day_signal"],
        ),
    )


# ── Backend dispatch (Redis when available, in-memory fallback) ────


def _redis_or_none():
    """Lazy import + best-effort acquire — returns None when Redis
    isn't configured or unreachable. Identical degradation to other
    callers of `app.core.redis.get_redis`."""
    try:
        from app.core.redis import get_redis

        return get_redis()
    except Exception:
        return None


def get(key: str) -> PulseComposition | None:
    """Return cached composition for `key` or None on miss."""
    r = _redis_or_none()
    if r is not None:
        try:
            raw = r.get(key)
            if raw is None:
                return None
            return _deserialize(raw)
        except Exception as exc:
            # Best-effort — cache failure must not break composition.
            logger.warning("pulse cache redis-get failed: %s", exc)
            return None

    # In-memory fallback.
    entry = _MEMORY_STORE.get(key)
    if entry is None:
        return None
    expires_at, payload = entry
    if time.time() > expires_at:
        _MEMORY_STORE.pop(key, None)
        return None
    try:
        return _deserialize(payload)
    except Exception:
        # Corrupt entry — drop + miss.
        _MEMORY_STORE.pop(key, None)
        return None


def put(key: str, comp: PulseComposition) -> None:
    """Write composition under `key` with 5-minute TTL."""
    try:
        payload = _serialize(comp)
    except Exception as exc:
        logger.warning("pulse cache serialization failed: %s", exc)
        return

    r = _redis_or_none()
    if r is not None:
        try:
            r.setex(key, CACHE_TTL_SECONDS, payload)
            return
        except Exception as exc:
            logger.warning("pulse cache redis-put failed: %s", exc)
            # Fall through to memory store; defense-in-depth.

    _MEMORY_STORE[key] = (time.time() + CACHE_TTL_SECONDS, payload)


def invalidate_for_user(user_id: str) -> int:
    """Drop all cached compositions for a given user across all
    work_areas hashes + minute windows. Useful when:
      • User updates work_areas (caller can either rely on the
        hash-change passive invalidation OR call this for explicit
        eviction; both are safe — hash-change is sufficient).
      • Admin triggers a forced re-composition.
      • Test isolation between cases.

    Returns the number of keys evicted (best-effort count).
    """
    prefix = f"pulse:{user_id}:"
    evicted = 0
    r = _redis_or_none()
    if r is not None:
        try:
            # SCAN over the prefix; DEL the matches. Avoids blocking
            # if many keys exist for the user.
            for k in r.scan_iter(match=f"{prefix}*"):
                r.delete(k)
                evicted += 1
        except Exception as exc:
            logger.warning(
                "pulse cache redis-invalidate failed: %s", exc
            )

    # Also evict from in-memory (defense-in-depth — when Redis is
    # primary in prod, in-memory is empty; in dev/test, Redis is
    # absent and in-memory carries the state).
    for key in list(_MEMORY_STORE.keys()):
        if key.startswith(prefix):
            _MEMORY_STORE.pop(key, None)
            evicted += 1
    return evicted
