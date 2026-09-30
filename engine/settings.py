"""Numerical settings: every bump size, tolerance and grid size lives here.

No numerical constant that affects a reported number may be hard-coded elsewhere in the engine.
The full settings object is echoed in every :class:`~engine.results.PricingResult` and shown in
the UI's Diagnostics tab.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class BumpSettings:
    """Finite-difference bump sizes for bump-and-revalue greeks.

    All greeks use central differences, error ``O(h²)``.

    Attributes:
        spot_rel: Relative spot bump ``h_S / S``.
        vol_abs: Absolute bump of the vol surface, in vol units (``0.001`` = 0.1 vol point).
        rate_abs: Absolute parallel bump of zero rates (``1e-4`` = 1 bp).
        time_days: Valuation-date roll in calendar days for theta and charm.

    """

    spot_rel: float = 1e-3
    vol_abs: float = 1e-3
    rate_abs: float = 1e-4
    time_days: int = 1

    def __post_init__(self) -> None:
        if not (self.spot_rel > 0 and self.vol_abs > 0 and self.rate_abs > 0):
            raise ValueError("bump sizes must be strictly positive")
        if self.time_days < 1:
            raise ValueError("time_days must be at least 1")


@dataclass(frozen=True, slots=True)
class ImpliedVolSettings:
    """Implied-volatility solver settings (Jäckel, "Let's Be Rational").

    Attributes:
        max_iterations: Householder(3) iterations after the rational initial guess. Two reach
            machine precision over the whole domain (Jäckel 2015, §5).

    """

    max_iterations: int = 2

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")


@dataclass(frozen=True, slots=True)
class TreeSettings:
    """Leisen–Reimer binomial tree.

    Attributes:
        steps: Number of time steps (odd, as Leisen–Reimer requires).

    """

    steps: int = 401

    def __post_init__(self) -> None:
        if self.steps < 3 or self.steps % 2 == 0:
            raise ValueError("tree steps must be odd and at least 3")


@dataclass(frozen=True, slots=True)
class PdeSettings:
    """Crank–Nicolson finite differences in ``x = ln S``.

    Attributes:
        space_nodes: Number of grid nodes in ``x``.
        time_steps: Number of time steps to expiry (dividend dates are inserted as extra nodes).
        n_std: Grid half-width in standard deviations ``σ√T`` around ``ln K``.
        rannacher_steps: Initial Crank–Nicolson steps replaced by two implicit-Euler half steps
            each (Rannacher smoothing of the payoff kink).
        penalty: Penalty parameter ``1/ε`` enforcing ``V ≥ payoff`` for early exercise.
        penalty_tol: Relative convergence tolerance of the penalty iteration.
        penalty_max_iter: Maximum penalty iterations per time step.

    """

    space_nodes: int = 800
    time_steps: int = 200
    n_std: float = 5.0
    rannacher_steps: int = 2
    penalty: float = 1e8
    penalty_tol: float = 1e-12
    penalty_max_iter: int = 25

    def __post_init__(self) -> None:
        if self.space_nodes < 20 or self.time_steps < 4:
            raise ValueError("PDE needs at least 20 space nodes and 4 time steps")
        if not (self.n_std > 0 and self.penalty > 0 and self.penalty_tol > 0):
            raise ValueError("PDE n_std, penalty and tolerance must be positive")
        if not 0 <= self.rannacher_steps < self.time_steps:
            raise ValueError("rannacher_steps must be in [0, time_steps)")


@dataclass(frozen=True, slots=True)
class DigitalSettings:
    """Risk smoothing of digital payoffs.

    Attributes:
        spread_width_rel: Width of the replicating call spread as a fraction of strike. Greeks of a
            digital are the greeks of ``payout/w·[C(K − w/2) − C(K + w/2)]`` (puts analogously);
            ``0`` gives the exact (unsmoothed) digital greeks. The price is always exact.

    """

    spread_width_rel: float = 0.01

    def __post_init__(self) -> None:
        if not 0.0 <= self.spread_width_rel < 0.5:
            raise ValueError("spread_width_rel must be in [0, 0.5)")


@dataclass(frozen=True, slots=True)
class ScenarioSettings:
    """Resolution of numerical methods in profiles and heatmaps (headline prices use full settings).

    Attributes:
        tree_steps: Tree steps for chart revaluations (odd).
        pde_space_nodes: PDE space nodes for chart revaluations.
        pde_time_steps: PDE time steps for chart revaluations.

    """

    tree_steps: int = 101
    pde_space_nodes: int = 200
    pde_time_steps: int = 100


@dataclass(frozen=True, slots=True)
class PricingSettings:
    """Top-level numerical settings passed to :func:`engine.pricing.price`.

    Attributes:
        bumps: Bump sizes for bump-and-revalue greeks.
        implied_vol: Implied-volatility solver settings.
        force_bump_greeks: Compute every greek by bump-and-revalue even where closed forms exist
            (used to cross-check analytic greeks).
        tree: Binomial tree settings.
        pde: Finite-difference settings.
        digital: Digital greek smoothing.
        scenario: Numerical-method resolution for charts.

    """

    bumps: BumpSettings = field(default_factory=BumpSettings)
    implied_vol: ImpliedVolSettings = field(default_factory=ImpliedVolSettings)
    force_bump_greeks: bool = False
    tree: TreeSettings = field(default_factory=TreeSettings)
    pde: PdeSettings = field(default_factory=PdeSettings)
    digital: DigitalSettings = field(default_factory=DigitalSettings)
    scenario: ScenarioSettings = field(default_factory=ScenarioSettings)

    def for_scenarios(self) -> PricingSettings:
        """Settings for chart revaluations: numerical resolution from :class:`ScenarioSettings`."""
        sc = self.scenario
        return replace(
            self,
            tree=TreeSettings(steps=sc.tree_steps),
            pde=replace(self.pde, space_nodes=sc.pde_space_nodes, time_steps=sc.pde_time_steps),
        )
