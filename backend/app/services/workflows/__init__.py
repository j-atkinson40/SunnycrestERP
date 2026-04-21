"""Workflow service adapters.

Thin adapter modules that bridge `workflow_engine` step execution to
existing backend services. Adapters preserve side effects verbatim
via service reuse — no logic duplication.

Added in Workflow Arc Phase 8b as the first migration of an
accounting agent into a real workflow definition (cash receipts).
Phase 8c–8f mirror this pattern for the remaining agent-backed
workflows.
"""
