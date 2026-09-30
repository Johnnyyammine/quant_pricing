"""Instrument base class. Instruments are pure data: payoff description plus schedule."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Instrument(ABC):
    """Base for all instruments.

    Attributes:
        quantity: Number of units of the underlying the position refers to (``N``). Unit prices
            are per one unit; position values are ``N ×`` unit price.
        currency: ISO currency code of the payoff.

    """

    quantity: float = 1.0
    currency: str = "EUR"

    @property
    @abstractmethod
    def maturity(self) -> dt.date:
        """Last date on which the instrument can pay or be exercised."""
