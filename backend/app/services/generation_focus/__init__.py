"""Generation Focus headless dispatch substrate (Phase R-6.0a).

Generation Focuses ship in two canonical operational modes per
canon §3.26.11.12.21:

  - Interactive: operator authors via canvas + commits via UI
    (existing surfaces — Personalization Studio, future Wall Designer
    + Drawing Takeoff + ...).

  - Headless: workflow step ``invoke_generation_focus`` invokes the
    canonical extraction logic via service-layer dispatch + stores
    the canonical line-item output in ``run_step.output_data`` for
    downstream chaining (typically an ``invoke_review_focus`` step).

This package is the canonical extension point for headless dispatch.
Each Generation Focus declares its dispatch entries here alongside
its interactive UI implementation. New Generation Focuses register
on package load via side-effect imports below.

Adding a new Generation Focus headless target:
  1. Author the extraction-as-pure-function in the focus's
     own service module (not here).
  2. Add an entry to ``HEADLESS_DISPATCH`` in ``headless_dispatch.py``
     pointing the (focus_id, op_id) tuple at the function.
  3. Future Generation Focuses inherit this pattern verbatim.
"""

from __future__ import annotations

from app.services.generation_focus.headless_dispatch import (
    HEADLESS_DISPATCH,
    HeadlessDispatchError,
    UnknownGenerationFocus,
    UnknownGenerationFocusOp,
    dispatch,
    list_dispatch_keys,
)

__all__ = [
    "HEADLESS_DISPATCH",
    "HeadlessDispatchError",
    "UnknownGenerationFocus",
    "UnknownGenerationFocusOp",
    "dispatch",
    "list_dispatch_keys",
]
