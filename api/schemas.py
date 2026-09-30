"""Request/response schemas. Rates, yields and vols are decimals (0.05 = 5%)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.instruments.vanilla import OptionType
from engine.results import Greek, GreekSource
from engine.settings import BumpSettings, ImpliedVolSettings

_BUMP_DEFAULTS = BumpSettings()
_IV_DEFAULTS = ImpliedVolSettings()
MAX_GRID_POINTS = 201


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ------------------------------------------------------------------ requests


class EuropeanOptionIn(_Schema):
    """European call or put."""

    type: Literal["european"] = "european"
    option_type: OptionType
    strike: float = Field(gt=0, description="Strike, in price units")
    expiry: dt.date
    quantity: float = Field(default=1.0, gt=0, description="Units of underlying")
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class MarketIn(_Schema):
    """Flat market: continuously compounded rates, ACT/365F.

    Under Black-76, ``spot`` is the forward (futures) price for the option expiry and the
    dividend yield and borrow spread are ignored.
    """

    valuation_date: dt.date
    spot: float = Field(gt=0)
    rate: float = Field(description="Discount zero rate, continuous, decimal")
    dividend_yield: float = Field(default=0.0, description="Continuous dividend yield, decimal")
    borrow: float = Field(default=0.0, description="Repo/borrow spread, continuous, decimal")
    vol: float = Field(gt=0, le=5, description="Implied volatility, decimal")


class ModelIn(_Schema):
    """Model selection."""

    type: Literal["bsm", "black76"] = "bsm"


class BumpSettingsIn(_Schema):
    """Bump sizes for bump-and-revalue greeks."""

    spot_rel: float = Field(default=_BUMP_DEFAULTS.spot_rel, gt=0, le=0.1)
    vol_abs: float = Field(default=_BUMP_DEFAULTS.vol_abs, gt=0, le=0.05)
    rate_abs: float = Field(default=_BUMP_DEFAULTS.rate_abs, gt=0, le=0.01)
    time_days: int = Field(default=_BUMP_DEFAULTS.time_days, ge=1, le=30)


class ImpliedVolSettingsIn(_Schema):
    """Implied-vol solver settings."""

    max_iterations: int = Field(default=_IV_DEFAULTS.max_iterations, ge=1, le=10)


class SettingsIn(_Schema):
    """Numerical settings."""

    bumps: BumpSettingsIn = BumpSettingsIn()
    implied_vol: ImpliedVolSettingsIn = ImpliedVolSettingsIn()
    force_bump_greeks: bool = Field(
        default=False, description="Bump-and-revalue every greek, even where closed forms exist"
    )


class PriceRequest(_Schema):
    """Price one instrument."""

    instrument: EuropeanOptionIn
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

    instrument: EuropeanOptionIn
    market: MarketIn
    model: ModelIn = ModelIn()
    target_price: float = Field(gt=0, description="Unit price, currency")
    settings: SettingsIn = SettingsIn()


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
    runtime_ms: float = Field(description="Engine wall-clock time for price and greeks, ms")
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
    forward: float
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


class MethodOut(_Schema):
    """A registered pricing method."""

    name: str
    label: str


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
