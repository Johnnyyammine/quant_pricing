"""Closed-form Black prices and greeks, written on the forward.

Inputs are the forward ``F(0,T)`` and its sensitivities to spot, rates and yield (from the model),
so the same formulas cover BSM (with or without escrowed discrete dividends) and Black-76::

    D = P(0,T),  s = σ√T,  d₁ = ln(F/K)/s + s/2,  d₂ = d₁ − s,  n = φ(·),  N = Φ(·)
    F_S = ∂F/∂S,  F_r = ∂F/∂r,  F_q = ∂F/∂q

Vanilla ``V = D·ω·[F·N(ωd₁) − K·N(ωd₂)]`` (Jäckel's accurate kernel), ``V_F = D·ω·N(ωd₁)``::

    Δ = V_F·F_S          Γ = D·n(d₁)/(F·s)·F_S²      ν = D·F·n(d₁)·√T
    vanna = −D·F_S·n(d₁)·d₂/σ      volga = ν·d₁·d₂/σ
    ρ = −T·V + V_F·F_r   φ = V_F·F_q

Cash-or-nothing digital paying ``Q`` if ``ω(S_T − K) > 0``: ``V = Q·D·N(ωd₂)``,
``V_F = Q·D·ω·n(d₂)/(F·s)``::

    Δ = V_F·F_S          Γ = −Q·D·ω·n(d₂)·d₁/(F·s)²·F_S²      ν = −Q·D·ω·n(d₂)·d₁/σ
    vanna = Q·D·ω·n(d₂)·(d₁d₂ − 1)/(F·s·σ)·F_S      volga = −Q·D·ω·n(d₂)·(d₁²d₂ − d₁ − d₂)/σ²
    ρ = −T·V + V_F·F_r   φ = V_F·F_q

Θ = ∂V/∂t and charm = ∂Δ/∂t are closed form only for time-homogeneous inputs (flat curves, flat
vol, no discrete dividends before expiry), where ``F = X·e^{μT}`` with carry ``μ`` and
``F_S = e^{μT}`` (BSM) or ``F_S = 1, μ = 0`` (Black-76)::

    vanilla  Θ = −D·F·n(d₁)·σ/(2√T) − ω(μ − r)·D·F·N(ωd₁) − ω·r·K·D·N(ωd₂)
             charm = −ω(μ − r)·D·F_S·N(ωd₁) − D·F_S·n(d₁)·(2μT − d₂s)/(2Ts)
    digital  Θ = r·V − Q·D·ω·n(d₂)·(2μT − d₁s)/(2Ts)
             charm = Δ·[r + d₂(2μT − d₁s)/(2Ts) + 1/(2T)]

References: E. G. Haug, *The Complete Guide to Option Pricing Formulas*, 2nd ed., ch. 1–2 and
§4.19.2 (cash-or-nothing); J. C. Hull, *Options, Futures, and Other Derivatives*.

At ``T = 0`` the price is the payoff; vanilla Δ is the (discounted) step function (½ at the money)
and every other greek is reported as 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from engine.numerics.black import black_undiscounted
from engine.numerics.normal import norm_cdf, norm_pdf
from engine.results import Greek


@dataclass(frozen=True, slots=True)
class BlackInputs:
    """Forward-based Black inputs.

    Attributes:
        forward: ``F(0, T)``.
        strike: ``K``.
        t: ``T`` in years.
        sigma: ``σ``.
        discount: ``D = P(0, T)``.
        omega: +1 call, −1 put.
        d_spot, d_rate, d_yield: ``∂F/∂S``, ``∂F/∂r``, ``∂F/∂q``.
        rate: Discount zero rate ``r`` (Θ/charm only).
        carry: Carry ``μ`` with ``F = X·e^{μT}`` (Θ/charm only; ``None`` when not time-homogeneous).

    """

    forward: float
    strike: float
    t: float
    sigma: float
    discount: float
    omega: int
    d_spot: float
    d_rate: float
    d_yield: float
    rate: float
    carry: float | None

    @property
    def stdev(self) -> float:
        """``s = σ√T``."""
        return self.sigma * math.sqrt(self.t)

    def d1_d2(self) -> tuple[float, float]:
        """``(d₁, d₂)``."""
        s = self.stdev
        d1 = math.log(self.forward / self.strike) / s + 0.5 * s
        return d1, d1 - s


def vanilla_price(p: BlackInputs) -> float:
    """``V = D·B(F, K, σ√T, ω)`` with the accurate undiscounted Black kernel."""
    if p.t <= 0.0:
        return p.discount * max(p.omega * (p.forward - p.strike), 0.0)
    return p.discount * black_undiscounted(p.forward, p.strike, p.stdev, p.omega)


def digital_price(p: BlackInputs, payout: float) -> float:
    """``V = Q·D·N(ωd₂)``; at expiry the payoff ``Q·1{ω(F − K) > 0}``."""
    if p.t <= 0.0:
        return payout * p.discount * (1.0 if p.omega * (p.forward - p.strike) > 0.0 else 0.0)
    return payout * p.discount * norm_cdf(p.omega * p.d1_d2()[1])


def _expired(p: BlackInputs, delta: float) -> dict[Greek, float]:
    out = dict.fromkeys(Greek, 0.0)
    out[Greek.DELTA] = delta
    return out


def vanilla_greeks(p: BlackInputs, price: float) -> dict[Greek, float]:
    """Vanilla greeks in pure model units (module docstring)."""
    w, f, k, dd, fs = p.omega, p.forward, p.strike, p.discount, p.d_spot
    if p.t <= 0.0:
        itm = w * (f - k)
        return _expired(p, dd * fs * w * (1.0 if itm > 0.0 else 0.5 if itm == 0.0 else 0.0))
    t, sigma, s = p.t, p.sigma, p.stdev
    d1, d2 = p.d1_d2()
    n1 = norm_pdf(d1)
    cdf1, cdf2 = norm_cdf(w * d1), norm_cdf(w * d2)
    v_f = dd * w * cdf1
    vega = dd * f * n1 * math.sqrt(t)
    greeks = {
        Greek.DELTA: v_f * fs,
        Greek.GAMMA: dd * n1 / (f * s) * fs * fs,
        Greek.VEGA: vega,
        Greek.VANNA: -dd * fs * n1 * d2 / sigma,
        Greek.VOLGA: vega * d1 * d2 / sigma,
        Greek.RHO: -t * price + v_f * p.d_rate,
        Greek.PHI: v_f * p.d_yield,
    }
    if p.carry is not None:
        mu, r = p.carry, p.rate
        greeks[Greek.THETA] = (
            -dd * f * n1 * sigma / (2.0 * math.sqrt(t))
            - w * (mu - r) * dd * f * cdf1
            - w * r * k * dd * cdf2
        )
        greeks[Greek.CHARM] = -w * (mu - r) * dd * fs * cdf1 - dd * fs * n1 * (
            2.0 * mu * t - d2 * s
        ) / (2.0 * t * s)
    return greeks


def digital_greeks(p: BlackInputs, price: float, payout: float) -> dict[Greek, float]:
    """Exact cash-or-nothing greeks in pure model units (module docstring)."""
    w, f, dd, fs = p.omega, p.forward, p.discount, p.d_spot
    if p.t <= 0.0:
        return _expired(p, 0.0)
    t, sigma, s = p.t, p.sigma, p.stdev
    d1, d2 = p.d1_d2()
    qdn = payout * dd * w * norm_pdf(d2)
    v_f = qdn / (f * s)
    greeks = {
        Greek.DELTA: v_f * fs,
        Greek.GAMMA: -qdn * d1 / (f * s) ** 2 * fs * fs,
        Greek.VEGA: -qdn * d1 / sigma,
        Greek.VANNA: qdn * (d1 * d2 - 1.0) / (f * s * sigma) * fs,
        Greek.VOLGA: -qdn * (d1 * d1 * d2 - d1 - d2) / sigma**2,
        Greek.RHO: -t * price + v_f * p.d_rate,
        Greek.PHI: v_f * p.d_yield,
    }
    if p.carry is not None:
        mu, r = p.carry, p.rate
        drift = (2.0 * mu * t - d1 * s) / (2.0 * t * s)
        greeks[Greek.THETA] = r * price - qdn * drift
        greeks[Greek.CHARM] = greeks[Greek.DELTA] * (r + d2 * drift + 1.0 / (2.0 * t))
    return greeks
