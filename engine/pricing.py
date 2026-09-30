"""Single pricing entry point: :func:`price`."""

from __future__ import annotations

import time
from collections.abc import Collection

from engine.errors import PricingError, UnsupportedCombinationError
from engine.instruments.base import Instrument
from engine.market.market_data import MarketData
from engine.methods.base import PricingMethod
from engine.models.base import Model
from engine.results import Diagnostics, Greek, Greeks, GreekSource, PricingResult
from engine.risk.greeks import bump_greeks
from engine.risk.smoothing import risk_proxy
from engine.settings import PricingSettings

ALL_GREEKS: tuple[Greek, ...] = tuple(Greek)


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
    bump-and-revalue through the same method (see :mod:`engine.risk.greeks`).

    Raises:
        UnsupportedCombinationError: ``method`` does not support ``(instrument, model)``.
        PricingError: The instrument has matured before the valuation date.

    """
    settings = settings or PricingSettings()
    if not method.supports(instrument, model):
        raise UnsupportedCombinationError(
            f"{method.name} does not support {type(instrument).__name__} under {model.name}"
        )
    if instrument.maturity < market.valuation_date:
        raise PricingError(
            f"instrument matured on {instrument.maturity}, before valuation date "
            f"{market.valuation_date}"
        )

    start = time.perf_counter()
    base = method.evaluate(instrument, market, model, settings)
    details = dict(base.details)

    greek_result: Greeks | None = None
    revaluations = 1
    warnings: tuple[str, ...] = ()
    proxy = risk_proxy(instrument, settings) if greeks else None
    if proxy is not None:
        # Greeks of the smoothed replica; the price stays exact (engine.risk.smoothing).
        values = dict.fromkeys(greeks, 0.0)
        sources: dict[Greek, GreekSource] = {}
        proxy_value = 0.0
        for leg in proxy.legs:
            res = price(leg.instrument, market, model, method, settings, greeks=greeks)
            assert res.greeks is not None
            proxy_value += leg.weight * res.price
            for g in greeks:
                values[g] += leg.weight * res.greeks.values[g]
                sources[g] = res.greeks.sources[g]
            revaluations += res.diagnostics.revaluations
            warnings += res.diagnostics.warnings
        greek_result = Greeks(values=values, sources=sources)
        details |= {
            "greeks_from": proxy.label,
            "spread_width": proxy.width,
            "replica_value": proxy_value,
            "smoothing_bias": proxy_value - base.value,
        }
    elif greeks:
        analytic = (
            {}
            if settings.force_bump_greeks
            else method.analytic_greeks(instrument, market, model, settings)
        )
        values = {g: analytic[g] for g in greeks if g in analytic}
        sources = dict.fromkeys(values, GreekSource.ANALYTIC)
        missing = [g for g in greeks if g not in analytic]
        if missing:
            bumped = bump_greeks(
                market,
                instrument.maturity,
                lambda m: method.evaluate(instrument, m, model, settings).value,
                missing,
                settings.bumps,
                base.value,
            )
            values.update(bumped.values)
            sources.update(dict.fromkeys(bumped.values, GreekSource.BUMP))
            revaluations = bumped.revaluations
            warnings = bumped.warnings
        greek_result = Greeks(values=values, sources=sources)

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
