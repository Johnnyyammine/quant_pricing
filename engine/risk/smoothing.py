"""Risk proxies: smoothed replicas whose greeks stand in for a discontinuous payoff's.

A cash-or-nothing digital paying ``Q`` is replicated by a centred spread of width ``w = ρ·K``
(``ρ = settings.digital.spread_width_rel``)::

    call:  Q/w · [C(K − w/2) − C(K + w/2)]        put:  Q/w · [P(K + w/2) − P(K − w/2)]

The replica converges to the digital as ``w → 0`` and its greeks stay bounded near expiry at the
strike, where the digital's Δ and Γ blow up. Prices are never replaced: the proxy only supplies
greeks, and the difference between the proxy's value and the exact price is reported as the
smoothing bias. With a vol smile (Phase 3) the replica also carries the skew term of digital risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.instruments.base import Instrument
from engine.instruments.vanilla import DigitalOption, EuropeanOption, OptionType
from engine.settings import PricingSettings


@dataclass(frozen=True, slots=True)
class ProxyLeg:
    """``weight`` units of ``instrument`` (weights apply to unit prices and greeks)."""

    weight: float
    instrument: Instrument


@dataclass(frozen=True, slots=True)
class RiskProxy:
    """A weighted replica supplying greeks, with a label and its smoothing width (price units)."""

    legs: tuple[ProxyLeg, ...]
    label: str
    width: float


def risk_proxy(instrument: Instrument, settings: PricingSettings) -> RiskProxy | None:
    """The smoothed replica for ``instrument``, or ``None`` if its own greeks are used."""
    width_rel = settings.digital.spread_width_rel
    if not isinstance(instrument, DigitalOption) or width_rel <= 0.0:
        return None
    k, w = instrument.strike, width_rel * instrument.strike
    lo, hi = k - 0.5 * w, k + 0.5 * w

    def leg(strike: float) -> EuropeanOption:
        return EuropeanOption(
            option_type=instrument.option_type,
            strike=strike,
            expiry=instrument.expiry,
            quantity=instrument.quantity,
            currency=instrument.currency,
        )

    scale = instrument.payout / w
    if instrument.option_type is OptionType.CALL:
        legs = (ProxyLeg(scale, leg(lo)), ProxyLeg(-scale, leg(hi)))
    else:
        legs = (ProxyLeg(scale, leg(hi)), ProxyLeg(-scale, leg(lo)))
    return RiskProxy(legs=legs, label="call-spread replica", width=w)
