"""Per-call cost computation using intelligence_model_routes pricing."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.intelligence import IntelligenceModelRoute


ZERO = Decimal("0")


def compute_cost(
    db: Session,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> Decimal:
    """Compute USD cost for a single Anthropic call.

    Looks up the route whose primary_model or fallback_model matches `model`.
    Returns Decimal(0) if the model isn't priced in the routes table yet — the
    caller gets zero rather than a crash, so observability never blocks execution.
    """
    if not input_tokens and not output_tokens:
        return ZERO

    route = (
        db.query(IntelligenceModelRoute)
        .filter(
            (IntelligenceModelRoute.primary_model == model)
            | (IntelligenceModelRoute.fallback_model == model)
        )
        .first()
    )
    if route is None:
        return ZERO

    million = Decimal("1000000")
    input_cost = (Decimal(input_tokens or 0) / million) * route.input_cost_per_million
    output_cost = (Decimal(output_tokens or 0) / million) * route.output_cost_per_million
    return (input_cost + output_cost).quantize(Decimal("0.000001"))
