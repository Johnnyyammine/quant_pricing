"""Mapping between API schemas and engine types. The only place the two meet."""

from __future__ import annotations

from api.schemas import (
    BumpSettingsIn,
    DiagnosticsOut,
    EuropeanOptionIn,
    GreekOut,
    GreeksOut,
    MarketIn,
    ModelIn,
    PriceResponse,
    SettingsIn,
)
from engine.instruments.vanilla import EuropeanOption
from engine.market.curves import FlatRateCurve
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.methods.base import PricingMethod
from engine.models.base import Model
from engine.models.black_scholes import BlackScholesMerton
from engine.results import PricingResult
from engine.risk.units import GreekMode, desk_greeks
from engine.settings import BumpSettings, PricingSettings


def to_instrument(x: EuropeanOptionIn) -> EuropeanOption:
    """Engine instrument from its schema."""
    return EuropeanOption(
        option_type=x.option_type,
        strike=x.strike,
        expiry=x.expiry,
        quantity=x.quantity,
        currency=x.currency,
    )


def to_market(x: MarketIn) -> MarketData:
    """Engine market snapshot from a flat-market schema."""
    return MarketData(
        valuation_date=x.valuation_date,
        spot=x.spot,
        discount=FlatRateCurve(x.rate),
        vol=FlatVolSurface(x.vol),
        dividend_yield=FlatRateCurve(x.dividend_yield),
        borrow=FlatRateCurve(x.borrow),
    )


def to_model(x: ModelIn) -> Model:
    """Engine model from its schema."""
    match x.type:
        case "bsm":
            return BlackScholesMerton()


def to_settings(x: SettingsIn) -> PricingSettings:
    """Engine settings from their schema."""
    b = x.bumps
    return PricingSettings(
        bumps=BumpSettings(
            spot_rel=b.spot_rel, vol_abs=b.vol_abs, rate_abs=b.rate_abs, time_days=b.time_days
        )
    )


def from_settings(s: PricingSettings) -> SettingsIn:
    """Settings schema from engine settings."""
    b = s.bumps
    return SettingsIn(
        bumps=BumpSettingsIn(
            spot_rel=b.spot_rel, vol_abs=b.vol_abs, rate_abs=b.rate_abs, time_days=b.time_days
        )
    )


def to_price_response(
    result: PricingResult,
    instrument: EuropeanOption,
    market: MarketData,
    method: PricingMethod,
) -> PriceResponse:
    """Serialise a pricing result with desk-unit greeks in both modes."""
    t = market.time_to(instrument.maturity)
    greeks = GreeksOut(pure=[], cash=[])
    if result.greeks is not None:
        greeks = GreeksOut(
            **{
                mode.value: [
                    GreekOut(key=g.greek, value=g.value, unit=g.unit, source=g.source)
                    for g in desk_greeks(
                        result.greeks, market.spot, instrument.quantity, instrument.currency, mode
                    )
                ]
                for mode in GreekMode
            }
        )
    d = result.diagnostics
    return PriceResponse(
        currency=instrument.currency,
        price=result.price,
        position_value=result.price * instrument.quantity,
        pct_notional=100.0 * result.price / market.spot,
        forward=market.forward(t),
        discount_factor=market.df(t),
        time_to_expiry=t,
        greeks=greeks,
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
