"""Closed-form BSM / Black-76: references, QuantLib oracle, parity, FD greeks, no-arbitrage."""

import datetime as dt
import math
import sys
from dataclasses import dataclass, replace

import pytest
import QuantLib as ql  # noqa: N813
from hypothesis import assume, given
from hypothesis import strategies as st

from engine.instruments.vanilla import EuropeanOption, OptionType
from engine.market.curves import FlatRateCurve
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.methods.analytic import AnalyticBlack
from engine.methods.black_formulas import BlackInputs, CarryModel, black_greeks, black_price
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton
from engine.pricing import price
from engine.results import Greek, GreekSource
from engine.settings import BumpSettings, PricingSettings

VAL = dt.date(2026, 1, 2)
EPS = sys.float_info.epsilon
BSM, B76, METHOD = BlackScholesMerton(), Black76(), AnalyticBlack()


def gbs(x, k, t, sigma, r, carry, omega, model=CarryModel.SPOT):
    p = BlackInputs(x, k, t, sigma, r, carry, omega, model)
    v = black_price(p)
    return v, black_greeks(p, v)


# ------------------------------------------------------------------ published reference values
# E. G. Haug, The Complete Guide to Option Pricing Formulas, 2nd ed. (numbers as printed, 4 dp);
# J. C. Hull, Options, Futures, and Other Derivatives (2 dp). In Haug's notation b = cost of carry.


def test_haug_generalised_bs_call():  # Haug 1.1.1: S=60, X=65, T=0.25, r=8%, b=8%, σ=30%
    v, _ = gbs(60, 65, 0.25, 0.30, 0.08, 0.08, 1)
    assert v == pytest.approx(2.1334, abs=5e-5)


def test_haug_merton73_put():  # Haug 1.1.2: S=100, X=95, T=0.5, r=10%, q=5%, σ=20%
    v, _ = gbs(100, 95, 0.5, 0.20, 0.10, 0.10 - 0.05, -1)
    assert v == pytest.approx(2.4648, abs=5e-5)


def test_haug_black76():  # Haug 1.1.3: F=19, X=19, T=0.75, r=10%, σ=28% → call = put = 1.7011
    for omega in (1, -1):
        v, _ = gbs(19, 19, 0.75, 0.28, 0.10, 0.0, omega, CarryModel.FORWARD)
        assert v == pytest.approx(1.7011, abs=5e-5)


def test_hull_example():  # Hull: S=42, K=40, r=10%, σ=20%, T=0.5 → c = 4.76, p = 0.81
    assert gbs(42, 40, 0.5, 0.2, 0.1, 0.1, 1)[0] == pytest.approx(4.76, abs=5e-3)
    assert gbs(42, 40, 0.5, 0.2, 0.1, 0.1, -1)[0] == pytest.approx(0.81, abs=5e-3)


def test_haug_delta():  # Haug 2.1.1: S=105, X=100, T=0.5, r=10%, b=0, σ=36%
    assert gbs(105, 100, 0.5, 0.36, 0.1, 0.0, 1)[1][Greek.DELTA] == pytest.approx(0.5946, abs=5e-5)
    assert gbs(105, 100, 0.5, 0.36, 0.1, 0.0, -1)[1][Greek.DELTA] == pytest.approx(
        -0.3566, abs=5e-5
    )


def test_haug_gamma():  # Haug 2.1.4: S=55, X=60, T=0.75, r=10%, b=10%, σ=30%
    assert gbs(55, 60, 0.75, 0.30, 0.10, 0.10, 1)[1][Greek.GAMMA] == pytest.approx(0.0278, abs=5e-5)


def test_haug_vega():  # Haug 2.1.5: S=55, X=60, T=0.75, r=10%, b=10%, σ=30% (QuantLib agrees)
    v = gbs(55, 60, 0.75, 0.30, 0.10, 0.10, 1)[1][Greek.VEGA]
    assert v == pytest.approx(18.9358, abs=5e-5)


# ------------------------------------------------------------------ QuantLib oracle


def _market(spot, r, q, b, sigma):
    return MarketData(
        valuation_date=VAL,
        spot=spot,
        discount=FlatRateCurve(r),
        vol=FlatVolSurface(sigma),
        dividend_yield=FlatRateCurve(q),
        borrow=FlatRateCurve(b),
    )


