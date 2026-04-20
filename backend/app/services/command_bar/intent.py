"""Command Bar intent classifier — Phase 1.

Rule-based only. No AI in Phase 1 — speed matters (p50 < 100ms
budget) and the rules cover the Phase 1 demand: navigate, search,
create, action.

Phase 4+ may layer an AI-based classifier for ambiguous queries
(e.g. "can we do a bronze vault by Friday"). That layer will call
`classify()` first; the AI-based path only kicks in when the rules
return SEARCH with no strong signal. Do NOT replace this module in
Phase 4 — extend it.

Input: free-text query string.
Output: one of the five `Intent` values below.

Design rules:

  - Fast. Measured in microseconds — zero DB, zero network, zero AI.
  - Deterministic. Same input → same output, always.
  - Conservative on CREATE + ACTION. We only classify CREATE when
    we see a create-verb prefix AND the rest of the query resolves
    to a known create entity via the registry. An ambiguous "new"
    falls through to SEARCH, which is harmless.
  - Generous on NAVIGATE. Exact alias / label match against the
    registry wins. Prefix match also qualifies.
  - Default is SEARCH. When in doubt, search.
"""

from __future__ import annotations

import re
from typing import Literal

from app.services.command_bar.registry import (
    ActionRegistryEntry,
    find_by_alias,
    list_actions,
    match_actions,
)


Intent = Literal[
    "navigate",   # query is a page / record name (or alias)
    "search",     # query is a search across vault entities
    "create",     # query starts with a create verb + entity type
    "action",     # query exactly matches a registered action alias
    "empty",      # query is empty / whitespace
]


# ── Verb vocabularies ────────────────────────────────────────────────
# Ordered by specificity: CREATE verbs come first because "new " is a
# strong signal. NAVIGATE verbs are secondary ("go to AR aging").
# Extracted from the legacy `command_bar_data_search.py` and tightened.

_CREATE_VERBS = {
    "new", "create", "add", "start", "draft",
    "compose",  # legacy verb retained for user muscle memory
}
_NAVIGATE_VERBS = ("go to ", "goto ", "open ", "navigate ", "navigate to ", "view ", "show ")


# Entity-shape detectors. These let us short-circuit to navigate-to-
# a-specific-record when the query matches a known entity number
# format. The resolver is still the authoritative source; intent
# classification is a hint.

# Sales order number: "SO-YYYY-NNNN" (any case, hyphen or space
# separator). Invoice: "INV-YYYY-NNNN". Quote: "Q-YYYY-NNNN".
# Case number: "CASE-YYYY-NNNN" or tenant-specific prefix.
_RECORD_NUMBER_RX = re.compile(
    r"^(SO|INV|Q|QT|PO|CASE|FH)[- ]?\d{2,4}[- ]?\d{3,5}$",
    re.IGNORECASE,
)


# ── Classification ───────────────────────────────────────────────────


def classify(query: str) -> Intent:
    """Return the intent for a query.

    Classification order:
      1. empty → empty
      2. record-number pattern → navigate (specific record)
      3. exact alias match on a registered action →
           action-type-specific (navigate | create)
      4. create verb + rest-of-query resolves to a create action →
           create
      5. navigate verb prefix → navigate
      6. prefix / alias match against any navigate action → navigate
      7. default → search

    Rule 3 catches "sales orders", "AR aging", "new sales order"
    when typed verbatim. Rule 4 catches "new" + fuzzy entity-type
    match. Rule 6 catches "AR" matching the navigate.ar_aging alias.
    """
    q = (query or "").strip()
    if not q:
        return "empty"

    # 2. Record-number pattern → navigate
    if _RECORD_NUMBER_RX.match(q):
        return "navigate"

    # 3. Exact label/alias match
    exact = find_by_alias(q)
    if exact is not None:
        return _intent_for_action(exact)

    # 4. Create-verb prefix + entity match
    lowered = q.lower()
    first_word, _, rest = lowered.partition(" ")
    if first_word in _CREATE_VERBS and rest.strip():
        # "new sales order", "create quote", "add contact"
        matches = match_actions(rest.strip(), max_results=3)
        for entry, score in matches:
            if entry.action_type == "create" and score >= 0.3:
                return "create"
        # fallthrough — "new foo bar" with no create match → search

    # 5. Navigate-verb prefix
    for verb in _NAVIGATE_VERBS:
        if lowered.startswith(verb):
            return "navigate"

    # 6. Prefix / fuzzy match against navigate actions
    nav_matches = match_actions(q, max_results=3)
    for entry, score in nav_matches:
        if entry.action_type == "navigate" and score >= 0.8:
            return "navigate"

    # 7. Default
    return "search"


def _intent_for_action(entry: ActionRegistryEntry) -> Intent:
    """Map an exact-matched action back to an Intent.

    Navigate actions → "navigate". Create actions → "create". Other
    action types are reserved for later phases; they'd land in
    "action" if we exposed that intent, but Phase 1 clients only
    distinguish navigate vs create vs search, so "action" would be
    a no-op. Mapping to "navigate" keeps the surface uniform.
    """
    if entry.action_type == "navigate":
        return "navigate"
    if entry.action_type == "create":
        return "create"
    # workflow / saved_view / search_only fall through to navigate
    # for now — they're all actions the client invokes from the
    # result tile, which is the same UX as navigate.
    return "navigate"


# ── Utility — used by intent tests and the retrieval orchestrator
#    to know whether we should query the entity resolver at all ───────


