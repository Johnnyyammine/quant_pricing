"""Leisen–Reimer tree and Crank–Nicolson PDE.

References: closed forms (Europeans, digitals), QuantLib BinomialVanillaEngine("lr") (the same
algorithm: agreement to round-off), QuantLib FdBlackScholesVanillaEngine with Spot and Escrowed
cash-dividend models, and tree-vs-PDE under the same model. Discretised comparisons use
self-calibrating tolerances: at resolutions N and 2N the finer result must lie within the observed
O(h²) correction |V_2N − V_N| of the reference (plus a round-off floor).
"""

import datetime as dt
import itertools
import math
from dataclasses import replace

import pytest
import QuantLib as ql  # noqa: N813
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from engine.errors import UnsupportedCombinationError
from engine.instruments.vanilla import AmericanOption, DigitalOption, EuropeanOption, OptionType
from engine.market.curves import FlatRateCurve, ZeroCurve
from engine.market.dividends import Dividend
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.methods.analytic import AnalyticBlack
from engine.methods.pde import CrankNicolsonPde, solve
from engine.methods.tree import LeisenReimerTree
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton, DividendTreatment
from engine.pricing import price
from engine.settings import DigitalSettings, PdeSettings, PricingSettings, TreeSettings

VAL = dt.date(2026, 1, 2)
BSM, B76 = BlackScholesMerton(), Black76()
SPOT_MODEL = BlackScholesMerton(dividend_treatment=DividendTreatment.SPOT)
TREE, PDE, ANALYTIC = LeisenReimerTree(), CrankNicolsonPde(), AnalyticBlack()
SPOT_QL = ql.FdBlackScholesVanillaEngine.Spot


def mkt(spot=100.0, r=0.05, q=0.02, sigma=0.25, divs=()):
    return MarketData(
        valuation_date=VAL,
        spot=spot,
        discount=FlatRateCurve(r),
        vol=FlatVolSurface(sigma),
        dividend_yield=FlatRateCurve(q),
        dividends=tuple(divs),
    )


def opt(cls, omega=OptionType.PUT, strike=110.0, days=365, **kw):
    return cls(option_type=omega, strike=strike, expiry=VAL + dt.timedelta(days=days), **kw)


def tree_price(inst, m, model, n):
    return price(inst, m, model, TREE, PricingSettings(tree=TreeSettings(n)), greeks=()).price


def pde_price(inst, m, model, n, nt=None):
    s = PricingSettings(pde=PdeSettings(space_nodes=n, time_steps=nt or n // 4))
    return price(inst, m, model, PDE, s, greeks=()).price


def assert_converges_to(fn, n, ref, floor=1e-9):
    v1, v2 = fn(n), fn(2 * n + 1)  # 2n + 1 keeps tree step counts odd
    assert abs(v2 - ref) <= abs(v2 - v1) + floor, (v1, v2, ref)


def assert_consistent(ours, ref, floor):
    """Both sides discretised: each is bounded by its own refinement correction (coarse, fine)."""
    (o1, o2), (r1, r2) = ours, ref
    assert abs(o2 - r2) <= abs(o2 - o1) + abs(r2 - r1) + floor, (ours, ref)


def ql_process(spot, r, q, sigma):
    today = ql.Date(VAL.day, VAL.month, VAL.year)
    ql.Settings.instance().evaluationDate = today
    dc = ql.Actual365Fixed()
    return today, ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(spot)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc, ql.Continuous)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc, ql.Continuous)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), sigma, dc)),
    )


# ------------------------------------------------------------------ Leisen–Reimer tree


params = st.fixed_dictionaries(
    {
        "moneyness": st.floats(0.7, 1.4),
        "days": st.integers(30, 1500),
        "sigma": st.floats(0.1, 0.6),
        "r": st.floats(0.0, 0.08),
        "q": st.floats(0.0, 0.06),
        "omega": st.sampled_from(list(OptionType)),
    }
)


