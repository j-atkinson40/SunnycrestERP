"""Bridgeable Command Bar Platform Layer — Phase 1.

Package layout:

    registry.py   — ActionRegistryEntry type + singleton registry.
                    OWNS the action entry schema. Phase 2+ registers
                    saved views; Phase 5 registers workflows; Phase 6
                    registers briefings.
    intent.py     — Rule-based intent classifier (navigate / search /
                    create / action). Deliberately non-AI for Phase 1
                    to preserve the p50 < 100ms latency budget. AI
                    classification for ambiguous queries is a future
                    layer, not a replacement for the rules.
    resolver.py   — pg_trgm-backed fuzzy entity resolver with recency
                    weighting, tenant isolation, permission filtering.
                    Single UNION ALL SQL per query across 6 entity
                    types.
    retrieval.py  — Orchestrator. OWNS the public result-shape
                    contract returned by `/api/v1/command-bar/query`.
                    Phase 2+ extends this shape; callers (frontend
                    + any future SDK clients) depend on it.

The /api/v1/ai-command/* endpoints remain alive alongside this
package. See CLAUDE.md §4 "Command Bar Migration Tracking" for the
deprecation plan.
"""

from app.services.command_bar.registry import (
    ActionRegistryEntry,
    ActionType,
    find_by_alias,
    get_registry,
    list_actions,
    match_actions,
    register_action,
    reset_registry,
)
from app.services.command_bar.intent import (
    Intent,
    classify,
    is_create_entity_query,
    should_search_entities,
)
from app.services.command_bar.retrieval import (
    QueryContext,
    QueryResponse,
    ResultItem,
    ResultType,
    query,
)

__all__ = [
    # registry
    "ActionRegistryEntry",
    "ActionType",
    "find_by_alias",
    "get_registry",
    "list_actions",
    "match_actions",
    "register_action",
    "reset_registry",
    # intent
    "Intent",
    "classify",
    "is_create_entity_query",
    "should_search_entities",
    # retrieval
    "QueryContext",
    "QueryResponse",
    "ResultItem",
    "ResultType",
    "query",
]
