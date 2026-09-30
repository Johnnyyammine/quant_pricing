"""Registry of available pricing methods, keyed by :attr:`PricingMethod.name`."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from engine.instruments.base import Instrument
from engine.methods.analytic import AnalyticBlack
from engine.methods.base import PricingMethod
from engine.models.base import Model

METHODS: Mapping[str, PricingMethod] = MappingProxyType({m.name: m for m in (AnalyticBlack(),)})


def get_method(name: str) -> PricingMethod:
    """Look up a method by name. Raises ``KeyError`` with the known names if absent."""
    try:
        return METHODS[name]
    except KeyError:
        raise KeyError(f"unknown method {name!r}; known: {sorted(METHODS)}") from None


def methods_for(instrument: Instrument, model: Model) -> list[PricingMethod]:
    """All registered methods that support ``(instrument, model)``."""
    return [m for m in METHODS.values() if m.supports(instrument, model)]