@settings(max_examples=40, deadline=None)
@given(params)
def test_tree_european_converges_second_order_to_closed_form(p):
    m = mkt(r=p["r"], q=p["q"], sigma=p["sigma"])
    e = opt(EuropeanOption, p["omega"], 100 * p["moneyness"], p["days"])
    ref = price(e, m, BSM, ANALYTIC, greeks=()).price
    assume(ref > 1e-4)
    assert_converges_to(lambda n: tree_price(e, m, BSM, n), 201, ref)


@settings(max_examples=40, deadline=None)
@given(params, st.sampled_from([201, 401]))
def test_tree_european_matches_quantlib_lr(p, n):
    """Same lattice as QuantLib's LR engine: agreement to round-off (flat curves, no dividends).

    American exercise is *not* compared with QuantLib's binomial engine: its American LR prices
    can fall below its own European LR prices (e.g. S = K = 100, σ = 50%, r = 5%, q = 2%, 201
    steps: 19.605 vs 19.695), which no American price can. American exercise is validated against
    QuantLib's FD engine, our PDE and dominance properties instead.
    """
    m = mkt(r=p["r"], q=p["q"], sigma=p["sigma"])
    e = opt(EuropeanOption, p["omega"], 100 * p["moneyness"], p["days"])
    today, process = ql_process(100.0, p["r"], p["q"], p["sigma"])
    kind = ql.Option.Call if p["omega"] is OptionType.CALL else ql.Option.Put
    q_opt = ql.VanillaOption(
        ql.PlainVanillaPayoff(kind, e.strike), ql.EuropeanExercise(today + p["days"])
    )
    q_opt.setPricingEngine(ql.BinomialVanillaEngine(process, "lr", n))
    assert tree_price(e, m, BSM, n) == pytest.approx(q_opt.NPV(), rel=1e-10, abs=1e-12)


@pytest.mark.parametrize("omega", list(OptionType))
def test_tree_american_matches_quantlib_fd(omega):
    m = mkt()
    a = opt(AmericanOption, omega, 100.0, 365)
    ref = [
        _ql_fd(AmericanOption, omega, 100.0, 365, 100.0, 0.05, 0.02, 0.25, [], SPOT_QL, t, x)
        for t, x in ((400, 800), (800, 1600))
    ]
    assert_consistent((tree_price(a, m, BSM, 2001), tree_price(a, m, BSM, 4001)), ref, 1e-5)


def test_tree_escrowed_dividends_converge_to_analytic_and_term_structures_work():
    divs = [
        Dividend(VAL + dt.timedelta(days=100), 2.0),
        Dividend(VAL + dt.timedelta(days=280), 1.0, 0.01),
    ]
    m = replace(mkt(divs=divs), discount=ZeroCurve((0.5, 1.0, 2.0), (0.03, 0.04, 0.045)))
    for omega in OptionType:
        e = opt(EuropeanOption, omega, 100.0, 400)
        ref = price(e, m, BSM, ANALYTIC, greeks=()).price
        assert_converges_to(lambda n, e=e: tree_price(e, m, BSM, n), 201, ref)


def test_tree_rejects_spot_jump_cash_dividends():
    m = mkt(divs=[Dividend(VAL + dt.timedelta(days=100), 2.0)])
    with pytest.raises(UnsupportedCombinationError, match="PDE"):
        price(opt(AmericanOption), m, SPOT_MODEL, TREE)


def test_tree_ladder_equals_per_spot_evaluation():
    m, a = mkt(), opt(AmericanOption)
    s = PricingSettings(tree=TreeSettings(101))
    ladder = TREE.evaluate_ladder(a, m, BSM, s, [0.9, 1.0, 1.1])
    singles = [TREE.evaluate(a, replace(m, spot=m.spot * k), BSM, s).value for k in (0.9, 1.0, 1.1)]
    assert ladder == pytest.approx(singles, rel=1e-14)


# ------------------------------------------------------------------ Crank–Nicolson PDE


