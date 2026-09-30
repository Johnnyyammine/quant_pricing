import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.errors import MarketDataError
from engine.market.curves import FlatRateCurve
from engine.market.vol import FlatVolSurface
from engine.risk import bumps


def test_forward_is_spot_times_carry(market):
    t = 1.5
    expected = 100.0 * math.exp((0.03 - 0.01 - 0.005) * t)
    assert market.forward(t) == pytest.approx(expected, rel=1e-15)


def test_borrow_enters_forward_not_discounting(market):
    from dataclasses import replace

    wider = replace(market, borrow=FlatRateCurve(0.02))
    assert wider.df(1.0) == market.df(1.0)
    assert wider.forward(1.0) < market.forward(1.0)


@given(st.floats(-0.1, 0.2), st.floats(0.0, 30.0))
def test_flat_curve_df_and_shift(r, t):
    c = FlatRateCurve(r)
    assert c.df(t) == pytest.approx(math.exp(-r * t), rel=1e-15)
    assert c.shifted(1e-4).zero_rate(t) == pytest.approx(r + 1e-4, abs=1e-18)


def test_invalid_market_rejected(market):
    from dataclasses import replace

    with pytest.raises(MarketDataError):
        replace(market, spot=0.0)
    with pytest.raises(MarketDataError):
        FlatVolSurface(-0.1)


def test_roll_valuation_date_reduces_time_to_expiry(market, call):
    rolled = bumps.roll_valuation_date(market, 1)
    assert market.time_to(call.expiry) - rolled.time_to(call.expiry) == pytest.approx(1 / 365)
