"""Crank–Nicolson finite differences in log-state for European, American and digital options.

The state ``X`` (see :mod:`.dynamics`) solves, backward in time, with ``x = ln X``::

    V_t + ½σ²·V_xx + (μ(t) − ½σ²)·V_x − r(t)·V = 0

with ``r(t)`` and ``μ(t)`` the local (per-step) forward discount and carry rates implied by the
curves (``μ = 0`` for Black-76).

**Grid.** Uniform in ``x``, ``ln K`` exactly on a node, half-width ``n_std·σ√T`` (extended to
cover every requested spot). The grid does not depend on spot, so bump greeks in spot are smooth.
``time_steps`` uniform steps, with dividend ex-dates inserted as extra time nodes.

**Scheme.** Crank–Nicolson, with the first ``rannacher_steps`` steps (and those following each
dividend jump) replaced by two implicit-Euler half steps (Rannacher smoothing of the payoff kink).
Dirichlet boundaries from the forward asymptotes: ``D(t,T)·max(ω(F_t(X) − K), 0)`` for vanillas
(``max`` with intrinsic for Americans), ``D(t,T)·Q·1{ω(F_t − K) > 0}`` for digitals.

**Early exercise.** Penalty method (P. A. Forsyth & K. R. Vetzal, "Quadratic convergence for
valuing American options using a penalty method", SIAM J. Sci. Comput. 23 (2002)): each step
solves ``(A + P)V = b + P·g`` with ``P = penalty·1{V < g}``, iterated to ``penalty_tol``. The
exercise boundary ``S*(t)`` is recorded per time node.

**Dividends.** Escrowed: no jumps; exercise uses ``S = X/Π_t + E_t`` (cum at ex-date nodes).
Spot-jump: at each ex-date ``V(S, t⁻) = V(S(1 − δ) − D, t⁺)`` by cubic-spline interpolation in
``x``; a cash dividend larger than ``S(1 − δ)`` is floored at the lowest grid node.

**Digitals.** The terminal payoff is cell-averaged (the node at the strike pays ½·Q), which
restores second-order convergence for the discontinuous payoff.

Values at the requested spots are read from the ``t = 0`` solution with a cubic spline in ``x``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.linalg import lapack

from engine.dates import SAME_INSTANT
from engine.instruments.base import Instrument
from engine.instruments.vanilla import AmericanOption, DigitalOption, EuropeanOption
from engine.market.market_data import MarketData
from engine.methods.base import MethodOutput, PricingMethod
from engine.methods.dynamics import StateDynamics, state_dynamics
from engine.models.base import Model
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton
from engine.settings import PdeSettings, PricingSettings

PdeInstrument = EuropeanOption | AmericanOption | DigitalOption


@dataclass(frozen=True, slots=True)
class PdeSolution:
    """Solution at ``t = 0`` on the grid, exercise boundary and solver statistics."""

    x: np.ndarray
    values: np.ndarray
    dynamics: StateDynamics
    boundary_t: list[float]
    boundary_s: list[float]  # nan where early exercise is not optimal on the grid
    time_nodes: int
    max_penalty_iterations: int

    def value_at_spot(self, spots: Sequence[float]) -> list[float]:
        """Values at today's ``spots`` (cubic spline in ``x = ln X``)."""
        spline = CubicSpline(self.x, self.values)
        xs = [math.log(self.dynamics.state_from_spot(s)) for s in spots]
        return [float(spline(x)) for x in xs]


def _tridiagonal_solve(
    sub: np.ndarray, main: np.ndarray, sup: np.ndarray, rhs: np.ndarray
) -> np.ndarray:
    """Solve a tridiagonal system with LAPACK ``dgtsv`` (partial pivoting)."""
    *_, x, info = lapack.dgtsv(sub, main, sup, rhs)
    if info != 0:
        raise ArithmeticError(f"tridiagonal solve failed (dgtsv info={info})")
    return np.asarray(x)


def _time_nodes(big_t: float, n: int, events: Sequence[float]) -> list[float]:
    nodes = {i * big_t / n for i in range(n + 1)}
    nodes |= {t for t in events if SAME_INSTANT < t < big_t - SAME_INSTANT}
    return sorted(nodes)


