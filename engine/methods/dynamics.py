"""State dynamics shared by the lattice and grid methods.

Both methods evolve a *state* ``X`` that is lognormal with volatility ``σ`` and deterministic
carry between events, and map it to spot for payoffs and exercise:

* BSM, escrowed dividends: ``X = Y`` with ``S_t = Y_t/Π_t + E_t`` (see
  :mod:`engine.market.market_data`); ``X`` has no jumps and ``X_T = S_T``.
* BSM, spot-jump dividends: ``X = S``, jumping ``S → S·(1 − δ) − D`` at ex-dates (PDE only).
* Black-76: ``X = F``, driftless, no dividends.

``growth(t)`` is the deterministic growth of ``E[X_t]`` between events (``G(t)`` or 1),
``forward_at_expiry(x, t)`` the forward of ``S_T`` given ``X_t = x``.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.errors import UnsupportedCombinationError
from engine.market.dividends import DividendEvent
from engine.market.market_data import MarketData
from engine.models.base import Model
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton, DividendTreatment


@dataclass(frozen=True, slots=True)
class StateDynamics:
    """Lognormal state with deterministic carry; see module docstring."""

    market: MarketData
    maturity: float
    sigma: float
    kind: str  # "escrowed" | "spot" | "forward"

    @property
    def jumps(self) -> list[DividendEvent]:
        """Dividend jumps applied to the state (spot-jump treatment only)."""
        return self.market.dividend_events(self.maturity) if self.kind == "spot" else []

    def growth(self, t: float) -> float:
        """Deterministic growth factor of the state from 0 to ``t`` (between jumps)."""
        return 1.0 if self.kind == "forward" else self.market.growth(t)

    def state_from_spot(self, spot: float) -> float:
        """``X_0`` for today's spot."""
        if self.kind == "escrowed":
            m, t = self.market, self.maturity
            return (spot - m.escrowed_cash(0.0, t)) * m.proportional_factor(0.0, t)
        return spot

    def spot_from_state(self, x: float, t: float, *, cum: bool = False) -> float:
        """Spot at ``t`` for state ``x`` (``cum``: just before any ex-date at ``t``)."""
        if self.kind != "escrowed":
            return x
        m, big_t = self.market, self.maturity
        return x / m.proportional_factor(t, big_t, cum=cum) + m.escrowed_cash(t, big_t, cum=cum)

    def spot_affine(self, t: float, *, cum: bool = False) -> tuple[float, float]:
        """``(a, c)`` with ``S = a·X + c`` at ``t`` (vectorisation helper)."""
        if self.kind != "escrowed":
            return 1.0, 0.0
        m, big_t = self.market, self.maturity
        return (
            1.0 / m.proportional_factor(t, big_t, cum=cum),
            m.escrowed_cash(t, big_t, cum=cum),
        )

    def forward_at_expiry(self, x: float, t: float) -> float:
        """Forward of ``S_T`` given ``X_t = x``."""
        g = self.growth(self.maturity) / self.growth(t)
        if self.kind == "spot":
            m, big_t = self.market, self.maturity
            return (x - m.escrowed_cash(t, big_t)) * m.proportional_factor(t, big_t) * g
        return x * g


def state_dynamics(
    market: MarketData, model: Model, maturity: float, strike: float, *, allow_jumps: bool
) -> StateDynamics:
    """Dynamics for ``model``; ``allow_jumps=False`` rejects spot-jump cash dividends (lattices)."""
    sigma = market.vol.vol(strike, maturity)
    if isinstance(model, Black76):
        return StateDynamics(market, maturity, sigma, "forward")
    assert isinstance(model, BlackScholesMerton)
    has_cash = any(e.cash > 0.0 for e in market.dividend_events(maturity))
    if model.dividend_treatment is DividendTreatment.SPOT and has_cash:
        if not allow_jumps:
            raise UnsupportedCombinationError(
                "a recombining tree cannot carry spot-jump cash dividends: use the PDE, or the "
                "escrowed treatment"
            )
        return StateDynamics(market, maturity, sigma, "spot")
    # Escrowed, or spot treatment with proportional dividends only (identical: S stays lognormal).
    return StateDynamics(market, maturity, sigma, "escrowed")