def _ql(spot, strike, days, sigma, r, q_total, omega):
    today = ql.Date(VAL.day, VAL.month, VAL.year)
    ql.Settings.instance().evaluationDate = today
    dc = ql.Actual365Fixed()
    process = ql.GeneralizedBlackScholesProcess(
        ql.QuoteHandle(ql.SimpleQuote(spot)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q_total, dc, ql.Continuous)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc, ql.Continuous)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), sigma, dc)),
    )
    kind = ql.Option.Call if omega > 0 else ql.Option.Put
    opt = ql.EuropeanOption(ql.PlainVanillaPayoff(kind, strike), ql.EuropeanExercise(today + days))
    opt.setPricingEngine(ql.AnalyticEuropeanEngine(process))
    return {
        "price": opt.NPV(),
        Greek.DELTA: opt.delta(),
        Greek.GAMMA: opt.gamma(),
        Greek.VEGA: opt.vega(),
        Greek.THETA: opt.theta(),
        Greek.RHO: opt.rho(),
        Greek.PHI: opt.dividendRho(),
    }


params = st.fixed_dictionaries(
    {
        "spot": st.floats(1.0, 1000.0),
        "moneyness": st.floats(0.5, 2.0),
        "days": st.integers(1, 3650),
        "sigma": st.floats(0.02, 1.5),
        "r": st.floats(-0.02, 0.12),
        "q": st.floats(0.0, 0.08),
        "b": st.floats(0.0, 0.03),
        "omega": st.sampled_from([1, -1]),
    }
)


def _option(p):
    return EuropeanOption(
        option_type=OptionType.CALL if p["omega"] > 0 else OptionType.PUT,
        strike=p["spot"] * p["moneyness"],
        expiry=VAL + dt.timedelta(days=p["days"]),
    )


@given(params)
def test_bsm_matches_quantlib(p):
    opt, mkt = _option(p), _market(p["spot"], p["r"], p["q"], p["b"], p["sigma"])
    res = price(opt, mkt, BSM, METHOD)
    ref = _ql(p["spot"], opt.strike, p["days"], p["sigma"], p["r"], p["q"] + p["b"], p["omega"])
    assume(ref["price"] > 1e-8 * p["spot"])  # QuantLib's direct formula loses digits below this
    scale = p["spot"]
    assert res.price == pytest.approx(ref["price"], rel=1e-10, abs=1e-13 * scale)
    assert res.greeks is not None
    for g in (Greek.DELTA, Greek.GAMMA, Greek.VEGA, Greek.THETA, Greek.RHO, Greek.PHI):
        assert res.greeks[g] == pytest.approx(ref[g], rel=1e-9, abs=1e-12 * scale), g
        assert res.greeks.sources[g] is GreekSource.ANALYTIC


@given(params)
def test_black76_matches_quantlib_zero_carry(p):
    """Black-76 equals generalised BS with q = r on the forward (b = 0)."""
    opt, mkt = _option(p), _market(p["spot"], p["r"], 0.0, 0.0, p["sigma"])
    res = price(opt, mkt, B76, METHOD)
    ref = _ql(p["spot"], opt.strike, p["days"], p["sigma"], p["r"], p["r"], p["omega"])
    assume(ref["price"] > 1e-8 * p["spot"])
    scale = p["spot"]
    assert res.price == pytest.approx(ref["price"], rel=1e-10, abs=1e-13 * scale)
    assert res.greeks is not None
    for g in (Greek.DELTA, Greek.GAMMA, Greek.VEGA, Greek.THETA):
        assert res.greeks[g] == pytest.approx(ref[g], rel=1e-9, abs=1e-12 * scale), g
    t = mkt.time_to(opt.expiry)
    assert res.greeks[Greek.RHO] == pytest.approx(-t * res.price, rel=1e-12)
    assert res.greeks[Greek.PHI] == 0.0


# ------------------------------------------------------------------ parity and no-arbitrage


