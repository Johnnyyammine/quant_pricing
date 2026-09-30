"""HTTP routes: validate → call engine → serialise."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import engine
from api import __version__
from api.mapping import to_instrument, to_market, to_model, to_price_response, to_settings
from api.schemas import (
    ErrorResponse,
    HealthResponse,
    MetaResponse,
    MethodOut,
    PriceRequest,
    PriceResponse,
)
from engine.methods.registry import METHODS, get_method

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/meta")
def meta() -> MetaResponse:
    """Registered pricing methods and version."""
    return MetaResponse(
        version=__version__,
        methods=[MethodOut(name=m.name, label=m.label) for m in METHODS.values()],
    )


@router.post("/price", responses={422: {"model": ErrorResponse}})
def price(req: PriceRequest) -> PriceResponse:
    """Price one instrument with greeks in desk units."""
    try:
        method = get_method(req.method)
    except KeyError as e:
        raise HTTPException(status_code=422, detail=str(e.args[0])) from None
    instrument = to_instrument(req.instrument)
    market = to_market(req.market)
    model, settings = to_model(req.model), to_settings(req.settings)
    result = engine.price(instrument, market, model, method, settings)
    return to_price_response(result, instrument, market, method)
