"""Analytic pricing with discrete dividends and term structures; cash-or-nothing digitals.

Oracles: QuantLib AnalyticDividendEuropeanEngine (escrowed cash dividends) and
AnalyticEuropeanEngine
with CashOrNothingPayoff; Richardson-extrapolated bumps for every closed-form greek.
"""

import datetime as dt
from dataclasses import replace

import pytest
import QuantLib as ql  # noqa: N813
from hypothesis import assume, given
from hypothesis import strategies as st

from engine.errors import UnsupportedCombinationError
from engine.instruments.vanilla import DigitalOption, EuropeanOption, OptionType
from engine.market.curves import FlatRateCurve, ZeroCurve
from engine.market.dividends import Dividend
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.methods.analytic import AnalyticBlack
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton, DividendTreatment
from engine.pricing import price
from engine.results import Greek, GreekSource
from engine.settings import DigitalSettings, PricingSettings
from tests.greek_checks import assert_greeks_match_bumps

VAL = dt.date(2026, 1, 2)
BSM, B76, METHOD = BlackScholesMerton(), Black76(), AnalyticBlack()
EXACT = PricingSettings(digital=DigitalSettings(spread_width_rel=0.0))


def _mkt(spot=100.0, r=0.03, q=0.0, b=0.0, sigma=0.25, divs=()):
    return MarketData(
        valuation_date=VAL,
        spot=spot,
        discount=FlatRateCurve(r),
        vol=FlatVolSurface(sigma),
        dividend_yield=FlatRateCurve(q),
        borrow=FlatRateCurve(b),
        dividends=tuple(divs),
    )


def _ql_setup(spot, r, q, sigma):
    today = ql.Date(VAL.day, VAL.month, VAL.year)
    ql.Settings.instance().evaluationDate = today
    dc = ql.Actual365Fixed()
    process = ql.GeneralizedBlackScholesProcess(
        ql.QuoteHandle(ql.SimpleQuote(spot)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc, ql.Continuous)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc, ql.Continuous)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), sigma, dc)),
    )
    return today, process


# ------------------------------------------------------------------ escrowed dividends


@given(
    st.floats(0.6, 1.6),
    st.integers(60, 1500),
    st.floats(0.1, 0.6),
    st.floats(0.0, 0.08),
    st.lists(st.tuples(st.integers(1, 1500), st.floats(0.1, 3.0)), min_size=1, max_size=4),
    st.sampled_from([1, -1]),
)
def test_escrowed_matches_quantlib(moneyness, days, sigma, r, divs, omega):
    """QuantLib's escrowed engine discounts dividends at r only, so q = b = 0 here (then both agree
    on the forward); the forward with q, b is covered in test_curves_dividends."""
    spot = 100.0
    divs = [(d, c) for d, c in divs if d <= days]
    assume(divs)
    mkt = _mkt(
        spot=spot, r=r, sigma=sigma, divs=[Dividend(VAL + dt.timedelta(days=d), c) for d, c in divs]
    )
    opt = EuropeanOption(
        option_type=OptionType.CALL if omega > 0 else OptionType.PUT,
        strike=spot * moneyness,
        expiry=VAL + dt.timedelta(days=days),
    )
    today, process = _ql_setup(spot, r, 0.0, sigma)
    schedule = ql.DividendVector([today + d for d, _ in divs], [c for _, c in divs])
    kind = ql.Option.Call if omega > 0 else ql.Option.Put
    q_opt = ql.VanillaOption(
        ql.PlainVanillaPayoff(kind, opt.strike), ql.EuropeanExercise(today + days)
    )
    q_opt.setPricingEngine(ql.AnalyticDividendEuropeanEngine(process, schedule))
    ref = q_opt.NPV()
    assume(ref > 1e-6 * spot)
    res = price(opt, mkt, BSM, METHOD)
    assert res.price == pytest.approx(ref, rel=1e-10)
    assert res.greeks is not None
    assert res.greeks[Greek.DELTA] == pytest.approx(q_opt.delta(), rel=1e-8, abs=1e-10)
    assert res.greeks[Greek.GAMMA] == pytest.approx(q_opt.gamma(), rel=1e-8, abs=1e-12)


def test_escrowed_and_term_structure_greeks_match_bumps():
    divs = (
        Dividend(VAL + dt.timedelta(days=90), 1.5),
        Dividend(VAL + dt.timedelta(days=270), 1.0, 0.01),
    )
    mkt = replace(
        _mkt(q=0.01, b=0.004, divs=divs),
        discount=ZeroCurve((0.25, 1.0, 2.0), (0.02, 0.028, 0.031)),
        dividend_yield=ZeroCurve((0.5, 2.0), (0.01, 0.015)),
    )
    for omega in (OptionType.CALL, OptionType.PUT):
        opt = EuropeanOption(option_type=omega, strike=95.0, expiry=VAL + dt.timedelta(days=400))
        res = price(opt, mkt, BSM, METHOD)
        assert res.greeks is not None
        assert res.greeks.sources[Greek.THETA] is GreekSource.BUMP  # not time-homogeneous
        assert res.greeks.sources[Greek.RHO] is GreekSource.ANALYTIC
        assert_greeks_match_bumps(
            opt, mkt, BSM, METHOD, greeks=[g for g in Greek if g not in (Greek.THETA, Greek.CHARM)]
        )


