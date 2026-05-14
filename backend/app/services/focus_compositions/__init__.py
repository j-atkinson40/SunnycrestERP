"""Focus compositions package — Tier 3 ORM exports only (B-2).

Sub-arc B-2 deleted the legacy R-5.0 `composition_service` module: its
service surface was structurally incompatible with the new three-tier
inheritance chain (focus_cores → focus_templates → focus_compositions).
Consumers were migrated to the canonical substrates:

  - Focus consumers       → `app.services.focus_template_inheritance`
  - Edge-panel consumers  → `app.services.edge_panel_inheritance`

This package retains its name only because the `focus_compositions`
ORM model still lives in `app.models.focus_composition` (Tier 3 of
the Focus inheritance chain). No service-layer surface remains here.
"""