def solve(
    instrument: PdeInstrument,
    market: MarketData,
    model: Model,
    settings: PdeSettings,
    spots: Sequence[float],
) -> PdeSolution:
    """Solve the pricing PDE on a grid covering ``spots`` (module docstring)."""
    big_t = market.time_to(instrument.expiry)
    k, omega = instrument.strike, instrument.option_type.omega
    dyn = state_dynamics(market, model, big_t, k, allow_jumps=True)
    american = isinstance(instrument, AmericanOption)
    digital = isinstance(instrument, DigitalOption)
    payout = instrument.payout if isinstance(instrument, DigitalOption) else 0.0

    # ---- space grid: ln K on a node, spot-independent unless a spot falls outside
    x_states = [dyn.state_from_spot(s) for s in spots]
    if min(x_states) <= 0.0:
        raise ValueError("spot below the escrowed dividends: the escrowed state is not positive")
    xk = math.log(k)
    half = settings.n_std * dyn.sigma * math.sqrt(big_t)
    lo = min(xk - half, min(math.log(x) for x in x_states) - 0.5 * half)
    hi = max(xk + half, max(math.log(x) for x in x_states) + 0.5 * half)
    n_x = settings.space_nodes
    dx = (hi - lo) / (n_x - 1)
    j_k = round((xk - lo) / dx)
    x = xk + (np.arange(n_x) - j_k) * dx
    states = np.exp(x)

    def payoff_at(t: float, *, cum: bool) -> np.ndarray:
        a, c = dyn.spot_affine(t, cum=cum)
        return np.maximum(omega * (a * states + c - k), 0.0)

    # ---- terminal condition
    if digital:
        above = np.clip((x + 0.5 * dx - xk) / dx, 0.0, 1.0)  # fraction of the cell above ln K
        v = payout * (above if omega > 0 else 1.0 - above)
    else:
        v = np.maximum(omega * (states - k), 0.0)

    jumps = {e.t: e for e in dyn.jumps}
    terminal_jumps = [e for t, e in jumps.items() if abs(t - big_t) <= SAME_INSTANT]
    times = _time_nodes(big_t, settings.time_steps, list(jumps))
    df = {t: market.df(t) for t in times}
    growth = {t: dyn.growth(t) for t in times}

    def apply_jump(values: np.ndarray, e_cash: float, e_prop: float) -> np.ndarray:
        post = np.maximum(states * (1.0 - e_prop) - e_cash, states[0])
        return np.asarray(CubicSpline(x, values)(np.log(post)))

    for e in terminal_jumps:
        v = apply_jump(v, e.cash, e.proportional)

    a_half = 0.5 * dyn.sigma**2 / dx**2
    boundary_t: list[float] = []
    boundary_s: list[float] = []
    max_iters = 0
    smooth_left = settings.rannacher_steps
    active = np.zeros(n_x, dtype=bool)  # exercise region carried between penalty solves

    # Per-node quantities, computed once: boundary values and exercise payoffs.
    disc_to_t = [df[times[-1]] / df[t] for t in times]
    ends = (float(states[0]), float(states[-1]))
    bcs: list[np.ndarray] = []
    exercises: list[np.ndarray | None] = []
    for i, t in enumerate(times):
        fwd = np.array([dyn.forward_at_expiry(e, t) for e in ends])
        if digital:
            bc = disc_to_t[i] * payout * (omega * (fwd - k) > 0.0)
        else:
            bc = disc_to_t[i] * np.maximum(omega * (fwd - k), 0.0)
        ex = None
        if american:
            # Exercise is possible just before and just after an ex-date at t (same elsewhere).
            ex = np.maximum(payoff_at(t, cum=True), payoff_at(t, cum=False))
            bc = np.maximum(bc, ex[[0, -1]])
        bcs.append(bc)
        exercises.append(ex)
    matrices: dict[
        tuple[float, float, float, float], tuple[np.ndarray, np.ndarray, np.ndarray]
    ] = {}

    def tridiagonal(
        theta: float, h: float, lo: float, di: float, up: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """``I − θh·L`` with identity rows for the Dirichlet boundaries (cached per step type)."""
        key = (theta * h, lo, di, up)
        if key not in matrices:
            sub = np.full(n_x - 1, -theta * h * lo)
            sub[-1] = 0.0
            sup = np.full(n_x - 1, -theta * h * up)
            sup[0] = 0.0
            main = np.full(n_x, 1.0 - theta * h * di)
            main[0] = main[-1] = 1.0
            matrices[key] = (sub, main, sup)
        return matrices[key]

    for n in range(len(times) - 1, 0, -1):
        t0, t1 = times[n - 1], times[n]
        dt = t1 - t0
        r = -math.log(df[t1] / df[t0]) / dt
        mu = math.log(growth[t1] / growth[t0]) / dt
        b = (mu - 0.5 * dyn.sigma**2) / (2.0 * dx)
        lower, diag, upper = a_half - b, -2.0 * a_half - r, a_half + b
        bc, exercise = bcs[n - 1], exercises[n - 1]

        substeps = [(1.0, 0.5 * dt), (1.0, 0.5 * dt)] if smooth_left > 0 else [(0.5, dt)]
        smooth_left -= 1
        for theta, h in substeps:
            rhs = v.copy()
            explicit = (1.0 - theta) * h
            if explicit:
                rhs[1:-1] = v[1:-1] + explicit * (lower * v[:-2] + diag * v[1:-1] + upper * v[2:])
            rhs[0], rhs[-1] = bc
            sub, main, sup = tridiagonal(theta, h, lower, diag, upper)
            if exercise is None:
                v = _tridiagonal_solve(sub, main, sup, rhs)
                continue
            # Penalty iteration, warm-started from the previous step's exercise region; stops when
            # the exercise region is stable or the update is below penalty_tol.
            for it in range(1, settings.penalty_max_iter + 1):
                pen = settings.penalty * active
                v_next = _tridiagonal_solve(sub, main + pen, sup, rhs + pen * exercise)
                new_active = v_next < exercise
                new_active[[0, -1]] = False
                change = np.max(np.abs(v_next - v)) / max(1.0, float(np.max(np.abs(v_next))))
                v = v_next
                max_iters = max(max_iters, it)
                if np.array_equal(new_active, active) or change < settings.penalty_tol:
                    break
                active = new_active

        if t0 in jumps and t0 > SAME_INSTANT:
            e = jumps[t0]
            v = apply_jump(v, e.cash, e.proportional)
            smooth_left = settings.rannacher_steps  # the jump re-introduces non-smoothness
        if exercise is not None:
            v = np.maximum(v, exercise)
            s_nodes = dyn.spot_affine(t0, cum=True)
            # Interior exercise region only: the Dirichlet rows always sit on the payoff deep in the
            # money, which is not evidence of optimal exercise.
            exercised = (v - exercise <= 1e-9 * k) & (exercise > 0.0)
            exercised[:2] = exercised[-2:] = False
            boundary_t.append(t0)
            if np.any(exercised):
                s_ex = s_nodes[0] * states[exercised] + s_nodes[1]
                boundary_s.append(float(np.max(s_ex) if omega < 0 else np.min(s_ex)))
            else:
                boundary_s.append(math.nan)

    return PdeSolution(
        x=x,
        values=v,
        dynamics=dyn,
        boundary_t=boundary_t[::-1],
        boundary_s=boundary_s[::-1],
        time_nodes=len(times),
        max_penalty_iterations=max_iters,
    )


class CrankNicolsonPde(PricingMethod):
    """Crank–Nicolson PDE in log-state (European, American, digital)."""

    name: ClassVar[str] = "cn_pde"
    label: ClassVar[str] = "Crank–Nicolson PDE"

    def supports(self, instrument: Instrument, model: Model) -> bool:
        """Europeans, Americans and digitals under BSM (both dividend treatments) or Black-76."""
        return isinstance(
            instrument, EuropeanOption | AmericanOption | DigitalOption
        ) and isinstance(model, BlackScholesMerton | Black76)

    def evaluate(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> MethodOutput:
        """Unit price with grid diagnostics."""
        assert isinstance(instrument, EuropeanOption | AmericanOption | DigitalOption)
        if market.time_to(instrument.expiry) <= 0.0:
            return MethodOutput(
                value=self.evaluate_ladder(instrument, market, model, settings, [1.0])[0]
            )
        sol = solve(instrument, market, model, settings.pde, [market.spot])
        return MethodOutput(
            value=sol.value_at_spot([market.spot])[0],
            details={
                "space_nodes": len(sol.x),
                "time_nodes": sol.time_nodes,
                "dx": float(sol.x[1] - sol.x[0]),
                "dividend_treatment": sol.dynamics.kind,
                "max_penalty_iterations": sol.max_penalty_iterations,
            },
        )

    def evaluate_ladder(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
        multipliers: Sequence[float],
    ) -> list[float]:
        """All spots from one solve."""
        assert isinstance(instrument, EuropeanOption | AmericanOption | DigitalOption)
        spots = [market.spot * m for m in multipliers]
        if market.time_to(instrument.expiry) <= 0.0:
            omega, k = instrument.option_type.omega, instrument.strike
            if isinstance(instrument, DigitalOption):
                return [instrument.payout * float(omega * (s - k) > 0.0) for s in spots]
            return [max(omega * (s - k), 0.0) for s in spots]
        return solve(instrument, market, model, settings.pde, spots).value_at_spot(spots)
