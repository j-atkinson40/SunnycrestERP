"""Widget framework API — layout CRUD and available widgets."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.widgets import widget_service

router = APIRouter()


@router.get("/available")
def get_available_widgets(
    page_context: str = Query(..., description="Page context slug, e.g. 'ops_board'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all widgets available to the current user for a page context."""
    return widget_service.get_available_widgets(
        db, current_user.company_id, current_user, page_context
    )


@router.get("/available-for-surface")
def get_widgets_for_surface(
    surface: str = Query(
        ...,
        description=(
            "Surface slug from the 7-surface enum: pulse_grid / "
            "focus_canvas / focus_stack / spaces_pin / floating_tablet / "
            "dashboard_grid / peek_inline. See DESIGN_LANGUAGE.md §12.5."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Widget Library Phase W-2 — surface-scoped widget catalog.

    Returns widgets that declare ``surface`` in their supported_surfaces,
    filtered by the 4-axis filter against the union of their declared
    page_contexts. Used by the WidgetPicker (`destination="sidebar"`)
    to populate the list of pinnable widgets without coupling to a
    specific page_context (sidebar pinning is page-context-independent).

    Same response shape as ``/widgets/available``.
    """
    return widget_service.get_widgets_for_surface(
        db, current_user.company_id, current_user, surface
    )


@router.get("/layout")
def get_layout(
    page_context: str = Query(..., description="Page context slug"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return user's widget layout for a page. Creates default if none exists."""
    return widget_service.get_user_layout(
        db, current_user.company_id, current_user, page_context
    )


@router.patch("/layout")
def save_layout(
    body: dict,
    page_context: str = Query(..., description="Page context slug"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save user's widget layout configuration."""
    widgets = body.get("widgets", [])
    return widget_service.save_user_layout(
        db, current_user.company_id, current_user, page_context, widgets
    )


@router.post("/layout/reset")
def reset_layout(
    page_context: str = Query(..., description="Page context slug"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user's saved layout. Next GET regenerates default."""
    deleted = widget_service.reset_user_layout(
        db, current_user.company_id, current_user.id, page_context
    )
    return {"reset": deleted}
