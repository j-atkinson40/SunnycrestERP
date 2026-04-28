"""Phase W-4a Pulse shared types.

Each layer service returns a `LayerContent` containing one or more
`LayerItem`s. The composition engine (Commit 3) collects these from
all four layers, applies intelligent ordering / sizing, and returns a
unified Pulse response to the frontend.

**LayerItem shape rationale:**

The frontend renders a heterogeneous mix of pinable widgets (with
`widget_id` + variant + size) and intelligence streams (with their
own keys + content shape). Both render through the same tetris layout
engine, so they share a single contract:
  • `kind` — discriminator: "widget" (pinable widget) | "stream"
            (Pulse-specific intelligence stream)
  • `component_key` — the renderer key. For widgets, the canonical
                      widget_id (e.g., "vault_schedule"). For streams,
                      a stable stream key (e.g.,
                      "anomaly_intelligence_stream", "tasks_assigned").
  • `variant_id` — for widgets: "glance" | "brief" | "detail" | "deep".
                    For streams: usually "brief"; renderer can
                    interpret as needed.
  • `size` — sizing hint as `{cols, rows}` (1×1, 2×1, 2×2 etc.) per
            the WidgetGrid pattern reused by PulseSurface.
  • `priority` — relative weight within the layer for ordering. Higher
                priority surfaces first / larger.
  • `payload` — pre-computed content for the renderer. For widgets,
                often empty (widget self-fetches via useWidgetData).
                For streams, contains the synthesized content or
                aggregation. Backend orchestrator may inline some
                widget data later if useful, but the contract is
                permissive.
  • `dismissed` — Phase W-4a Commit 4 will read pulse_signals to mark
                  recently-dismissed items; included on the contract
                  now so frontend doesn't change shape between commits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


LayerName = Literal["personal", "operational", "anomaly", "activity"]
ItemKind = Literal["widget", "stream"]
VariantId = Literal["glance", "brief", "detail", "deep"]


@dataclass(frozen=True)
class LayerItem:
    """A single piece of content rendered inside a Pulse layer.

    Frozen so layer services can build immutable content lists; the
    composition engine assembles them without mutation.
    """

    # Unique within a single composition response. Used by the
    # frontend to key components and by signal tracking to identify
    # which piece a dismiss/navigate event applies to. Stable per
    # render: derived from `kind:component_key` (+ optional
    # discriminator for multi-instance components like one-card-per-
    # task).
    item_id: str
    kind: ItemKind
    component_key: str
    variant_id: VariantId
    # Sizing hint (cols × rows) — mirrors WidgetGrid sizing model.
    cols: int
    rows: int
    # Relative priority within the layer. Higher = more prominent.
    # Composition engine (Commit 3) may use this to drive sizing
    # adjustments + ordering within a layer.
    priority: int
    # Renderer payload — content for streams, optional pre-fetched
    # data for widgets. Use simple JSON-serializable dicts.
    payload: dict[str, Any] = field(default_factory=dict)
    # Phase W-4a Commit 4 — surface dismiss state from pulse_signals
    # so frontend can suppress recently-dismissed items. Default False
    # in Commit 2 (signal tracking lands in Commit 4).
    dismissed: bool = False


@dataclass(frozen=True)
class LayerContent:
    """Composed content for a single layer.

    Each layer service returns one `LayerContent` per
    `compose_for_user` call. The list of items is layer-internal
    ordering; the composition engine may further reorder by priority
    across layers if needed.
    """

    layer: LayerName
    items: list[LayerItem]
    # Optional layer-level metadata — e.g., "no work areas selected"
    # advisory for the operational layer, or "no anomalies" empty-
    # state hint for the anomaly layer. Frontend can render this
    # above the layer content.
    advisory: str | None = None


# ── Phase W-4a Commit 3 — top-level composition types ──────────────


TimeOfDaySignal = Literal["morning", "midday", "end_of_day", "off_hours"]


@dataclass(frozen=True)
class ReferencedItem:
    """An entity mentioned by an intelligence stream's synthesized
    text. Frontend can render these as click-through chips beneath
    the synthesis copy.
    """

    # Kind of referenced item — e.g. "anomaly", "delivery", "task".
    # Frontend renders an entity-appropriate chip + navigation.
    kind: str
    # Stable identifier (often UUID); referenced via the appropriate
    # backend route per kind.
    entity_id: str
    # Display label for the chip.
    label: str
    # Optional click-through route. None means render as static chip.
    href: str | None = None


@dataclass(frozen=True)
class IntelligenceStream:
    """A synthesized intelligence stream piece on Pulse.

    Distinct from `LayerItem(kind="stream")` — that's a structural
    pulse-piece (the renderable block); this is the *content* of an
    intelligence-synthesized piece. The composition engine emits
    both: a LayerItem with `component_key` matching the stream's
    `stream_id` (so the frontend renderer registry can dispatch),
    plus the `IntelligenceStream` content under
    `PulseComposition.intelligence_streams` so the frontend has the
    synthesized text without an extra round trip.

    For Phase W-4a Commit 3 only the V1 anomaly intelligence stream
    ships. V2 (Haiku-cached) deferred per D6. Phase W-4b adds smart
    email surfacing, daily briefing, cross-tenant coordination,
    conflict detection.
    """

    stream_id: str
    layer: LayerName
    title: str
    synthesized_text: str
    referenced_items: list[ReferencedItem]
    priority: int


@dataclass(frozen=True)
class PulseCompositionMetadata:
    """Metadata accompanying every Pulse composition response.

    Surfaces the composition's provenance to the frontend (which
    work areas drove composition; whether the vertical default
    fallback applied; what time-of-day signal was active). The
    frontend uses this for the first-login banner trigger
    (`vertical_default_applied=True` ⇒ surface a "personalize" CTA)
    and for subtle UX cues per time of day.
    """

    work_areas_used: list[str]
    vertical_default_applied: bool
    time_of_day_signal: TimeOfDaySignal


@dataclass(frozen=True)
class PulseComposition:
    """Top-level Pulse composition response shape.

    Returned from `composition_engine.compose_for_user` and serialized
    by the `GET /api/v1/pulse/composition` endpoint. Frontend
    PulseSurface (Commit 5) consumes this shape directly.

    `layers` is ordered: Personal → Operational → Anomaly → Activity
    per §3.26.2.4. The frontend tetris layout engine respects layer
    ordering as the structural top-down sequence; within each layer
    the items are already priority-sorted by the layer service.

    `intelligence_streams` is a parallel list of synthesized stream
    content (not LayerItems). For Phase W-4a Commit 3 this contains
    the V1 anomaly intelligence stream when anomalies exist; empty
    list otherwise. Phase W-4b extends with email/briefing/etc.
    """

    user_id: str
    composed_at: datetime
    layers: list[LayerContent]
    intelligence_streams: list[IntelligenceStream]
    metadata: PulseCompositionMetadata