@settings(max_examples=30, deadline=None)
@given(params)
def test_pde_european_converges_to_closed_form(p):
    m = mkt(r=p["r"], q=p["q"], sigma=p["sigma"])
    e = opt(EuropeanOption, p["omega"], 100 * p["moneyness"], p["days"])
    ref = price(e, m, BSM, ANALYTIC, greeks=()).price
    assume(ref > 1e-3)
    assert_converges_to(lambda n: pde_price(e, m, BSM, n), 400, ref, floor=1e-7)


@settings(max_examples=20, deadline=None)
@given(params)
def test_pde_digital_converges_to_closed_form(p):
    """Cell-averaged payoff keeps second-order convergence for the discontinuous digital."""
    m = mkt(r=p["r"], q=p["q"], sigma=p["sigma"])
    d = opt(DigitalOption, p["omega"], 100 * p["moneyness"], p["days"], payout=1.0)
    exact = PricingSettings(digital=DigitalSettings(spread_width_rel=0.0))
    ref = price(d, m, BSM, ANALYTIC, exact, greeks=()).price
    assume(ref > 1e-3)
    assert_converges_to(lambda n: pde_price(d, m, BSM, n), 400, ref, floor=1e-8)


def _ql_fd(inst_cls, omega, strike, days, spot, r, q, sigma, divs, model, t_grid=800, x_grid=1600):
    today, process = ql_process(spot, r, q, sigma)
    kind = ql.Option.Call if omega is OptionType.CALL else ql.Option.Put
    exercise = (
        ql.AmericanExercise(today, today + days)
        if inst_cls is AmericanOption
        else ql.EuropeanExercise(today + days)
    )
    q_opt = ql.VanillaOption(ql.PlainVanillaPayoff(kind, strike), exercise)
    schedule = ql.DividendVector([today + d for d, _ in divs], [c for _, c in divs])
    engine = ql.FdBlackScholesVanillaEngine(
        process,
        schedule,
        t_grid,
        x_grid,
        4,
        ql.FdmSchemeDesc.CrankNicolson(),
        False,
        -ql.nullDouble(),
        model,
    )
    q_opt.setPricingEngine(engine)
    return q_opt.NPV()


@pytest.mark.parametrize("omega", list(OptionType))
@pytest.mark.parametrize(
    ("treatment", "ql_model"),
    [
        (DividendTreatment.SPOT, ql.FdBlackScholesVanillaEngine.Spot),
        (DividendTreatment.ESCROWED, ql.FdBlackScholesVanillaEngine.Escrowed),
    ],
)
def test_pde_american_with_cash_dividends_matches_quantlib_fd(omega, treatment, ql_model):
    """QuantLib's escrowed PV uses r only, so q = 0 here (our forward includes q correctly)."""
    divs = [(90, 2.5), (270, 2.5)]
    m = mkt(q=0.0, divs=[Dividend(VAL + dt.timedelta(days=d), c) for d, c in divs])
    a = opt(AmericanOption, omega, 100.0, 365)
    model = BlackScholesMerton(dividend_treatment=treatment)
    ref = [
        _ql_fd(AmericanOption, omega, 100.0, 365, 100.0, 0.05, 0.0, 0.25, divs, ql_model, t, x)
        for t, x in ((400, 800), (800, 1600))
    ]
    assert_consistent(
        (pde_price(a, m, model, 800, 400), pde_price(a, m, model, 1600, 800)), ref, 1e-5
    )


def test_american_tree_and_pde_agree_under_escrowed_dividends():
    divs = [
        Dividend(VAL + dt.timedelta(days=60), 1.5),
        Dividend(VAL + dt.timedelta(days=240), 1.5, 0.005),
    ]
    m = replace(mkt(divs=divs), discount=ZeroCurve((0.25, 1.0, 2.0), (0.03, 0.04, 0.045)))
    for omega in OptionType:
        a = opt(AmericanOption, omega, 100.0, 450)
        tree = tree_price(a, m, BSM, 4001)
        pde = pde_price(a, m, BSM, 3200, 800)
        assert pde == pytest.approx(tree, abs=2e-3), omega


