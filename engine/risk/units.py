"""Conversion of pure-unit greeks into desk units.

Cash greeks are currency amounts for the position of ``N`` units at spot ``S``:

======  ==========================  ======================================
Greek   Cash definition             Unit
======  ==========================  ======================================
Δ       Δ·S·N                       CCY (cash delta)
Γ       Γ·S²·N / 100                CCY per 1% spot (change in cash delta)
ν       ν·N / 100                   CCY per vol point
Θ       Θ·N / 365                   CCY per calendar day
ρ       ρ·N / 10⁴                   CCY per bp
φ       φ·N / 10⁴                   CCY per bp of dividend yield
vanna   vanna·S·N / 100             CCY of cash delta per vol point
volga   volga·N / 10⁴               CCY per vol point² (change in vega per vol pt)
charm   charm·S·N / 365             CCY of cash delta per calendar day
======  ==========================  ======================================

Pure greeks are the cash greeks as a percentage of notional ``N·S``: ``pure = 100·cash/(N·S)``.
Hence pure Δ is in %, pure Γ is the change in Δ(%) for a 1% spot move (``= Γ·S``), and the others
are % of notional per unit of bump.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from engine.dates import DAYS_PER_YEAR_ACT365F
from engine.results import Greek, Greeks, GreekSource

PERCENT: float = 100.0
VOL_POINT: float = 0.01
BASIS_POINT: float = 1e-4
SPOT_MOVE_1PCT: float = 0.01


class GreekMode(StrEnum):
    """Display mode for greeks."""

    PURE = "pure"
    CASH = "cash"


@dataclass(frozen=True, slots=True)
class DeskGreek:
    """A greek in desk units, ready for display."""

    greek: Greek
    value: float
    unit: str
    source: GreekSource


_CASH_UNITS: Mapping[Greek, str] = {
    Greek.DELTA: "{ccy}",
    Greek.GAMMA: "{ccy} / 1%",
    Greek.VEGA: "{ccy} / vol pt",
    Greek.THETA: "{ccy} / day",
    Greek.RHO: "{ccy} / bp",
    Greek.PHI: "{ccy} / bp",
    Greek.VANNA: "{ccy} Δ / vol pt",
    Greek.VOLGA: "{ccy} / vol pt²",
    Greek.CHARM: "{ccy} Δ / day",
}

_PURE_UNITS: Mapping[Greek, str] = {
    Greek.DELTA: "%",
    Greek.GAMMA: "%Δ / 1%",
    Greek.VEGA: "% / vol pt",
    Greek.THETA: "% / day",
    Greek.RHO: "% / bp",
    Greek.PHI: "% / bp",
    Greek.VANNA: "%Δ / vol pt",
    Greek.VOLGA: "% / vol pt²",
    Greek.CHARM: "%Δ / day",
}


def greek_unit(greek: Greek, mode: GreekMode, currency: str) -> str:
    """Display unit of ``greek`` in ``mode``."""
    return (_CASH_UNITS if mode is GreekMode.CASH else _PURE_UNITS)[greek].format(ccy=currency)


def cash_greek(greek: Greek, value: float, spot: float, quantity: float) -> float:
    """Convert a pure-unit greek to its cash value for a position of ``quantity`` units."""
    match greek:
        case Greek.DELTA:
            return value * spot * quantity
        case Greek.GAMMA:
            return value * spot * spot * SPOT_MOVE_1PCT * quantity
        case Greek.VEGA:
            return value * VOL_POINT * quantity
        case Greek.THETA:
            return value / DAYS_PER_YEAR_ACT365F * quantity
        case Greek.RHO | Greek.PHI:
            return value * BASIS_POINT * quantity
        case Greek.VANNA:
            return value * spot * VOL_POINT * quantity
        case Greek.VOLGA:
            return value * VOL_POINT * VOL_POINT * quantity
        case Greek.CHARM:
            return value * spot / DAYS_PER_YEAR_ACT365F * quantity


def desk_greeks(
    greeks: Greeks,
    spot: float,
    quantity: float,
    currency: str,
    mode: GreekMode,
) -> list[DeskGreek]:
    """All greeks in ``greeks`` converted to desk units, in :class:`Greek` declaration order."""
    notional = quantity * spot
    out: list[DeskGreek] = []
    for g in Greek:
        if g not in greeks.values:
            continue
        cash = cash_greek(g, greeks.values[g], spot, quantity)
        value = cash if mode is GreekMode.CASH else PERCENT * cash / notional
        unit = greek_unit(g, mode, currency)
        out.append(DeskGreek(greek=g, value=value, unit=unit, source=greeks.sources[g]))
    return out
