import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.results import Greek, Greeks, GreekSource
from engine.risk.units import GreekMode, cash_greek, desk_greeks

finite = st.floats(-1e6, 1e6, allow_nan=False)


def _greeks(v: dict[Greek, float]) -> Greeks:
    return Greeks(values=v, sources=dict.fromkeys(v, GreekSource.ANALYTIC))


def test_cash_definitions():
    s, n = 200.0, 10.0
    assert cash_greek(Greek.DELTA, 0.5, s, n) == pytest.approx(0.5 * 200 * 10)
    # Cash gamma per 1%: change in cash delta for a 1% spot move
    assert cash_greek(Greek.GAMMA, 0.02, s, n) == pytest.approx(0.02 * 200 * 2.0 * 10)
    assert cash_greek(Greek.VEGA, 40.0, s, n) == pytest.approx(4.0)
    assert cash_greek(Greek.THETA, -3.65, s, n) == pytest.approx(-0.1)
    assert cash_greek(Greek.RHO, 50.0, s, n) == pytest.approx(0.05)
    assert cash_greek(Greek.VANNA, 0.1, s, n) == pytest.approx(0.1 * 200 * 0.01 * 10)
    assert cash_greek(Greek.VOLGA, 100.0, s, n) == pytest.approx(0.1)
    assert cash_greek(Greek.CHARM, 0.365, s, n) == pytest.approx(0.365 * 200 / 365 * 10)


def test_cash_gamma_is_delta_change_for_one_percent_move_valued_at_spot():
    # Constant Γ: Δ(S') − Δ(S) = Γ·(S' − S). Cash gamma = S·[Δ(1.01 S) − Δ(S)] = Γ S² / 100.
    gamma, s, n = 0.013, 87.0, 4.0
    delta_change = gamma * (1.01 * s - s)
    assert cash_greek(Greek.GAMMA, gamma, s, n) == pytest.approx(n * s * delta_change)


@given(st.dictionaries(st.sampled_from(list(Greek)), finite, min_size=1), st.floats(1, 1e4))
def test_pure_is_percent_of_notional(values, spot):
    g = _greeks(values)
    cash = desk_greeks(g, spot, 3.0, "EUR", GreekMode.CASH)
    pure = desk_greeks(g, spot, 3.0, "EUR", GreekMode.PURE)
    assert [c.greek for c in cash] == [p.greek for p in pure]
    for c, p in zip(cash, pure, strict=True):
        assert p.value == pytest.approx(100 * c.value / (3.0 * spot), rel=1e-12, abs=1e-300)
        assert "EUR" in c.unit
        assert "EUR" not in p.unit


def test_pure_delta_and_gamma_units():
    g = _greeks({Greek.DELTA: 0.55, Greek.GAMMA: 0.02})
    pure = {d.greek: d for d in desk_greeks(g, 100.0, 1.0, "EUR", GreekMode.PURE)}
    assert pure[Greek.DELTA].value == pytest.approx(55.0)
    assert pure[Greek.DELTA].unit == "%"
    assert pure[Greek.GAMMA].value == pytest.approx(2.0)  # Δ moves 2 %-points per 1% spot