@given(params)
def test_put_call_parity(p):
    mkt = _market(p["spot"], p["r"], p["q"], p["b"], p["sigma"])
    call = replace(_option(p), option_type=OptionType.CALL)
    put = replace(call, option_type=OptionType.PUT)
    c = price(call, mkt, BSM, METHOD, greeks=()).price
    pv = price(put, mkt, BSM, METHOD, greeks=()).price
    t = mkt.time_to(call.expiry)
    f, d = mkt.forward(t), mkt.df(t)
    assert c - pv == pytest.approx(d * (f - call.strike), abs=1e-12 * (f + call.strike))


@given(params)
def test_no_arbitrage_bounds(p):
    mkt = _market(p["spot"], p["r"], p["q"], p["b"], p["sigma"])
    opt = _option(p)
    v = price(opt, mkt, BSM, METHOD, greeks=()).price
    t = mkt.time_to(opt.expiry)
    f, d, k = mkt.forward(t), mkt.df(t), opt.strike
    tol = 1e-12 * (f + k)
    if p["omega"] > 0:
        assert max(d * (f - k), 0.0) - tol <= v <= d * f + tol
    else:
        assert max(d * (k - f), 0.0) - tol <= v <= d * k + tol


@given(params, st.floats(1.001, 1.5))
def test_monotone_in_vol_and_strike_convex_in_strike(p, bump):
    mkt = _market(p["spot"], p["r"], p["q"], p["b"], p["sigma"])
    opt = _option(p)

    def v(o=opt, m=mkt):
        return price(o, m, BSM, METHOD, greeks=()).price

    tol = 1e-13 * p["spot"]
    assert v(m=replace(mkt, vol=FlatVolSurface(p["sigma"] * bump))) >= v() - tol
    k = opt.strike
    lo, mid, hi = (v(o=replace(opt, strike=k * f)) for f in (1 / bump, 1.0, bump))
    if p["omega"] > 0:
        assert lo >= mid - tol
        assert mid >= hi - tol
    else:
        assert lo <= mid + tol
        assert mid <= hi + tol
    # Butterfly on a non-uniform strike grid: weights keep the portfolio's value non-negative.
    k_lo, k_hi = k / bump, k * bump
    w_lo, w_hi = (k_hi - k) / (k_hi - k_lo), (k - k_lo) / (k_hi - k_lo)
    assert w_lo * lo + w_hi * hi - mid >= -tol


@given(params, st.floats(1.001, 2.0))
def test_monotone_in_total_variance_at_fixed_forward(p, factor):
    x, t = p["spot"], p["days"] / 365
    k = x * p["moneyness"]
    v1, _ = gbs(x, k, t, p["sigma"], p["r"], 0.0, p["omega"], CarryModel.FORWARD)
    sigma2 = p["sigma"] * math.sqrt(factor)
    v2, _ = gbs(x, k, t, sigma2, p["r"], 0.0, p["omega"], CarryModel.FORWARD)
    assert v2 >= v1 - 1e-13 * x


# ------------------------------------------------------------------ analytic vs finite differences


