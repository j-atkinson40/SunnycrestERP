"""Offered updates (Focus Variations V-2) — level-generic publish/offer/
accept/decline over versioned artifact lineages. See service.py."""

from app.services.artifact_updates.diff import derive_core_diff
from app.services.artifact_updates.service import (
    ARTIFACT_FOCUS_CORE,
    TARGET_FOCUS_TEMPLATE,
    ArtifactUpdateError,
    accept_offer,
    decline_offer,
    get_offer,
    get_publish_preview,
    offer_states_for_targets,
    publish_core_update,
)

__all__ = [
    "ARTIFACT_FOCUS_CORE",
    "TARGET_FOCUS_TEMPLATE",
    "ArtifactUpdateError",
    "accept_offer",
    "decline_offer",
    "derive_core_diff",
    "get_offer",
    "get_publish_preview",
    "offer_states_for_targets",
    "publish_core_update",
]
