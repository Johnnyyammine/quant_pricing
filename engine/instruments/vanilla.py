"""Vanilla option definitions."""

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
class EuropeanOption(Instrument):
    """European call or put paying ``max(ω·(S_T − K), 0)`` at ``expiry``.

    Settlement lag is zero in Phase 0/1: payment date equals ``expiry``.
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
