"""HTTP routes: validate → call engine → serialise."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, HTTPException

import engine
from api import __version__
from api.mapping import (
    desk_list,
    desk_values,
    to_instrument,
    to_market,
    to_model,
    to_price_response,
    to_settings,
)
from api.schemas import (
    CompareRequest,
    CompareResponse,
    ConvergencePointOut,
    ErrorResponse,
    ExerciseBoundary,
    HealthResponse,
    HeatmapRequest,
    HeatmapResponse,
    ImpliedVolRequest,
    ImpliedVolResponse,
    MetaResponse,
    MethodComparison,
    MethodOut,
    PriceRequest,
    PriceResponse,
    ProfileRequest,
    ProfileResponse,
    ProfileSeries,
)
from engine.calibration.implied_vol import option_implied_vol
from engine.dates import DAYS_PER_YEAR_ACT365F
from engine.errors import PricingError
from engine.instruments.base import Instrument
from engine.instruments.vanilla import (
    AmericanOption,
    DigitalOption,
    EuropeanOption,
    OptionType,
    VanillaOption,
)
from engine.market.market_data import MarketData
from engine.methods.analytic import AnalyticBlack
from engine.methods.base import PricingMethod
from engine.methods.pde import CrankNicolsonPde, solve
from engine.methods.registry import METHODS, get_method
from engine.models.base import Model
from engine.models.black_scholes import BlackScholesMerton
from engine.results import Greek
from engine.risk.comparison import convergence, resolution_of
from engine.risk.scenarios import ProfilePoint, spot_profile, spot_value_grid, time_profile
from engine.risk.units import GreekMode, greek_unit
from engine.settings import PricingSettings

router = APIRouter(prefix="/api")
ERRORS: dict[int | str, dict[str, Any]] = {422: {"model": ErrorResponse}}


@dataclass(frozen=True, slots=True)
class _Context:
    instrument: Instrument
    market: MarketData
    model: Model
    method: PricingMethod
    settings: PricingSettings

    @property
    def days_to_expiry(self) -> int:
        return (self.instrument.maturity - self.market.valuation_date).days


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


def _strike(inst: Instrument) -> float:
    assert isinstance(inst, VanillaOption | DigitalOption)
    return inst.strike


@router.get("/health")
def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok", version=__version__)


_SAMPLES: dict[Literal["european", "american", "digital"], Instrument] = {
    "european": EuropeanOption(option_type=OptionType.CALL, strike=1.0, expiry=dt.date.max),
    "american": AmericanOption(option_type=OptionType.CALL, strike=1.0, expiry=dt.date.max),
    "digital": DigitalOption(option_type=OptionType.CALL, strike=1.0, expiry=dt.date.max),
}


@router.get("/meta")
def meta() -> MetaResponse:
    """Registered pricing methods, the products each supports, and version."""
    bsm = BlackScholesMerton()
    return MetaResponse(
        version=__version__,
        methods=[
            MethodOut(
                name=m.name,
                label=m.label,
                instruments=[k for k, inst in _SAMPLES.items() if m.supports(inst, bsm)],
            )
            for m in METHODS.values()
        ],
    )


@router.post("/price", responses=ERRORS)
def price(req: PriceRequest) -> PriceResponse:
    """Price one instrument with greeks in desk units."""
    c = _context(req)
    result = engine.price(c.instrument, c.market, c.model, c.method, c.settings)
    return to_price_response(result, c.instrument, c.market, c.model, c.method)


@router.post("/profile", responses=ERRORS)
def profile(req: ProfileRequest) -> ProfileResponse:
    """Position value and desk greeks along spot or time (full revaluation at each point).

    Numerical methods run at the scenario resolution (``settings.scenario``).
    """
    c = _context(req.pricing)
    settings = c.settings.for_scenarios()
    inst, qty, ccy = c.instrument, c.instrument.quantity, c.instrument.currency
    greeks = list(Greek) if req.greeks is None else req.greeks
    d_max = c.days_to_expiry
    series: list[ProfileSeries] = []
    payoff: list[float] | None = None

    if req.axis == "spot":
        shifts = [x / 100.0 for x in _linspace(-req.spot_range_pct, req.spot_range_pct, req.points)]
        x = [c.market.spot * (1.0 + s) for s in shifts]
        payoff = [qty * _payoff(inst, s) for s in x]
        horizons = sorted({min(max(h, 0), d_max) for h in req.horizons_days})
        for h in horizons:
            points = spot_profile(inst, c.market, c.model, c.method, settings, shifts, h, greeks)
            label = "Today" if h == 0 else ("Expiry" if h == d_max else f"+{h}d")
            series.append(_series(points, inst, label, h, 0.0, greeks))
    else:
        if d_max <= 0:
            raise HTTPException(422, "time profile needs an option that has not expired")
        rolls = sorted({round(v) for v in _linspace(0, d_max, min(req.points, d_max + 1))})
        x = [float(d_max - r) for r in rolls]
        for pct in req.spot_shifts_pct:
            points = time_profile(
                inst, c.market, c.model, c.method, settings, rolls, pct / 100, greeks
            )
            label = "Spot" if pct == 0 else f"Spot {pct:+g}%"
            series.append(_series(points, inst, label, 0, pct, greeks))

    return ProfileResponse(
        axis=req.axis,
        x=x,
        currency=ccy,
        notional=qty * c.market.spot,
        strike=_strike(inst),
        spot=c.market.spot,
        payoff=payoff,
        units={m.value: {g: greek_unit(g, m, ccy) for g in Greek} for m in GreekMode},
        series=series,
    )


def _payoff(inst: Instrument, s: float) -> float:
    if isinstance(inst, DigitalOption):
        return inst.payout * float(inst.option_type.omega * (s - inst.strike) > 0.0)
    assert isinstance(inst, VanillaOption)
    return max(inst.option_type.omega * (s - inst.strike), 0.0)


def _series(
    points: list[ProfilePoint],
    inst: Instrument,
    label: str,
    horizon: int,
    spot_shift_pct: float,
    greeks: list[Greek],
) -> ProfileSeries:
    by_mode: dict[GreekMode, dict[Greek, list[float]]] = {
        m: {g: [] for g in greeks} for m in GreekMode
    }
    for p in points:
        for m in GreekMode:
            values = desk_values(p.greeks, p.spot, inst, m)
            for g in greeks:
                by_mode[m][g].append(values.get(g, math.nan))
    return ProfileSeries(
        label=label,
        horizon_days=horizon,
        spot_shift_pct=spot_shift_pct,
        position_value=[p.value * inst.quantity for p in points],
        greeks={m.value: v for m, v in by_mode.items()},
    )


@router.post("/heatmap", responses=ERRORS)
def heatmap(req: HeatmapRequest) -> HeatmapResponse:
    """Full-revaluation position values over spot × vol shocks, optionally after a time roll."""
    c = _context(req.pricing)
    if req.horizon_days > c.days_to_expiry:
        raise HTTPException(422, f"horizon beyond expiry ({c.days_to_expiry} days)")
    settings = c.settings.for_scenarios()
    spot_pct = _linspace(-req.spot_range_pct, req.spot_range_pct, req.spot_steps)
    vol_pts = _linspace(-req.vol_range_pts, req.vol_range_pts, req.vol_steps)
    grid = spot_value_grid(
        c.instrument,
        c.market,
        c.model,
        c.method,
        settings,
        [s / 100 for s in spot_pct],
        [v / 100 for v in vol_pts],
        req.horizon_days,
    )
    qty = c.instrument.quantity
    base = engine.price(c.instrument, c.market, c.model, c.method, settings, greeks=()).price
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
    """Flat implied volatility reproducing a unit price (Let's Be Rational), European only."""
    inst, market, model = to_instrument(req.instrument), to_market(req.market), to_model(req.model)
    if not isinstance(inst, EuropeanOption):
        raise HTTPException(422, "implied vol from price is available for European vanillas")
    settings = to_settings(req.settings)
    sigma = option_implied_vol(inst, market, model, req.target_price, settings.implied_vol)
    t = market.time_to(inst.expiry)
    return ImpliedVolResponse(
        implied_vol=sigma,
        forward=model.forward(market, t),
        discount_factor=market.df(t),
        time_to_expiry=t,
    )


@router.post("/compare", responses=ERRORS)
def compare(req: CompareRequest) -> CompareResponse:
    """The product under every registered method, with convergence and exercise boundary."""
    c = _context(req.pricing)
    inst, market, model = c.instrument, c.market, c.model
    rows: list[MethodComparison] = []
    for m in METHODS.values():
        if not m.supports(inst, model):
            rows.append(
                MethodComparison(
                    method=m.name,
                    label=m.label,
                    supported=False,
                    error=f"does not price {type(inst).__name__} under {model.name}",
                )
            )
            continue
        try:
            res = engine.price(inst, market, model, m, c.settings)
            conv = convergence(inst, market, model, m, c.settings) if req.convergence else []
        except PricingError as e:
            rows.append(
                MethodComparison(method=m.name, label=m.label, supported=False, error=str(e))
            )
            continue
        rows.append(
            MethodComparison(
                method=m.name,
                label=m.label,
                supported=True,
                price=res.price,
                runtime_ms=res.diagnostics.runtime_ms,
                greeks=desk_list(res.greeks, market.spot, inst, GreekMode.CASH),
                resolution=resolution_of(m, c.settings),
                convergence=[
                    ConvergencePointOut(
                        resolution=p.resolution, price=p.value, runtime_ms=p.runtime_ms
                    )
                    for p in conv
                ],
            )
        )

    european: float | None = None
    boundary: ExerciseBoundary | None = None
    if isinstance(inst, AmericanOption):
        euro = EuropeanOption(
            option_type=inst.option_type,
            strike=inst.strike,
            expiry=inst.expiry,
            quantity=inst.quantity,
            currency=inst.currency,
        )
        for m in (AnalyticBlack(), CrankNicolsonPde()):
            try:
                european = engine.price(euro, market, model, m, c.settings, greeks=()).price
                break
            except PricingError:
                continue
        if market.time_to(inst.expiry) > 0.0:
            sol = solve(inst, market, model, c.settings.pde, [market.spot])
            boundary = ExerciseBoundary(
                days=[t * DAYS_PER_YEAR_ACT365F for t in sol.boundary_t], spot=sol.boundary_s
            )
    return CompareResponse(
        currency=inst.currency, methods=rows, european_price=european, boundary=boundary
    )
