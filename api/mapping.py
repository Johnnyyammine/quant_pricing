"""Mapping between API schemas and engine types. The only place the two meet."""

from __future__ import annotations

import datetime as dt
import math

from api.schemas import (
    AmericanOptionIn,
    BumpSettingsIn,
    CurveIn,
    DiagnosticsOut,
    DigitalOptionIn,
    DigitalSettingsIn,
    EuropeanOptionIn,
    GreekOut,
    GreeksOut,
    ImpliedVolSettingsIn,
    MarketIn,
    ModelIn,
    PdeSettingsIn,
    PriceResponse,
    RateIn,
    ScenarioSettingsIn,
    SettingsIn,
    TreeSettingsIn,
)
from engine.dates import year_fraction
from engine.errors import MarketDataError
from engine.instruments.base import Instrument
from engine.instruments.vanilla import AmericanOption, DigitalOption, EuropeanOption
from engine.market.curves import FlatRateCurve, RateCurve, ZeroCurve
from engine.market.dividends import Dividend
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.methods.base import PricingMethod
from engine.models.base import Model
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton
from engine.results import Greek, Greeks, PricingResult
from engine.risk.units import GreekMode, desk_greeks
from engine.settings import (
    BumpSettings,
    DigitalSettings,
    ImpliedVolSettings,
    PdeSettings,
    PricingSettings,
    ScenarioSettings,
    TreeSettings,
)


def to_instrument(x: EuropeanOptionIn | AmericanOptionIn | DigitalOptionIn) -> Instrument:
    """Engine instrument from its schema."""
    match x:
        case DigitalOptionIn():
            return DigitalOption(
                option_type=x.option_type,
                strike=x.strike,
                expiry=x.expiry,
                payout=x.payout,
                quantity=x.quantity,
                currency=x.currency,
            )
        case AmericanOptionIn():
            return AmericanOption(
                option_type=x.option_type,
                strike=x.strike,
                expiry=x.expiry,
                quantity=x.quantity,
                currency=x.currency,
            )
        case EuropeanOptionIn():
            return EuropeanOption(
                option_type=x.option_type,
                strike=x.strike,
                expiry=x.expiry,
                quantity=x.quantity,
                currency=x.currency,
            )


def to_curve(x: RateIn, valuation_date: dt.date) -> RateCurve:
    """Flat curve from a number; log-linear zero curve from pillars (dates → ACT/365F)."""
    if not isinstance(x, CurveIn):
        return FlatRateCurve(x)
    pillars = sorted(x.pillars, key=lambda p: p.date)
    if pillars[0].date <= valuation_date:
        raise MarketDataError("curve pillars must be after the valuation date")
    if len({p.date for p in pillars}) != len(pillars):
        raise MarketDataError("curve pillar dates must be distinct")
    return ZeroCurve(
        times=tuple(year_fraction(valuation_date, p.date) for p in pillars),
        zero_rates=tuple(p.rate for p in pillars),
    )


def to_market(x: MarketIn) -> MarketData:
    """Engine market snapshot."""
    return MarketData(
        valuation_date=x.valuation_date,
        spot=x.spot,
        discount=to_curve(x.rate, x.valuation_date),
        vol=FlatVolSurface(x.vol),
        dividend_yield=to_curve(x.dividend_yield, x.valuation_date),
        borrow=to_curve(x.borrow, x.valuation_date),
        dividends=tuple(Dividend(d.ex_date, d.cash, d.proportional) for d in x.dividends),
    )


def to_model(x: ModelIn) -> Model:
    """Engine model from its schema."""
    match x.type:
        case "bsm":
            return BlackScholesMerton(dividend_treatment=x.dividend_treatment)
        case "black76":
            return Black76()


def to_settings(x: SettingsIn) -> PricingSettings:
    """Engine settings from their schema."""
    return PricingSettings(
        bumps=BumpSettings(**x.bumps.model_dump()),
        implied_vol=ImpliedVolSettings(**x.implied_vol.model_dump()),
        force_bump_greeks=x.force_bump_greeks,
        tree=TreeSettings(**x.tree.model_dump()),
        pde=PdeSettings(**x.pde.model_dump()),
        digital=DigitalSettings(**x.digital.model_dump()),
        scenario=ScenarioSettings(**x.scenario.model_dump()),
    )


def from_settings(s: PricingSettings) -> SettingsIn:
    """Settings schema from engine settings."""
    b, t, p, sc = s.bumps, s.tree, s.pde, s.scenario
    return SettingsIn(
        bumps=BumpSettingsIn(
            spot_rel=b.spot_rel, vol_abs=b.vol_abs, rate_abs=b.rate_abs, time_days=b.time_days
        ),
        implied_vol=ImpliedVolSettingsIn(max_iterations=s.implied_vol.max_iterations),
        force_bump_greeks=s.force_bump_greeks,
        tree=TreeSettingsIn(steps=t.steps),
        pde=PdeSettingsIn(
            space_nodes=p.space_nodes,
            time_steps=p.time_steps,
            n_std=p.n_std,
            rannacher_steps=p.rannacher_steps,
            penalty=p.penalty,
            penalty_tol=p.penalty_tol,
            penalty_max_iter=p.penalty_max_iter,
        ),
        digital=DigitalSettingsIn(spread_width_rel=s.digital.spread_width_rel),
        scenario=ScenarioSettingsIn(
            tree_steps=sc.tree_steps,
            pde_space_nodes=sc.pde_space_nodes,
            pde_time_steps=sc.pde_time_steps,
        ),
    )


def desk_list(
    greeks: Greeks | None, spot: float, inst: Instrument, mode: GreekMode
) -> list[GreekOut]:
    """Greeks in desk units for one mode."""
    if greeks is None:
        return []
    return [
        GreekOut(key=g.greek, value=g.value, unit=g.unit, source=g.source)
        for g in desk_greeks(greeks, spot, inst.quantity, inst.currency, mode)
    ]


def greeks_out(greeks: Greeks | None, spot: float, instrument: Instrument) -> GreeksOut:
    """Greeks in desk units, both modes."""
    return GreeksOut(
        pure=desk_list(greeks, spot, instrument, GreekMode.PURE),
        cash=desk_list(greeks, spot, instrument, GreekMode.CASH),
    )


def desk_values(
    greeks: Greeks | None, spot: float, instrument: Instrument, mode: GreekMode
) -> dict[Greek, float]:
    """Desk-unit greek values keyed by greek (``nan`` if absent)."""
    if greeks is None:
        return dict.fromkeys(Greek, math.nan)
    return {g.key: g.value for g in desk_list(greeks, spot, instrument, mode)}


def to_price_response(
    result: PricingResult,
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
) -> PriceResponse:
    """Serialise a pricing result with desk-unit greeks in both modes."""
    t = max(market.time_to(instrument.maturity), 0.0)
    d = result.diagnostics
    return PriceResponse(
        currency=instrument.currency,
        price=result.price,
        position_value=result.price * instrument.quantity,
        pct_notional=100.0 * result.price / market.spot,
        notional=instrument.quantity * market.spot,
        forward=model.forward(market, t),
        discount_factor=market.df(t),
        time_to_expiry=t,
        greeks=greeks_out(result.greeks, market.spot, instrument),
        diagnostics=DiagnosticsOut(
            method=d.method,
            method_label=method.label,
            model=d.model,
            runtime_ms=d.runtime_ms,
            revaluations=d.revaluations,
            settings=from_settings(d.settings),
            details=dict(d.details),
            warnings=list(d.warnings),
        ),
    )
