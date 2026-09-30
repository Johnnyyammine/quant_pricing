"""Pricing-method interface.

A method (analytic, tree, PDE, Monte Carlo) declares which (instrument, model) pairs it supports,
evaluates a unit price, and may supply analytic greeks. Greeks it does not supply are filled in by
the generic bump-and-revalue layer in :mod:`engine.risk.greeks`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import ClassVar

from engine.instruments.base import Instrument
from engine.market.market_data import MarketData
from engine.models.base import Model
from engine.results import Greek
from engine.settings import PricingSettings


@dataclass(frozen=True, slots=True)
class MethodOutput:
    """Raw output of one method evaluation: the unit price and method diagnostics."""

    value: float
    details: Mapping[str, float | int | str] = field(default_factory=dict)


class PricingMethod(ABC):
    """Base class for pricing methods."""

    name: ClassVar[str]
    label: ClassVar[str]

    @abstractmethod
    def supports(self, instrument: Instrument, model: Model) -> bool:
        """True if this method can price ``instrument`` under ``model``."""

    @abstractmethod
    def evaluate(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> MethodOutput:
        """Unit price of ``instrument``. Called only when :meth:`supports` is true."""

    def evaluate_ladder(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
        multipliers: Sequence[float],
    ) -> list[float]:
        """Unit prices at spots ``market.spot·m`` for each ``m``.

        Default: one :meth:`evaluate` per spot. Grid and lattice methods override this to share
        one solve across all spots (the result must equal the per-spot evaluation up to the
        method's own discretisation).
        """
        return [
            self.evaluate(instrument, replace(market, spot=market.spot * m), model, settings).value
            for m in multipliers
        ]

    def analytic_greeks(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> Mapping[Greek, float]:
        """Greeks available in closed form, in pure model units. Default: none."""
        return {}