def test_spot_treatment_needs_pde_with_cash_dividends():
    spot_model = BlackScholesMerton(dividend_treatment=DividendTreatment.SPOT)
    opt = EuropeanOption(
        option_type=OptionType.CALL, strike=100.0, expiry=VAL + dt.timedelta(days=365)
    )
    cash = _mkt(divs=[Dividend(VAL + dt.timedelta(days=100), 1.0)])
    with pytest.raises(UnsupportedCombinationError, match="PDE"):
        price(opt, cash, spot_model, METHOD)
    # Proportional-only dividends keep S lognormal: both treatments agree.
    prop = _mkt(divs=[Dividend(VAL + dt.timedelta(days=100), 0.0, 0.02)])
    assert price(opt, prop, spot_model, METHOD).price == price(opt, prop, BSM, METHOD).price


def test_black76_ignores_dividends():
    opt = EuropeanOption(
        option_type=OptionType.CALL, strike=100.0, expiry=VAL + dt.timedelta(days=365)
    )
    with_divs = _mkt(divs=[Dividend(VAL + dt.timedelta(days=100), 5.0)])
    assert price(opt, with_divs, B76, METHOD).price == price(opt, _mkt(), B76, METHOD).price


# ------------------------------------------------------------------ digitals


digital_params = st.fixed_dictionaries(
    {
        "moneyness": st.floats(0.7, 1.4),
        "days": st.integers(20, 1825),
        "sigma": st.floats(0.08, 0.8),
        "r": st.floats(-0.01, 0.08),
        "q": st.floats(0.0, 0.05),
        "omega": st.sampled_from([1, -1]),
        "payout": st.floats(0.5, 10.0),
    }
)


def _digital(p):
    return DigitalOption(
        option_type=OptionType.CALL if p["omega"] > 0 else OptionType.PUT,
        strike=100.0 * p["moneyness"],
        expiry=VAL + dt.timedelta(days=p["days"]),
        payout=p["payout"],
    )


@given(digital_params)
def test_digital_matches_quantlib(p):
    opt, mkt = _digital(p), _mkt(r=p["r"], q=p["q"], sigma=p["sigma"])
    today, process = _ql_setup(100.0, p["r"], p["q"], p["sigma"])
    kind = ql.Option.Call if p["omega"] > 0 else ql.Option.Put
    q_opt = ql.VanillaOption(
        ql.CashOrNothingPayoff(kind, opt.strike, opt.payout), ql.EuropeanExercise(today + p["days"])
    )
    q_opt.setPricingEngine(ql.AnalyticEuropeanEngine(process))
    assume(q_opt.NPV() > 1e-8 * opt.payout)
    res = price(opt, mkt, BSM, METHOD, EXACT)
    assert res.price == pytest.approx(q_opt.NPV(), rel=1e-10)
    assert res.greeks is not None
    ref = {
        Greek.DELTA: q_opt.delta(),
        Greek.GAMMA: q_opt.gamma(),
        Greek.VEGA: q_opt.vega(),
        Greek.THETA: q_opt.theta(),
        Greek.RHO: q_opt.rho(),
        Greek.PHI: q_opt.dividendRho(),
    }
    for g, v in ref.items():
        assert res.greeks[g] == pytest.approx(v, rel=1e-8, abs=1e-10 * opt.payout), g


@given(digital_params, st.sampled_from([BSM, B76]))
def test_digital_greeks_match_richardson_bumps(p, model):
    assert_greeks_match_bumps(
        _digital(p), _mkt(r=p["r"], q=p["q"], sigma=p["sigma"]), model, METHOD, EXACT
    )


def test_digital_smoothing_uses_call_spread_and_converges():
    opt = DigitalOption(
        option_type=OptionType.CALL, strike=100.0, expiry=VAL + dt.timedelta(days=30), payout=1.0
    )
    mkt = _mkt()
    exact = price(opt, mkt, BSM, METHOD, EXACT)
    smooth = price(opt, mkt, BSM, METHOD)  # default 1% spread
    assert smooth.price == exact.price  # price is never smoothed
    d = smooth.diagnostics.details
    assert d["greeks_from"] == "call-spread replica"
    assert d["spread_width"] == pytest.approx(1.0)
    assert abs(d["smoothing_bias"]) < 5e-3
    assert smooth.greeks is not None
    assert exact.greeks is not None
    # Near-ATM, short-dated: the replica's gamma is bounded below the exact digital's in magnitude.
    assert abs(smooth.greeks[Greek.GAMMA]) < abs(exact.greeks[Greek.GAMMA]) * 1.5
    # As the width → 0 the replica greeks converge to the exact ones.
    tiny = price(
        opt, mkt, BSM, METHOD, PricingSettings(digital=DigitalSettings(spread_width_rel=1e-5))
    )
    assert tiny.greeks is not None
    for g in (Greek.DELTA, Greek.VEGA, Greek.RHO):
        assert tiny.greeks[g] == pytest.approx(exact.greeks[g], rel=1e-4), g
