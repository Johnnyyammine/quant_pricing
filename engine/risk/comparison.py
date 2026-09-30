"""Method comparison: the same product under every supporting method, and convergence ladders."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from engine.instruments.base import Instrument
from engine.market.market_data import MarketData
from engine.methods.base import PricingMethod
from engine.methods.pde import CrankNicolsonPde
from engine.methods.tree import LeisenReimerTree
from engine.models.base import Model
from engine.pricing import price
from engine.settings import PricingSettings, TreeSettings

#: Resolutions shown in convergence plots.
TREE_STEPS: tuple[int, ...] = (51, 101, 201, 401, 801, 1601)
PDE_SPACE_NODES: tuple[int, ...] = (100, 200, 400, 800, 1600)
#: Time steps per space node in PDE convergence runs (matches the default grid's 800 × 200).
PDE_TIME_PER_SPACE: float = 0.25


@dataclass(frozen=True, slots=True)
class ConvergencePoint:
    """Price at one resolution (tree steps, or PDE space nodes) and its runtime."""

    resolution: int
    value: float
    runtime_ms: float


def convergence(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings,
) -> list[ConvergencePoint]:
    """Price along the method's resolution ladder (empty for closed forms)."""
    runs: list[tuple[int, PricingSettings]]
    if isinstance(method, LeisenReimerTree):
        runs = [(n, replace(settings, tree=TreeSettings(steps=n))) for n in TREE_STEPS]
    elif isinstance(method, CrankNicolsonPde):
        runs = [
            (
                n,
                replace(
                    settings,
                    pde=replace(
                        settings.pde,
                        space_nodes=n,
                        time_steps=max(4, round(n * PDE_TIME_PER_SPACE)),
                    ),
                ),
            )
            for n in PDE_SPACE_NODES
        ]
    else:
        return []
    out = []
    for n, s in runs:
        t0 = time.perf_counter()
        v = price(instrument, market, model, method, s, greeks=()).price
        out.append(ConvergencePoint(n, v, (time.perf_counter() - t0) * 1e3))
    return out


def resolution_of(method: PricingMethod, settings: PricingSettings) -> int | None:
    """The method's resolution under ``settings`` (for marking it on convergence plots)."""
    if isinstance(method, LeisenReimerTree):
        return settings.tree.steps
    if isinstance(method, CrankNicolsonPde):
        return settings.pde.space_nodes
    return None


__all__ = ["ConvergencePoint", "convergence", "resolution_of"]
