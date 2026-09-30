"""Request/response schemas. Rates, yields and vols are decimals (0.05 = 5%)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.instruments.vanilla import OptionType
from engine.models.black_scholes import DividendTreatment
from engine.results import Greek, GreekSource
from engine.settings import (
    BumpSettings,
    DigitalSettings,
    ImpliedVolSettings,
    PdeSettings,
    ScenarioSettings,
    TreeSettings,
)

_BUMP = BumpSettings()
_IV = ImpliedVolSettings()
_TREE = TreeSettings()
_PDE = PdeSettings()
_DIGITAL = DigitalSettings()
_SCENARIO = ScenarioSettings()
MAX_GRID_POINTS = 201


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ------------------------------------------------------------------ instruments


class _OptionFields(_Schema):
    option_type: OptionType
    strike: float = Field(gt=0, description="Strike, in price units")
    expiry: dt.date
    quantity: float = Field(default=1.0, gt=0, description="Units of underlying")
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class EuropeanOptionIn(_OptionFields):
    """European call or put."""

    type: Literal["european"] = "european"


class AmericanOptionIn(_OptionFields):
    """American call or put (exercisable any day up to expiry)."""

    type: Literal["american"]


class DigitalOptionIn(_OptionFields):
    """Cash-or-nothing digital paying ``payout`` per unit if in the money at expiry."""

    type: Literal["digital"]
    payout: float = Field(default=1.0, gt=0, description="Cash per unit, currency")


InstrumentIn = Annotated[
    EuropeanOptionIn | AmericanOptionIn | DigitalOptionIn, Field(discriminator="type")
]


# ------------------------------------------------------------------ market


class PillarIn(_Schema):
    """Continuously compounded zero rate to ``date`` (ACT/365F from the valuation date)."""

    date: dt.date
    rate: float


class CurveIn(_Schema):
    """Zero curve with log-linear discount factors between pillars.

    Flat before the first pillar; the last forward is extended beyond the last.
    """

    pillars: list[PillarIn] = Field(min_length=1)


RateIn = float | CurveIn


class DividendIn(_Schema):
    """Discrete dividend: ``S → S·(1 − proportional) − cash`` at the ex-date open."""

    ex_date: dt.date
    cash: float = Field(default=0.0, ge=0, description="Cash per share, currency")
    proportional: float = Field(default=0.0, ge=0, lt=1, description="Fraction of spot")


class MarketIn(_Schema):
    """Market snapshot. Each rate is a flat decimal or a pillar curve.

    Under Black-76, ``spot`` is the forward (futures) price for the option expiry and the
    dividend yield, borrow and discrete dividends are ignored.
    """

    valuation_date: dt.date
    spot: float = Field(gt=0)
    rate: RateIn = Field(description="Discount zero rate(s), continuous")
    dividend_yield: RateIn = Field(default=0.0, description="Continuous dividend yield(s)")
    borrow: RateIn = Field(default=0.0, description="Repo/borrow spread(s), continuous")
    dividends: list[DividendIn] = Field(default=[], max_length=100)
    vol: float = Field(gt=0, le=5, description="Implied volatility, decimal")


class ModelIn(_Schema):
    """Model selection."""

    type: Literal["bsm", "black76"] = "bsm"
    dividend_treatment: DividendTreatment = Field(
        default=DividendTreatment.ESCROWED,
        description="BSM cash dividends: escrowed (lognormal S − PV) or spot jumps (PDE only)",
    )


# ------------------------------------------------------------------ settings


class BumpSettingsIn(_Schema):
    """Bump sizes for bump-and-revalue greeks."""

    spot_rel: float = Field(default=_BUMP.spot_rel, gt=0, le=0.1)
    vol_abs: float = Field(default=_BUMP.vol_abs, gt=0, le=0.05)
    rate_abs: float = Field(default=_BUMP.rate_abs, gt=0, le=0.01)
    time_days: int = Field(default=_BUMP.time_days, ge=1, le=30)


class ImpliedVolSettingsIn(_Schema):
    """Implied-vol solver settings."""

    max_iterations: int = Field(default=_IV.max_iterations, ge=1, le=10)


class TreeSettingsIn(_Schema):
    """Leisen–Reimer tree."""

    steps: int = Field(default=_TREE.steps, ge=3, le=20001, description="Odd")


class PdeSettingsIn(_Schema):
    """Crank–Nicolson PDE."""

    space_nodes: int = Field(default=_PDE.space_nodes, ge=20, le=20000)
    time_steps: int = Field(default=_PDE.time_steps, ge=4, le=20000)
    n_std: float = Field(default=_PDE.n_std, gt=0, le=20)
    rannacher_steps: int = Field(default=_PDE.rannacher_steps, ge=0, le=100)
    penalty: float = Field(default=_PDE.penalty, gt=0)
    penalty_tol: float = Field(default=_PDE.penalty_tol, gt=0)
    penalty_max_iter: int = Field(default=_PDE.penalty_max_iter, ge=1, le=1000)


class DigitalSettingsIn(_Schema):
    """Digital greek smoothing."""

    spread_width_rel: float = Field(default=_DIGITAL.spread_width_rel, ge=0, lt=0.5)


class ScenarioSettingsIn(_Schema):
    """Numerical-method resolution for charts."""

    tree_steps: int = Field(default=_SCENARIO.tree_steps, ge=3, le=20001)
    pde_space_nodes: int = Field(default=_SCENARIO.pde_space_nodes, ge=20, le=20000)
    pde_time_steps: int = Field(default=_SCENARIO.pde_time_steps, ge=4, le=20000)


class SettingsIn(_Schema):
    """Numerical settings."""

    bumps: BumpSettingsIn = BumpSettingsIn()
    implied_vol: ImpliedVolSettingsIn = ImpliedVolSettingsIn()
    force_bump_greeks: bool = Field(
        default=False, description="Bump-and-revalue every greek, even where closed forms exist"
    )
    tree: TreeSettingsIn = TreeSettingsIn()
    pde: PdeSettingsIn = PdeSettingsIn()
    digital: DigitalSettingsIn = DigitalSettingsIn()
    scenario: ScenarioSettingsIn = ScenarioSettingsIn()


# ------------------------------------------------------------------ requests


class PriceRequest(_Schema):
    """Price one instrument."""

    instrument: InstrumentIn
    market: MarketIn
    model: ModelIn = ModelIn()
    method: str = "analytic"
    settings: SettingsIn = SettingsIn()


class ProfileRequest(_Schema):
    """Price and greeks along spot (at several horizons) or along time (at several spot shifts)."""

    pricing: PriceRequest
    axis: Literal["spot", "time"]
    points: int = Field(default=81, ge=2, le=MAX_GRID_POINTS)
    spot_range_pct: float = Field(default=30.0, gt=0, lt=100, description="Spot axis: ±range, %")
    horizons_days: list[int] = Field(
        default=[0], min_length=1, max_length=6, description="Spot axis: valuation-date rolls"
    )
    spot_shifts_pct: list[float] = Field(
        default=[0.0], min_length=1, max_length=6, description="Time axis: spot shifts, %"
    )
    greeks: list[Greek] | None = Field(
        default=None, description="Greeks to compute (default all; [] for value only)"
    )


class HeatmapRequest(_Schema):
    """Full-revaluation value grid over spot and vol shocks."""

    pricing: PriceRequest
    spot_range_pct: float = Field(default=20.0, gt=0, lt=100)
    spot_steps: int = Field(default=21, ge=3, le=101)
    vol_range_pts: float = Field(default=10.0, gt=0, le=100)
    vol_steps: int = Field(default=21, ge=3, le=101)
    horizon_days: int = Field(default=0, ge=0)


class ImpliedVolRequest(_Schema):
    """Implied vol from a unit price. ``market.vol`` is ignored."""

    instrument: InstrumentIn
    market: MarketIn
    model: ModelIn = ModelIn()
    target_price: float = Field(gt=0, description="Unit price, currency")
    settings: SettingsIn = SettingsIn()


class CompareRequest(_Schema):
    """The same product under every registered method."""

    pricing: PriceRequest
    convergence: bool = True


# ------------------------------------------------------------------ responses


class GreekOut(_Schema):
    """One greek in desk units."""

    key: Greek
    value: float
    unit: str
    source: GreekSource


class GreeksOut(_Schema):
    """Greeks in both display modes so the UI can toggle without refetching."""

    pure: list[GreekOut]
    cash: list[GreekOut]


class DiagnosticsOut(_Schema):
    """Diagnostics of a pricing run."""

    method: str
    method_label: str
    model: str
    runtime_ms: float = Field(description="Engine CPU time for price and greeks, ms")
    revaluations: int
    settings: SettingsIn
    details: dict[str, float | int | str]
    warnings: list[str]


class PriceResponse(_Schema):
    """Price, market-derived quantities, greeks and diagnostics."""

    currency: str
    price: float = Field(description="Unit price, currency")
    position_value: float = Field(description="quantity × unit price, currency")
    pct_notional: float = Field(description="100 × unit price / spot, %")
    notional: float = Field(description="quantity × spot, currency")
    forward: float = Field(description="Model forward to expiry, including discrete dividends")
    discount_factor: float
    time_to_expiry: float = Field(description="ACT/365F year fraction")
    greeks: GreeksOut
    diagnostics: DiagnosticsOut


class ProfileSeries(_Schema):
    """One line family of a profile: value and greeks along the x axis."""

    label: str
    horizon_days: int
    spot_shift_pct: float
    position_value: list[float]
    greeks: dict[Literal["pure", "cash"], dict[Greek, list[float]]]


class ProfileResponse(_Schema):
    """Profiles along spot or time."""

    axis: Literal["spot", "time"]
    x: list[float] = Field(description="Spot level, or days to expiry")
    currency: str
    notional: float = Field(description="quantity × current spot, currency")
    strike: float
    spot: float
    payoff: list[float] | None = Field(description="Spot axis: position payoff at expiry")
    units: dict[Literal["pure", "cash"], dict[Greek, str]]
    series: list[ProfileSeries]


class HeatmapResponse(_Schema):
    """Position values on a vol × spot grid (rows: vol shifts). ``null`` = shock out of domain."""

    currency: str
    spot_shifts_pct: list[float]
    vol_shifts_pts: list[float]
    horizon_days: int
    base_value: float = Field(description="Current position value, currency")
    notional: float = Field(description="quantity × current spot, currency")
    values: list[list[float | None]]


class ImpliedVolResponse(_Schema):
    """Implied vol and the quantities it was solved from."""

    implied_vol: float = Field(description="Decimal")
    forward: float
    discount_factor: float
    time_to_expiry: float


class ConvergencePointOut(_Schema):
    """Price at one resolution."""

    resolution: int
    price: float = Field(description="Unit price, currency")
    runtime_ms: float


class MethodComparison(_Schema):
    """One method's result, or why it cannot price this product."""

    method: str
    label: str
    supported: bool
    error: str | None = None
    price: float | None = Field(default=None, description="Unit price, currency")
    runtime_ms: float | None = None
    greeks: list[GreekOut] | None = Field(default=None, description="Cash greeks")
    resolution: int | None = Field(default=None, description="Tree steps or PDE space nodes")
    convergence: list[ConvergencePointOut] = []


class ExerciseBoundary(_Schema):
    """PDE early-exercise boundary: exercise when spot is beyond ``spot`` at ``days``."""

    days: list[float] = Field(description="Days from the valuation date")
    spot: list[float | None] = Field(description="Critical spot S*; null where not exercised")


class CompareResponse(_Schema):
    """Methods side by side."""

    currency: str
    methods: list[MethodComparison]
    european_price: float | None = Field(
        default=None, description="Same contract with European exercise (unit, closed form)"
    )
    boundary: ExerciseBoundary | None = None


class MethodOut(_Schema):
    """A registered pricing method and the products it supports."""

    name: str
    label: str
    instruments: list[Literal["european", "american", "digital"]]


class MetaResponse(_Schema):
    """Static metadata for the UI."""

    version: str
    methods: list[MethodOut]


class HealthResponse(_Schema):
    """Liveness probe."""

    status: Literal["ok"]
    version: str


class ErrorResponse(_Schema):
    """Engine error surfaced to the client."""

    detail: str
