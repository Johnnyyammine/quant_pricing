import datetime as dt
import os

import pytest
from hypothesis import HealthCheck, settings

from engine.instruments.vanilla import EuropeanOption, OptionType
from engine.market.curves import FlatRateCurve
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface

settings.register_profile("ci", max_examples=500, deadline=None, derandomize=True)
settings.register_profile(
    "dev", max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))

VAL_DATE = dt.date(2026, 1, 2)


@pytest.fixture
def market() -> MarketData:
    return MarketData(
        valuation_date=VAL_DATE,
        spot=100.0,
        discount=FlatRateCurve(0.03),
        vol=FlatVolSurface(0.20),
        dividend_yield=FlatRateCurve(0.01),
        borrow=FlatRateCurve(0.005),
    )


@pytest.fixture
def call() -> EuropeanOption:
    return EuropeanOption(
        option_type=OptionType.CALL, strike=95.0, expiry=VAL_DATE + dt.timedelta(days=365)
    )
