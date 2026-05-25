"""Task substrate v1 — plugin contracts package.

Three plugin categories per state doc §5.4 + build prompt §5.4:

- creators: TaskCreator Protocol — per-provenance_kind task creation logic.
- surfaces: TaskSurface Protocol — visual editor surface registrations.
- type_behaviors: TaskTypeBehavior Protocol — per-task-type lifecycle
  + routing + surface defaults.

Each contract module exports its Protocol + registry helpers. Five
v1 task type behavior plugins live in `types/` package; they
auto-register at import time.
"""
