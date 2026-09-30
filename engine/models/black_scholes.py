"""Black–Scholes–Merton model.

Between dividends ``dS/S = (r − q − b) dt + σ dW`` under the pricing measure, with the volatility
taken from the market's implied-vol surface at the instrument's strike and expiry. Discrete cash
dividends are handled by one of two treatments (see ``docs/models/black_scholes.md``):

* ``ESCROWED`` (default): ``S − E_t`` (spot less escrowed cash dividends) is lognormal with vol
  ``σ``. ``S_T`` is then lognormal with the dividend-adjusted forward, so Europeans are exactly
  Black on the forward — consistent with implied vols quoted against forwards.
* ``SPOT``: ``S`` itself is lognormal with vol ``σ`` between ex-dates and jumps
  ``S → S·(1 − δ) − D`` at each ex-date. No closed form with cash dividends; PDE only.

With proportional dividends only, both treatments coincide (``S_T`` stays lognormal).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from engine.models.base import Model


class DividendTreatment(StrEnum):
    """How discrete cash dividends enter the dynamics."""

    ESCROWED = "escrowed"
    SPOT = "spot"


@dataclass(frozen=True, slots=True)
class BlackScholesMerton(Model):
    """Lognormal dynamics with volatility read from the market vol surface."""

    name: ClassVar[str] = "bsm"
    dividend_treatment: DividendTreatment = DividendTreatment.ESCROWED
