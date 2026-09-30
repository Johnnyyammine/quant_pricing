"""Leisen–Reimer binomial tree for European and American vanillas.

D. Leisen & M. Reimer, "Binomial models for option valuation – examining and improving
convergence", Applied Mathematical Finance 3 (1996).

The tree is built on the driftless martingale part of the state (see :mod:`.dynamics`)::

    X_t = X_0·g(t)·M_t,   M lognormal, E[M_t] = 1,  g = deterministic carry growth

so time-dependent rates, yields and escrowed dividends need no special treatment: each node's
state is ``X_0·g(t_i)·u^j·d^{i−j}`` and each step discounts with ``P(t_{i+1})/P(t_i)``. With ``n``
(odd) uniform steps and Peizer–Pratt method-2 inversion
``h(z) = ½ + sign(z)·√(¼ − ¼·exp(−(z/(n + ⅓ + 0.1/(n+1)))²·(n + ⅙)))``::

    p = h(d₂),  p' = h(d₁),  u = p'/p,  d = (1 − p·u)/(1 − p)

with the Black ``d₁, d₂`` on the forward ``F = X_0·g(T)`` and strike ``K`` (``X_T = S_T``). The tree
is centred on the strike, so its price is smooth in spot and converges as ``O(n⁻²)`` for
Europeans. American exercise compares continuation with ``max(ω(S − K), 0)`` at each node, with
``S = a(t_i)·X + c(t_i)`` (cum-dividend at the node); exercise just before an ex-date is resolved
to one step.

Spots in a ladder are priced together (arrays of shape ``spots × nodes``). Spot-jump cash
dividends are not supported (the tree would not recombine); use the PDE.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import ClassVar

import numpy as np

from engine.instruments.base import Instrument
from engine.instruments.vanilla import AmericanOption, EuropeanOption, VanillaOption
from engine.market.market_data import MarketData
from engine.methods.base import MethodOutput, PricingMethod
from engine.methods.dynamics import state_dynamics
from engine.models.base import Model
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton
from engine.settings import PricingSettings


def peizer_pratt(z: np.ndarray, n: int) -> np.ndarray:
    """Peizer–Pratt method-2 inversion of the normal distribution for an ``n``-step tree."""
    a = z / (n + 1.0 / 3.0 + 0.1 / (n + 1.0))
    return 0.5 + np.sign(z) * np.sqrt(0.25 - 0.25 * np.exp(-a * a * (n + 1.0 / 6.0)))


class LeisenReimerTree(PricingMethod):
    """Leisen–Reimer binomial tree (European and American vanillas)."""

    name: ClassVar[str] = "lr_tree"
    label: ClassVar[str] = "Leisen–Reimer tree"

    def supports(self, instrument: Instrument, model: Model) -> bool:
        """European and American vanillas under BSM (escrowed dividends) or Black-76."""
        return isinstance(instrument, EuropeanOption | AmericanOption) and isinstance(
            model, BlackScholesMerton | Black76
        )

    def evaluate(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> MethodOutput:
        """Unit price at the market's spot."""
        value = self.evaluate_ladder(instrument, market, model, settings, [1.0])[0]
        return MethodOutput(
            value=value, details={"steps": settings.tree.steps, "scheme": "Leisen–Reimer, PP2"}
        )

    def evaluate_ladder(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
        multipliers: Sequence[float],
    ) -> list[float]:
        """Unit prices at ``spot·m`` for every ``m`` in one vectorised backward induction."""
        assert isinstance(instrument, VanillaOption)
        big_t = market.time_to(instrument.expiry)
        k, omega = instrument.strike, instrument.option_type.omega
        spots = market.spot * np.asarray(multipliers, dtype=float)
        if big_t <= 0.0:
            return [max(omega * (s - k), 0.0) for s in spots]

        dyn = state_dynamics(market, model, big_t, k, allow_jumps=False)
        american = isinstance(instrument, AmericanOption)
        n = settings.tree.steps
        dt = big_t / n
        times = [i * dt for i in range(n + 1)]
        growth = [dyn.growth(t) for t in times]
        dfs = [market.df(t) for t in times]

        x0 = np.array([dyn.state_from_spot(float(s)) for s in spots])[:, None]
        if np.any(x0 <= 0.0):
            raise ValueError(
                "spot below the escrowed dividends: the escrowed state is not positive"
            )
        stdev = dyn.sigma * math.sqrt(big_t)
        fwd = x0 * growth[-1]
        d1 = np.log(fwd / k) / stdev + 0.5 * stdev
        p = peizer_pratt(d1 - stdev, n)
        u = peizer_pratt(d1, n) / p
        d = (1.0 - p * u) / (1.0 - p)
        log_u, log_d = np.log(u), np.log(d)

        def nodes(i: int, cum: bool) -> np.ndarray:
            j = np.arange(i + 1)[None, :]
            state = x0 * growth[i] * np.exp(i * log_d + j * (log_u - log_d))
            a, c = dyn.spot_affine(times[i], cum=cum)
            return np.asarray(a * state + c)

        values = np.maximum(omega * (nodes(n, cum=False) - k), 0.0)
        for i in range(n - 1, -1, -1):
            values = (dfs[i + 1] / dfs[i]) * (p * values[:, 1:] + (1.0 - p) * values[:, :-1])
            if american:  # exercise just before or just after an ex-date at t_i
                exercise = (
                    np.maximum(nodes(i, cum=True), nodes(i, cum=False))
                    if omega > 0
                    else (np.minimum(nodes(i, cum=True), nodes(i, cum=False)))
                )
                values = np.maximum(values, omega * (exercise - k))
        return [float(v) for v in values[:, 0]]
