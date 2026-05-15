"""Shared constants for the Focus Template Inheritance package.

Sub-arc C-2.1.2 lifts `EDIT_SESSION_WINDOW_SECONDS` here so cores
(Tier 1) + templates (Tier 2) reuse a single canonical value. Without
this module the constant would be duplicated in each service file,
inviting drift when one is tuned and the other isn't.

Edge-panel session-aware semantics (deferred) will consume the same
constant when that work lands.
"""

from __future__ import annotations


# Session-aware update window. Updates carrying an `edit_session_id`
# that matches the row's `last_edit_session_id` AND fall within this
# many seconds of `last_edit_session_at` mutate in place; outside the
# window OR with a different token version-bump per the B-1 behavior.
#
# Tuning notes: 300s is long enough to comfortably cover a single
# editor's scrub-and-tune cycle (slider drags, repeated keypresses)
# without straddling editor-leave / editor-return where a fresh
# version trail is desirable. Bumping is safe; lowering risks
# fragmenting in-session work into multiple versions.
EDIT_SESSION_WINDOW_SECONDS: int = 300