def test_american_black76_pde_matches_tree():
    m = mkt(q=0.0)
    for omega in OptionType:
        a = opt(AmericanOption, omega, 100.0, 365)
        assert pde_price(a, m, B76, 3200, 800) == pytest.approx(
            tree_price(a, m, B76, 4001), abs=2e-3
        )


@settings(max_examples=25, deadline=None)
@given(params)
def test_american_dominates_european_and_intrinsic(p):
    m = mkt(r=p["r"], q=p["q"], sigma=p["sigma"])
    k = 100 * p["moneyness"]
    am = pde_price(opt(AmericanOption, p["omega"], k, p["days"]), m, BSM, 400)
    eu = pde_price(opt(EuropeanOption, p["omega"], k, p["days"]), m, BSM, 400)
    intrinsic = max(p["omega"].omega * (100.0 - k), 0.0)
    assert am >= eu - 1e-10
    assert am >= intrinsic - 1e-10


def test_american_call_without_dividends_is_european():
    m = mkt(q=0.0)
    am = pde_price(opt(AmericanOption, OptionType.CALL, 100.0, 365), m, BSM, 800)
    eu = pde_price(opt(EuropeanOption, OptionType.CALL, 100.0, 365), m, BSM, 800)
    assert am == pytest.approx(eu, abs=1e-10)


def test_put_exercise_boundary_is_below_strike_and_rises_to_it():
    sol = solve(opt(AmericanOption), mkt(), BSM, PdeSettings(), [100.0])
    boundary = [s for s in sol.boundary_s if not math.isnan(s)]
    assert boundary
    assert all(s < 110.0 for s in boundary)
    # Without discrete dividends the put boundary rises (weakly, up to grid resolution) to expiry.
    step = boundary[-1] * (sol.x[1] - sol.x[0])
    assert all(b >= a - 2 * step for a, b in itertools.pairwise(boundary))
    assert boundary[-1] > 0.95 * 110.0


def test_put_is_not_exercised_just_before_a_large_cash_dividend():
    m = mkt(divs=[Dividend(VAL + dt.timedelta(days=180), 5.0)])
    sol = solve(opt(AmericanOption, strike=100.0), m, BSM, PdeSettings(), [100.0])
    t_div = 180 / 365
    before = [
        s
        for t, s in zip(sol.boundary_t, sol.boundary_s, strict=True)
        if t_div - 10 / 365 < t < t_div
    ]
    after = [
        s
        for t, s in zip(sol.boundary_t, sol.boundary_s, strict=True)
        if t_div < t < t_div + 10 / 365
    ]
    # Waiting for the dividend drop dominates: the boundary collapses (or vanishes) before it.
    lo_before = min((s for s in before if not math.isnan(s)), default=0.0)
    hi_after = max(s for s in after if not math.isnan(s))
    assert lo_before < hi_after


def test_pde_ladder_is_consistent_with_single_evaluation():
    m, a = mkt(), opt(AmericanOption)
    s = PricingSettings()
    ladder = PDE.evaluate_ladder(a, m, BSM, s, [0.999, 1.0, 1.001])
    assert ladder[1] == pytest.approx(PDE.evaluate(a, m, BSM, s).value, abs=5e-4)


def test_numerical_greeks_close_to_analytic_for_europeans():
    m, e = mkt(), opt(EuropeanOption)
    analytic = price(e, m, BSM, ANALYTIC).greeks
    for method in (TREE, PDE):
        g = price(e, m, BSM, method).greeks
        assert g is not None
        assert analytic is not None
        for k in ("delta", "gamma", "vega", "theta", "rho"):
            key = next(x for x in analytic.values if x.value == k)
            assert g[key] == pytest.approx(analytic[key], rel=2e-3, abs=1e-4), (method.name, k)