def should_search_entities(intent: Intent) -> bool:
    """The resolver is expensive (UNION ALL across 6 entity types
    with trigram similarity). Skip it for `create` and `empty`
    intents — those never want entity results. Also skip for
    `navigate` if the query matched a record-number pattern: the
    resolver will usually find the record, but the exact number
    match in the resolver is redundant with its existence.

    For Phase 1 simplicity we run the resolver on navigate + search
    + action. Future phases can tighten this."""
    return intent in ("navigate", "search", "action")


def is_create_entity_query(query: str) -> str | None:
    """If the query is 'new X' / 'create X' / 'add X', return the
    entity type for X (or None if no match). Used by the retrieval
    orchestrator to prioritize the create action in results."""
    q = (query or "").strip().lower()
    if not q:
        return None
    first_word, _, rest = q.partition(" ")
    if first_word not in _CREATE_VERBS or not rest.strip():
        return None
    matches = match_actions(rest.strip(), max_results=3)
    for entry, score in matches:
        if entry.action_type == "create" and score >= 0.3 and entry.entity_type:
            return entry.entity_type
    return None


# ── Phase 4 — CREATE_WITH_NL detection ───────────────────────────────
# Additive helper. Does NOT extend the Intent Literal (existing
# callers keep their Literal types valid). Callers that route NL
# creation first call `classify()` — if it returns `"create"` — then
# call `detect_create_with_nl()` to see whether there's NL content
# after the entity keyword. If so, route to the NL overlay flow; if
# None, fall through to empty invocation (navigate to the creation
# route).
#
# Rule for "CREATE_WITH_NL":
#   query starts with a create verb ("new", "create", "add", etc),
#   followed by a tokens that resolve to a known create action's
#   entity_type, followed by NON-EMPTY content. The content must
#   have at least 3 significant chars (so "new case " with trailing
#   space doesn't count as NL invocation).


_NL_CONTENT_MIN_CHARS: int = 3


def detect_create_with_nl(query: str) -> tuple[str, str] | None:
    """If the query is `<create_verb> <entity_type> <nl_content>` with
    non-empty NL content, return `(entity_type, nl_content)`. Else
    return None.

    `entity_type` is pulled from the matched create action's
    `entity_type` field in the registry (e.g. "case", "sales_order",
    "contact", "event"). `nl_content` is the text after the entity
    keyword, stripped but otherwise preserved as the user typed it.

    Two recognition modes:
      1. Exact match: the create action's label or aliases appear
         verbatim after the verb. "new case John Smith..." matches
         the "case" alias. The nl_content is everything after the
         matched alias (case-insensitive prefix match).
      2. Fuzzy match via registry: if no alias matches verbatim, use
         the create-action scorer (same path as `is_create_entity_query`)
         and treat the best-match's entity_type as the target. The
         content split is heuristic: take the first 1-2 words as the
         entity-type phrase, rest as NL.

    Performance: pure string ops + in-memory registry scan. <1ms.
    """
    raw = (query or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    first_word, _, rest = lowered.partition(" ")
    if first_word not in _CREATE_VERBS or not rest.strip():
        return None

    # Need the raw-case rest for NL content preservation.
    _verb_len = len(first_word) + 1
    rest_raw = raw[_verb_len:].strip()

    # Mode 1 — exact-alias prefix match. Aliases in the registry are
    # stored verb-inclusive ("new case") AND verb-less ("case",
    # "arrangement"). We check each alias candidate in two forms:
    # the alias as-written AND the alias with a leading create-verb
    # stripped (so "new case" also matches when `rest` is "case ...").
    # Prefer longest match to handle "sales order" vs "order".
    def _candidate_phrases(entry: ActionRegistryEntry) -> list[str]:
        phrases: list[str] = []
        for raw in list(entry.aliases) + [entry.label]:
            p = raw.lower().strip()
            if not p:
                continue
            phrases.append(p)
            # Strip leading create-verb ("new ", "create ", etc).
            head, _, tail = p.partition(" ")
            if head in _CREATE_VERBS and tail:
                phrases.append(tail)
        return phrases

    best_alias_match: tuple[int, str] | None = None  # (len, entity_type)
    for entry in list_actions(action_type="create"):
        if not entry.entity_type:
            continue
        for phrase_lc in _candidate_phrases(entry):
            # Match as a WORD-boundary prefix; require the next char
            # to be whitespace or end-of-string so "case" doesn't
            # partially match "casebook" etc.
            if rest.startswith(phrase_lc) and (
                len(rest) == len(phrase_lc)
                or rest[len(phrase_lc)] in (" ", "\t")
            ):
                if best_alias_match is None or len(phrase_lc) > best_alias_match[0]:
                    best_alias_match = (len(phrase_lc), entry.entity_type)

    if best_alias_match is not None:
        matched_len, entity_type = best_alias_match
        # Slice NL content from the raw string (preserving case +
        # any internal whitespace structure the user typed).
        nl_content = rest_raw[matched_len:].strip()
        if len(nl_content) >= _NL_CONTENT_MIN_CHARS:
            return (entity_type, nl_content)
        return None

    # Mode 2 — fuzzy fallback. Use the existing entity-type matcher;
    # if it picks an entity type, take the first token of rest as the
    # entity keyword and everything after as NL content. This is a
    # last-resort path for unusual vocabulary ("compose case xyz").
    entity_type = is_create_entity_query(raw)
    if entity_type is None:
        return None
    # Conservative heuristic: peel off the first 1-2 tokens and use
    # the rest as NL. Skip if the resulting content is too short.
    tokens = rest_raw.split()
    if len(tokens) < 2:
        return None
    # Try 1-token entity keyword first, then 2-token if the 1-token
    # leftover looks wrong.
    nl_content_1 = " ".join(tokens[1:]).strip()
    if len(nl_content_1) >= _NL_CONTENT_MIN_CHARS:
        return (entity_type, nl_content_1)
    return None