@given(
    st.fixed_dictionaries(
        {
            "spot": st.floats(10.0, 500.0),
            "moneyness": st.floats(0.7, 1.4),
            "days": st.integers(30, 1825),
            "sigma": st.floats(0.08, 0.8),
            "r": st.floats(-0.01, 0.08),
            "q": st.floats(0.0, 0.05),
            "b": st.floats(0.0, 0.02),
            "omega": st.sampled_from([1, -1]),
        }
    ),
    st.sampled_from([BSM, B76]),
)
def test_analytic_greeks_match_richardson_bumps(p, model):
    """Bump greeks at h and h/2, Richardson-extrapolated to O(h⁴), against closed forms."""
    opt, mkt = _option(p), _market(p["spot"], p["r"], p["q"], p["b"], p["sigma"])
    analytic = price(opt, mkt, model, METHOD).greeks
    h = BumpSettings(spot_rel=2e-3, vol_abs=2e-3, rate_abs=2e-4, time_days=1)
    h2 = BumpSettings(spot_rel=1e-3, vol_abs=1e-3, rate_abs=1e-4, time_days=1)
    g1 = price(opt, mkt, model, METHOD, PricingSettings(bumps=h, force_bump_greeks=True)).greeks
    g2 = price(opt, mkt, model, METHOD, PricingSettings(bumps=h2, force_bump_greeks=True)).greeks
    assert analytic is not None
    assert g1 is not None
    assert g2 is not None
    # Round-off floor of each stencil at the smaller bumps: ε·(|V| + S) / (stencil denominator).
    v = price(opt, mkt, model, METHOD, greeks=()).price
    hs, hv, hr = h2.spot_rel * p["spot"], h2.vol_abs, h2.rate_abs
    denominator = {
        Greek.DELTA: hs,
        Greek.GAMMA: hs * hs,
        Greek.VEGA: hv,
        Greek.VOLGA: hv * hv,
        Greek.VANNA: hs * hv,
        Greek.RHO: hr,
        Greek.PHI: hr,
    }
    for g, den in denominator.items():
        richardson = (4 * g2[g] - g1[g]) / 3
        # Richardson leaves an O(h⁴) residual, which must be small next to the O(h²) correction
        # it removed (|g1 − g2|); a formula error would not shrink with h. The 1e-6 relative floor
        # covers points where the h² coefficient vanishes by coincidence but h⁴ does not.
        rounding = 256 * EPS * (abs(v) + p["spot"]) / den
        tol = 1e-6 * abs(analytic[g]) + 0.05 * abs(g1[g] - g2[g]) + rounding
        assert abs(richardson - analytic[g]) <= tol, g
    # Time: Richardson over 1-day and 2-day rolls, with the same self-calibrating tolerance. The
    # spot bump inside charm is reduced so its own O(h_S²) error does not dominate.
    fine_spot = 1e-4
    t1, t2 = (
        price(
            opt,
            mkt,
            model,
            METHOD,
            PricingSettings(
                bumps=BumpSettings(spot_rel=fine_spot, time_days=days), force_bump_greeks=True
            ),
        ).greeks
        for days in (1, 2)
    )
    assert t1 is not None
    assert t2 is not None
    h_t = 1 / 365
    for g, den in ((Greek.THETA, h_t), (Greek.CHARM, h_t * fine_spot * p["spot"])):
        richardson = (4 * t1[g] - t2[g]) / 3
        rounding = 256 * EPS * (abs(v) + p["spot"]) / den
        tol = 1e-6 * abs(analytic[g]) + 0.05 * abs(t1[g] - t2[g]) + rounding
        assert abs(richardson - analytic[g]) <= tol, g


# ------------------------------------------------------------------ edge cases and wiring


def test_expiry_day_is_intrinsic(market, call):
    today = replace(call, expiry=market.valuation_date)
    res = price(today, market, BSM, METHOD)
    assert res.price == pytest.approx(max(market.spot - call.strike, 0.0))
    assert res.greeks is not None
    assert res.greeks[Greek.DELTA] == 1.0
    assert res.greeks[Greek.GAMMA] == 0.0


def test_diagnostics_report_black_quantities(market, call):
    d = price(call, market, BSM, METHOD).diagnostics.details
    assert d["sigma"] == pytest.approx(0.20)
    assert d["d2"] == pytest.approx(d["d1"] - d["stdev"])


@dataclass(frozen=True)
class SlopedCurve:
    """Upward-sloping zero curve z(t) = a + c·t (not time-homogeneous)."""

    a: float
    c: float

    def df(self, t: float) -> float:
        return math.exp(-self.zero_rate(t) * t)

    def zero_rate(self, t: float) -> float:
        return self.a + self.c * t

    def shifted(self, dz: float) -> "SlopedCurve":
        return SlopedCurve(self.a + dz, self.c)


def test_theta_and_charm_fall_back_to_bumps_for_non_flat_curves(market, call):
    sloped = replace(market, discount=SlopedCurve(0.02, 0.005))
    g = price(call, sloped, BSM, METHOD).greeks
    assert g is not None
    assert g.sources[Greek.THETA] is GreekSource.BUMP
    assert g.sources[Greek.CHARM] is GreekSource.BUMP
    assert g.sources[Greek.DELTA] is GreekSource.ANALYTIC


def test_force_bump_greeks(market, call):
    g = price(call, market, BSM, METHOD, PricingSettings(force_bump_greeks=True)).greeks
    assert g is not None
    assert set(g.sources.values()) == {GreekSource.BUMP}
