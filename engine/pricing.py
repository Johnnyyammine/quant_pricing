"""Pricing entry points: :func:`price` (one spot) and :func:`price_ladder` (many spots)."""

from __future__ import annotations

import time
from collections.abc import Collection, Sequence
from dataclasses import replace

from engine.errors import PricingError, UnsupportedCombinationError
from engine.instruments.base import Instrument
from engine.market.market_data import MarketData
from engine.methods.base import PricingMethod
from engine.models.base import Model
from engine.results import Diagnostics, Greek, Greeks, GreekSource, PricingResult
from engine.risk.greeks import ladder_bump_greeks
from engine.risk.smoothing import risk_proxy
from engine.settings import PricingSettings

ALL_GREEKS: tuple[Greek, ...] = tuple(Greek)


def _check(instrument: Instrument, market: MarketData, model: Model, method: PricingMethod) -> None:
    if not method.supports(instrument, model):
        raise UnsupportedCombinationError(
            f"{method.name} does not support {type(instrument).__name__} under {model.name}"
        )
    if instrument.maturity < market.valuation_date:
        raise PricingError(
            f"instrument matured on {instrument.maturity}, before valuation date "
            f"{market.valuation_date}"
        )


def _ladder_greeks(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings,
    multipliers: Sequence[float],
    greeks: Collection[Greek],
) -> tuple[list[Greeks], int, tuple[str, ...]]:
    """Greeks at each spot: closed forms where the method has them, the rest by ladder bumps."""
    proxy = risk_proxy(instrument, settings)
    if proxy is not None:
        # Greeks of the smoothed replica (engine.risk.smoothing); prices are not replaced.
        totals = [dict.fromkeys(greeks, 0.0) for _ in multipliers]
        sources: dict[Greek, GreekSource] = {}
        revaluations = 0
        warnings: tuple[str, ...] = ()
        for leg in proxy.legs:
            leg_greeks, n, w = _ladder_greeks(
                leg.instrument, market, model, method, settings, multipliers, greeks
            )
            revaluations += n
            warnings += w
            for total, g_leg in zip(totals, leg_greeks, strict=True):
                for g in greeks:
                    total[g] += leg.weight * g_leg.values[g]
                sources |= g_leg.sources
        return [Greeks(values=t, sources=sources) for t in totals], revaluations, warnings

    per_spot: list[dict[Greek, float]] = [{} for _ in multipliers]
    if not settings.force_bump_greeks:
        for k, m in enumerate(multipliers):
            shocked = replace(market, spot=market.spot * m)
            analytic = method.analytic_greeks(instrument, shocked, model, settings)
            per_spot[k] = {g: analytic[g] for g in greeks if g in analytic}
    missing = sorted({g for g in greeks for k in range(len(multipliers)) if g not in per_spot[k]})
    sources = {g: GreekSource.ANALYTIC for g in greeks if g not in missing}
    revaluations = 1
    warnings = ()
    if missing:
        bumped = ladder_bump_greeks(
            market,
            instrument.maturity,
            lambda m, mults: method.evaluate_ladder(instrument, m, model, settings, mults),
            missing,
            settings.bumps,
            multipliers,
        )
        for k, b in enumerate(bumped):
            per_spot[k].update(b.values)
        sources |= dict.fromkeys(missing, GreekSource.BUMP)
        revaluations, warnings = bumped[0].revaluations, bumped[0].warnings
    return [Greeks(values=v, sources=sources) for v in per_spot], revaluations, warnings


def price(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings | None = None,
    *,
    greeks: Collection[Greek] = ALL_GREEKS,
) -> PricingResult:
    """Price ``instrument`` and compute ``greeks``.

    Greeks the method provides in closed form are taken as is; the rest come from central
    bump-and-revalue through the same method (:mod:`engine.risk.greeks`). Instruments with a risk
    proxy (digitals) take their greeks from the proxy (:mod:`engine.risk.smoothing`).

    Raises:
        UnsupportedCombinationError: ``method`` does not support ``(instrument, model)``.
        PricingError: The instrument has matured before the valuation date.

    """
    settings = settings or PricingSettings()
    _check(instrument, market, model, method)
    start = time.perf_counter()
    base = method.evaluate(instrument, market, model, settings)
    details = dict(base.details)
    greek_result: Greeks | None = None
    revaluations = 1
    warnings: tuple[str, ...] = ()
    if greeks:
        (greek_result,), revaluations, warnings = _ladder_greeks(
            instrument, market, model, method, settings, [1.0], greeks
        )
        proxy = risk_proxy(instrument, settings)
        if proxy is not None:
            proxy_value = sum(
                leg.weight * method.evaluate(leg.instrument, market, model, settings).value
                for leg in proxy.legs
            )
            details |= {
                "greeks_from": proxy.label,
                "spread_width": proxy.width,
                "replica_value": proxy_value,
                "smoothing_bias": proxy_value - base.value,
            }
    runtime_ms = (time.perf_counter() - start) * 1e3
    return PricingResult(
        price=base.value,
        greeks=greek_result,
        diagnostics=Diagnostics(
            method=method.name,
            model=model.name,
            runtime_ms=runtime_ms,
            revaluations=revaluations,
            settings=settings,
            details=details,
            warnings=warnings,
        ),
    )


def price_ladder(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings,
    multipliers: Sequence[float],
    *,
    greeks: Collection[Greek] = ALL_GREEKS,
) -> list[tuple[float, Greeks | None]]:
    """Unit price and greeks at each spot ``market.spot·m``, sharing solves across spots."""
    _check(instrument, market, model, method)
    values = method.evaluate_ladder(instrument, market, model, settings, multipliers)
    if not greeks:
        return [(v, None) for v in values]
    per_spot, _, _ = _ladder_greeks(
        instrument, market, model, method, settings, multipliers, greeks
    )
    return list(zip(values, per_spot, strict=True))
