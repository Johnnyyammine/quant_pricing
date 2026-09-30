"""HTTP routes: validate → call engine → serialise."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException

import engine
from api import __version__
from api.mapping import (
    desk_values,
    to_instrument,
    to_market,
    to_model,
    to_price_response,
    to_settings,
)
from api.schemas import (
    ErrorResponse,
    HealthResponse,
    HeatmapRequest,
    HeatmapResponse,
    ImpliedVolRequest,
    ImpliedVolResponse,
    MetaResponse,
    MethodOut,
    PriceRequest,
    PriceResponse,
    ProfileRequest,
    ProfileResponse,
    ProfileSeries,
)
from engine.calibration.implied_vol import option_implied_vol
from engine.instruments.vanilla import EuropeanOption
from engine.market.market_data import MarketData
from engine.methods.base import PricingMethod
from engine.methods.registry import METHODS, get_method
from engine.models.base import Model
from engine.results import Greek
from engine.risk.scenarios import spot_profile, spot_value_grid, time_profile
from engine.risk.units import GreekMode, greek_unit
from engine.settings import PricingSettings

router = APIRouter(prefix="/api")
ERRORS: dict[int | str, dict[str, Any]] = {422: {"model": ErrorResponse}}


@dataclass(frozen=True, slots=True)
class _Context:
    instrument: EuropeanOption
    market: MarketData
    model: Model
    method: PricingMethod
    settings: PricingSettings

    @property
    def days_to_expiry(self) -> int:
        return (self.instrument.expiry - self.market.valuation_date).days


def _context(req: PriceRequest) -> _Context:
    try:
        method = get_method(req.method)
    except KeyError as e:
        raise HTTPException(status_code=422, detail=str(e.args[0])) from None
    return _Context(
        instrument=to_instrument(req.instrument),
        market=to_market(req.market),
        model=to_model(req.model),
        method=method,
        settings=to_settings(req.settings),
    )


def _linspace(lo: float, hi: float, n: int) -> list[float]:
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


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


@router.post("/price", responses=ERRORS)
def price(req: PriceRequest) -> PriceResponse:
    """Price one instrument with greeks in desk units."""
    c = _context(req)
    result = engine.price(c.instrument, c.market, c.model, c.method, c.settings)
    return to_price_response(result, c.instrument, c.market, c.model, c.method)


@router.post("/profile", responses=ERRORS)
def profile(req: ProfileRequest) -> ProfileResponse:
    """Position value and desk greeks along spot or time (full revaluation at each point)."""
    c = _context(req.pricing)
    inst, qty, ccy = c.instrument, c.instrument.quantity, c.instrument.currency
    d_max = c.days_to_expiry
    series: list[ProfileSeries] = []
    payoff: list[float] | None = None

    if req.axis == "spot":
        shifts = [x / 100.0 for x in _linspace(-req.spot_range_pct, req.spot_range_pct, req.points)]
        x = [c.market.spot * (1.0 + s) for s in shifts]
        omega = inst.option_type.omega
        payoff = [qty * max(omega * (s - inst.strike), 0.0) for s in x]
        horizons = sorted({min(max(h, 0), d_max) for h in req.horizons_days})
        for h in horizons:
            points = spot_profile(inst, c.market, c.model, c.method, c.settings, shifts, h)
            label = "Today" if h == 0 else ("Expiry" if h == d_max else f"+{h}d")
            series.append(_series(points, inst, label, h, 0.0))
    else:
        if d_max <= 0:
            raise HTTPException(422, "time profile needs an option that has not expired")
        rolls = sorted({round(v) for v in _linspace(0, d_max, min(req.points, d_max + 1))})
        x = [float(d_max - r) for r in rolls]
        for pct in req.spot_shifts_pct:
            points = time_profile(inst, c.market, c.model, c.method, c.settings, rolls, pct / 100)
            label = "Spot" if pct == 0 else f"Spot {pct:+g}%"
            series.append(_series(points, inst, label, 0, pct))

    return ProfileResponse(
        axis=req.axis,
        x=x,
        currency=ccy,
        notional=qty * c.market.spot,
        strike=inst.strike,
        spot=c.market.spot,
        payoff=payoff,
        units={m.value: {g: greek_unit(g, m, ccy) for g in Greek} for m in GreekMode},
        series=series,
    )


def _series(
    points: list[tuple[MarketData, engine.PricingResult]],
    inst: EuropeanOption,
    label: str,
    horizon: int,
    spot_shift_pct: float,
) -> ProfileSeries:
    greeks: dict[GreekMode, dict[Greek, list[float]]] = {
        m: {g: [] for g in Greek} for m in GreekMode
    }
    for mkt, res in points:
        for m in GreekMode:
            for g, v in desk_values(res.greeks, mkt.spot, inst, m).items():
                greeks[m][g].append(v)
    return ProfileSeries(
        label=label,
        horizon_days=horizon,
        spot_shift_pct=spot_shift_pct,
        position_value=[res.price * inst.quantity for _, res in points],
        greeks={m.value: v for m, v in greeks.items()},
    )


@router.post("/heatmap", responses=ERRORS)
def heatmap(req: HeatmapRequest) -> HeatmapResponse:
    """Full-revaluation position values over spot × vol shocks, optionally after a time roll."""
    c = _context(req.pricing)
    if req.horizon_days > c.days_to_expiry:
        raise HTTPException(422, f"horizon beyond expiry ({c.days_to_expiry} days)")
    spot_pct = _linspace(-req.spot_range_pct, req.spot_range_pct, req.spot_steps)
    vol_pts = _linspace(-req.vol_range_pts, req.vol_range_pts, req.vol_steps)
    grid = spot_value_grid(
        c.instrument,
        c.market,
        c.model,
        c.method,
        c.settings,
        [s / 100 for s in spot_pct],
        [v / 100 for v in vol_pts],
        req.horizon_days,
    )
    qty = c.instrument.quantity
    base = engine.price(c.instrument, c.market, c.model, c.method, c.settings, greeks=()).price
    return HeatmapResponse(
        currency=c.instrument.currency,
        spot_shifts_pct=spot_pct,
        vol_shifts_pts=vol_pts,
        horizon_days=req.horizon_days,
        base_value=base * qty,
        notional=qty * c.market.spot,
        values=[[None if math.isnan(v) else v * qty for v in row] for row in grid],
    )


@router.post("/implied-vol", responses=ERRORS)
def implied_vol(req: ImpliedVolRequest) -> ImpliedVolResponse:
    """Flat implied volatility reproducing a unit price (Let's Be Rational)."""
    inst, market, model = to_instrument(req.instrument), to_market(req.market), to_model(req.model)
    settings = to_settings(req.settings)
    sigma = option_implied_vol(inst, market, model, req.target_price, settings.implied_vol)
    t = market.time_to(inst.expiry)
    return ImpliedVolResponse(
        implied_vol=sigma,
        forward=model.forward(market, t),
        discount_factor=market.df(t),
        time_to_expiry=t,
    )
