"""Vanilla and digital option definitions (pure data)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from engine.instruments.base import Instrument


class OptionType(StrEnum):
    """Call or put. ``omega`` is +1 for a call and −1 for a put."""

    CALL = "call"
    PUT = "put"

    @property
    def omega(self) -> int:
        """Payoff sign ``ω`` such that the payoff is ``max(ω·(S − K), 0)``."""
        return 1 if self is OptionType.CALL else -1


@dataclass(frozen=True, slots=True, kw_only=True)
class VanillaOption(Instrument):
    """Call or put on ``max(ω·(S − K), 0)``; exercise style is given by the subclass.

    Settlement lag is zero: payment on the exercise date.
    """

    option_type: OptionType
    strike: float
    expiry: dt.date

    def __post_init__(self) -> None:
        if not self.strike > 0.0:
            raise ValueError(f"strike must be positive, got {self.strike}")

    @property
    def maturity(self) -> dt.date:
        """Expiry date."""
        return self.expiry


@dataclass(frozen=True, slots=True, kw_only=True)
class EuropeanOption(VanillaOption):
    """Exercisable at expiry only."""


@dataclass(frozen=True, slots=True, kw_only=True)
class AmericanOption(VanillaOption):
    """Exercisable on any date up to and including expiry (continuous exercise)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DigitalOption(Instrument):
    """European cash-or-nothing digital: pays ``payout`` per unit if ``ω·(S_T − K) > 0``.

    Attributes:
        payout: Cash amount per unit of underlying, in the instrument currency.

    """

    option_type: OptionType
    strike: float
    expiry: dt.date
    payout: float = 1.0

    def __post_init__(self) -> None:
        if not (self.strike > 0.0 and self.payout > 0.0):
            raise ValueError("strike and payout must be positive")

    @property
    def maturity(self) -> dt.date:
        """Expiry date."""
        return self.expiry
