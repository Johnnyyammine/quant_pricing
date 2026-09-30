"""Request/response schemas. Rates, yields and vols are decimals (0.05 = 5%)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.instruments.vanilla import OptionType
from engine.results import Greek, GreekSource
from engine.settings import BumpSettings

_BUMP_DEFAULTS = BumpSettings()


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
    """Flat market: continuously compounded rates, ACT/365F."""

    valuation_date: dt.date
    spot: float = Field(gt=0)
    rate: float = Field(description="Discount zero rate, continuous, decimal")
    dividend_yield: float = Field(default=0.0, description="Continuous dividend yield, decimal")
    borrow: float = Field(default=0.0, description="Repo/borrow spread, continuous, decimal")
    vol: float = Field(gt=0, le=5, description="Implied volatility, decimal")


class ModelIn(_Schema):
    """Model selection."""

    type: Literal["bsm"] = "bsm"


class BumpSettingsIn(_Schema):
    """Bump sizes for bump-and-revalue greeks."""

    spot_rel: float = Field(default=_BUMP_DEFAULTS.spot_rel, gt=0, le=0.1)
    vol_abs: float = Field(default=_BUMP_DEFAULTS.vol_abs, gt=0, le=0.05)
    rate_abs: float = Field(default=_BUMP_DEFAULTS.rate_abs, gt=0, le=0.01)
    time_days: int = Field(default=_BUMP_DEFAULTS.time_days, ge=1, le=30)


class SettingsIn(_Schema):
    """Numerical settings."""

    bumps: BumpSettingsIn = BumpSettingsIn()


class PriceRequest(_Schema):
    """Price one instrument."""

    instrument: EuropeanOptionIn
    market: MarketIn
    model: ModelIn = ModelIn()
    method: str = "forward_intrinsic"
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
    forward: float
    discount_factor: float
    time_to_expiry: float = Field(description="ACT/365F year fraction")
    greeks: GreeksOut
    diagnostics: DiagnosticsOut


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
